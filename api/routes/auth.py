"""
Auth Routes — same login as Contracts Bot (user, admin).
No default credentials: bootstrap users come from env (see api/auth.py, docs/AUTH_DESIGN.md).
Users with must_change_password receive a restricted token that only works for the password-change flow.
Tokens are stored in auth_sessions and validated server-side (see docs/PRODUCTION_AND_APP_CONVERSION.md).
"""

# Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/AUTH_DESIGN.md;
#   docs/PRODUCTION_AND_APP_CONVERSION.md

import os
import logging
import json
import time
from datetime import datetime, timezone, timedelta
import secrets
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import (
    create_access_token,
    password_change_pending,
    check_super_admin_password,
    check_admin_password,
    check_director_password,
    check_user_password,
    decode_token,
    get_current_user,
    get_current_user_allow_password_change,
    get_user_by_username,
    hash_password,
)
from api.client_ip import get_client_ip
from api.models.user import User
from api.models.auth_token import EmailVerificationToken, PasswordResetToken
from api.models.audit import AuditLog
from api.models.ip_block import IPBlock
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Account lockout security constants
MAX_LOGIN_ATTEMPTS = 5  # Lock account after this many consecutive failed attempts
LOGIN_WINDOW_MINUTES = 15  # Time window for tracking failed attempts (in minutes)

# IP blocking constants (for admin honeypot/trap)
MAX_ADMIN_ATTEMPTS_FROM_IP = 1  # Block IP on FIRST attempt to access admin (honeypot)
ADMIN_BLOCK_WINDOW_MINUTES = 60  # Time window for admin attempt tracking (in minutes)
ADMIN_BLOCK_DURATION_HOURS = 720  # How long to block the IP (in hours) - 30 days

# Token validity duration
TOKEN_EXPIRY_HOURS = int(os.getenv("AUTH_TOKEN_EXPIRY_HOURS", "24"))

# Public registration: per-IP cooldown (seconds) to limit abuse (in-process; multi-worker = per worker)
_REGISTER_LAST_BY_IP: dict[str, float] = {}
REGISTER_IP_COOLDOWN_SEC = float(os.getenv("AUTH_REGISTER_IP_COOLDOWN_SEC", "120"))


def _public_registration_enabled() -> bool:
    """Public self-service signup is OFF by default ("coming soon").

    Read at request time so the flag can be flipped via env without code changes. Pro
    players are admin-provisioned and sign in with TD-issued credentials; admin user
    creation paths (bulk-create, POST /api/users) are unaffected by this flag.
    """
    return os.getenv("PUBLIC_REGISTRATION_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")

# Legacy hardcoded credentials removed for security.
# Authentication now uses database-backed users only.
# See api/auth.py for proper authentication implementation.


def validate_token(token: str) -> tuple[bool, str | None]:
    """
    Validate token against auth_sessions. Returns (True, role) or (False, None).
    Caller must pass a non-empty token.
    """
    if not (token or "").strip():
        return False, None
    try:
        from database import get_database_manager
        db = get_database_manager()
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, role FROM auth_sessions WHERE token = %s AND expires_at > %s",
                (token.strip(), datetime.now(timezone.utc).isoformat()),
            )
            row = cur.fetchone()
            if row:
                return True, (row[1] or "user")
        finally:
            conn.close()
    except Exception as e:
        logger.warning("validate_token failed: %s", e)
    return False, None


def store_token(token: str, username: str, role: str) -> None:
    """Store token in auth_sessions with expiry."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat()
            cur.execute(
                "INSERT INTO auth_sessions (token, username, role, expires_at) VALUES (%s, %s, %s, %s)",
                (token, username, role, expires_at),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("store_token failed: %s", e)
        raise


def invalidate_token(token: str) -> bool:
    """Remove token from auth_sessions. Returns True if a row was deleted."""
    if not (token or "").strip():
        return False
    try:
        from database import get_database_manager
        db = get_database_manager()
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM auth_sessions WHERE token = %s", (token.strip(),))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
        finally:
            conn.close()
    except Exception as e:
        logger.warning("invalidate_token failed: %s", e)
    return False


def validate_password_strength(password: str) -> bool:
    """Validate password has 8+ chars, uppercase, lowercase, number, special char."""
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


class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: str
    must_change_password: bool = False
    requires_email_setup: bool = False
    force_password_reset: bool = False

class MeResponse(BaseModel):
    role: str
    sub: str
    must_change_password: bool = False

class RegistrationRequest(BaseModel):
    username: str
    email: str
    password: str
    captcha_token: str
    license_key: str = "FREE-TRIAL-2024"  # Default license key

class RegistrationResponse(BaseModel):
    message: str
    username: str


class PublicRegistrationRequest(BaseModel):
    """Self-service signup (non-pro players). No CAPTCHA; rate-limited per IP."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=200)
    license_number: str | None = Field(None, max_length=64)


