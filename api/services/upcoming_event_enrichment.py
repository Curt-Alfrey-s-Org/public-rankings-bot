"""
Enrich upcoming_events with hints from RSS news feeds (player counts, format changes).

Runs during admin refresh-upcoming only (manual-triggered). Hints are suggestions —
directors always edit values in the Tournament Wizard.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from api.services.news_feeds import fetch_all_feeds_sync

logger = logging.getLogger(__name__)

# Field sizes commonly announced in tour news (8–256).
_PLAYER_COUNT_PATTERNS = (
    re.compile(r"\b(\d{2,3})\s*[-]?\s*players?\b", re.I),
    re.compile(r"\bfield of (\d{2,3})\b", re.I),
    re.compile(r"\b(\d{2,3})\s*[-]?\s*player\s+(?:field|draw|bracket)\b", re.I),
    re.compile(r"\b(\d{2,3})\s*entrants?\b", re.I),
    re.compile(r"\bdraw (?:of|for|size)\s*(\d{2,3})\b", re.I),
    re.compile(r"\b(\d{2,3})\s*[-]?\s*player\b", re.I),
)

_FORMAT_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"double[- ]elim", re.I), "double"),
    (re.compile(r"single[- ]elim", re.I), "single"),
    (re.compile(r"round[- ]robin", re.I), "round_robin"),
    (re.compile(r"group stage", re.I), "group_stage"),
)

_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "at",
        "for",
        "to",
        "on",
        "with",
        "wpa",
        "wpba",
        "pool",
        "billiards",
        "championship",
        "championships",
        "open",
        "classic",
        "tournament",
        "event",
        "cup",
        "series",
        "world",
        "international",
        "2024",
        "2025",
        "2026",
        "2027",
    }
)


def _normalize_tokens(text: str) -> set[str]:
    raw = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return {t for t in raw.split() if len(t) >= 3 and t not in _STOP_WORDS}


def _match_score(event_name: str, article_title: str) -> float:
    event_tokens = _normalize_tokens(event_name)
    title_tokens = _normalize_tokens(article_title)
    if not event_tokens or not title_tokens:
        return 0.0
    overlap = len(event_tokens & title_tokens)
    if overlap == 0:
        return 0.0
    return overlap / max(len(event_tokens), 1)


def _valid_player_count(n: int) -> bool:
    return 8 <= n <= 256


def extract_player_count(text: str) -> Optional[int]:
    if not text:
        return None
    candidates: List[int] = []
    for pat in _PLAYER_COUNT_PATTERNS:
        for m in pat.finditer(text):
            try:
                val = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if _valid_player_count(val):
                candidates.append(val)
    if not candidates:
        return None
    # Prefer standard draw sizes when multiple matches.
    draw_sizes = {8, 16, 32, 48, 64, 80, 96, 128, 256}
    for c in candidates:
        if c in draw_sizes:
            return c
    return candidates[0]


def extract_elimination_type(text: str) -> Optional[str]:
    if not text:
        return None
    for pat, fmt in _FORMAT_PATTERNS:
        if pat.search(text):
            return fmt
    return None


def parse_format_field(format_str: Optional[str]) -> Dict[str, Any]:
    """Parse upcoming_events.format column (e.g. '64 Player Double Elimination')."""
    out: Dict[str, Any] = {}
    if not format_str:
        return out
    pc = extract_player_count(format_str)
    if pc:
        out["max_players"] = pc
    elim = extract_elimination_type(format_str)
    if elim:
        out["elimination_type"] = elim
    return out


def _hint(
    field: str,
    value: Any,
    source: str,
    source_url: str,
    article_title: str,
    confidence: float,
) -> Dict[str, Any]:
    return {
        "field": field,
        "value": value,
        "source": source,
        "source_url": source_url,
        "article_title": article_title,
        "confidence": round(confidence, 2),
    }


def enrich_event_from_text(
    event: Dict[str, Any],
    text: str,
    *,
    source: str,
    source_url: str,
    article_title: str,
    base_confidence: float,
) -> List[Dict[str, Any]]:
    hints: List[Dict[str, Any]] = []
    pc = extract_player_count(text)
    if pc:
        hints.append(
            _hint("max_players", pc, source, source_url, article_title, base_confidence)
        )
    elim = extract_elimination_type(text)
    if elim:
        hints.append(
            _hint("elimination_type", elim, source, source_url, article_title, base_confidence * 0.9)
        )
    return hints


def _merge_hints(existing: List[Dict[str, Any]], new_hints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_field: Dict[str, Dict[str, Any]] = {}
    for h in existing + new_hints:
        field = h.get("field")
        if not field:
            continue
        prev = by_field.get(field)
        if prev is None or (h.get("confidence") or 0) >= (prev.get("confidence") or 0):
            by_field[field] = h
    return list(by_field.values())


def enrich_upcoming_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Attach max_players + enrichment JSONB hints from RSS feeds and format fields.
    Mutates copies of event dicts.
    """
    if not events:
        return events

    articles: List[Dict[str, Any]] = []
    try:
        articles = fetch_all_feeds_sync()
    except Exception as e:
        logger.warning("News feed fetch for upcoming enrichment failed: %s", e)

    enriched: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for raw in events:
        event = dict(raw)
        hints: List[Dict[str, Any]] = []
        matched: List[Dict[str, str]] = []

        fmt_parsed = parse_format_field(event.get("format"))
        if fmt_parsed.get("max_players"):
            hints.append(
                _hint(
                    "max_players",
                    fmt_parsed["max_players"],
                    "calendar",
                    event.get("url") or "",
                    event.get("name") or "Event listing",
                    0.75,
                )
            )
        if fmt_parsed.get("elimination_type"):
            hints.append(
                _hint(
                    "elimination_type",
                    fmt_parsed["elimination_type"],
                    "calendar",
                    event.get("url") or "",
                    event.get("name") or "Event listing",
                    0.7,
                )
            )

        event_name = (event.get("name") or "").strip()
        for article in articles[:80]:
            title = (article.get("title") or "").strip()
            if not title or not event_name:
                continue
            score = _match_score(event_name, title)
            if score < 0.35:
                continue
            text = f"{title}. {article.get('summary') or ''}"
            article_hints = enrich_event_from_text(
                event,
                text,
                source=article.get("source") or "News",
                source_url=article.get("url") or "",
                article_title=title,
                base_confidence=min(0.95, 0.5 + score * 0.45),
            )
            if article_hints:
                hints.extend(article_hints)
                matched.append(
                    {
                        "title": title,
                        "url": article.get("url") or "",
                        "source": article.get("source") or "News",
                        "match_score": round(score, 2),
                    }
                )

        hints = _merge_hints([], hints)
        best_players = next((h for h in hints if h["field"] == "max_players"), None)
        if best_players:
            event["max_players"] = int(best_players["value"])

        event["enrichment"] = {
            "hints": hints,
            "matched_articles": matched[:5],
            "enriched_at": now_iso,
        }
        enriched.append(event)

    logger.info(
        "Upcoming event enrichment: %d events, %d RSS articles scanned",
        len(enriched),
        len(articles),
    )
    return enriched


def enrichment_to_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)
