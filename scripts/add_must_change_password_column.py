#!/usr/bin/env python3
"""
One-off: add users.must_change_password if missing. Use the same DATABASE_URL as the API.
Run from project root: python3 scripts/add_must_change_password_column.py
Or with env: DATABASE_URL=postgresql://... python3 scripts/add_must_change_password_column.py
"""
import os
import sys

# Load .env from project root
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(root, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if k == "DATABASE_URL" and v:
                    os.environ.setdefault("DATABASE_URL", v)
                    break

sys.path.insert(0, root)
from sqlalchemy import text
from database import SessionLocal

def main():
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"))
        db.commit()
        print("Column users.must_change_password added or already exists.")
    except Exception as e:
        db.rollback()
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
