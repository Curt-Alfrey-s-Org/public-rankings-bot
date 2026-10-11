"""
Promo code validation, redemption, and referral tracking.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.ai_coach import PromoCode, Referral
from api.config.admin_config import get_effective_tier_config
from api.services.db_service import (
    get_promo_by_code,
    create_referral,
    update_user_tier,
    add_analyses_to_limit,
    get_or_create_usage,
)


class PromoCodeError(Exception):
    """Raised when promo code is invalid or cannot be applied."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_code(db: Session, code: str) -> PromoCode:
    """
    Validate promo code. Returns PromoCode if valid.
    Raises PromoCodeError if invalid, expired, or usage limit reached.
    """
    promo = get_promo_by_code(db, code)
    if not promo:
        raise PromoCodeError("Invalid or expired promo code", status_code=404)

    if not promo.is_active:
        raise PromoCodeError("This promo code is no longer active", status_code=410)

    if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
        raise PromoCodeError("Promo code has reached usage limit", status_code=410)

    expires_at = _as_utc(promo.expires_at)
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise PromoCodeError("Promo code has expired", status_code=410)

    return promo


def apply_code(
    db: Session,
    user_id: str,
    code: str,
) -> dict:
    """
    Validate code, apply benefits to user, and return upgrade info.
    Returns dict with: tier_upgrade, duration_days, bonus_analyses, discount_percent.
    Raises PromoCodeError on validation failure.
    """
    promo = validate_code(db, code)

    usage = get_or_create_usage(db, user_id)
    tier_config = get_effective_tier_config().get(promo.trial_tier, get_effective_tier_config().get("ROOKIE", {}))

    # Tier upgrade
    trial_expires_at = datetime.now(timezone.utc) + timedelta(days=promo.trial_duration_days)
    discount_percent = promo.discount_percent or promo.upgrade_discount_percent or 0
    discount_expires_at = None
    if promo.upgrade_duration_months:
        discount_expires_at = datetime.now(timezone.utc) + timedelta(
            days=promo.upgrade_duration_months * 30
        )

    update_user_tier(
        db,
        user_id=user_id,
        new_tier=promo.trial_tier,
        trial_expires_at=trial_expires_at,
        discount_percent=discount_percent,
        discount_expires_at=discount_expires_at,
    )

    # Bonus analyses
    bonus = promo.bonus_analyses or 0
    if bonus > 0:
        add_analyses_to_limit(db, user_id, bonus)

    # Increment usage
    promo.current_uses += 1

    db.commit()

    return {
        "tier_upgrade": promo.trial_tier,
        "duration_days": promo.trial_duration_days,
        "bonus_analyses": bonus,
        "discount_percent": discount_percent,
        "trial_expires_at": trial_expires_at.isoformat(),
    }


def track_referral(
    db: Session,
    referred_user_id: str,
    referrer_code: str,
) -> Optional[Referral]:
    """
    Create referral record linking referred user to the promo code's referrer.
    Call after successful apply_code.
    Returns Referral or None if promo not found.
    """
    promo = get_promo_by_code(db, referrer_code)
    if not promo:
        return None

    ref = create_referral(
        db,
        referred_user_id=referred_user_id,
        promo_code_id=promo.id,
        referrer_id=promo.influencer_id,
    )
    db.commit()
    return ref
