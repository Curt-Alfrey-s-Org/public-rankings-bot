"""
Payment routes for AI Coach 1-hour pass purchases via Stripe.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from database import get_db
from api.auth import get_current_user_object as get_current_user
from api.models.payment import Payment, Subscription
from api.services.stripe_client import (
    create_payment_intent,
    confirm_payment,
    create_customer_if_needed,
    get_active_subscription,
    cancel_payment_intent,
    StripeServiceError,
)
from api.services.payment_notifications import notify_payment_success

router = APIRouter(prefix="/api/payments", tags=["payments"])


class IntentRequest(BaseModel):
    hours: int = 1
    amount_cents: int = 999


class IntentResponse(BaseModel):
    client_secret: str
    intent_id: str
    status: str
    amount: int


class ConfirmRequest(BaseModel):
    payment_intent_id: str


class ConfirmResponse(BaseModel):
    intent_id: str
    status: str
    hours_added: int
    hours_remaining: int


class StatusResponse(BaseModel):
    intent_id: str
    status: str
    amount: int | None
    created_at: str | None


# SimpleUser from auth has .id = username
def _user_id(user) -> str:
    return getattr(user, "id", None) or getattr(user, "username", None) or str(user.get("sub", ""))


@router.post("/intent", response_model=IntentResponse)
async def create_intent(
    req: IntentRequest | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe PaymentIntent for an AI Coach 1-hour pass.
    Returns client_secret for frontend Stripe Elements.
    """
    uid = _user_id(user)
    hours = (req or IntentRequest()).hours
    amount_cents = (req or IntentRequest()).amount_cents

    if hours < 1 or amount_cents < 100:
        raise HTTPException(status_code=400, detail="Invalid hours or amount")

    try:
        result = create_payment_intent(user_id=uid, hours=hours, amount_cents=amount_cents)
    except StripeServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    payment = Payment(
        user_id=uid,
        stripe_intent_id=result["id"],
        amount_cents=amount_cents,
        hours=hours,
        status="pending",
    )
    db.add(payment)
    db.commit()

    return IntentResponse(
        client_secret=result["client_secret"],
        intent_id=result["id"],
        status=result["status"],
        amount=result["amount"],
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_and_update_tier(
    req: ConfirmRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm a payment and add purchased hours to user's subscription.
    """
    uid = _user_id(user)
    intent_id = req.payment_intent_id

    payment = db.query(Payment).filter(
        Payment.stripe_intent_id == intent_id,
        Payment.user_id == uid,
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "succeeded":
        sub = get_active_subscription(uid, db)
        hours_remaining = sub["hours_remaining"] if sub else 0
        return ConfirmResponse(
            intent_id=intent_id,
            status="succeeded",
            hours_added=0,
            hours_remaining=hours_remaining,
        )

    try:
        result = confirm_payment(intent_id)
    except StripeServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if result["status"] != "succeeded":
        payment.status = result["status"]
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Payment not succeeded: {result['status']}",
        )

    payment.status = "succeeded"
    hours_purchased = int(result.get("metadata", {}).get("hours", payment.hours) or payment.hours)

    # Add hours to subscription (create or update)
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == uid)
        .order_by(Subscription.updated_at.desc())
        .first()
    )

    if sub:
        sub.hours_remaining += hours_purchased
        sub.updated_at = datetime.now(timezone.utc)
        if not sub.expires_at or sub.expires_at < datetime.now(timezone.utc):
            sub.expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    else:
        sub = Subscription(
            user_id=uid,
            hours_remaining=hours_purchased,
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        )
        db.add(sub)

    db.commit()
    db.refresh(sub)

    notify_payment_success(uid, payment.amount_cents, hours_purchased)

    return ConfirmResponse(
        intent_id=intent_id,
        status="succeeded",
        hours_added=hours_purchased,
        hours_remaining=sub.hours_remaining,
    )


@router.get("/status/{intent_id}", response_model=StatusResponse)
async def get_payment_status(
    intent_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get status of a payment intent.
    """
    uid = _user_id(user)

    payment = db.query(Payment).filter(
        Payment.stripe_intent_id == intent_id,
        Payment.user_id == uid,
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return StatusResponse(
        intent_id=payment.stripe_intent_id,
        status=payment.status,
        amount=payment.amount_cents,
        created_at=payment.created_at.isoformat() if payment.created_at else None,
    )


@router.delete("/cancel/{intent_id}")
async def cancel_intent(
    intent_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel a pending payment intent.
    """
    uid = _user_id(user)

    payment = db.query(Payment).filter(
        Payment.stripe_intent_id == intent_id,
        Payment.user_id == uid,
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel: status is {payment.status}")

    ok = cancel_payment_intent(intent_id)
    if not ok:
        raise HTTPException(status_code=502, detail="Could not cancel payment with Stripe")

    payment.status = "canceled"
    db.commit()

    return {"status": "canceled", "intent_id": intent_id}
