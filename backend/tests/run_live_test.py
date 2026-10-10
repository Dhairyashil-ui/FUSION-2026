import sys
import os
import json

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.services.query_parser import QueryParser
from app.services.groq_service import GroqService

TEST_QUERIES = [
    "Find flood affected buildings in Pune.",
    "Find new buildings constructed in Pune between 2020 and 2026 and show them on a map.",
    "Monitor vehicles entering restricted areas in Pune right now.",
    "Predict areas likely to flood tomorrow in Pune and give me a risk map.",
    "Find forest converted to agriculture in Maharashtra."
]


def run_tests():
    api_key_configured = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip() and settings.GROQ_API_KEY != "your_groq_api_key_here")
    print("=" * 80)
    print("FUSION-2026 QUERY PARSER - 5-QUERY TEST SUITE")
    print(f"GROQ API Key Status: {'CONFIGURED (Live Groq LLM)' if api_key_configured else 'NOT CONFIGURED in .env'}")
    print(f"Model: {settings.GROQ_MODEL}")
    print("=" * 80)

    if not api_key_configured:
        print("\nNOTE: To run live against Groq, place your GROQ_API_KEY in backend/.env")
        print("Below are the verified Pydantic-validated structures matching the schema:\n")

    parser = QueryParser()

    for idx, query in enumerate(TEST_QUERIES, 1):
        print(f"\n--- TEST QUERY {idx} ---")
        print(f"Query: \"{query}\"")
        try:
            if api_key_configured:
                result = parser.parse(query)
                print("Result (Live Groq Output):")
                print(json.dumps(result.model_dump(), indent=2))
            else:
                from tests.test_query_parser import MOCK_RESPONSES
                from app.schemas.query_schema import QueryUnderstanding
                mock_data = MOCK_RESPONSES[query]
                result = QueryUnderstanding.model_validate(mock_data)
                print("Result (Validated Schema Output):")
                print(json.dumps(result.model_dump(), indent=2))
        except Exception as e:
            print(f"Error executing query: {e}")


if __name__ == "__main__":
    run_tests()
