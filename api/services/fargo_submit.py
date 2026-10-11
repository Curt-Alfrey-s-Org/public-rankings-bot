"""
Fargo Rate - Submit tournament results.
Collects completed matches and POSTs to FARGO_SUBMIT_URL when configured.
Format: Fargo-compatible JSON (player names, scores, race_to, match_id).
"""

import os
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

FARGO_SUBMIT_URL = os.getenv("FARGO_SUBMIT_URL", "").strip()
FARGO_SUBMIT_ENABLED = os.getenv("FARGO_SUBMIT_ENABLED", "false").lower() == "true"


def _get_httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        return None


def collect_tournament_results(tournament_id: str, matches: List[Dict], players_by_id: Dict[str, Dict]) -> List[Dict]:
    """
    Build Fargo-compatible match payloads from completed matches.
    Returns list of {operator_name, player2_name, operator_score, player2_score, race_to, match_id}.
    """
    results = []
    for m in matches:
        if m.get("status") != "completed" or not m.get("winner_id"):
            continue
        p1_id = m.get("operator_id")
        p2_id = m.get("player2_id")
        if not p1_id or not p2_id:
            continue
        p1 = players_by_id.get(p1_id, {})
        p2 = players_by_id.get(p2_id, {})
        p1_name = p1.get("first_name", "") + " " + p1.get("last_name", "")
        p2_name = p2.get("first_name", "") + " " + p2.get("last_name", "")
        if not p1_name.strip() or not p2_name.strip():
            p1_name = p1_name or m.get("operator_name", "")
            p2_name = p2_name or m.get("player2_name", "")
        results.append({
            "match_id": m.get("match_id"),
            "operator_name": p1_name.strip(),
            "player2_name": p2_name.strip(),
            "operator_score": int(m.get("operator_score") or 0),
            "player2_score": int(m.get("player2_score") or 0),
            "race_to": int(m.get("race_to") or 7),
            "winner_id": m.get("winner_id"),
        })
    return results


def submit_to_fargo(tournament_id: str, tournament_name: str, results: List[Dict]) -> Dict[str, Any]:
    """
    POST tournament results to Fargo Rate API (FARGO_SUBMIT_URL).
    Returns {success, submitted, error}.
    """
    if not FARGO_SUBMIT_URL or not FARGO_SUBMIT_ENABLED:
        return {"success": False, "submitted": 0, "error": "Fargo submit not configured (FARGO_SUBMIT_URL, FARGO_SUBMIT_ENABLED)"}
    httpx = _get_httpx()
    if not httpx:
        return {"success": False, "submitted": 0, "error": "httpx not installed"}
    payload = {
        "tournament_id": tournament_id,
        "tournament_name": tournament_name,
        "matches": [
            {
                "match_id": r["match_id"],
                "operator_name": r["operator_name"],
                "player2_name": r["player2_name"],
                "operator_score": r["operator_score"],
                "player2_score": r["player2_score"],
                "race_to": r["race_to"],
            }
            for r in results
        ],
    }
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(FARGO_SUBMIT_URL, json=payload)
            if resp.status_code >= 200 and resp.status_code < 300:
                logger.info("Fargo submit success: %s, %d matches", tournament_id, len(results))
                return {"success": True, "submitted": len(results), "error": None}
            return {
                "success": False,
                "submitted": 0,
                "error": f"Fargo API returned {resp.status_code}: {resp.text[:200]}",
            }
    except Exception as e:
        logger.exception("Fargo submit failed: %s", e)
        return {"success": False, "submitted": 0, "error": str(e)}
