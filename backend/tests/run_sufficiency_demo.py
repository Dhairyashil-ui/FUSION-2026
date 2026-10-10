import sys
import os
import json

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_sufficiency_checker import SEVEN_TEST_CASES
from app.services.sufficiency_checker import sufficiency_checker
from app.schemas.query_schema import QueryUnderstanding


def run_demo():
    print("=" * 80)
    print("FUSION-2026 QUERY SUFFICIENCY CHECKER - 7 TEST CASES REPORT")
    print("=" * 80)

    for case in SEVEN_TEST_CASES:
        understanding = QueryUnderstanding.model_validate(case["understanding"])
        result = sufficiency_checker.check(understanding)

        print(f"\n[{case['id']}] Query: \"{case['query']}\"")
        print("-" * 80)
        print("1. EXTRACTED 5 FIELDS:")
        print(f"   WHAT:         {understanding.what.value}")
        print(f"   WHERE:        {understanding.where.value} ({understanding.where.type or 'unspecified'})")
        print(f"   TARGET:       {understanding.target.values}")
        print(f"   MEASUREMENT:  {understanding.measurement.value}")
        print(f"   OUTPUT:       {understanding.output_format.values}")
        print("2. SUFFICIENCY EVALUATION:")
        print(f"   STATUS:       {result.status} (is_sufficient={result.is_sufficient})")
        print(f"   KNOWN:        {result.known_information.model_dump()}")
        print(f"   MISSING:      {result.missing_information}")
        print("3. QUESTIONS GENERATED:")
        if result.questions_for_user:
            for q in result.questions_for_user:
                print(f"   -> \"{q}\"")
        else:
            print("   -> (None - Query is READY to proceed)")
        print(f"   REASON:       {result.reason}")


if __name__ == "__main__":
    run_demo()
