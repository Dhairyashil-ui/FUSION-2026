import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def test_live_conversation():
    print("Testing live multi-turn conversation on running backend server...")
    
    # 1. Create a new project
    proj_resp = requests.post(f"{BASE_URL}/projects", json={"name": "Live Multi-Turn Validation"})
    assert proj_resp.status_code == 201, f"Failed to create project: {proj_resp.text}"
    project = proj_resp.json()
    project_id = project["id"]
    print(f"Project created: {project_id}")

    turns = [
        ("Turn 1 (Incomplete)", "Find commercial buildings with solar panels in Pune."),
        ("Turn 2 (Provide Measurement)", "Filter them within 200m of open drainage."),
        ("Turn 3 (Accumulate Target)", "Also include hospitals and bridges."),
        ("Turn 4 (Explicit Correction)", "Actually analyze Barcelona instead."),
        ("Turn 5 (Output Format)", "Export as GeoJSON and report.")
    ]

    for label, query in turns:
        print(f"\n--- {label}: '{query}' ---")
        q_resp = requests.post(
            f"{BASE_URL}/query",
            json={"project_id": project_id, "query": query}
        )
        assert q_resp.status_code == 200, f"Query failed ({q_resp.status_code}): {q_resp.text}"
        data = q_resp.json()
        u = data["understanding"]
        s = data["sufficiency"]

        print(f"Turn Number: {data['conversation_number']}")
        print(f"WHAT: {u['what']['value']}")
        print(f"WHERE: {u['where']['value']}")
        print(f"TARGETS: {u['target']['values']}")
        print(f"MEASUREMENT: {u['measurement']['value']}")
        print(f"OUTPUT FORMATS: {u['output_format']['values']}")
        print(f"SUFFICIENCY: status={s['status']}, is_sufficient={s['is_sufficient']}")
        print(f"MISSING: {s['missing_information']}")
        print(f"ASSISTANT: {data['assistant_response']}")

    # Clean up project
    del_resp = requests.delete(f"{BASE_URL}/projects/{project_id}")
    print(f"\nCleaned up test project: {del_resp.status_code}")
    print("\nALL LIVE MULTI-TURN API TURNS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_conversation()
