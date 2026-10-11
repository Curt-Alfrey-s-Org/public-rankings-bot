"""
Coupon/promo code redemption and validation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from api.auth import get_current_user_object as get_current_user
from api.services.promo_service import validate_code, apply_code, track_referral, PromoCodeError

router = APIRouter(prefix="/api/coupon", tags=["coupons"])


def _user_id(user) -> str:
    return getattr(user, "id", None) or getattr(user, "username", None) or str(getattr(user, "sub", ""))


class RedeemRequest(BaseModel):
    code: str


class RedeemResponse(BaseModel):
    success: bool
    message: str
    tier_granted: str
    duration_days: int
    bonus_analyses: int = 0
    discount_percent: int = 0


class ValidateResponse(BaseModel):
    valid: bool
    code: str
    message: str
    tier_granted: str | None = None
    duration_days: int | None = None


@router.post("/redeem", response_model=RedeemResponse)
async def redeem_coupon(
    request: RedeemRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate promo code, apply benefits (tier upgrade + usage boost), and record referral.
    """
    uid = _user_id(user)
    code = (request.code or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="Promo code is required")

    try:
        result = apply_code(db, uid, code)
    except PromoCodeError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    track_referral(db, referred_user_id=uid, referrer_code=code)

    return RedeemResponse(
        success=True,
        message=f"Welcome to {result['tier_upgrade']}! {result['duration_days']}-day trial activated.",
        tier_granted=result["tier_upgrade"],
        duration_days=result["duration_days"],
        bonus_analyses=result.get("bonus_analyses", 0),
        discount_percent=result.get("discount_percent", 0),
    )


@router.get("/validate/{code}", response_model=ValidateResponse)
async def validate_coupon(
    code: str,
    db: Session = Depends(get_db),
):
    """
    Check if promo code exists and is valid before redeeming.
    Does not require authentication.
    """
    if not code or not code.strip():
        return ValidateResponse(
            valid=False,
            code=code or "",
            message="Invalid code",
        )

    try:
        promo = validate_code(db, code)
        return ValidateResponse(
            valid=True,
            code=promo.code,
            message="Code is valid",
            tier_granted=promo.trial_tier,
            duration_days=promo.trial_duration_days,
        )
    except PromoCodeError as e:
        return ValidateResponse(
            valid=False,
            code=code.strip().upper(),
            message=e.message,
        )
