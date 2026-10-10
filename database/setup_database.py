#!/usr/bin/env python3
"""
FUSION 2026 - Database and Supabase Setup & Migration Utility
Tests connection to configured database and Supabase API, and ensures schemas are initialized.
"""
import os
import sys
import json
import urllib.request
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.config import settings
from app.database import init_db, verify_database_connection, get_database_url


def test_supabase_api():
    print("--- 1. Testing Supabase REST & Auth API ---")
    if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
        print("  [SKIP] Supabase credentials not fully configured.")
        return False

    headers = {
        "apikey": settings.SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}"
    }

    try:
        url = f"{settings.SUPABASE_URL}/auth/v1/settings"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                print(f"  [OK] Supabase API connected: {settings.SUPABASE_URL}")
                return True
    except Exception as exc:
        print(f"  [WARN] Supabase API ping warning: {exc}")
    return False


def test_database_engine():
    print("\n--- 2. Initializing & Verifying Database Tables ---")
    db_url = get_database_url()
    print(f"  Target Database URL: {db_url}")

    try:
        init_db()
        status = verify_database_connection()
        print(f"  [OK] Database status: {json.dumps(status, indent=2)}")
        return True
    except Exception as exc:
        print(f"  [FAIL] Database initialization failed: {exc}")
        return False


def test_groq_llm():
    print("\n--- 3. Testing Groq LLM with configured Model ---")
    print(f"  Model: {settings.GROQ_MODEL}")
    if not settings.GROQ_API_KEY:
        print("  [FAIL] GROQ_API_KEY is not set.")
        return False

    from app.services.groq_service import groq_service
    try:
        res = groq_service.generate(
            system_prompt="You are FUSION 2026 GeoAI engine.",
            user_prompt="Say 'GeoAI engine ready' in 3 words.",
            temperature=0.0
        )
        print(f"  [OK] Groq response: {res.strip()}")
        return True
    except Exception as exc:
        print(f"  [FAIL] Groq test failed: {exc}")
        return False


def main():
    print("==================================================")
    print(" FUSION 2026 - Setup & Health Diagnostic Tool")
    print("==================================================")
    supabase_ok = test_supabase_api()
    db_ok = test_database_engine()
    groq_ok = test_groq_llm()

    print("\n==================================================")
    if db_ok and groq_ok:
        print(" SUCCESS: All services ready and operational!")
    else:
        print(" WARNING: Some components require attention.")
    print("==================================================")


if __name__ == "__main__":
    main()
