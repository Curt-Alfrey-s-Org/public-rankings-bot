#!/usr/bin/env python3
"""
Ensure super_admin user 'tornybotca1' exists. Requires SUPER_ADMIN_PASSWORD (must meet strength rules).
Run inside API container (Docker flow - no host DB port):

  docker exec -e SUPER_ADMIN_PASSWORD='your-password' rankings-bot-api python scripts/ensure_super_admin.py

Then log in at the site or in the app with tornybotca1 and the password you set.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)

# DATABASE_URL uses postgres/rankings-bot-postgres (Docker network). Run inside container.
from database import get_db_session
from api.models.user import User
from api.auth import hash_password

USERNAME = "tornybotca1"
PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
if not PASSWORD:
    raise RuntimeError(
        "SUPER_ADMIN_PASSWORD environment variable is required. "
        "Set it to a strong password for the super admin user."
    )
EMAIL = "tornybotca1@superadmin.local"


def main() -> None:
    db = get_db_session()
    try:
        user = db.query(User).filter_by(username=USERNAME).first()
        if user:
            user.role = "super_admin"
            user.password_hash = hash_password(PASSWORD)
            if hasattr(user, "must_change_password"):
                user.must_change_password = False
            db.commit()
            print(f"Updated user '{USERNAME}' to super_admin with password '{PASSWORD}'.")
        else:
            email = EMAIL
            if db.query(User).filter_by(email=email).first():
                email = f"{USERNAME}-{os.getpid()}@superadmin.local"
            db.add(
                User(
                    username=USERNAME,
                    email=email,
                    password_hash=hash_password(PASSWORD),
                    role="super_admin",
                    email_verified=True,
                )
            )
            db.commit()
            print(f"Created user '{USERNAME}' (super_admin) with password '{PASSWORD}'.")
    finally:
        db.close()
    print("Log in at the site or in the app with tornybotca1 and the password you set, then create admin accounts from the app.")


if __name__ == "__main__":
    main()
