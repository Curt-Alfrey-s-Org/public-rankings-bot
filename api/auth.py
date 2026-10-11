"""
Auth: JWT-based authentication. Single source of truth: database (users table).
- All roles (super_admin, admin, director, user) are stored as User rows; passwords verified via password_hash.
- Bootstrap: env credentials (SUPER_ADMIN_*, ADMIN_*, DIRECTOR_*, USER_*, SCORE_KEEPER_*) only create
  missing users at startup; never used at login. There is NO built-in default password: in production a
  missing SUPER_ADMIN_PASSWORD (when the super admin does not exist yet) aborts startup.
- must_change_password / force_password_reset: login issues a restricted token (PASSWORD_CHANGE_CLAIM); until the user changes
  their password, every protected dependency rejects it with 403 except the password-change flow.
- No file or env fallbacks at login time; one authenticate path: get user by username -> verify password.
"""

# Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/AUTH_DESIGN.md;
#   docs/ROLES_AND_PERMISSIONS.md; docs/ROLE_CAPABILITIES.md

import os
import logging
from datetime import datetime, timedelta
from typing import Literal, Optional
from functools import wraps

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Simple user object for AI Coach compatibility
class SimpleUser:
    """Simple user object that works with AI Coach attribute access"""
    def __init__(self, username: str, role: str):
        self.id = username  # Use username as ID
        self.username = username
        self.role = role
        self.sub = username

