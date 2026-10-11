"""
LLM-powered name resolution for ambiguous player name matches.

Used as a second-pass arbiter when deterministic matching (SequenceMatcher)
returns an ambiguous score (0.60-0.84). The LLM receives both names plus
context (country, ranking system, approximate rank) and returns a structured
confidence judgment.

Design:
- Never replaces deterministic matching -- only called for the ambiguous zone.
- Gracefully degrades: if Ollama is down, returns None so callers fall back
  to their existing threshold logic.
- Batch-friendly for scraper runs.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from api.services.ollama_client import OllamaClient, get_ollama_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a data-matching expert for professional billiards/pool player databases.
Your task: determine whether two name strings refer to the same real person.

Consider:
- International name ordering (family name first vs given name first)
- Transliteration variants (Arabic, Chinese, Thai, Filipino names)
- Hyphenated vs space-separated compound surnames
- Nicknames, initials, and abbreviations (e.g. "R. Amit" vs "Rubilen Amit")
- Common misspellings in sports databases
- The provided context (country, ranking system) as supporting evidence

Respond with ONLY valid JSON:
{"same_person": true or false, "confidence": 0.0 to 1.0, "reasoning": "brief explanation"}"""


@dataclass
class NameMatchResult:
    """Result of an LLM-assisted name comparison."""

    same_person: bool
    confidence: float
    reasoning: str
    model: str = ""
    error: Optional[str] = None

    @property
    def is_confident_match(self) -> bool:
        return self.same_person and self.confidence >= 0.8

    @property
    def is_confident_mismatch(self) -> bool:
        return not self.same_person and self.confidence >= 0.8


def _build_comparison_prompt(
    name_a: str, name_b: str, context: Optional[Dict[str, Any]] = None
) -> str:
    ctx_parts = []
    if context:
        if context.get("country_a") or context.get("country_b"):
            ctx_parts.append(
                f"Countries: {context.get('country_a', '?')} / {context.get('country_b', '?')}"
            )
        if context.get("system_a") or context.get("system_b"):
            ctx_parts.append(
                f"Ranking systems: {context.get('system_a', '?')} / {context.get('system_b', '?')}"
            )
        if context.get("rank_a") or context.get("rank_b"):
            ctx_parts.append(
                f"Approximate ranks: #{context.get('rank_a', '?')} / #{context.get('rank_b', '?')}"
            )

    ctx_str = "\n".join(ctx_parts) if ctx_parts else "No additional context."
    return f'Name A: "{name_a}"\nName B: "{name_b}"\nContext:\n{ctx_str}\n\nAre these the same person?'


async def resolve_name_match(
    name_a: str,
    name_b: str,
    context: Optional[Dict[str, Any]] = None,
    client: Optional[OllamaClient] = None,
) -> Optional[NameMatchResult]:
    """
    Ask the LLM whether two names refer to the same person.

    Returns None if Ollama is unavailable (caller should use existing logic).
    """
    client = client or get_ollama_client()
    if client is None:
        return None

    prompt = _build_comparison_prompt(name_a, name_b, context)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    resp = await client.chat(
        messages=messages,
        model=client.model_structured,
        temperature=0.05,
        format_json=True,
        feature="name_resolution",
    )

    if resp.error:
        logger.warning(
            "Ollama name resolution failed for '%s' vs '%s': %s",
            name_a,
            name_b,
            resp.error,
        )
        return None

    try:
        data = json.loads(resp.content)
        return NameMatchResult(
            same_person=bool(data.get("same_person", False)),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")),
            model=resp.model,
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(
            "Could not parse Ollama name resolution response: %s (raw: %s)",
            e,
            resp.content[:200],
        )
        return None


async def resolve_batch(
    pairs: List[Tuple[str, str, Optional[Dict[str, Any]]]],
    client: Optional[OllamaClient] = None,
) -> List[Optional[NameMatchResult]]:
    """
    Resolve a batch of name pairs sequentially.

    Each element is (name_a, name_b, context_dict_or_None).
    Returns a list of results in the same order (None for failed lookups).
    """
    client = client or get_ollama_client()
    if client is None:
        return [None] * len(pairs)

    results: List[Optional[NameMatchResult]] = []
    for name_a, name_b, ctx in pairs:
        result = await resolve_name_match(name_a, name_b, ctx, client=client)
        results.append(result)
    return results
