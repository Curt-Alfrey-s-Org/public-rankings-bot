#!/usr/bin/env python3
"""
Create a user or reset their password. Run on the server where the API and DB run.

  cd /path/to/Rankings-Bot
  source .env 2>/dev/null || true
  python3 scripts/create_or_reset_user.py debbieltstup

  python3 scripts/create_or_reset_user.py USERNAME [role]
  python3 scripts/create_or_reset_user.py --verify-only USERNAME   # Just set email_verified=True

You will be prompted to enter a password (and confirm) unless --verify-only. Password must be 8+ chars
with uppercase, lowercase, number, and special character.

Roles: user, director, admin, super_admin, score_keeper, moderator (default: user)
"""

import getpass
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

from database import get_db_context
from api.models.user import User
from api.auth import hash_password

ALLOWED_ROLES = ("user", "director", "admin", "super_admin", "score_keeper", "moderator")


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
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    verify_only = sys.argv[1] == "--verify-only"
    if verify_only:
        if len(sys.argv) < 3:
            print("Usage: create_or_reset_user.py --verify-only USERNAME", file=sys.stderr)
            sys.exit(1)
        username = sys.argv[2].strip()
    else:
        username = sys.argv[1].strip()
        role = sys.argv[2].strip() if len(sys.argv) > 2 else "user"
    if not verify_only and role not in ALLOWED_ROLES:
        print(f"Invalid role: {role}. Allowed: {', '.join(ALLOWED_ROLES)}", file=sys.stderr)
        sys.exit(1)

    if verify_only:
        with get_db_context() as db:
            user = db.query(User).filter_by(username=username).first()
            if not user:
                print(f"User '{username}' not found.", file=sys.stderr)
                sys.exit(1)
            if hasattr(user, "email_verified"):
                user.email_verified = True
                db.commit()
                print(f"Marked user '{username}' as email verified.")
            else:
                print(f"User model has no email_verified field.", file=sys.stderr)
                sys.exit(1)
        return

    print(f"Set password for user '{username}' (role: {role}).")
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
            user.password_hash = hash_password(pw1)
            user.role = role
            if hasattr(user, "must_change_password"):
                user.must_change_password = False
            if hasattr(user, "email_verified"):
                user.email_verified = True  # Admin-initiated reset: treat as verified
            db.commit()
            print(f"Updated user '{username}' with new password and role '{role}'.")
        else:
            email = f"{username}@user.local"
            if db.query(User).filter_by(email=email).first():
                email = f"{username}-{os.getpid()}@user.local"
            db.add(
                User(
                    username=username,
                    email=email,
                    password_hash=hash_password(pw1),
                    role=role,
                    email_verified=True,
                )
            )
            db.commit()
            print(f"Created user '{username}' with role '{role}'.")
    print(f"User can now log in with username '{username}' and the password you set.")


if __name__ == "__main__":
    main()