class VerificationRequest(BaseModel):
    token: str

class VerificationResponse(BaseModel):
    message: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ============================================================================
# CENTRALIZED AUTH ENDPOINTS (New)
# ============================================================================

def _record_login(
    db: Session,
    user: User | None,
    event_type: str,
    success: bool,
    details: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record login event to audit log.
    
    Args:
        db: Database session
        user: User object (may be None for failed logins)
        event_type: Type of event (login_success, login_failed, etc.)
        success: Whether the operation succeeded
        details: Optional details about the event
        ip_address: Client IP address
        user_agent: Client user agent
        
    Raises:
        Exception: Re-raises database errors after logging (prevents silent failures)
    """
    try:
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                details=details,
                timestamp=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        # Log full error details to help debugging
        error_msg = f"Audit log insert failed for event_type={event_type}, user_id={user.id if user else None}: {type(exc).__name__}: {str(exc)}"
        logger.error(error_msg)
        # Re-raise the exception to prevent silent failures
        # The caller should handle this appropriately
        raise RuntimeError(error_msg) from exc


def _apply_register_rate_limit(ip_address: str | None) -> None:
    if not ip_address:
        return
    now = time.monotonic()
    last = _REGISTER_LAST_BY_IP.get(ip_address)
    if last is not None and (now - last) < REGISTER_IP_COOLDOWN_SEC:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts from this network. Please wait a few minutes and try again.",
        )
    _REGISTER_LAST_BY_IP[ip_address] = now
    # Bound memory: drop entries older than cooldown (lazy prune on access)
    if len(_REGISTER_LAST_BY_IP) > 10_000:
        cutoff = now - REGISTER_IP_COOLDOWN_SEC
        stale = [k for k, v in _REGISTER_LAST_BY_IP.items() if v < cutoff]
        for k in stale[:5000]:
            _REGISTER_LAST_BY_IP.pop(k, None)


def _get_client_ip(request: Request | None) -> str | None:
    """Proxy-resolved client IP (api/client_ip.py). The raw X-Forwarded-For header is
    client-controlled and must not drive lockouts or honeypot IP blocks (review 2026-09-25)."""
    return get_client_ip(request)


def _is_ip_blocked(db: Session, ip_address: str | None) -> bool:
    """Check if an IP is currently blocked."""
    if not ip_address:
        return False
    block = (
        db.query(IPBlock)
        .filter(
            IPBlock.ip_address == ip_address,
            IPBlock.is_active == True,
            (IPBlock.expires_at.is_(None) | (IPBlock.expires_at > datetime.utcnow()))
        )
        .first()
    )
    return bool(block)


def _block_ip(db: Session, ip_address: str, reason: str) -> None:
    """Block an IP address."""
    if not ip_address:
        return
    
    # Check if already blocked
    existing = (
        db.query(IPBlock)
        .filter(IPBlock.ip_address == ip_address, IPBlock.is_active == True)
        .first()
    )
    
    if existing:
        # Update existing block
        existing.attempt_count += 1
        existing.blocked_at = datetime.utcnow()
        existing.expires_at = datetime.utcnow() + timedelta(hours=ADMIN_BLOCK_DURATION_HOURS)
    else:
        # Create new block
        block = IPBlock(
            ip_address=ip_address,
            reason=reason,
            attempt_count=1,
            first_attempt=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ADMIN_BLOCK_DURATION_HOURS)
        )
        db.add(block)
    
    db.commit()


def _count_admin_attempts_from_ip(db: Session, ip_address: str) -> int:
    """Count failed admin login attempts from an IP in the last ADMIN_BLOCK_WINDOW_MINUTES."""
    if not ip_address:
        return 0
    window_start = datetime.utcnow() - timedelta(minutes=ADMIN_BLOCK_WINDOW_MINUTES)
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.ip_address == ip_address,
            AuditLog.event_type == "login_failed_admin",
            AuditLog.timestamp >= window_start,
        )
        .count()
    )


def _is_locked(user: User) -> bool:
    return bool(user.account_locked_until and user.account_locked_until > datetime.utcnow())


def _count_recent_failures(db: Session, user: User) -> int:
    window_start = datetime.utcnow() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user.id,
            AuditLog.event_type == "login_failed",
            AuditLog.timestamp >= window_start,
        )
        .count()
    )


def _authenticate_local(
    body: LoginRequest,
    db: Session,
    request: Request | None = None,
) -> tuple[User | None, str, str]:
    """Authenticate user against local database.
    
    Args:
        body: Login request with username and password
        db: Database session
        request: FastAPI request object (for IP/user-agent extraction)
        
    Returns:
        Tuple of (User, role, JWT token)
        
    Raises:
        HTTPException: 401 for invalid credentials, 423 for locked account, 403 for unverified email, 429 for IP blocked
        RuntimeError: If audit logging fails (database/schema issues)
    """
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent") if request else None
    
    # Admin account is a HONEYPOT/TRAP - block IP on first attempt, silently
    is_admin_attempt = body.username.lower() == "admin"
    if is_admin_attempt:
        # Check if this IP is already blocked from honeypot
        if _is_ip_blocked(db, ip_address):
            try:
                _record_login(
                    db,
                    None,
                    "honeypot_blocked_ip",
                    False,
                    details=f"Blocked IP attempting admin login (honeypot)",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except RuntimeError as e:
                logger.error(f"Failed to log honeypot block for {ip_address}: {e}")
            # Return generic error - don't reveal they're blocked
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # FIRST ATTEMPT TO ADMIN = IMMEDIATE IP BLOCK (honeypot trap)
        _block_ip(db, ip_address, "honeypot_admin_trap")
        try:
            _record_login(
                db,
                None,
                "honeypot_trapped",
                False,
                details=f"IP blocked - attempted admin login (honeypot trap activated)",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except RuntimeError as e:
            logger.error(f"Failed to log honeypot trap for {ip_address}: {e}")
        # Return generic error - don't reveal they've been trapped
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Case/whitespace-insensitive lookup so pro accounts stored under the Fargo name
    # (mixed case, single-spaced) resolve to the real user; login() re-queries by
    # user.username to read the must_change_password / requires_email_setup flags.
    user = get_user_by_username(db, body.username)

    # For disabled accounts (especially admin), skip account lockout and only track IP attempts
    if user and not user.is_active:
        # Disabled account - don't check or apply account lockout, just track attempt
        try:
            _record_login(
                db,
                user,
                "login_failed",
                False,
                details="Attempt on disabled account",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except RuntimeError as e:
            logger.error(f"Failed to log login_failed for disabled user {user.username}: {e}")
        # Fall through to admin IP tracking below
    elif user and _is_locked(user):
        try:
            _record_login(
                db,
                user,
                "login_locked",
                False,
                details=f"Account locked until {user.account_locked_until.isoformat()}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except RuntimeError as e:
            # Log audit failure but still inform user account is locked
            logger.error(f"Failed to log locked login attempt for user {user.username}: {e}")
        raise HTTPException(status_code=423, detail="Account locked. Try again later.")

    if check_super_admin_password(body.username, body.password, db):
        token = create_access_token("super_admin", subject=body.username)
        if user:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.utcnow()
        _record_login(db, user, "login_success", True, ip_address=ip_address, user_agent=user_agent)
        return user, "super_admin", token

    if check_admin_password(body.username, body.password, db):
        token = create_access_token("admin", subject=body.username)
        if user:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.utcnow()
        _record_login(db, user, "login_success", True, ip_address=ip_address, user_agent=user_agent)
        return user, "admin", token

    if check_director_password(body.username, body.password, db):
        token = create_access_token("director", subject=body.username)
        if user:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.utcnow()
        _record_login(db, user, "login_success", True, ip_address=ip_address, user_agent=user_agent)
        return user, "director", token

    if check_user_password(body.username, body.password, db):
        # Allow login if email setup is required (Fargo accounts) even if email not verified
        # Otherwise, require email verification
        if user and not user.email_verified and not getattr(user, "requires_email_setup", False):
            try:
                _record_login(
                    db,
                    user,
                    "login_blocked_email_not_verified",
                    False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except RuntimeError as e:
                # Log audit failure but still block the login
                logger.error(f"Failed to log email-not-verified attempt for user {user.username}: {e}")
            raise HTTPException(status_code=403, detail="Email not verified. Please check your email.")
        token = create_access_token("user", subject=body.username)
        if user:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.utcnow()
        _record_login(db, user, "login_success", True, ip_address=ip_address, user_agent=user_agent)
        return user, "user", token

    if user and user.is_active:
        # Active account - track failed attempts for account lockout
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        db.commit()
        try:
            _record_login(
                db,
                user,
                "login_failed",
                False,
                details="Invalid username or password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except RuntimeError as e:
            # Log audit failure but continue with lockout check
            logger.error(f"Failed to log login_failed for user {user.username}: {e}")
        
        try:
            recent_failures = _count_recent_failures(db, user)
        except Exception as exc:
            logger.warning(f"Failed to count recent failures for user {user.username}: {type(exc).__name__}: {exc}")
            recent_failures = user.failed_login_attempts

        if recent_failures >= MAX_LOGIN_ATTEMPTS:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=LOGIN_WINDOW_MINUTES)
            user.failed_login_attempts = 0
            db.commit()
            try:
                _record_login(
                    db,
                    user,
                    "login_locked",
                    False,
                    details=f"Locked after {recent_failures} failed attempts",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except RuntimeError as e:
                # Log audit failure but still enforce the lockout
                logger.error(f"Failed to log account lockout for user {user.username}: {e}")
            raise HTTPException(status_code=423, detail="Account locked. Too many failed attempts.")

    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Login via local database. Returns JWT access token with role and user."""
    user, role, token = _authenticate_local(body, db, request)
    username = user.username if user else body.username
    
    # Query the user fresh from database to get accurate flags
    # (needed because ORM user object may have stale defaults)
    if user:
        fresh_user = db.query(User).filter_by(username=username).first()
        must_change = bool(fresh_user and getattr(fresh_user, "must_change_password", False))
        requires_email_setup = bool(fresh_user and getattr(fresh_user, "requires_email_setup", False))
        force_password_reset = bool(fresh_user and getattr(fresh_user, "force_password_reset", False))
    else:
        must_change = False
        requires_email_setup = False
        force_password_reset = False

    if must_change or force_password_reset:
        # Server-side enforcement: re-issue a restricted token (same role/subject as
        # _authenticate_local) that only works for the password-change flow until the
        # user has changed their password. See api/auth.py PASSWORD_CHANGE_CLAIM.
        # force_password_reset (Pro/Fargo first login, set by /setup-email) is enforced the
        # same way as must_change_password; POST /api/users/change-password clears both.
        token = create_access_token(role, subject=body.username, password_change_required=True)

    return TokenResponse(
        access_token=token,
        role=role,
        user=username,
        must_change_password=must_change,
        requires_email_setup=requires_email_setup,
        force_password_reset=force_password_reset
    )


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_public(
    body: PublicRegistrationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public self-service registration (role=user). Email verification required before login.
    Pro accounts are provisioned from WPA license data by admins; those players should not use this endpoint.
    """
    if not _public_registration_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Self-service signup is coming soon. Pro players: sign in with the username "
                "and temporary password provided by your tournament director."
            ),
        )
    ip_address = _get_client_ip(request)
    user_agent = (request.headers.get("user-agent") or "")[:255]
    _apply_register_rate_limit(ip_address)

    username = body.username.strip().lower()
    if len(username) < 3 or len(username) > 50:
        raise HTTPException(status_code=400, detail="Username must be 3–50 characters")
    if not re.match(r"^[a-z0-9._-]+$", username):
        raise HTTPException(
            status_code=400,
            detail="Username may only contain lowercase letters, digits, dots, underscores, and hyphens",
        )

    email = str(body.email).strip().lower()
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    if not validate_password_strength(body.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )

    prefs: dict = {}
    if body.full_name and body.full_name.strip():
        prefs["display_name"] = body.full_name.strip()[:200]

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(body.password),
        role="user",
        email_verified=False,
        is_active=True,
        preferences_json=json.dumps(prefs) if prefs else None,
    )
    db.add(user)
    db.flush()

    lic = (body.license_number or "").strip()
    if lic:
        try:
            row = db.execute(
                text("""
                    SELECT player_id, first_name, last_name, license_number
                    FROM players
                    WHERE license_number IS NOT NULL
                      AND LOWER(TRIM(license_number)) = LOWER(TRIM(:lic))
                    LIMIT 1
                """),
                {"lic": lic},
            ).fetchone()
            if row:
                player_id, first_name, last_name, lic_db = row[0], row[1], row[2], row[3]
                player_name = f"{first_name or ''} {last_name or ''}".strip() or username
                db.execute(
                    text("""
                        INSERT INTO user_player_links (user_id, player_id, player_name, license_number, created_at, updated_at)
                        VALUES (:user_id, :player_id, :player_name, :license_number, NOW(), NOW())
                        ON CONFLICT (user_id) DO UPDATE SET
                            player_id = EXCLUDED.player_id,
                            player_name = EXCLUDED.player_name,
                            license_number = EXCLUDED.license_number,
                            updated_at = NOW()
                    """),
                    {
                        "user_id": user.id,
                        "player_id": player_id,
                        "player_name": player_name,
                        "license_number": (lic_db or lic).strip() if lic_db else lic,
                    },
                )
        except Exception as exc:
            logger.warning("Optional player link on register failed for %s: %s", username, exc)

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(verification_token)

    try:
        from api.services.email import send_verification_email

        await send_verification_email(user.email, user.username, token)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", email, e)

    db.add(
        AuditLog(
            user_id=user.id,
            event_type="user_registered_public",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details=f"Public registration username={username}",
            timestamp=datetime.utcnow(),
        )
    )
    db.commit()

    return RegistrationResponse(
        message="Account created. Check your email to verify your address before signing in.",
        username=username,
    )


@router.get("/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user_allow_password_change)):
    """Return current user (role and sub) from Bearer token.

    Accepts restricted (must_change_password) tokens so the web app can restore the
    session and show the password-change gate; reports must_change_password.
    """
    return MeResponse(
        role=user["role"],
        sub=user.get("sub", user["role"]),
        must_change_password=password_change_pending(user),
    )


def _register_local(
    body: RegistrationRequest,
    db: Session,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RegistrationResponse:
    if not body.captcha_token or len(body.captcha_token.strip()) == 0:
        raise HTTPException(status_code=400, detail="CAPTCHA token required")

    if not body.username or len(body.username) < 3 or len(body.username) > 20:
        raise HTTPException(status_code=400, detail="Username must be 3-20 characters")

    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    if not body.email or not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", body.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    if not validate_password_strength(body.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )

    password_hash = hash_password(body.password)
    user = User(
        username=body.username,
        email=body.email,
        password_hash=password_hash,
        role="user",
        email_verified=False,
    )
    db.add(user)
    db.flush()
    return RegistrationResponse(
        message="Registration successful. Please verify your email before logging in.",
        username=body.username,
    )


class LogoutRequest(BaseModel):
    token: str | None = None


@router.post("/logout")
async def logout(req: LogoutRequest | None = None):
    """Logout. Optionally send {"token": "..."} in body to invalidate the token server-side."""
    if req is not None and req.token:
        invalidate_token(req.token)
    return {"success": True}


class EmailSetupRequest(BaseModel):
    email: EmailStr


class EmailSetupResponse(BaseModel):
    message: str
    email: str
    requires_verification: bool = True


@router.post("/setup-email", response_model=EmailSetupResponse)
async def setup_email(
    body: EmailSetupRequest,
    # Allowed with a restricted token: in the web app, Fargo email setup runs before the password-change gate.
    current_user: dict = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """
    Set email address for Fargo account activation.
    User must have requires_email_setup=True to use this endpoint.
    After email is set, verification email is sent and force_password_reset is enabled.
    """
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if email setup is required
    if not getattr(user, "requires_email_setup", False):
        raise HTTPException(
            status_code=400,
            detail="Email setup not required for this account"
        )
    
    email = body.email.strip().lower()
    
    # Validate email format (EmailStr already does this, but be explicit)
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Check if email is already in use by another user
    existing = db.query(User).filter(
        User.email == email,
        User.id != user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use by another user")
    
    # Update user email
    user.email = email
    user.email_verified = False  # Require verification
    user.requires_email_setup = False  # Email is now set
    user.force_password_reset = True  # Force password reset after email verification
    
    # Create and send verification email
    try:
        from api.models.auth_token import EmailVerificationToken
        from api.services.email import send_verification_email
        
        # Create verification token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        db.add(verification_token)
        
        # Send verification email
        await send_verification_email(user.email, user.username, token)
        
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        # Don't fail the request - email is set, verification can be resent
    
    # Log the action
    try:
        _record_login(
            db,
            user,
            "email_setup_completed",
            True,
            details=f"Email set to {email}",
        )
    except Exception as e:
        logger.warning(f"Failed to log email setup: {e}")
    
    db.commit()
    
    return EmailSetupResponse(
        message="Email address set successfully. Please check your email to verify your account.",
        email=email,
        requires_verification=True
    )


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Verify email address using verification token.
    After verification, if force_password_reset is True, user must reset password.
    """
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="Verification token is required")
    
    # Find verification token
    verification_token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token == token.strip(),
            EmailVerificationToken.used == False,
            EmailVerificationToken.expires_at > datetime.utcnow()
        )
        .first()
    )
    
    if not verification_token:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    # Get user
    user = db.query(User).filter_by(id=verification_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mark token as used
    verification_token.used = True
    
    # Verify email
    user.email_verified = True
    
    # If force_password_reset is set, keep it (user must reset password after verification)
    # This is set during email setup for Fargo accounts
    
    try:
        _record_login(
            db,
            user,
            "email_verified",
            True,
            details=f"Email {user.email} verified",
        )
    except Exception as e:
        logger.warning(f"Failed to log email verification: {e}")
    
    db.commit()
    
    return {
        "message": "Email verified successfully. You can now log in.",
        "requires_password_reset": getattr(user, "force_password_reset", False)
    }


async def _issue_verification_email(db: Session, user: User) -> None:
    """Create a fresh email-verification token for ``user`` and send the email.

    The token is persisted before sending so the user can retry even if the SMTP
    send fails (the send is best-effort and never aborts the request).
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    db.add(EmailVerificationToken(user_id=user.id, token=token, expires_at=expires_at))
    db.commit()
    try:
        from api.services.email import send_verification_email

        await send_verification_email(user.email, user.username, token)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", user.email, e)


def _has_real_email(user: User) -> bool:
    """True when the user has set a real (non-placeholder) email address.

    Fargo accounts start with a ``pending_<username>@fargo.local`` placeholder; those
    users must complete email setup (POST /auth/setup-email) before a verification
    email can be sent.
    """
    email = (user.email or "").strip().lower()
    return bool(email) and not email.endswith("@fargo.local") and not getattr(user, "requires_email_setup", False)


@router.post("/resend-verification", response_model=VerificationResponse)
async def resend_verification(
    current_user: dict = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """Resend the email-verification link for the currently signed-in user."""
    username = current_user.get("sub")
    user = get_user_by_username(db, username) if username else None
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, "email_verified", False):
        return VerificationResponse(message="Your email is already verified. You can sign in.")
    if not _has_real_email(user):
        raise HTTPException(status_code=400, detail="Please set your email address first.")
    await _issue_verification_email(db, user)
    return VerificationResponse(message="Verification email sent. Please check your inbox.")


class RequestVerificationEmailRequest(BaseModel):
    email: EmailStr


@router.post("/request-verification-email", response_model=VerificationResponse)
async def request_verification_email(
    body: RequestVerificationEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public: request a new verification email by address.

    Always returns a generic success message to avoid account enumeration. Throttled
    per IP to prevent email bombing.
    """
    _apply_register_rate_limit(_get_client_ip(request))
    generic = VerificationResponse(
        message="If that email is registered and not yet verified, a new verification link has been sent."
    )
    email = str(body.email).strip().lower()
    user = db.query(User).filter_by(email=email).first()
    if user and not getattr(user, "email_verified", False) and _has_real_email(user):
        try:
            await _issue_verification_email(db, user)
        except Exception as e:
            logger.error("request_verification_email send failed for %s: %s", email, e)
    return generic
