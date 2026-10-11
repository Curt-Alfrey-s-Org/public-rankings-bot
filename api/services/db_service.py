"""
Database service layer for promo codes, referrals, and user tier management.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from api.models.ai_coach import PromoCode, Referral, AICoachUsage
from api.config.admin_config import get_effective_tier_config


def get_promo_by_code(db: Session, code: str) -> Optional[PromoCode]:
    """
    Look up promo code by code string (case-insensitive).
    Returns PromoCode or None.
    """
    return (
        db.query(PromoCode)
        .filter(PromoCode.code == code.upper().strip())
        .first()
    )


def create_referral(
    db: Session,
    referred_user_id: str,
    promo_code_id: str,
    referrer_id: str,
) -> Referral:
    """
    Create a referral record for a user who redeemed a promo code.
    Returns the created Referral.
    """
    ref = Referral(
        promo_code_id=promo_code_id,
        referred_user_id=referred_user_id,
        referrer_id=referrer_id,
        referral_date=datetime.now(timezone.utc),
        is_active=True,
        reward_status="pending",
    )
    db.add(ref)
    db.flush()  # Get ref.id if needed
    return ref


def update_user_tier(
    db: Session,
    user_id: str,
    new_tier: str,
    trial_expires_at: Optional[datetime] = None,
    discount_percent: int = 0,
    discount_expires_at: Optional[datetime] = None,
) -> AICoachUsage:
    """
    Update user's tier and limits.
    Creates AICoachUsage if it doesn't exist.
    Returns the usage record.
    """
    usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
    if not usage:
        usage = AICoachUsage(
            user_id=user_id,
            tier="FREEBIE",
            analyses_limit=0,
            lifetime_limit=3,
        )
        db.add(usage)

    tier_config = get_effective_tier_config().get(new_tier, get_effective_tier_config().get("FREEBIE", {}))
    usage.tier = new_tier
    usage.trial_tier = new_tier
    usage.trial_expires_at = trial_expires_at
    usage.analyses_limit = tier_config.get("monthly_limit") or 999999
    usage.lifetime_limit = tier_config.get("lifetime_limit")
    usage.max_video_duration_seconds = tier_config.get("max_video_duration", 30)
    if discount_percent is not None:
        usage.discount_percent = discount_percent
    if discount_expires_at is not None:
        usage.discount_expires_at = discount_expires_at
    usage.updated_at = datetime.now(timezone.utc)
    return usage


def add_analyses_to_limit(
    db: Session,
    user_id: str,
    count: int,
) -> AICoachUsage:
    """
    Add extra analyses to user's limit (monthly or lifetime depending on tier).
    Creates AICoachUsage if it doesn't exist.
    Returns the usage record.
    """
    usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
    if not usage:
        usage = AICoachUsage(
            user_id=user_id,
            tier="FREEBIE",
            analyses_limit=3,
            lifetime_limit=3,
        )
        db.add(usage)

    if usage.tier == "FREEBIE":
        usage.lifetime_limit = (usage.lifetime_limit or 3) + count
    else:
        usage.analyses_limit = (usage.analyses_limit or 0) + count
    usage.updated_at = datetime.now(timezone.utc)
    return usage


def get_or_create_usage(db: Session, user_id: str) -> AICoachUsage:
    """Get user's usage record or create a default FREEBIE one."""
    usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
    if not usage:
        usage = AICoachUsage(
            user_id=user_id,
            tier="FREEBIE",
            analyses_limit=0,
            lifetime_limit=3,
        )
        db.add(usage)
    return usage
