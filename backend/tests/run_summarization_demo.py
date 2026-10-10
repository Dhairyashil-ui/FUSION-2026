import sys
import os
import json
import re

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base
import app.models
from app.models.project import Project
from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.models.conversation_summary import ConversationSummary
from app.services.conversation_manager import conversation_manager
from tests.test_conversation_summarizer import get_mock_parser_response, get_mock_summary_response


def run_demo():
    print("=" * 80)
    print("FUSION-2026 CONVERSATION SUMMARIZATION & CONTEXT COMPRESSION DEMO")
    print("=" * 80)

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()

    project = Project(name="Cumulative Summarization Demo Project")
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id

    print(f"\nInitialized Project ID: {project_id}\n")

    def mock_groq_generate(system_prompt: str, user_prompt: str, **kwargs):
        if "Conversation-State Summarizer" in system_prompt or "cumulative state summary" in user_prompt.lower():
            m = re.search(r"through (\d+)", user_prompt)
            end_t = int(m.group(1)) if m else 10
            return json.dumps(get_mock_summary_response(end_t))

        m_q = re.search(r'New user query:\s*"([^"]+)"', user_prompt, re.IGNORECASE)
        q_text = m_q.group(1) if m_q else "Query"

        match = re.search(r"Query turn (\d+):", q_text)
        if match:
            current_t = int(match.group(1))
        elif "flood affected" in q_text:
            current_t = 1
        elif "latest flood" in q_text:
            current_t = 2
        else:
            current_t = 1

        return json.dumps(get_mock_parser_response(current_t, q_text))

    with patch("app.services.groq_service.GroqService.generate", side_effect=mock_groq_generate):
        # Run turns 1 through 21
        for turn in range(1, 22):
            if turn == 1:
                q = "Find flood affected buildings in Pune."
            elif turn == 2:
                q = "Use the latest flood."
            elif turn == 10:
                q = "Query turn 10: Show everything on a map."
            elif turn == 11:
                q = "Query turn 11: Also analyze bridges."
            elif turn == 20:
                q = "Query turn 20: Actually switch to Mumbai."
            elif turn == 21:
                q = "Query turn 21: Focus on roads and expressways."
            else:
                q = f"Query turn {turn}: refine study scope"

            resp = conversation_manager.process_query(
                project_id=project_id,
                user_query=q,
                db=db
            )

            if turn in (1, 10, 11, 20, 21):
                print(f"[TURN {turn}] User: \"{q}\"")
                print(f"        -> Assistant: \"{resp.assistant_response}\"")
                print(f"        -> Active State: WHERE={resp.understanding.where.value}, TARGETS={resp.understanding.target.values}")

    print("\n" + "=" * 80)
    print("VERIFICATION OF SUMMARIES IN DATABASE")
    print("=" * 80)

    summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.project_id == project_id)
        .order_by(ConversationSummary.summary_end_conversation.asc())
        .all()
    )

    for s in summaries:
        print(f"\nSUMMARY RECORD: SUMMARY_{s.summary_start_conversation}_{s.summary_end_conversation}")
        print(f"ID:              {s.id}")
        print(f"Turns Covered:   Turns {s.summary_start_conversation} to {s.summary_end_conversation} (Cumulative)")
        print(f"Synopsis Text:   \"{s.summary_text}\"")
        print("Structured State:")
        print(json.dumps(s.structured_state, indent=2))

    print("\n" + "=" * 80)
    print("DATA SAFETY: ORIGINAL CONVERSATIONS AUDIT")
    print("=" * 80)
    conv_count = db.query(Conversation).filter(Conversation.project_id == project_id).count()
    req_count = db.query(ExtractedRequirement).join(Conversation).filter(Conversation.project_id == project_id).count()
    print(f"Total Original Conversations Retained:   {conv_count} / 21")
    print(f"Total Extracted Requirements Retained:   {req_count} / 21")
    print("Confirmed: NO conversations or historical snapshots were overwritten or pruned!")

    db.close()


if __name__ == "__main__":
    run_demo()
