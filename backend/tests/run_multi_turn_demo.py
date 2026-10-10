import sys
import os
import json
import uuid

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
from app.services.conversation_manager import conversation_manager
from tests.test_multi_turn_conversation import SEQUENCE_TURNS


def run_demo():
    print("=" * 80)
    print("FUSION-2026 MULTI-TURN CONVERSATION DEMO (TURNS 1-6)")
    print("=" * 80)

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()

    project = Project(name="Pune to Mumbai Infrastructure Discovery")
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id

    print(f"\nCreated Project ID: {project_id} (Name: '{project.name}')\n")

    for turn_info in SEQUENCE_TURNS:
        print(f"\n>>> USER (Turn #{turn_info['turn']}): \"{turn_info['query']}\"")
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(turn_info["mock_llm"])):
            result = conversation_manager.process_query(
                project_id=project_id,
                user_query=turn_info["query"],
                db=db
            )
            print(f"<<< ASSISTANT: \"{result.assistant_response}\"")
            print(f"    [Status: {result.sufficiency.status}]")
            print(f"    Current Extracted State:")
            print(f"      - WHAT:          {result.understanding.what.value}")
            print(f"      - WHERE:         {result.understanding.where.value}")
            print(f"      - TARGET:        {result.understanding.target.values}")
            print(f"      - MEASUREMENT:   {result.understanding.measurement.value}")
            print(f"      - OUTPUT FORMAT: {result.understanding.output_format.values}")
            print(f"      - MISSING:       {result.sufficiency.missing_information}")

    # Inspect Database Records
    print("\n" + "=" * 80)
    print("DATABASE RECORDS AUDIT")
    print("=" * 80)
    convs = db.query(Conversation).filter(Conversation.project_id == project_id).order_by(Conversation.conversation_number.asc()).all()
    print(f"\n1. TABLE: conversations ({len(convs)} rows):")
    for c in convs:
        print(f"   Turn {c.conversation_number} | ID: {str(c.id)[:8]}... | User: \"{c.user_query}\" | Assistant: \"{c.assistant_response}\"")

    reqs = (
        db.query(ExtractedRequirement)
        .join(Conversation, Conversation.id == ExtractedRequirement.conversation_id)
        .filter(Conversation.project_id == project_id)
        .order_by(Conversation.conversation_number.asc())
        .all()
    )
    print(f"\n2. TABLE: extracted_requirements ({len(reqs)} versioned snapshots):")
    for idx, r in enumerate(reqs, 1):
        print(f"   Snapshot {idx} | WHERE={r.where_data.get('value')} | MEASUREMENT={r.measurement_data.get('value') if r.measurement_data else None} | TARGET={r.target.get('values')} | OUTPUT={r.output_format.get('values')} | Sufficient={r.is_sufficient}")

    db.close()


if __name__ == "__main__":
    run_demo()
