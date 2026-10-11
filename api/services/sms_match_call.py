"""
Match call SMS service (Twilio or AWS SNS).
Sends "Your match is up — Opponent: X, Table: N, Race to: R" to players.
Config: MATCH_REMINDER_SMS_ENABLED, TWILIO_* or AWS_SNS_*.
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

MATCH_REMINDER_SMS_ENABLED = os.getenv("MATCH_REMINDER_SMS_ENABLED", "false").lower() in ("1", "true", "yes")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
AWS_SNS_TOPIC_ARN = os.getenv("AWS_SNS_TOPIC_ARN", "").strip()
AWS_REGION = os.getenv("AWS_REGION", "us-east-1").strip()


def _build_message(opponent_name: str, table_number: Optional[int], race_to: int) -> str:
    parts = [f"Your match is up. Opponent: {opponent_name}"]
    if table_number is not None:
        parts.append(f"Table: {table_number}")
    parts.append(f"Race to: {race_to}")
    return " — ".join(parts)


def _send_twilio(to_phone: str, body: str) -> bool:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        return False
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(to=to_phone, from_=TWILIO_FROM_NUMBER, body=body)
        return True
    except Exception as e:
        logger.warning("Twilio SMS failed: %s", e)
        return False


def _send_sns(to_phone: str, body: str) -> bool:
    """Send SMS via AWS SNS. Uses PhoneNumber for direct SMS."""
    try:
        import boto3
        sns = boto3.client("sns", region_name=AWS_REGION or "us-east-1")
        sns.publish(PhoneNumber=to_phone, Message=body)
        return True
    except Exception as e:
        logger.warning("SNS SMS failed: %s", e)
        return False


def send_match_call_sms(
    player_phone: str,
    opponent_name: str,
    table_number: Optional[int] = None,
    race_to: int = 7,
) -> bool:
    """
    Send match call SMS to a player. Uses Twilio if configured, else SNS.
    Returns True if sent successfully.
    """
    if not MATCH_REMINDER_SMS_ENABLED or not player_phone or not player_phone.strip():
        return False
    phone = player_phone.strip()
    if not phone.startswith("+") and len(phone) == 10:
        phone = "+1" + phone
    elif not phone.startswith("+"):
        phone = "+" + phone
    body = _build_message(opponent_name, table_number, race_to)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
        return _send_twilio(phone, body)
    if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE"):
        return _send_sns(phone, body)
    return False


def notify_match_players(
    p1_phone: Optional[str],
    p2_phone: Optional[str],
    p1_name: str,
    p2_name: str,
    table_number: Optional[int] = None,
    race_to: int = 7,
) -> List[str]:
    """
    Send match call SMS to both players. Returns list of player_ids or names that were sent to.
    """
    sent = []
    if p1_phone and send_match_call_sms(p1_phone, p2_name, table_number, race_to):
        sent.append("operator")
    if p2_phone and send_match_call_sms(p2_phone, p1_name, table_number, race_to):
        sent.append("player2")
    return sent
