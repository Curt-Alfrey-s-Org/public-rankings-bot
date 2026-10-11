"""
In-process cache for player overview narratives: skip Ollama and activity logging when
ranking/overview data is unchanged since the last successful generation.

Uses a SHA-256 of the JSON-serialized overview payload (excluding narrative fields).
Per-process only; multiple API workers each keep their own cache (acceptable tradeoff).
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Dict, Tuple

_MAX_ENTRIES = 2000
_lock = threading.Lock()
# cache_key -> (data_hash, last_narrative_text). On unchanged data, API returns this text with narrative_unchanged=true.
_cache: OrderedDict[str, Tuple[str, str]] = OrderedDict()

NARRATIVE_UNCHANGED_MESSAGE = "No changes to report since the last summary."


def narrative_cache_key(canonical_player_name: str) -> str:
    return (canonical_player_name or "").strip().lower()


def h2h_narrative_cache_key(player_id: str, opponent_id: str) -> str:
    """Stable key for a pair of players (order-independent). IDs are URL player names."""
    a, b = sorted([(player_id or "").strip().lower(), (opponent_id or "").strip().lower()])
    return f"h2h:{a}|{b}"


def tournament_history_narrative_cache_key(player_name: str) -> str:
    return f"thist:{(player_name or '').strip().lower()}"


def hash_overview_payload(result: Dict[str, Any]) -> str:
    """Stable hash of everything sent to the narrative model (no narrative fields)."""
    payload = {k: v for k, v in result.items() if k not in ("narrative", "narrative_unchanged")}
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lookup_unchanged(player_key: str, data_hash: str) -> bool:
    """True if we already have a narrative for this cache key at this exact data hash."""
    return get_cached_narrative(player_key, data_hash) is not None


def get_cached_narrative(cache_key: str, data_hash: str) -> str | None:
    """Return stored narrative text when cache has this key and hash; else None."""
    with _lock:
        ent = _cache.get(cache_key)
        if not ent:
            return None
        old_hash, text = ent
        if old_hash != data_hash:
            return None
        t = (text or "").strip()
        return t if t else None


def remember_narrative(player_key: str, data_hash: str, narrative: str) -> None:
    """Store after a successful Ollama call."""
    if not narrative or not narrative.strip():
        return
    with _lock:
        _cache[player_key] = (data_hash, narrative.strip())
        _cache.move_to_end(player_key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)


def invalidate_player(player_key: str) -> None:
    """Optional: drop cache for one player (e.g. after admin edit)."""
    with _lock:
        _cache.pop(player_key, None)
