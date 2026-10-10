import sys
import os
import json
import uuid
import re
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base
import app.models
from app.models.project import Project
from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.models.conversation_summary import ConversationSummary
from app.services.conversation_manager import conversation_manager
from app.services.summary_service import summary_service
from app.schemas.summary_schema import ConversationSummarySchema

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def get_mock_parser_response(turn: int, query: str):
    """Generates a realistic QueryUnderstanding dict for each turn."""
    target_list = ["commercial buildings", "solar panels"]
    if turn >= 3:
        target_list.append("open drainage")
    if turn >= 11:
        target_list.append("hospitals")
    if turn >= 21:
        target_list = ["roads", "expressways"]

    where_val = "Mumbai" if turn >= 20 else "Pune"
    outputs = ["interactive map"] if turn >= 4 else []
    if turn >= 31:
        outputs.append("GeoJSON")

    measurement_val = "within 200m distance threshold" if turn >= 2 else None

    return {
        "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
        "where": {"value": where_val, "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
        "target": {"values": target_list, "confidence": 0.98, "provided_by_user": True},
        "measurement": {"value": measurement_val, "confidence": 0.95 if measurement_val else 0.0, "provided_by_user": bool(measurement_val)},
        "output_format": {"values": outputs, "confidence": 0.95 if outputs else 0.0, "provided_by_user": bool(outputs)}
    }


def get_mock_summary_response(end_turn: int):
    """Generates a cumulative summary dict for turns 1..end_turn."""
    where_val = "Mumbai" if end_turn >= 20 else "Pune"
    targets = ["commercial buildings", "solar panels", "open drainage"]
    if end_turn >= 20:
        targets = ["roads", "expressways"]

    corrections = []
    if end_turn >= 20:
        corrections.append("Location changed from Pune to Mumbai at Turn 20")

    return {
        "what": "infrastructure discovery",
        "where": {"value": where_val, "type": "city_or_named_area"},
        "target": targets,
        "measurement": {"value": "within 200m distance threshold"},
        "output_format": ["interactive map"],
        "confirmed_information": [
            "Analytical objective is infrastructure discovery",
            f"Active Area of Interest is {where_val}",
            "Proximity constraint 200m distance threshold applied"
        ],
        "important_constraints": [],
        "unresolved_information": [],
        "user_corrections": corrections,
        "summary_text": f"Cumulative state 1-{end_turn}: Infrastructure discovery in {where_val} for {', '.join(targets)} on a map.",
        "current_state": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": where_val, "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": targets, "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "within 200m distance threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["interactive map"], "confidence": 0.95, "provided_by_user": True}
        }
    }


def test_summarization_cycle_1_to_31():
    db = TestingSessionLocal()
    project = Project(name="31-Turn Geospatial Longitudinal Study")
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id

    context_used_in_turns = {}

    def mock_groq_generate(system_prompt: str, user_prompt: str, **kwargs):
        # 1. Summary call check
        if "Conversation-State Summarizer" in system_prompt or "cumulative state summary" in user_prompt.lower():
            m = re.search(r"through (\d+)", user_prompt)
            end_t = int(m.group(1)) if m else 10
            return json.dumps(get_mock_summary_response(end_t))

        # 2. Query extraction call check
        m_q = re.search(r'New user query:\s*"([^"]+)"', user_prompt, re.IGNORECASE)
        q_text = m_q.group(1) if m_q else "Query"

        match = re.search(r"Query turn (\d+):", q_text)
        if match:
            current_t = int(match.group(1))
        elif "solar panels" in q_text:
            current_t = 1
        elif "200" in q_text:
            current_t = 2
        else:
            current_t = 1

        has_summary_context = "HISTORICAL CUMULATIVE SUMMARY" in user_prompt
        context_used_in_turns[current_t] = has_summary_context
        return json.dumps(get_mock_parser_response(current_t, q_text))

    with patch("app.services.groq_service.GroqService.generate", side_effect=mock_groq_generate):
        for turn in range(1, 32):
            if turn == 1:
                q = "Find commercial buildings with solar panels in Pune."
            elif turn == 2:
                q = "Filter within 200m of open drainage."
            elif turn == 10:
                q = "Query turn 10: Show everything on a map."
            elif turn == 11:
                q = "Query turn 11: Also analyze hospitals."
            elif turn == 20:
                q = "Query turn 20: Actually switch to Mumbai."
            elif turn == 21:
                q = "Query turn 21: Focus on roads and expressways."
            elif turn == 30:
                q = "Query turn 30: Filter for expressways."
            elif turn == 31:
                q = "Query turn 31: Output GeoJSON format."
            else:
                q = f"Query turn {turn}: minor detail refinement"

            resp = conversation_manager.process_query(
                project_id=project_id,
                user_query=q,
                db=db
            )
            assert resp.conversation_number == turn

    # 1. Verify Turn 10 created SUMMARY_1_10
    sum_10 = (
        db.query(ConversationSummary)
        .filter(
            ConversationSummary.project_id == project_id,
            ConversationSummary.summary_end_conversation == 10
        )
        .first()
    )
    assert sum_10 is not None
    assert sum_10.summary_start_conversation == 1
    assert sum_10.summary_end_conversation == 10
    print("PASS: SUMMARY_1_10 exists in database!")

    # 2. Verify Turn 11 used SUMMARY_1_10 as compressed context
    assert context_used_in_turns.get(11) is True
    print("PASS: Conversation 11 used SUMMARY_1_10 in context!")

    # 3. Verify Turn 20 created cumulative SUMMARY_1_20
    sum_20 = (
        db.query(ConversationSummary)
        .filter(
            ConversationSummary.project_id == project_id,
            ConversationSummary.summary_end_conversation == 20
        )
        .first()
    )
    assert sum_20 is not None
    assert sum_20.summary_start_conversation == 1
    assert sum_20.summary_end_conversation == 20
    print("PASS: SUMMARY_1_20 exists in database (cumulative from 1 to 20)!")

    # 4. Verify Turn 21 used SUMMARY_1_20 as compressed context
    assert context_used_in_turns.get(21) is True
    print("PASS: Conversation 21 used SUMMARY_1_20 in context!")

    # 5. Verify Turn 30 created cumulative SUMMARY_1_30
    sum_30 = (
        db.query(ConversationSummary)
        .filter(
            ConversationSummary.project_id == project_id,
            ConversationSummary.summary_end_conversation == 30
        )
        .first()
    )
    assert sum_30 is not None
    assert sum_30.summary_start_conversation == 1
    assert sum_30.summary_end_conversation == 30
    print("PASS: SUMMARY_1_30 exists in database (cumulative from 1 to 30)!")

    # 6. Verify Turn 31 used SUMMARY_1_30 as compressed context
    assert context_used_in_turns.get(31) is True
    print("PASS: Conversation 31 used SUMMARY_1_30 in context!")

    # 7. Verify all 31 original conversations remain preserved in DB
    all_convs = db.query(Conversation).filter(Conversation.project_id == project_id).all()
    assert len(all_convs) == 31
    all_reqs = db.query(ExtractedRequirement).join(Conversation).filter(Conversation.project_id == project_id).all()
    assert len(all_reqs) == 31
    print(f"PASS: All 31 conversations and all 31 extracted requirements are fully preserved in DB!")

    db.close()


if __name__ == "__main__":
    test_summarization_cycle_1_to_31()