# JWT: require secure secret from environment
SECRET_KEY = os.getenv("JWT_SECRET")
_JWT_PLACEHOLDERS = ("rankings-bot-change-in-production", "change-this-in-production")
if not SECRET_KEY or SECRET_KEY.strip() in _JWT_PLACEHOLDERS:
    raise RuntimeError(
        "JWT_SECRET environment variable is required and must be set to a strong random value. "
        "Generate one with: openssl rand -hex 32"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Bearer token
security = HTTPBearer(auto_error=False)
optional_bearer = HTTPBearer(auto_error=False)

Role = Literal["admin", "director", "user", "super_admin", "score_keeper"]

# Password hashing: pwdlib multi-hasher per the FastAPI security tutorial
# (https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#password-hashing).
# Argon2 first = current algorithm for new/updated hashes; bcrypt second so existing
# stored hashes keep verifying and transparently upgrade to Argon2 on next successful
# login via verify_and_update() (pwdlib guide: https://frankie567.github.io/pwdlib/guide/).
_password_hasher = PasswordHash((Argon2Hasher(), BcryptHasher()))

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def _password_bytes(plain: str, max_len: int = 72) -> bytes:
    """bcrypt verifies at most 72 bytes (bcrypt>=4.1 raises beyond that). Legacy hashes
    were created from the truncated bytes, so legacy verification must truncate the same way."""
    if not isinstance(plain, str):
        plain = str(plain or "")
    raw = plain.encode("utf-8")
    return raw[:max_len] if len(raw) > max_len else raw


def _hash_password(password: str) -> str:
    """Hash for storage (Argon2id via pwdlib — no length limit)."""
    return _password_hasher.hash(password)


def _verify_and_update_hash(plain: str, hashed: str) -> tuple[bool, Optional[str]]:
    """Verify plaintext against a stored hash (Argon2 or legacy bcrypt).

    Returns (valid, updated_hash): updated_hash is a new Argon2 hash to persist when
    the stored hash uses an outdated algorithm/parameters (pwdlib verify_and_update
    semantics); None when the hash is current or the password is wrong.
    """
    if not (plain and hashed):
        return False, None
    try:
        if hashed.startswith(_BCRYPT_PREFIXES):
            # Legacy bcrypt: verify with the same 72-byte truncation the hash was
            # created with, but re-hash the FULL password with the current hasher
            # so the upgraded Argon2 hash matches what the user actually types.
            if not _password_hasher.verify(_password_bytes(plain), hashed):
                return False, None
            return True, _password_hasher.hash(plain)
        return _password_hasher.verify_and_update(plain, hashed)
    except Exception:
        # Unknown/malformed hash or backend error — treat as verification failure.
        return False, None


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against stored hash (Argon2 or legacy bcrypt)."""
    valid, _ = _verify_and_update_hash(plain, hashed)
    return valid


def _verify_user_password(db: Session, user, plain: str) -> bool:
    """Verify against user.password_hash and transparently upgrade outdated hashes
    (legacy bcrypt → Argon2) on success. A failed upgrade never blocks login."""
    valid, updated = _verify_and_update_hash(plain, user.password_hash)
    if valid and updated:
        try:
            user.password_hash = updated
            db.commit()
            logger.info("Password hash upgraded to current algorithm for user %s",
                        getattr(user, "username", "?"))
        except Exception as e:
            logger.warning("Password hash upgrade failed for user %s: %s",
                           getattr(user, "username", "?"), e)
            try:
                db.rollback()
            except Exception as rollback_error:
                logger.warning("DB rollback failed after hash upgrade: %s", rollback_error)
    return valid

# JWT claim marking a token issued to a user whose must_change_password (or
# force_password_reset) flag is set.
# Such a token may only be used for the password-change flow (see get_current_user and
# api/middleware/access_control.py); everything else returns 403 PASSWORD_CHANGE_REQUIRED_DETAIL.
PASSWORD_CHANGE_CLAIM = "pwd_change_required"
PASSWORD_CHANGE_REQUIRED_DETAIL = "Password change required"


def create_access_token(role: Role, subject: str = "", password_change_required: bool = False) -> str:
    """Create a JWT with role and optional subject (e.g. username for admin).
    All roles use ACCESS_TOKEN_EXPIRE_DAYS (super_admin previously had 2h; aligned for parity).
    password_change_required=True marks the token as restricted to the password-change flow."""
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject or role,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    if password_change_required:
        payload[PASSWORD_CHANGE_CLAIM] = True
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _user_still_must_change_password(username: str) -> bool:
    """DB check: True while the user's must_change_password or force_password_reset flag is still set.

    A restricted token regains normal access as soon as the user has changed their
    password (the web app keeps using the same token after POST /api/users/change-password).
    Fails closed: unknown user or DB error -> still restricted.
    """
    if not username:
        return True
    try:
        from database import get_session_local

        db = get_session_local()()
        try:
            user = get_user_by_username(db, username)
            if user is None:
                return True
            return bool(
                getattr(user, "must_change_password", False)
                or getattr(user, "force_password_reset", False)
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning("Password-change state lookup failed for %s: %s", username, e)
        return True


def password_change_pending(payload: dict | None) -> bool:
    """True when the token carries PASSWORD_CHANGE_CLAIM and the user has not changed their password yet."""
    if not payload or not payload.get(PASSWORD_CHANGE_CLAIM):
        return False
    return _user_still_must_change_password(str(payload.get("sub") or ""))


def _raise_password_change_required() -> None:
    raise HTTPException(status_code=403, detail=PASSWORD_CHANGE_REQUIRED_DETAIL)

def decode_token(token: str) -> dict:
    """Decode and validate JWT; raise HTTPException if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_allow_password_change(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Dependency: require valid Bearer token; return payload with role.

    Also accepts a restricted (must_change_password) token. Use ONLY for the
    password-change flow: POST /api/users/change-password, GET /api/auth/me,
    POST /api/auth/setup-email, POST /api/auth/resend-verification.
    """
    if not credentials:
        logger.warning("Auth: no credentials (Authorization header missing or not Bearer)")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    role = payload.get("role")
    if role not in ("admin", "director", "user", "super_admin", "score_keeper"):
        raise HTTPException(status_code=401, detail="Invalid role")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Dependency: require valid Bearer token; return payload with role.

    Rejects (403) a token issued while must_change_password is set, until the user
    has changed their password (server-side enforcement; not just the browser gate).
    """
    payload = get_current_user_allow_password_change(credentials)
    if password_change_pending(payload):
        _raise_password_change_required()
    return payload


def get_current_user_object(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> SimpleUser:
    """Dependency: return user object with id attribute for AI Coach compatibility."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    role = payload.get("role")
    username = payload.get("sub")
    
    if role not in ("admin", "director", "user", "super_admin", "score_keeper"):
        raise HTTPException(status_code=401, detail="Invalid role")
    if password_change_pending(payload):
        _raise_password_change_required()

    # Return SimpleUser object with attribute access
    return SimpleUser(username=username, role=role)

def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> dict | None:
    """Dependency: optional auth; return payload or None."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None
    # Restricted (must_change_password) tokens are treated as anonymous.
    if password_change_pending(payload):
        return None
    return payload

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin or super_admin (both have full access)."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user

def require_director_or_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require director, admin, or super_admin (create players/tournaments, data input)."""
    if user.get("role") not in ("admin", "director", "super_admin"):
        raise HTTPException(status_code=403, detail="Director or Admin only")
    return user


def require_score_keeper(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require score_keeper JWT (tablet/device in scorekeeper mode for table score entry)."""
    if user.get("role") != "score_keeper":
        raise HTTPException(status_code=403, detail="Score keeper only")
    return user


def require_director_or_score_keeper(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: director, scorekeeper-mode device, admin, or super_admin (score entry, timers, match state)."""
    if user.get("role") not in ("director", "score_keeper", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Director or Score keeper required")
    return user


def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require super_admin role only (e.g. rebuild & deploy). Not advertised."""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_admin_or_super_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin or super_admin (e.g. user management, full deploy)."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin or super admin required")
    return user


# Super admin: single source of truth is the database. Env is used only to bootstrap the first user.
def get_super_admin_username() -> str:
    return (os.getenv("SUPER_ADMIN_USERNAME") or "tornybotca1").strip()


# -----------------------------------------------------------------------------
# Startup bootstrap (env credentials only; no hardcoded passwords).
# -----------------------------------------------------------------------------
# Each entry: (env prefix, default username, role, required).
#   <PREFIX>_USERNAME       optional, defaults to the username shown here
#   <PREFIX>_PASSWORD       plaintext password used to create the user (hashed with Argon2)
#   <PREFIX>_PASSWORD_HASH  alternative: pre-computed Argon2/bcrypt hash
# Users are created only when missing; existing passwords are never overwritten.
# "required" accounts must be creatable in production: if the user does not exist and no
# password is configured, startup fails (BootstrapConfigError). Optional accounts are
# simply skipped when no password is configured.
BOOTSTRAP_ACCOUNTS: tuple[tuple[str, str, str, bool], ...] = (
    ("SUPER_ADMIN", "tornybotca1", "super_admin", True),
    ("ADMIN", "admin", "admin", False),
    ("DIRECTOR", "director", "director", False),
    ("USER", "user", "user", False),
    ("SCORE_KEEPER", "scorekeeper", "score_keeper", False),
)

_HASH_PREFIXES = ("$argon2",) + _BCRYPT_PREFIXES
_PASSWORD_SPECIALS = "!@#$%^&*()-_+={}[]|:;<>?,./~`"


class BootstrapConfigError(RuntimeError):
    """Bootstrap credentials are missing or invalid (fatal in production)."""


def is_production() -> bool:
    """Production unless DEBUG is truthy (same rule as the JWT_SECRET startup check)."""
    return os.environ.get("DEBUG", "false").strip().lower() not in ("1", "true", "yes")


def _password_meets_policy(password: str) -> bool:
    """Same rule as api.routes.auth.validate_password_strength (8+ chars, upper, lower, digit, special)."""
    return (
        len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
        and any(c in _PASSWORD_SPECIALS for c in password)
    )


def _bootstrap_password_hash(prefix: str) -> tuple[Optional[str], Optional[str]]:
    """Return (password_hash, error) from <PREFIX>_PASSWORD_HASH or <PREFIX>_PASSWORD. (None, None) = not configured."""
    pw_hash = (os.environ.get(f"{prefix}_PASSWORD_HASH") or "").strip()
    if pw_hash:
        if not pw_hash.startswith(_HASH_PREFIXES):
            return None, f"{prefix}_PASSWORD_HASH is not an Argon2 or bcrypt hash"
        return pw_hash, None
    password = (os.environ.get(f"{prefix}_PASSWORD") or "").strip()
    if not password:
        return None, None
    if not _password_meets_policy(password):
        return None, (
            f"{prefix}_PASSWORD does not meet the password policy "
            "(8+ chars with uppercase, lowercase, number, and special character)"
        )
    return _hash_password(password), None


def ensure_bootstrap_users(db: Session) -> dict:
    """Create missing bootstrap users from env credentials.

    Returns {"created": [...], "existing": [...], "skipped": [...], "errors": [...]}.
    Raises BootstrapConfigError when any configuration error was found (e.g. production
    without SUPER_ADMIN_PASSWORD while the super admin does not exist yet, or a password
    that fails the policy). In development (DEBUG=true) a missing password only skips
    that account with a warning, so local dev keeps working without a known default.
    Database errors propagate to the caller (never silently swallowed).
    """
    from api.models.user import User

    production = is_production()
    summary: dict = {"created": [], "existing": [], "skipped": [], "errors": []}
    try:
        for prefix, default_username, role, required in BOOTSTRAP_ACCOUNTS:
            username = (os.environ.get(f"{prefix}_USERNAME") or default_username).strip()
            if not username:
                summary["skipped"].append(f"{prefix}: empty username")
                continue

            existing = db.query(User).filter_by(username=username).first()
            if existing:
                if role == "super_admin" and getattr(existing, "role", None) != "super_admin":
                    existing.role = "super_admin"
                summary["existing"].append(username)
                continue

            password_hash, error = _bootstrap_password_hash(prefix)
            if error:
                summary["errors"].append(error)
                continue
            if password_hash is None:
                if required and production:
                    summary["errors"].append(
                        f"{prefix}_PASSWORD must be set in production to create the {role} user "
                        f"'{username}' (no default password exists). See docs/ENV_VARS.md."
                    )
                elif required:
                    logger.warning(
                        "[BOOTSTRAP] %s user '%s' not created: set %s_PASSWORD (dev: DEBUG=true) to create it.",
                        role, username, prefix,
                    )
                    summary["skipped"].append(f"{prefix}: no password configured")
                else:
                    summary["skipped"].append(f"{prefix}: no password configured")
                continue

            if username.lower() == "admin":
                logger.warning(
                    "[BOOTSTRAP] Username 'admin' is the login honeypot (web login blocks the IP). "
                    "Set %s_USERNAME to a different name.", prefix,
                )
            email_domain = "superadmin.local" if role == "super_admin" else "bootstrap.local"
            email = f"{username.lower()}@{email_domain}"
            if db.query(User).filter_by(email=email).first():
                summary["skipped"].append(f"{prefix}: email {email} already in use")
                continue

            db.add(User(
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                email_verified=True,
                must_change_password=True,  # Force password change on first login (enforced server-side)
            ))
            summary["created"].append(username)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if summary["errors"]:
        raise BootstrapConfigError("Auth bootstrap configuration error: " + "; ".join(summary["errors"]))
    return summary


# Optional env for bootstrap only (see docs/AUTH_DESIGN.md)
def get_admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "admin")


# Director credentials from env (bootstrap only)
def get_director_username() -> str:
    return os.getenv("DIRECTOR_USERNAME", "director")

def get_director_password_hash() -> str | None:
    return os.getenv("DIRECTOR_PASSWORD_HASH")

# User credentials from env (bootstrap only)
def get_user_username() -> str:
    return os.getenv("USER_USERNAME", "user")

def get_user_password_hash() -> str | None:
    return os.getenv("USER_PASSWORD_HASH")


def get_score_keeper_username() -> str:
    return os.getenv("SCORE_KEEPER_USERNAME", "scorekeeper")


def get_score_keeper_password_hash() -> str | None:
    return os.getenv("SCORE_KEEPER_PASSWORD_HASH")


def require_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin or super_admin (both have admin access)."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_authenticated_user(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require any authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def hash_password(password: str) -> str:
    """Hash a plaintext password (for DB storage)."""
    return _hash_password(password)


# -----------------------------------------------------------------------------
# Single authenticate path (DB only). No file or env at login time.
# -----------------------------------------------------------------------------

def get_user_by_username(db: Session, username: str):
    """Get User by username from DB. Returns None if not found or on DB error.

    Pro (Fargo) accounts store the username as the player's Fargo name (mixed case,
    single-spaced). To let players sign in with that name regardless of how they type
    it, fall back to a case-insensitive, whitespace-collapsed match when the exact
    match misses. Exact match is tried first so existing lowercase usernames are
    unaffected.
    """
    try:
        from sqlalchemy import func
        from api.models.user import User
        u = " ".join((username or "").split())
        if not u:
            return None
        user = db.query(User).filter_by(username=u).first()
        if user:
            return user
        return db.query(User).filter(func.lower(User.username) == u.lower()).first()
    except Exception as e:
        logger.debug("get_user_by_username failed: %s", e)
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.warning("DB rollback failed in get_user_by_username: %s", rollback_error)
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[tuple]:
    """
    Single login path: look up user by username, verify password. Returns (user, must_change_password) or None.
    Use this for all roles; role comes from user.role. No env or file fallbacks.
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    plain = (password or "").strip()
    if not plain:
        return None
    if not _verify_user_password(db, user, plain):
        return None
    must_change = getattr(user, "must_change_password", False)
    return (user, bool(must_change))


def check_super_admin_password(username: str, password: str, db: Optional[Session] = None) -> bool:
    """Check super_admin password against database. Super admin is always from DB."""
    if not db:
        return False
    user = get_user_by_username(db, username)
    if not user or user.role != "super_admin":
        return False
    return _verify_user_password(db, user, password)


def check_admin_password(username: str, password: str, db: Optional[Session] = None) -> bool:
    """Check admin password against database."""
    if not db:
        return False
    user = get_user_by_username(db, username)
    if not user or user.role != "admin":
        return False
    return _verify_user_password(db, user, password)


def get_admin_password_hash() -> str | None:
    return os.getenv("ADMIN_PASSWORD_HASH")


def check_director_password(username: str, password: str, db: Optional[Session] = None) -> bool:
    """Check director password against database."""
    if not db:
        return False
    user = get_user_by_username(db, username)
    if not user or user.role != "director":
        return False
    return _verify_user_password(db, user, password)


def check_user_password(username: str, password: str, db: Optional[Session] = None) -> bool:
    """Check user password against database."""
    if not db:
        return False
    user = get_user_by_username(db, username)
    if not user or user.role != "user":
        return False
    return _verify_user_password(db, user, password)
