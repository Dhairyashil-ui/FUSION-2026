#!/usr/bin/env python3
"""
Migrates database/schema.sql directly to Supabase PostgreSQL database.
"""
import os
import sys
import psycopg2
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Supabase PostgreSQL Connection String (using pooler in ap-northeast-1)
DB_URL = "postgresql://postgres.ageskiwfgxjomotrfoqo:y5Q%21Rz8._Gbwfv6@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    schema_file = BASE_DIR / "database" / "schema.sql"
    print(f"Reading schema from: {schema_file}")
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    print("Executing schema.sql in Supabase...")
    cur.execute(schema_sql)
    conn.commit()
    print("Schema executed successfully!")

    # Verify tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    print("\nVerified Supabase tables created:")
    for t in tables:
        print(f"  - {t}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
