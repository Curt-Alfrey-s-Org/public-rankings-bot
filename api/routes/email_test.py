"""
Email test endpoint - verify SendGrid integration and template rendering.
"""

from fastapi import APIRouter, HTTPException
from api.services.email_service import (
    send_analysis_ready,
    send_ranking_alert,
    render_template,
    RankingChange,
)

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/test-send")
async def test_send():
    """
    Test email sending. Sends to a placeholder unless SENDGRID_TEST_EMAIL is set.
    Mocks SendGrid in tests - this endpoint is for manual verification.
    """
    import os

    test_email = os.getenv("SENDGRID_TEST_EMAIL", "test@example.com")

    # Test 1: analysis_ready
    ok1 = send_analysis_ready(
        user_email=test_email,
        analysis_id="test-anl-123",
        overall_score=7.8,
    )

    # Test 2: ranking_alert
    ranking_change: RankingChange = {
        "player_name": "Test Player",
        "old_rank": 5,
        "new_rank": 3,
        "movement": "+2",
        "points_change": 12.5,
        "division": "Women",
        "association": "WPBA",
    }
    ok2 = send_ranking_alert(user_email=test_email, ranking_change=ranking_change)

    return {
        "status": "ok" if (ok1 and ok2) else "partial",
        "analysis_ready": ok1,
        "ranking_alert": ok2,
        "test_email": test_email,
    }


@router.get("/test-render")
async def test_render():
    """
    Render templates with sample data. Does not send any email.
    Useful for verifying template structure.
    """
    analysis_html = render_template(
        "analysis_ready.html",
        {
            "user_email": "test@example.com",
            "analysis_id": "sample-anl-456",
            "overall_score": "8.2",
            "dashboard_url": "https://rankings-bot.ai/ai-coach",
        },
    )
    ranking_html = render_template(
        "ranking_alert.html",
        {
            "user_email": "test@example.com",
            "player_name": "Sample Player",
            "old_rank": "5",
            "new_rank": "3",
            "movement": "+2",
            "points_change": "12.5",
            "division": "Women",
            "association": "WPBA",
            "rankings_url": "https://rankings-bot.ai/rankings",
        },
    )
    return {
        "analysis_ready_length": len(analysis_html),
        "ranking_alert_length": len(ranking_html),
        "analysis_ready_preview": analysis_html[:500] + "..." if len(analysis_html) > 500 else analysis_html,
        "ranking_alert_preview": ranking_html[:500] + "..." if len(ranking_html) > 500 else ranking_html,
    }
