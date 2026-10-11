"""
Tournament event broadcast for SSE stream.
Events: match_score_update, match_completed, rack_completed, player_advanced, tournament_progress.
Thread-safe: emit from sync (update_match_score), consume from async stream.
"""

import logging
import threading
from collections import deque
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

_MAX_EVENTS = 100
_queues: Dict[str, deque] = {}
_lock = threading.Lock()


def emit(tournament_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    """Emit event from sync context (e.g. update_match_score)."""
    with _lock:
        if tournament_id not in _queues:
            _queues[tournament_id] = deque(maxlen=_MAX_EVENTS)
        _queues[tournament_id].append({"type": event_type, **payload})


def get_events_since(tournament_id: str, last_index: int = 0) -> List[Dict]:
    """Get events for tournament since last_index (for SSE stream)."""
    with _lock:
        if tournament_id not in _queues:
            return []
        items = list(_queues[tournament_id])
    return items[last_index:]
