#!/usr/bin/env python3
"""
Create Debbie Teichert user with director role and specified password.
Run inside API container (Docker flow):

  docker exec rankings-bot-api python scripts/create_debbie_user.py

Then log in with the credentials specified.
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

# DATABASE_URL uses postgres (Docker network). Run inside container.
from database import get_db_session
from api.models.user import User
from api.auth import hash_password

USERNAME = "debbie_teichert"  # Convert spaces to underscores for username
FULL_NAME = "Debbie Teichert"
PASSWORD = "Temppass123!"
EMAIL = "debbie.teichert@example.com"  # Placeholder email
ROLE = "director"


def main() -> None:
    db = get_db_session()
    try:
        user = db.query(User).filter_by(username=USERNAME).first()
        if user:
            print(f"User '{USERNAME}' already exists. Updating password and role...")
            user.role = ROLE
            user.password_hash = hash_password(PASSWORD)
            if hasattr(user, "must_change_password"):
                user.must_change_password = False
            db.commit()
            print(f"Updated user '{USERNAME}' to {ROLE} role with password '{PASSWORD}'.")
        else:
            email = EMAIL
            # Ensure email is unique
            counter = 1
            while db.query(User).filter_by(email=email).first():
                email = f"debbie.teichert{counter}@example.com"
                counter += 1

            db.add(
                User(
                    username=USERNAME,
                    email=email,
                    password_hash=hash_password(PASSWORD),
                    role=ROLE,
                    email_verified=True,  # Skip email verification for admin-created accounts
                )
            )
            db.commit()
            print(f"Created user '{USERNAME}' ({FULL_NAME}) with {ROLE} role and password '{PASSWORD}'.")
            print(f"Email: {email}")
    finally:
        db.close()
    print("\nLogin credentials:")
    print(f"  Username: {USERNAME}")
    print(f"  Password: {PASSWORD}")
    print(f"  Role: {ROLE}")


if __name__ == "__main__":
    main()