#!/usr/bin/env python3
"""Reset super admin password.

Required env (no defaults; the script exits with an error if either is missing):
  DATABASE_URL          e.g. postgresql://<user>:change-me@<host>:5432/<db>
  SUPER_ADMIN_PASSWORD  new password for the super admin (never printed)
Optional: SUPER_ADMIN_USERNAME (default tornybotca1).
"""
import sys
import os

# Repo root (parent of scripts/) so `api` imports without a hardcoded host path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database URL: from the environment only (no hardcoded credentials). Fail fast.
# psycopg2 accepts a postgresql://<user>:change-me@<host>/<db> URL directly.
db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
    sys.exit("ERROR: DATABASE_URL environment variable is required (no default).")

from api.auth import hash_password
import psycopg2

new_password = os.environ.get("SUPER_ADMIN_PASSWORD")
if not new_password:
    raise RuntimeError(
        "SUPER_ADMIN_PASSWORD environment variable is required. "
        "Set it to the new password for the super admin user."
    )
username = (os.environ.get("SUPER_ADMIN_USERNAME") or "tornybotca1").strip()

# Hash the password
password_hash = hash_password(new_password)

# Update the database
try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    cur.execute(
        "UPDATE users SET password_hash = %s WHERE username = %s",
        (password_hash, username)
    )
    
    if cur.rowcount == 0:
        print(f"User {username} not found")
    else:
        print(f"Password updated for {username}")
        conn.commit()
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
