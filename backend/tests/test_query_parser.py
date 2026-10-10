import sys
import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.schemas.query_schema import QueryUnderstanding

client = TestClient(app)

MOCK_RESPONSES = {
    "Find commercial buildings with solar panels in Pune.": {
        "what": {
            "value": "infrastructure discovery",
            "confidence": 0.95,
            "provided_by_user": True
        },
        "where": {
            "value": "Pune",
            "type": "city_or_named_area",
            "confidence": 0.99,
            "provided_by_user": True
        },
        "target": {
            "values": ["commercial buildings", "solar panels"],
            "confidence": 0.98,
            "provided_by_user": True
        },
        "measurement": {
            "value": None,
            "confidence": 0.0,
            "provided_by_user": False
        },
        "output_format": {
            "values": [],
            "confidence": 0.0,
            "provided_by_user": False
        }
    },
    "Find commercial buildings with solar panels within 200 metres of open drainage in Pune. Give me a map and GeoJSON.": {
        "what": {
            "value": "infrastructure discovery",
            "confidence": 0.95,
            "provided_by_user": True
        },
        "where": {
            "value": "Pune",
            "type": "city_or_named_area",
            "confidence": 0.99,
            "provided_by_user": True
        },
        "target": {
            "values": ["commercial buildings", "solar panels", "open drainage"],
            "confidence": 0.98,
            "provided_by_user": True
        },
        "measurement": {
            "value": "find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold",
            "confidence": 0.95,
            "provided_by_user": True
        },
        "output_format": {
            "values": ["interactive map", "GeoJSON"],
            "confidence": 0.95,
            "provided_by_user": True
        }
    }
}


def test_query_parse_endpoint():
    for query, expected_json in MOCK_RESPONSES.items():
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(expected_json)):
            response = client.post("/api/query/parse", json={"query": query})
            assert response.status_code == 200, f"Failed for query: {query}"
            data = response.json()
            understanding = QueryUnderstanding.model_validate(data)
            assert understanding.what.value == expected_json["what"]["value"]
            assert understanding.where.value == expected_json["where"]["value"]
            assert understanding.measurement.value == expected_json["measurement"]["value"]
            assert understanding.target.values == expected_json["target"]["values"]
            assert understanding.output_format.values == expected_json["output_format"]["values"]
            print(f"PASS: {query}")


if __name__ == "__main__":
    test_query_parse_endpoint()
