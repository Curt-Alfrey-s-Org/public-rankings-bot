"""
Stripe client for AI Coach 1-hour pass purchases.
Uses PaymentIntents for one-time payments.
"""

import os
import logging
from typing import Optional

from api.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# 1-hour pass: $9.99
DEFAULT_AMOUNT_CENTS = 999
DEFAULT_HOURS = 1
STRIPE_BREAKER = CircuitBreaker(name="stripe", failure_threshold=5, recovery_timeout_sec=45)


class StripeServiceError(RuntimeError):
    """Raised when Stripe operations cannot be completed."""


def _get_stripe():
    """Lazy import Stripe. Returns None if not configured."""
    if not STRIPE_SECRET_KEY:
        raise StripeServiceError("STRIPE_SECRET_KEY not configured")
    try:
        import stripe

        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise StripeServiceError("stripe package not installed")


def create_payment_intent(
    user_id: str,
    hours: int = 1,
    amount_cents: int = 999,
) -> dict:
    """
    Create a Stripe PaymentIntent for an AI Coach hour pass.

    Args:
        user_id: User identifier (username or ID)
        hours: Number of hours to purchase (default 1)
        amount_cents: Amount in cents (default 999 = $9.99)

    Returns:
        Dict with client_secret, id, status

    Raises:
        StripeServiceError: if Stripe is unavailable or API call fails
    """
    try:
        stripe = _get_stripe()
        intent = STRIPE_BREAKER.call(
            stripe.PaymentIntent.create,
            amount=amount_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={"user_id": user_id, "hours": str(hours)},
        )
        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
            "amount": amount_cents,
        }
    except StripeServiceError:
        raise
    except CircuitBreakerOpenError as e:
        logger.warning("Stripe breaker open: %s", e)
        raise StripeServiceError("Stripe temporarily unavailable, please retry shortly") from e
    except Exception as e:
        logger.exception("Failed to create PaymentIntent: %s", e)
        raise StripeServiceError("Failed to create payment intent") from e


def confirm_payment(payment_intent_id: str) -> dict:
    """
    Retrieve and confirm payment intent status.
    Returns intent details if succeeded.

    Args:
        payment_intent_id: Stripe PaymentIntent ID

    Returns:
        Dict with id, status, amount

    Raises:
        StripeServiceError: if Stripe is unavailable or API call fails
    """
    try:
        stripe = _get_stripe()
        intent = STRIPE_BREAKER.call(stripe.PaymentIntent.retrieve, payment_intent_id)
        return {
            "id": intent.id,
            "status": intent.status,
            "amount": intent.amount,
            "metadata": dict(intent.metadata or {}),
        }
    except StripeServiceError:
        raise
    except CircuitBreakerOpenError as e:
        logger.warning("Stripe breaker open: %s", e)
        raise StripeServiceError("Stripe temporarily unavailable, please retry shortly") from e
    except Exception as e:
        logger.exception("Failed to confirm payment: %s", e)
        raise StripeServiceError("Failed to confirm payment") from e


def create_customer_if_needed(user_id: str, email: str) -> Optional[str]:
    """
    Create or retrieve Stripe Customer for user.
    Returns stripe_customer_id or None.
    """
    stripe = _get_stripe()
    if not stripe:
        return None

    try:
        customers = stripe.Customer.list(email=email, limit=1)
        if customers.data:
            return customers.data[0].id
        customer = stripe.Customer.create(
            email=email,
            metadata={"user_id": user_id},
        )
        return customer.id
    except Exception as e:
        logger.exception(f"Failed to create customer: {e}")
        return None


def get_active_subscription(user_id: str, db_session) -> Optional[dict]:
    """
    Get user's active subscription (hours remaining) from our DB.
    Does not call Stripe - uses local Subscription table.
    """
    from api.models.payment import Subscription

    sub = (
        db_session.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.hours_remaining > 0,
        )
        .order_by(Subscription.updated_at.desc())
        .first()
    )
    if not sub:
        return None
    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "hours_remaining": sub.hours_remaining,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
    }


def cancel_payment_intent(payment_intent_id: str) -> bool:
    """
    Cancel a PaymentIntent.
    Returns True if canceled, False on error.
    """
    stripe = _get_stripe()
    if not stripe:
        return False

    try:
        intent = stripe.PaymentIntent.cancel(payment_intent_id)
        return intent.status == "canceled"
    except Exception as e:
        logger.exception(f"Failed to cancel PaymentIntent: {e}")
        return False


def verify_webhook_signature(payload: bytes, sig_header: str) -> Optional[dict]:
    """
    Verify Stripe webhook signature and return event.
    Returns event dict or None if invalid.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured")
        return None

    try:
        import stripe

        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            webhook_secret,
        )
        return event
    except ValueError as e:
        logger.warning(f"Webhook payload invalid: {e}")
        return None
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return None
