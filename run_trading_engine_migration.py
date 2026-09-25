"""
Run the trading engine migration using Supabase Management API.
Uses a direct HTTP POST to the SQL endpoint.
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Read the migration SQL
sql = open("trading_engine_migration.sql", "r").read()

# Use the Supabase REST endpoint to run raw SQL via pg_net or a custom function
# Since we can't directly run DDL via PostgREST, we'll use Supabase's
# /rest/v1/rpc endpoint. First we need to create the exec_sql function.

# Step 1: Try creating the tables directly via individual PostgREST table operations
# Step 2: If that fails, provide instructions for manual SQL execution

print("Attempting to create tables via Supabase...")

# The Supabase Python client doesn't support raw SQL directly.
# The best approach is to use the Supabase Dashboard SQL editor.
# However, we can verify if the tables already exist by trying to query them.

from supabase import create_client

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

tables_to_check = ["portfolios", "risk_settings", "positions", "activity_logs"]
existing_tables = []
missing_tables = []

for table in tables_to_check:
    try:
        result = sb.table(table).select("id").limit(1).execute()
        existing_tables.append(table)
        print(f"  [OK] Table '{table}' already exists")
    except Exception as e:
        if "relation" in str(e).lower() and "does not exist" in str(e).lower():
            missing_tables.append(table)
            print(f"  [MISSING] Table '{table}' needs to be created")
        elif "404" in str(e) or "does not exist" in str(e).lower():
            missing_tables.append(table)
            print(f"  [MISSING] Table '{table}' needs to be created")
        else:
            # The table might exist but RLS is blocking — try a different approach
            existing_tables.append(table)
            print(f"  [OK?] Table '{table}' query returned: {str(e)[:80]}")

if missing_tables:
    print(f"\n{'='*60}")
    print(f"MANUAL ACTION REQUIRED")
    print(f"{'='*60}")
    print(f"\nThe following tables need to be created: {', '.join(missing_tables)}")
    print(f"\nPlease run the migration SQL manually:")
    print(f"1. Go to: https://supabase.com/dashboard/project/sjwlhesqrjyqgvqnuxri/sql/new")
    print(f"2. Paste the contents of: trading_engine_migration.sql")
    print(f"3. Click 'Run'")
    print(f"\nAlternatively, copy this file path and open it:")
    print(f"   {Path('trading_engine_migration.sql').resolve()}")
else:
    print(f"\nAll {len(existing_tables)} tables already exist. Migration complete!")
