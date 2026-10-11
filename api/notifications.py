"""
Ranking change email notifications.
Players subscribe with email + player name; we notify when that player's ranking changes.
Uses SMTP if configured (env); otherwise logs only.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
import asyncio
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Live update connections with user context
active_connections: List[Dict[str, Any]] = []


def _get_smtp_config():
    """Return (host, port, user, password, from_addr) or None if not configured."""
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_addr = os.getenv("SMTP_FROM", user or "rankings@localhost").strip()
    return (host, port, user, password, from_addr)


def send_email(to: str, subject: str, body_text: str) -> bool:
    """Send email. Returns True if sent, False if skipped (no SMTP) or failed."""
    cfg = _get_smtp_config()
    if not cfg:
        logger.info("[NOTIFY] No SMTP configured; would send to %s: %s", to, subject)
        return False
    host, port, user, password, from_addr = cfg
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.attach(MIMEText(body_text, "plain"))
        with smtplib.SMTP(host, port) as server:
            if port == 587:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("[NOTIFY] Sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.warning("[NOTIFY] Failed to send to %s: %s", to, e)
        return False


async def broadcast_live_update(
    event_type: str,
    data: Dict[str, Any],
    required_roles: Optional[List[str]] = None,
    required_permissions: Optional[List[str]] = None,
    payment_features: Optional[List[str]] = None
):
    """
    Broadcast live update to connected WebSocket clients with role/permission filtering

    Args:
        event_type: Type of update (e.g., 'tournament_score_updated', 'ranking_changed')
        data: Update data payload
        required_roles: List of roles that can receive this update (None = all roles)
        required_permissions: List of specific permissions required
        payment_features: List of payment features required to see this update
    """
    message = {
        "type": "live_update",
        "event": event_type,
        "data": data,
        "timestamp": str(asyncio.get_event_loop().time())
    }

    disconnected = []
    sent_count = 0

    for connection_info in active_connections:
        websocket = connection_info["websocket"]
        user_info = connection_info.get("user_info", {})

        # Check role-based access
        if required_roles:
            user_role = user_info.get("role")
            if not user_role or user_role not in required_roles:
                continue

        # Check permission-based access
        if required_permissions:
            user_permissions = user_info.get("permissions", [])
            if not any(perm in user_permissions for perm in required_permissions):
                continue

        # Check payment feature access
        if payment_features:
            user_features = user_info.get("payment_features", [])
            if not any(feature in user_features for feature in payment_features):
                continue

        try:
            await websocket.send_json(message)
            sent_count += 1
        except Exception as e:
            logger.warning("Failed to send live update to client: %s", e)
            disconnected.append(connection_info)

    # Remove disconnected clients
    for conn_info in disconnected:
        if conn_info in active_connections:
            active_connections.remove(conn_info)

    logger.info("Broadcasted %s update to %d clients (filtered from %d total)",
                event_type, sent_count, len(active_connections) + len(disconnected))


# Specific broadcast functions for different data types

async def broadcast_tournament_update(tournament_id: str, update_type: str, data: Dict[str, Any]):
    """
    Broadcast tournament-related updates (scores, status changes, etc.)
    Available to users, directors, and admins
    """
    await broadcast_live_update(
        f"tournament_{update_type}",
        {"tournament_id": tournament_id, **data},
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_ranking_update(player_name: str, ranking_system: str, data: Dict[str, Any]):
    """
    Broadcast ranking changes
    Available to all authenticated users
    """
    await broadcast_live_update(
        "ranking_updated",
        {"player_name": player_name, "ranking_system": ranking_system, **data},
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_cache_invalidation(reason: str, details: Optional[Dict[str, Any]] = None):
    """
    Broadcast cache invalidation event to all connected clients
    Forces UI to refresh cached data after database updates

    Args:
        reason: Description of what caused the cache invalidation
        details: Optional additional details about the update
    """
    data = {
        "reason": reason,
        "timestamp": str(asyncio.get_event_loop().time())
    }
    if details:
        data.update(details)

    await broadcast_live_update(
        "cache_invalidated",
        data,
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_tournament_created(tournament_data: Dict[str, Any]):
    """
    Broadcast new tournament creation
    Available to all users
    """
    await broadcast_live_update(
        "tournament_created",
        tournament_data,
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_player_registration(tournament_id: str, player_name: str, action: str):
    """
    Broadcast player registration/unregistration updates
    Available to directors and admins for the tournament
    """
    await broadcast_live_update(
        f"player_{action}",
        {"tournament_id": tournament_id, "player_name": player_name},
        required_roles=["director", "admin", "super_admin"]
    )


async def broadcast_match_score_update(match_id: str, tournament_id: str, score_data: Dict[str, Any]):
    """
    Broadcast match score updates
    Available to all users (but could be restricted based on tournament settings)
    """
    await broadcast_live_update(
        "match_score_updated",
        {"match_id": match_id, "tournament_id": tournament_id, **score_data},
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_rack_completed(match_id: str, tournament_id: str, rack_data: Dict[str, Any]):
    """
    Broadcast rack/game completion events for live Est. rating updates
    Available to all users for real-time tournament viewing
    """
    await broadcast_live_update(
        "rack_completed",
        {
            "match_id": match_id,
            "tournament_id": tournament_id,
            "event_type": "rack_completed",
            **rack_data
        },
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def broadcast_rating_updated(player_id: str, rating_data: Dict[str, Any]):
    """
    Broadcast rating update events when player ratings change
    Available to all users for real-time rating tracking
    """
    await broadcast_live_update(
        "rating_updated",
        {
            "player_id": player_id,
            "event_type": "rating_updated",
            **rating_data
        },
        required_roles=["user", "director", "admin", "super_admin"]
    )


async def connect_live_updates(websocket: WebSocket, user_info: Optional[Dict[str, Any]] = None):
    """
    Connect a WebSocket client for live updates with user context

    Args:
        websocket: WebSocket connection
        user_info: User authentication context including role, permissions, payment features
    """
    logger.info("connect_live_updates called with user_info: %s", user_info)
    await websocket.accept()
    logger.info("WebSocket accepted")

    # Default user info if not provided
    if user_info is None:
        user_info = {"role": "user", "permissions": [], "payment_features": []}

    connection_info = {
        "websocket": websocket,
        "user_info": user_info,
        "connected_at": asyncio.get_event_loop().time()
    }

    active_connections.append(connection_info)
    logger.info("Client connected for live updates. User: %s, Role: %s. Total connections: %d",
                user_info.get("username", "anonymous"),
                user_info.get("role", "unknown"),
                len(active_connections))

    try:
        while True:
            # Keep connection alive and listen for client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle client messages if needed (e.g., ping/pong, subscription updates)
                logger.debug("Received message from client: %s", data[:100])
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": str(asyncio.get_event_loop().time())})
                except Exception:
                    break
    except Exception as e:
        logger.info("Client disconnected from live updates: %s", e)
    finally:
        # Remove this connection from active connections
        if connection_info in active_connections:
            active_connections.remove(connection_info)
        logger.info("Client disconnected. Remaining connections: %d", len(active_connections))


def process_ranking_change_notifications(db_manager, base_url: str = ""):
    """
    Find recent ranking changes, get subscribers for those players, and send notification emails.
    base_url: base URL for unsubscribe link (e.g. https://yoursite.com or http://localhost:5174).
    """
    base_url = (base_url or os.getenv("NOTIFY_UNSUBSCRIBE_BASE_URL", "http://localhost:5174")).rstrip("/")
    pairs = db_manager.get_recent_change_player_systems(limit=100)
    sent = 0
    for (player_name, system) in pairs:
        subs = db_manager.get_subscriptions_for_player_system(player_name, system)
        if not subs:
            continue
        # Get latest change for this player/system for the email body
        movement = db_manager.get_movement(system, limit=50)
        change = next((m for m in movement if m["player_name"] == player_name), None)
        if not change:
            continue
        old_r, new_r = change.get("old_rank"), change.get("new_rank")
        old_p, new_p = change.get("old_points"), change.get("new_points")
        change_type = change.get("change_type", "change")
        change_date = change.get("change_date", "")
        subject = f"Ranking update: {player_name} ({system})"
        body_lines = [
            f"Hi,",
            f"",
            f"There was a ranking change for {player_name} ({system}):",
            f"  Change: {change_type}",
            f"  Date: {change_date}",
        ]
        if old_r is not None and new_r is not None:
            body_lines.append(f"  Rank: #{old_r} → #{new_r}")
        if old_p is not None and new_p is not None:
            body_lines.append(f"  Points: {old_p} → {new_p}")
        body_lines.extend(["", "You received this because you signed up for ranking change notifications.", ""])
        for sub in subs:
            unsub_url = f"{base_url.rstrip('/')}/api/rankings/notify-unsubscribe?token={sub['unsubscribe_token']}"
            body_lines.append(f"To unsubscribe: {unsub_url}")
            body = "\n".join(body_lines)
            if send_email(sub["email"], subject, body):
                sent += 1
    if sent:
        logger.info("[NOTIFY] Sent %d ranking change notification(s)", sent)
    return sent


def post_refresh_webhook(results: dict) -> bool:
    """POST refresh summary to WEBHOOK_URL if set. Returns True if sent."""
    url = os.getenv("WEBHOOK_URL", "").strip()
    if not url:
        return False
    try:
        import requests
        r = requests.post(url, json=results, timeout=10)
        if r.ok:
            logger.info("[WEBHOOK] Posted refresh summary to %s", url)
            return True
        logger.warning("[WEBHOOK] %s returned %s", url, r.status_code)
        return False
    except Exception as e:
        logger.warning("[WEBHOOK] Failed to post to %s: %s", url, e)
        return False
