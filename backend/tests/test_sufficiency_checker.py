import sys
import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.services.sufficiency_checker import sufficiency_checker
from app.schemas.query_schema import QueryUnderstanding
from app.schemas.sufficiency_schema import QueryCheckResponse

client = TestClient(app)

SEVEN_TEST_CASES = [
    {
        "id": "TEST 1",
        "query": "Find commercial buildings with solar panels in Pune.",
        "understanding": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_status": "NEEDS_INFORMATION",
        "expected_is_sufficient": False,
        "expected_missing": ["measurement", "output_format"],
        "expected_questions": [
            "What spatial relationships, constraints, filters, or operations should be applied?",
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    },
    {
        "id": "TEST 2",
        "query": "Find commercial buildings with solar panels within 200 metres of open drainage in Pune. Give me a map and GeoJSON.",
        "understanding": {
            "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["commercial buildings", "solar panels", "open drainage"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_status": "READY",
        "expected_is_sufficient": True,
        "expected_missing": [],
        "expected_questions": []
    },
    {
        "id": "TEST 3",
        "query": "Find flood affected buildings.",
        "understanding": {
            "what": {"value": "flood/disaster analysis", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            "target": {"values": ["buildings"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_status": "NEEDS_INFORMATION",
        "expected_is_sufficient": False,
        "expected_missing": ["where", "measurement", "output_format"],
        "expected_questions": [
            "Which area should I analyze?",
            "What spatial relationships, constraints, filters, or operations should be applied?",
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    },
    {
        "id": "TEST 4",
        "query": "Monitor vehicles entering restricted zones in Pune within 50m of checkpoint and send alerts.",
        "understanding": {
            "what": {"value": "vehicle anomaly detection", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["vehicles", "restricted zones"], "confidence": 0.98, "provided_by_user": True},
            "measurement": {"value": "within 50m proximity of checkpoint", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["alerts"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_status": "READY",
        "expected_is_sufficient": True,
        "expected_missing": [],
        "expected_questions": []
    },
    {
        "id": "TEST 5",
        "query": "Analyze something in Pune.",
        "understanding": {
            "what": {"value": "unclear", "confidence": 0.2, "provided_by_user": False},
            "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": [], "confidence": 0.0, "provided_by_user": False},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_status": "NEEDS_INFORMATION",
        "expected_is_sufficient": False,
        "expected_missing": ["what"],
        "expected_questions": ["What would you like me to analyze in Pune?"]
    },
    {
        "id": "TEST 6",
        "query": "Find forest converted to agriculture in Maharashtra filtered by area threshold > 10 ha as GeoJSON.",
        "understanding": {
            "what": {"value": "land-cover change", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Maharashtra", "type": "state", "confidence": 0.99, "provided_by_user": True},
            "target": {"values": ["forest", "agricultural land"], "confidence": 0.95, "provided_by_user": True},
            "measurement": {"value": "filter by area threshold > 10 ha", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": ["GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        },
        "expected_status": "READY",
        "expected_is_sufficient": True,
        "expected_missing": [],
        "expected_questions": []
    },
    {
        "id": "TEST 7",
        "query": "Find areas likely to flood using elevation model.",
        "understanding": {
            "what": {"value": "flood risk prediction", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            "target": {"values": ["flood-prone areas"], "confidence": 0.90, "provided_by_user": True},
            "measurement": {"value": "elevation model constraint analysis", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        },
        "expected_status": "NEEDS_INFORMATION",
        "expected_is_sufficient": False,
        "expected_missing": ["where", "output_format"],
        "expected_questions": [
            "Which area should I analyze?",
            "What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?"
        ]
    }
]


def test_sufficiency_checker_unit():
    for case in SEVEN_TEST_CASES:
        understanding = QueryUnderstanding.model_validate(case["understanding"])
        result = sufficiency_checker.check(understanding)
        assert result.status == case["expected_status"], f"{case['id']} status mismatch"
        assert result.is_sufficient == case["expected_is_sufficient"], f"{case['id']} is_sufficient mismatch"
        assert result.missing_information == case["expected_missing"], f"{case['id']} missing_information mismatch"
        assert result.questions_for_user == case["expected_questions"], f"{case['id']} questions mismatch"


def test_query_check_endpoint():
    for case in SEVEN_TEST_CASES:
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(case["understanding"])):
            res = client.post("/api/query/check", json={"query": case["query"]})
            assert res.status_code == 200, f"Endpoint failed on {case['id']}"
            data = res.json()
            response_model = QueryCheckResponse.model_validate(data)
            assert response_model.sufficiency.status == case["expected_status"]
            assert response_model.sufficiency.missing_information == case["expected_missing"]
            assert response_model.sufficiency.questions_for_user == case["expected_questions"]
