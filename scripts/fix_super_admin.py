#!/usr/bin/env python3
"""Check super admin account and reset password if needed.

Required env (no defaults; the script exits with an error if either is missing):
  DATABASE_URL          e.g. postgresql://<user>:change-me@<host>:5432/<db>
  SUPER_ADMIN_PASSWORD  new password for the super admin (never printed)
Optional: SUPER_ADMIN_USERNAME (default tornybotca1).
"""
import os
import sys

# Repo root (parent of scripts/) so `api` and `database` import without a hardcoded host path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database URL: from the environment only (no hardcoded credentials). Fail fast.
db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
    sys.exit("ERROR: DATABASE_URL environment variable is required (no default).")
username = (os.environ.get("SUPER_ADMIN_USERNAME") or "tornybotca1").strip()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.user import User
from api.auth import hash_password

engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Find the user
    user = db.query(User).filter_by(username=username).first()
    
    if not user:
        print(f"ERROR: User {username} not found")
        sys.exit(1)
    
    print(f"Found user: {user.username}")
    print(f"Role: {user.role}")
    print(f"Is active: {user.is_active}")
    print(f"Failed login attempts: {user.failed_login_attempts}")
    print(f"Account locked until: {user.account_locked_until}")
    
    # Reset password from environment
    new_password = os.environ.get("SUPER_ADMIN_PASSWORD")
    if not new_password:
        raise RuntimeError(
            "SUPER_ADMIN_PASSWORD environment variable is required. "
            "Set it to the password for the super admin user."
        )
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.account_locked_until = None
    
    db.commit()
    print("\n✓ Password reset (new password taken from SUPER_ADMIN_PASSWORD; not printed)")
    print(f"✓ Account unlocked")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
