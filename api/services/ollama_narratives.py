"""
LLM-powered narrative generation for player performance and matchup summaries.

Receives structured JSON data (ratings, history, head-to-head stats) and
generates 2-3 sentence human-readable summaries via Ollama.

Design:
- Gracefully degrades: returns None if Ollama is unavailable.
- Narratives are designed to be cached by callers (regenerate on data change).
"""

import json
import logging
from typing import Any, Dict, Optional

from api.services.ollama_client import OllamaClient, get_ollama_client

logger = logging.getLogger(__name__)

_PLAYER_NARRATIVE_SYSTEM = """You turn structured billiards player JSON into a short factual summary for players.
Rules:
- Use ONLY fields and values present in the JSON. Do not invent trends (e.g. do not say "rising", "climbing", "momentum", or "drop" unless the JSON explicitly includes prior values or deltas).
- No sports-broadcast tone, hype, metaphors, or opinions. Plain language only.
- State numbers and dates as given (rank, points, Fargo, country, snapshot dates). Omit null/empty fields.
- At most 3 short sentences. No bullet characters or headers.
Return ONLY the summary text, nothing else."""

_MATCHUP_NARRATIVE_SYSTEM = """You turn structured JSON about two billiards players into a short factual matchup note.
Rules:
- Use ONLY fields in the JSON (names, ratings, match counts, win counts, listed probabilities). No hype or "edge" language unless the JSON contains a numeric probability you can quote.
- No broadcast or storytelling tone. Plain facts only.
- At most 3 short sentences. No bullet characters or headers.
Return ONLY the text, nothing else."""

_TOURNAMENT_HISTORY_NARRATIVE_SYSTEM = """You turn structured JSON about one player's tournament history into a short factual summary.
Rules:
- Use ONLY fields in the JSON (player name, placements, tournament names, dates, associations, statistics). Do not invent events or results not listed.
- Mention trends only if the data supports them (e.g. counts of wins, recent finishes from the listed tournaments).
- No hype or broadcast tone. Plain language only.
- At most 3 short sentences. No bullet characters or headers.
Return ONLY the summary text, nothing else."""


async def generate_player_narrative(
    player_data: Dict[str, Any],
    client: Optional[OllamaClient] = None,
) -> Optional[str]:
    """
    Generate a natural-language summary for a player's performance data.

    Args:
        player_data: Dict with keys like player_name, rank, points, fargo_rating,
                     alfa_rating, recent_tournaments, rank_change, etc.
        client: Optional OllamaClient override.

    Returns:
        Narrative string, or None if unavailable.
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    try:
        data_str = json.dumps(player_data, default=str)[:4000]
    except (TypeError, ValueError):
        data_str = str(player_data)[:4000]

    resp = await client.chat(
        messages=[
            {"role": "system", "content": _PLAYER_NARRATIVE_SYSTEM},
            {"role": "user", "content": f"Write a player summary from this data:\n{data_str}"},
        ],
        model=client.model_chat,
        temperature=0.15,
        feature="player_narrative",
        log_metadata={"trust_zone": "app_authenticated"},
    )

    if resp.error:
        logger.warning("Ollama player narrative failed: %s", resp.error)
        return None

    narrative = resp.content.strip()
    if not narrative:
        return None

    logger.info(
        "Generated player narrative (%d chars, %.1fs)",
        len(narrative),
        resp.duration_seconds,
    )
    return narrative


async def generate_matchup_narrative(
    h2h_data: Dict[str, Any],
    client: Optional[OllamaClient] = None,
) -> Optional[str]:
    """
    Generate a natural-language matchup preview for two players.

    Args:
        h2h_data: Dict with keys like operator_name, player2_name, operator_rating,
                  player2_rating, head_to_head_record, recent_form, etc.
        client: Optional OllamaClient override.

    Returns:
        Narrative string, or None if unavailable.
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    try:
        data_str = json.dumps(h2h_data, default=str)[:4000]
    except (TypeError, ValueError):
        data_str = str(h2h_data)[:4000]

    resp = await client.chat(
        messages=[
            {"role": "system", "content": _MATCHUP_NARRATIVE_SYSTEM},
            {"role": "user", "content": f"Write a matchup preview from this data:\n{data_str}"},
        ],
        model=client.model_chat,
        temperature=0.15,
        feature="matchup_narrative",
        log_metadata={"trust_zone": "app_authenticated"},
    )

    if resp.error:
        logger.warning("Ollama matchup narrative failed: %s", resp.error)
        return None

    narrative = resp.content.strip()
    if not narrative:
        return None

    logger.info(
        "Generated matchup narrative (%d chars, %.1fs)",
        len(narrative),
        resp.duration_seconds,
    )
    return narrative


async def generate_tournament_history_narrative(
    tournaments_payload: Dict[str, Any],
    client: Optional[OllamaClient] = None,
) -> Optional[str]:
    """
    Summarize a player's tournament arc from structured history + statistics.

    Args:
        tournaments_payload: player_name, statistics, tournament_results (list, may be truncated).

    Returns:
        Narrative string, or None if unavailable.
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    try:
        data_str = json.dumps(tournaments_payload, default=str)[:4000]
    except (TypeError, ValueError):
        data_str = str(tournaments_payload)[:4000]

    resp = await client.chat(
        messages=[
            {"role": "system", "content": _TOURNAMENT_HISTORY_NARRATIVE_SYSTEM},
            {"role": "user", "content": f"Write a tournament history summary from this data:\n{data_str}"},
        ],
        model=client.model_chat,
        temperature=0.15,
        feature="tournament_history_narrative",
        log_metadata={"trust_zone": "app_authenticated"},
    )

    if resp.error:
        logger.warning("Ollama tournament history narrative failed: %s", resp.error)
        return None

    narrative = resp.content.strip()
    if not narrative:
        return None

    logger.info(
        "Generated tournament history narrative (%d chars, %.1fs)",
        len(narrative),
        resp.duration_seconds,
    )
    return narrative
