"""
Tournament registration payment via Stripe.
Uses tournament_registration_settings for entry_fee, tournament_payments for tracking.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def create_tournament_registration_intent(
    tournament_id: str,
    player_id: str,
    amount_cents: int,
    db_conn,
) -> Optional[Dict[str, Any]]:
    """
    Create Stripe PaymentIntent for tournament entry fee.
    Records in tournament_payments (status=pending).
    Returns {client_secret, intent_id, amount} or None.
    """
    from api.services.stripe_client import _get_stripe, StripeServiceError
    try:
        stripe = _get_stripe()
    except StripeServiceError as exc:
        logger.warning("Tournament payment unavailable: %s", exc)
        return None
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "type": "tournament_registration",
                "tournament_id": tournament_id,
                "player_id": player_id,
            },
        )
        cur = db_conn.cursor()
        cur.execute(
            """
            INSERT INTO tournament_payments (tournament_id, player_id, amount_cents, status, stripe_payment_id)
            VALUES (%s, %s, %s, 'pending', %s)
            """,
            (tournament_id, player_id, amount_cents, intent.id),
        )
        db_conn.commit()
        return {
            "client_secret": intent.client_secret,
            "intent_id": intent.id,
            "amount": amount_cents,
        }
    except Exception as e:
        logger.exception("Tournament payment intent failed: %s", e)
        return None


def confirm_tournament_payment(
    intent_id: str,
    db_conn,
) -> Optional[Dict[str, Any]]:
    """
    Confirm tournament payment and mark tournament_payments as paid.
    Returns {tournament_id, player_id, status} or None.
    """
    from api.services.stripe_client import confirm_payment, StripeServiceError
    try:
        result = confirm_payment(intent_id)
    except StripeServiceError as exc:
        logger.warning("Tournament payment confirmation unavailable: %s", exc)
        return None
    if not result or result.get("status") != "succeeded":
        return None
    metadata = result.get("metadata") or {}
    if metadata.get("type") != "tournament_registration":
        return None
    tournament_id = metadata.get("tournament_id")
    player_id = metadata.get("player_id")
    if not tournament_id or not player_id:
        return None
    cur = db_conn.cursor()
    cur.execute(
        "UPDATE tournament_payments SET status = 'paid', stripe_payment_id = %s WHERE tournament_id = %s AND player_id = %s",
        (intent_id, tournament_id, player_id),
    )
    db_conn.commit()
    return {"tournament_id": tournament_id, "player_id": player_id, "status": "paid"}


def get_entry_fee_cents(tournament_id: str, db_conn) -> int:
    """Get entry fee from tournament_registration_settings. Returns 0 if free or not set."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT entry_fee_cents FROM tournament_registration_settings WHERE tournament_id = %s",
        (tournament_id,),
    )
    row = cur.fetchone()
    if not row:
        return 0
    val = row[0] if hasattr(row, "__getitem__") else row.get("entry_fee_cents")
    return int(val or 0)


def has_paid(tournament_id: str, player_id: str, db_conn) -> bool:
    """Check if player has paid for tournament."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT 1 FROM tournament_payments WHERE tournament_id = %s AND player_id = %s AND status = 'paid'",
        (tournament_id, player_id),
    )
    return cur.fetchone() is not None


def get_registration_settings(tournament_id: str, db_conn) -> Dict[str, Any]:
    """Get registration settings for tournament. Returns dict with entry_fee_cents, payment_required, etc."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT entry_fee_cents, early_bird_fee_cents, early_bird_deadline, payment_required FROM tournament_registration_settings WHERE tournament_id = %s",
        (tournament_id,),
    )
    row = cur.fetchone()
    if not row:
        return {"entry_fee_cents": 0, "payment_required": 0}
    return {
        "entry_fee_cents": int(row[0] or 0),
        "early_bird_fee_cents": int(row[1]) if row[1] is not None else None,
        "early_bird_deadline": row[2],
        "payment_required": int(row[3] or 0),
    }


def upsert_registration_settings(
    tournament_id: str,
    entry_fee_cents: int = 0,
    payment_required: bool = False,
    db_conn=None,
) -> bool:
    """Create or update registration settings. Returns True on success."""
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO tournament_registration_settings (tournament_id, entry_fee_cents, payment_required)
        VALUES (%s, %s, %s)
        ON CONFLICT (tournament_id) DO UPDATE SET
            entry_fee_cents = EXCLUDED.entry_fee_cents,
            payment_required = EXCLUDED.payment_required
        """,
        (tournament_id, entry_fee_cents, 1 if payment_required else 0),
    )
    db_conn.commit()
    return True


def add_to_waitlist(tournament_id: str, player_id: str, db_conn) -> int:
    """Add player to waitlist. Returns position (1-based)."""
    cur = db_conn.cursor()
    cur.execute("SELECT 1 FROM tournament_waitlist WHERE tournament_id = %s AND player_id = %s", (tournament_id, player_id))
    if cur.fetchone():
        cur.execute(
            "SELECT position FROM tournament_waitlist WHERE tournament_id = %s AND player_id = %s",
            (tournament_id, player_id),
        )
        r = cur.fetchone()
        return int(r[0] if hasattr(r, "__getitem__") else r.get("position", 0))
    cur.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM tournament_waitlist WHERE tournament_id = %s", (tournament_id,))
    pos = int(cur.fetchone()[0])
    cur.execute("INSERT INTO tournament_waitlist (tournament_id, player_id, position) VALUES (%s, %s, %s)", (tournament_id, player_id, pos))
    db_conn.commit()
    return pos


def get_waitlist(tournament_id: str, db_conn) -> list:
    """Get waitlist for tournament. Returns list of {player_id, position}."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT player_id, position FROM tournament_waitlist WHERE tournament_id = %s ORDER BY position",
        (tournament_id,),
    )
    rows = cur.fetchall()
    return [dict(row) if hasattr(row, "keys") else {"player_id": row[0], "position": row[1]} for row in rows]


def get_waitlist_position(tournament_id: str, player_id: str, db_conn) -> Optional[int]:
    """Get player's waitlist position or None if not on waitlist."""
    cur = db_conn.cursor()
    cur.execute("SELECT position FROM tournament_waitlist WHERE tournament_id = %s AND player_id = %s", (tournament_id, player_id))
    row = cur.fetchone()
    if not row:
        return None
    return int(row[0] if hasattr(row, "__getitem__") else row.get("position"))
