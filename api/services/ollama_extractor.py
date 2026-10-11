"""
LLM-powered structured data extraction for scrapers.

Used as a fallback when regex-based parsing returns empty or partial results.
The LLM receives stripped text (HTML tags removed) and returns structured JSON
matching the expected schema.

Design:
- Never replaces regex parsing -- only called when regex yields nothing.
- Gracefully degrades: returns None if Ollama is unavailable.
- Accepts pre-stripped text to avoid sending raw HTML to the model.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from api.services.ollama_client import OllamaClient, get_ollama_client

logger = logging.getLogger(__name__)

_BRACKET_SYSTEM_PROMPT = """You are a data extraction expert for billiards/pool tournament results.
Given tournament page text, extract structured placement and match data.

Return ONLY valid JSON with this exact schema:
{
  "champion": "Full Name" or null,
  "runner_up": "Full Name" or null,
  "final_score": "9-7" or null,
  "placements": [
    {"place": 1, "player_name": "Full Name"},
    {"place": 2, "player_name": "Full Name"}
  ],
  "matches": [
    {
      "operator_name": "Full Name",
      "player2_name": "Full Name",
      "operator_score": 9,
      "player2_score": 7,
      "winner_name": "Full Name",
      "round_num": "Final"
    }
  ]
}

Rules:
- Extract only what is clearly stated in the text. Do not invent data.
- Player names should be full names as written (preserve original casing).
- If a field cannot be determined, use null.
- Placements list should include all finishers you can identify (1st, 2nd, 3rd, etc.).
- Match scores should be integers. If no score is visible, use null for both scores.
- round_num can be "Final", "Semi-Final", "Quarter-Final", "Round of 16", or "Bracket"."""


_PDF_RANKINGS_SYSTEM_PROMPT = """You are a data extraction expert for billiards/pool ranking documents.
Given raw text extracted from a PDF ranking document, extract player ranking data.

The expected columns are provided. Extract each player row as a JSON object.

Return ONLY a valid JSON array of objects. Each object should have keys matching
the expected columns. Example:
[
  {"rank": 1, "name": "Alice Smith", "points": 1200.5, "country": "USA"},
  {"rank": 2, "name": "Beth Jones", "points": 980.0, "country": "GBR"}
]

Rules:
- Extract only rows that clearly represent player rankings.
- Preserve original name spelling and casing.
- Convert rank and points to numbers. If a value is unclear, use null.
- Skip header rows, footnotes, and non-data text."""


async def extract_bracket_data(
    page_text: str,
    client: Optional[OllamaClient] = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract tournament bracket/result data from page text using LLM.

    Args:
        page_text: Plain text (HTML tags already stripped).
        client: Optional OllamaClient override.

    Returns:
        Dict with champion, runner_up, final_score, placements, matches.
        None if Ollama is unavailable or extraction fails.
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    truncated = page_text[:6000]
    prompt = f"Extract tournament results from this text:\n\n{truncated}"

    resp = await client.chat(
        messages=[
            {"role": "system", "content": _BRACKET_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=client.model_structured,
        temperature=0.05,
        format_json=True,
        feature="bracket_extraction",
    )

    if resp.error:
        logger.warning("Ollama bracket extraction failed: %s", resp.error)
        return None

    try:
        data = json.loads(resp.content)
        result: Dict[str, Any] = {
            "champion": data.get("champion"),
            "runner_up": data.get("runner_up"),
            "final_score": data.get("final_score"),
            "placements": data.get("placements", []),
            "matches": data.get("matches", []),
        }
        if not result["champion"] and not result["placements"]:
            logger.debug("LLM bracket extraction returned no usable data")
            return None
        logger.info(
            "LLM extracted bracket data: champion=%s, placements=%d, matches=%d",
            result["champion"],
            len(result["placements"]),
            len(result["matches"]),
        )
        return result
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(
            "Could not parse LLM bracket extraction: %s (raw: %s)",
            e,
            resp.content[:200],
        )
        return None


async def extract_pdf_rankings(
    raw_text: str,
    expected_columns: List[str],
    client: Optional[OllamaClient] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Extract ranking rows from messy PDF text using LLM.

    Args:
        raw_text: Raw text from pdfplumber or similar.
        expected_columns: List of expected column names (e.g. ["rank", "name", "points", "country"]).
        client: Optional OllamaClient override.

    Returns:
        List of dicts per player row, or None if unavailable.
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    truncated = raw_text[:8000]
    columns_str = ", ".join(expected_columns)
    prompt = f"Expected columns: {columns_str}\n\nExtract player rankings from this PDF text:\n\n{truncated}"

    resp = await client.chat(
        messages=[
            {"role": "system", "content": _PDF_RANKINGS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=client.model_structured,
        temperature=0.05,
        format_json=True,
        feature="pdf_extraction",
    )

    if resp.error:
        logger.warning("Ollama PDF extraction failed: %s", resp.error)
        return None

    try:
        data = json.loads(resp.content)
        if isinstance(data, list) and len(data) > 0:
            logger.info("LLM extracted %d ranking rows from PDF text", len(data))
            return data
        logger.debug("LLM PDF extraction returned empty list")
        return None
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(
            "Could not parse LLM PDF extraction: %s (raw: %s)",
            e,
            resp.content[:200],
        )
        return None
