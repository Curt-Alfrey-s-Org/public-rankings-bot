#!/usr/bin/env python3
"""
Ensure user 'Bama' exists with role admin and set password from prompt.
Run on the server (where the API and DB run). Uses same DATABASE_URL as the API.

  cd /path/to/Rankings-Bot
  source .env 2>/dev/null || true
  python3 scripts/set_bama_admin.py

You will be prompted to enter a password (and confirm). Then log in at the site with Bama / that password.
Password must be 8+ chars with uppercase, lowercase, number, and special character.
"""

import getpass
import os
import sys

# Project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Load .env if present
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)

from database import get_db_context
from api.models.user import User
from api.auth import hash_password


def validate_password_strength(password: str) -> bool:
    """Same rules as API: 8+ chars, upper, lower, digit, special."""
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()-_+={}[]|:;<>?,./~`" for c in password):
        return False
    return True


def main() -> None:
    username = "Bama"
    email = "Bama@admin.local"

    print("Set password for user 'Bama' (admin role).")
    pw1 = getpass.getpass("Enter new password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    if not validate_password_strength(pw1):
        print(
            "Password must be 8+ characters with uppercase, lowercase, number, and special character.",
            file=sys.stderr,
        )
        sys.exit(1)

    with get_db_context() as db:
        user = db.query(User).filter_by(username=username).first()
        if user:
            user.role = "admin"
            user.password_hash = hash_password(pw1)
            if hasattr(user, "must_change_password"):
                user.must_change_password = False
            db.commit()
            print(f"Updated existing user '{username}' to admin and set new password.")
        else:
            if db.query(User).filter_by(email=email).first():
                email = f"Bama-admin-{os.getpid()}@admin.local"
            db.add(
                User(
                    username=username,
                    email=email,
                    password_hash=hash_password(pw1),
                    role="admin",
                    email_verified=True,
                )
            )
            db.commit()
            print(f"Created user '{username}' with role admin and set password.")
    print("You can now log in at https://www.probilliardssoftware.com/ with Bama and your new password.")


if __name__ == "__main__":
    main()
