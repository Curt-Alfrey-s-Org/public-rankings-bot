#!/usr/bin/env python3
"""
Verify a user's email (set email_verified=True) so they can log in.
Usage: python scripts/verify_user_email.py <username>

Run inside API container:
  docker exec rankings-bot-api python scripts/verify_user_email.py guestrus
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

from database import get_db_session
from api.models.user import User


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_user_email.py <username>")
        sys.exit(1)
    username = sys.argv[1].strip()
    if not username:
        print("Username cannot be empty")
        sys.exit(1)

    db = get_db_session()
    try:
        user = db.query(User).filter_by(username=username).first()
        if not user:
            print(f"User '{username}' not found.")
            sys.exit(1)
        if user.email_verified:
            print(f"User '{username}' is already verified.")
            sys.exit(0)
        user.email_verified = True
        db.commit()
        print(f"Verified email for user '{username}'. They can now log in.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
