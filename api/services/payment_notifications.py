"""
Payment success notifications (email, etc.).
Can be mocked in tests.
"""

import logging
import os

logger = logging.getLogger(__name__)


def notify_payment_success(user_id: str, amount_cents: int, hours: int) -> None:
    """
    Trigger notification on payment success (e.g. email receipt).
    Override or mock in tests.
    """
    logger.info(
        "[PAYMENT] Success: user=%s amount_cents=%s hours=%s",
        user_id,
        amount_cents,
        hours,
    )
    if os.getenv("PAYMENT_RECEIPT_EMAIL_ENABLED", "").strip().lower() not in ("1", "true", "yes"):
        return
    try:
        from database import get_db_session
        from api.models.user import User
        from api.services.email_service import send_payment_receipt

        db = get_db_session()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                logger.warning("[PAYMENT] User not found for receipt email: %s", user_id)
                return
            email = (getattr(user, "email", None) or "").strip()
            if not email:
                logger.warning("[PAYMENT] User has no email for receipt: %s", user_id)
                return
            ok = send_payment_receipt(email, amount_cents=amount_cents, hours=hours, user_id=user_id)
            if not ok:
                logger.warning("[PAYMENT] Receipt email failed for user=%s", user_id)
        finally:
            db.close()
    except Exception as e:
        logger.exception("[PAYMENT] Receipt notification failed for user=%s: %s", user_id, e)
