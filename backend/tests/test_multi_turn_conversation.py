import sys
import os
import json
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, get_db
import app.models  # Ensure all model tables are registered in Base.metadata
from app.models.project import Project
from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.services.conversation_manager import conversation_manager, ProjectNotFoundError
from app.schemas.query_schema import QueryUnderstanding
from app.main import app

# Set up in-memory SQLite database with StaticPool for cross-connection persistence
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

SEQUENCE_TURNS = [
    {
        "turn": 1,
        "query": "Find commercial buildings with solar panels in Pune.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_where": "Pune",
        "expected_measurement": None,
        "expected_targets": ["commercial buildings", "solar panels"],
        "expected_outputs": [],
        "expected_status": "NEEDS_INFORMATION",
        "expected_questions": [
            "What spatial relationships, constraints, filters, or operations should be applied?",
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    },
    {
        "turn": 2,
        "query": "Filter them by distance to open drainage using a 200 m threshold.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels", "open drainage"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_where": "Pune",
        "expected_measurement": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
        "expected_targets": ["commercial buildings", "solar panels", "open drainage"],
        "expected_outputs": [],
        "expected_status": "NEEDS_INFORMATION",
        "expected_questions": [
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    },
    {
        "turn": 3,
        "query": "Also include hospitals.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels", "open drainage", "hospitals"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_where": "Pune",
        "expected_measurement": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
        "expected_targets": ["commercial buildings", "solar panels", "open drainage", "hospitals"],
        "expected_outputs": [],
        "expected_status": "NEEDS_INFORMATION",
        "expected_questions": [
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    },
    {
        "turn": 4,
        "query": "Give me an interactive map and GeoJSON.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels", "open drainage", "hospitals"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_where": "Pune",
        "expected_measurement": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
        "expected_targets": ["commercial buildings", "solar panels", "open drainage", "hospitals"],
        "expected_outputs": ["interactive map", "GeoJSON"],
        "expected_status": "READY",
        "expected_questions": []
    },
    {
        "turn": 5,
        "query": "Actually analyze Mumbai instead.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Mumbai", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels", "open drainage", "hospitals"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_where": "Mumbai",
        "expected_measurement": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
        "expected_targets": ["commercial buildings", "solar panels", "open drainage", "hospitals"],
        "expected_outputs": ["interactive map", "GeoJSON"],
        "expected_status": "READY",
        "expected_questions": []
    },
    {
        "turn": 6,
        "query": "Only include fire stations.",
        "mock_llm": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Mumbai", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["fire stations"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_where": "Mumbai",
        "expected_measurement": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
        "expected_targets": ["fire stations"],
        "expected_outputs": ["interactive map", "GeoJSON"],
        "expected_status": "READY",
        "expected_questions": []
    }
]


def test_multi_turn_pipeline():
    db = TestingSessionLocal()
    project = Project(name="Pune to Mumbai Infrastructure Discovery")
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id

    for turn_info in SEQUENCE_TURNS:
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(turn_info["mock_llm"])):
            resp = conversation_manager.process_query(
                project_id=project_id,
                user_query=turn_info["query"],
                db=db
            )
            assert resp.conversation_number == turn_info["turn"]
            assert resp.understanding.where.value == turn_info["expected_where"]
            assert resp.understanding.measurement.value == turn_info["expected_measurement"]
            assert resp.understanding.target.values == turn_info["expected_targets"]
            assert resp.understanding.output_format.values == turn_info["expected_outputs"]
            assert resp.sufficiency.status == turn_info["expected_status"]
            if turn_info["expected_questions"]:
                assert resp.sufficiency.questions_for_user == turn_info["expected_questions"]
            print(f"PASS Turn {resp.conversation_number}: '{resp.user_query}' -> where={resp.understanding.where.value}, targets={resp.understanding.target.values}, status={resp.sufficiency.status}")

    # Verify Database Records
    convs = db.query(Conversation).filter(Conversation.project_id == project_id).order_by(Conversation.conversation_number.asc()).all()
    assert len(convs) == 6
    for idx, c in enumerate(convs, 1):
        assert c.conversation_number == idx

    reqs = (
        db.query(ExtractedRequirement)
        .join(Conversation, Conversation.id == ExtractedRequirement.conversation_id)
        .filter(Conversation.project_id == project_id)
        .order_by(Conversation.conversation_number.asc())
        .all()
    )
    assert len(reqs) == 6
    assert reqs[0].where_data["value"] == "Pune"
    assert reqs[4].where_data["value"] == "Mumbai"
    assert reqs[5].target["values"] == ["fire stations"]
    print("PASS Database: All 6 conversation records and 6 versioned requirement records verified!")
    db.close()


def test_api_multi_turn_endpoint():
    db = TestingSessionLocal()
    project = Project(name="API Test Project")
    db.add(project)
    db.commit()
    db.refresh(project)
    p_id = str(project.id)
    db.close()

    for turn_info in SEQUENCE_TURNS:
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(turn_info["mock_llm"])):
            res = client.post("/api/query", json={"project_id": p_id, "query": turn_info["query"]})
            assert res.status_code == 200, f"Turn {turn_info['turn']} failed HTTP {res.status_code}"
            data = res.json()
            assert data["conversation_number"] == turn_info["turn"]
            assert data["understanding"]["where"]["value"] == turn_info["expected_where"]
            assert data["understanding"]["target"]["values"] == turn_info["expected_targets"]
            assert data["sufficiency"]["status"] == turn_info["expected_status"]
            print(f"PASS API Turn {data['conversation_number']}: HTTP 200")


def test_invalid_project_id():
    fake_id = str(uuid.uuid4())
    res = client.post("/api/query", json={"project_id": fake_id, "query": "Find buildings in Pune."})
    assert res.status_code == 404
    assert f"Project with ID '{fake_id}' does not exist" in res.json()["detail"]
    print("PASS Controlled 404 on nonexistent project ID")


if __name__ == "__main__":
    test_multi_turn_pipeline()
    test_api_multi_turn_endpoint()
    test_invalid_project_id()
