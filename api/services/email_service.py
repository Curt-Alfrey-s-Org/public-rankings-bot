"""
Email notification service for AI Coach - SendGrid integration.
Sends analysis-ready and ranking-alert emails.
"""

import os
import logging
from pathlib import Path
from typing import TypedDict, Optional

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "user10@example.com")
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
EMAIL_DRY_RUN = os.getenv("EMAIL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")


class RankingChange(TypedDict, total=False):
    """Ranking change data for alert emails."""

    player_name: str
    old_rank: int
    new_rank: int
    movement: str  # e.g. "+2", "-1"
    points_change: Optional[float]
    division: Optional[str]
    association: Optional[str]


def _load_template(name: str, context: dict) -> str:
    """Load and render HTML template with context (simple {{ var }} substitution)."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    content = path.read_text(encoding="utf-8")
    for key, value in context.items():
        content = content.replace(f"{{{{ {key} }}}}", str(value))
        content = content.replace(f"{{{key}}}", str(value))
    return content


def _get_sendgrid_client():
    """Get SendGrid client. Returns None if API key not configured."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        api_key = os.getenv("SENDGRID_API_KEY")
        if not api_key:
            logger.warning("SENDGRID_API_KEY not configured")
            return None, Mail
        return SendGridAPIClient(api_key), Mail
    except ImportError as e:
        logger.warning(f"SendGrid not installed: {e}")
        return None, None


def send_analysis_ready(
    user_email: str,
    analysis_id: str,
    overall_score: Optional[float] = None,
) -> bool:
    """
    Send email when AI Coach analysis is ready.

    Args:
        user_email: Recipient email
        analysis_id: Analysis UUID
        overall_score: Overall coaching score (0-10) if available

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        client, Mail = _get_sendgrid_client()
        if client is None or Mail is None:
            if EMAIL_DRY_RUN:
                logger.info("[DRY-RUN] Would send analysis_ready to %s", user_email)
                return True
            logger.error("Email service unavailable for analysis_ready (set SENDGRID_API_KEY or EMAIL_DRY_RUN=1)")
            return False

        score_str = f"{overall_score:.1f}" if overall_score is not None else "N/A"
        context = {
            "user_email": user_email,
            "analysis_id": analysis_id,
            "overall_score": score_str,
            "dashboard_url": os.getenv("RANKINGS_BOT_URL", "https://rankings-bot.ai") + "/ai-coach",
        }
        html = _load_template("analysis_ready.html", context)

        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=user_email,
            subject="Your AI Pool Coach analysis is ready",
            html_content=html,
        )
        response = client.send(message)
        if response.status_code in (200, 201, 202):
            logger.info(f"Analysis ready email sent to {user_email}")
            return True
        logger.error(f"SendGrid error {response.status_code}: {response.body}")
        return False
    except Exception as e:
        logger.exception(f"Failed to send analysis_ready email: {e}")
        return False


def send_ranking_alert(
    user_email: str,
    ranking_change: RankingChange,
) -> bool:
    """
    Send email when a player's ranking changes.

    Args:
        user_email: Recipient email
        ranking_change: Dict with player_name, old_rank, new_rank, movement, etc.

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        client, Mail = _get_sendgrid_client()
        if client is None or Mail is None:
            if EMAIL_DRY_RUN:
                logger.info("[DRY-RUN] Would send ranking_alert to %s", user_email)
                return True
            logger.error("Email service unavailable for ranking_alert (set SENDGRID_API_KEY or EMAIL_DRY_RUN=1)")
            return False

        context = {
            "user_email": user_email,
            "player_name": ranking_change.get("player_name", "Player"),
            "old_rank": str(ranking_change.get("old_rank", "—")),
            "new_rank": str(ranking_change.get("new_rank", "—")),
            "movement": ranking_change.get("movement", ""),
            "points_change": str(ranking_change.get("points_change", "")),
            "division": ranking_change.get("division", ""),
            "association": ranking_change.get("association", ""),
            "rankings_url": os.getenv("RANKINGS_BOT_URL", "https://rankings-bot.ai") + "/rankings",
        }
        html = _load_template("ranking_alert.html", context)

        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=user_email,
            subject=f"Ranking update: {context['player_name']} - {context['movement']}",
            html_content=html,
        )
        response = client.send(message)
        if response.status_code in (200, 201, 202):
            logger.info(f"Ranking alert email sent to {user_email}")
            return True
        logger.error(f"SendGrid error {response.status_code}: {response.body}")
        return False
    except Exception as e:
        logger.exception(f"Failed to send ranking_alert email: {e}")
        return False


def send_payment_receipt(
    user_email: str,
    amount_cents: int,
    hours: int,
    user_id: Optional[str] = None,
) -> bool:
    """Send payment receipt email for successful hour-pack purchase."""
    try:
        client, Mail = _get_sendgrid_client()
        if client is None or Mail is None:
            if EMAIL_DRY_RUN:
                logger.info("[DRY-RUN] Would send payment_receipt to %s", user_email)
                return True
            logger.error("Email service unavailable for payment_receipt (set SENDGRID_API_KEY or EMAIL_DRY_RUN=1)")
            return False

        amount_usd = f"${amount_cents / 100:.2f}"
        dashboard_url = os.getenv("RANKINGS_BOT_URL", "https://rankings-bot.ai") + "/ai-coach"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:16px;">
          <h2 style="margin:0 0 12px 0;">Payment Received</h2>
          <p>Thank you for your purchase.</p>
          <ul>
            <li><strong>Amount:</strong> {amount_usd}</li>
            <li><strong>Hours added:</strong> {hours}</li>
            <li><strong>User:</strong> {user_id or "N/A"}</li>
          </ul>
          <p>Your AI Coach hours are now available in your account.</p>
          <p><a href="{dashboard_url}">Open AI Coach</a></p>
        </div>
        """.strip()
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=user_email,
            subject="Your Pro Billiards Software payment receipt",
            html_content=html,
        )
        response = client.send(message)
        if response.status_code in (200, 201, 202):
            logger.info("Payment receipt email sent to %s", user_email)
            return True
        logger.error("SendGrid error %s: %s", response.status_code, response.body)
        return False
    except Exception as e:
        logger.exception("Failed to send payment_receipt email: %s", e)
        return False


def render_template(name: str, context: dict) -> str:
    """
    Render a template with sample data (for testing).
    Does not send any email.
    """
    return _load_template(name, context)
