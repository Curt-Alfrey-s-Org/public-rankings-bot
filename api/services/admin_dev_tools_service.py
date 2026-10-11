"""
Super-admin AI dev tools: Grok-backed analysis and safe read-only rankings queries.

Ollama remains the default for in-app lightweight tasks (name match, narratives).
Grok (XAI_API_KEY) is used here for heavier reasoning; no automatic code apply.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from api.services.ci_failure_suggestion import (
    DOCS_ASSIST_SYSTEM,
    build_ci_failure_user_message,
    call_xai_chat_sync,
    parse_rankings_assist_json,
)
from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)

ALLOWED_RANKING_SYSTEMS = frozenset(
    {
        "WPBA_Women",
        "WPA_Men",
        "WPA_Women",
        "WPA_Heyball_Men",
        "WPA_Heyball_Women",
        "WPBA",
        "WPA",
        "FARGO",
    }
)

DOCS_ALLOWLIST = (
    "INDEX.md",
    "ENV_VARS.md",
    "PRODUCTION_DEPLOYMENT.md",
    "START_STOP_RESTART.md",
    "OLLAMA_AND_AI_MONITOR.md",
)


class RankingsAssistFilters(BaseModel):
    ranking_system: Optional[str] = None
    name_contains: Optional[str] = Field(None, max_length=120)
    min_fargo: Optional[float] = None
    max_fargo: Optional[float] = None
    min_rank: Optional[int] = Field(None, ge=1, le=50000)
    max_rank: Optional[int] = Field(None, ge=1, le=50000)
    min_points: Optional[float] = None
    max_points: Optional[float] = None
    country_contains: Optional[str] = Field(None, max_length=80)
    limit: int = Field(25, ge=1, le=50)

    @field_validator("ranking_system")
    @classmethod
    def _rs(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in ALLOWED_RANKING_SYSTEMS:
            raise ValueError(f"ranking_system must be one of {sorted(ALLOWED_RANKING_SYSTEMS)} or null")
        return v

    @field_validator("name_contains", "country_contains")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = re.sub(r"[%_\\]", " ", (v or "").strip())[:120]
        return s or None


def grok_rankings_assist_parse(question: str, api_key: str) -> RankingsAssistFilters:
    prompt = f"""You map a natural-language question about billiards rankings data to a JSON filter object.
Return ONLY a JSON object (no markdown) with these optional keys:
- ranking_system: one of {sorted(ALLOWED_RANKING_SYSTEMS)} or omit/null for any
- name_contains: substring for player_name (ASCII letters, spaces, hyphen, period, apostrophe only — use short substring)
- min_fargo, max_fargo: numbers
- min_rank, max_rank: integers
- min_points, max_points: numbers
- country_contains: short substring for country field
- limit: 1-50 default 25

If the question cannot be mapped safely, return {{"limit": 10}} and we will return few rows.

User question: {question!r}
"""
    raw = call_xai_chat_sync(
        api_key,
        prompt,
        system_prompt="You output only compact JSON objects. No prose.",
        temperature=0.1,
        timeout_seconds=60.0,
    )
    parsed = parse_rankings_assist_json(raw) or {}
    try:
        return RankingsAssistFilters.model_validate(parsed)
    except Exception as e:
        logger.warning("Rankings assist parse fallback: %s", e)
        return RankingsAssistFilters(limit=15)


def run_rankings_assist(engine, filters: RankingsAssistFilters) -> List[Dict[str, Any]]:
    wheres = [
        """snapshot_date = (
            SELECT MAX(snapshot_date) FROM rankings r2
            WHERE r2.player_name = r1.player_name AND r2.ranking_system = r1.ranking_system
        )"""
    ]
    params: Dict[str, Any] = {"lim": filters.limit}

    if filters.ranking_system:
        wheres.append("ranking_system = :rs")
        params["rs"] = filters.ranking_system
    if filters.name_contains:
        wheres.append("player_name ILIKE :name_like")
        params["name_like"] = f"%{filters.name_contains}%"
    if filters.country_contains:
        wheres.append("country ILIKE :country_like")
        params["country_like"] = f"%{filters.country_contains}%"
    if filters.min_fargo is not None:
        wheres.append("fargo_rating >= :min_fargo")
        params["min_fargo"] = filters.min_fargo
    if filters.max_fargo is not None:
        wheres.append("fargo_rating <= :max_fargo")
        params["max_fargo"] = filters.max_fargo
    if filters.min_rank is not None:
        wheres.append("rank >= :min_rank")
        params["min_rank"] = filters.min_rank
    if filters.max_rank is not None:
        wheres.append("rank <= :max_rank")
        params["max_rank"] = filters.max_rank
    if filters.min_points is not None:
        wheres.append("points >= :min_points")
        params["min_points"] = filters.min_points
    if filters.max_points is not None:
        wheres.append("points <= :max_points")
        params["max_points"] = filters.max_points

    sql = f"""
        SELECT player_name, rank, points, country, fargo_rating, ranking_system, snapshot_date
        FROM rankings r1
        WHERE {' AND '.join(wheres)}
        ORDER BY ranking_system, rank ASC NULLS LAST
        LIMIT :lim
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def load_docs_excerpt(max_total_chars: int = 48_000) -> str:
    parts: List[str] = []
    total = 0
    docs_dir = PROJECT_ROOT / "docs"
    for name in DOCS_ALLOWLIST:
        path = (docs_dir / name).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            continue
        if not path.is_file():
            continue
        try:
            chunk = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
            continue
        block = f"=== {name} ===\n{chunk}\n"
        if total + len(block) > max_total_chars:
            block = block[: max_total_chars - total]
        parts.append(block)
        total += len(block)
        if total >= max_total_chars:
            break
    return "\n".join(parts)


def grok_scraper_diagnose(api_key: str, error_message: str, html_snippet: str, page_url: str) -> str:
    html_snippet = (html_snippet or "")[:24_000]
    msg = (
        f"URL: {page_url or '(none)'}\n\nError / traceback summary:\n{error_message[:8000]}\n\n"
        f"HTML snippet (truncated):\n{html_snippet}\n\n"
        "Suggest likely root causes, CSS selector or parser hints, and concrete next debugging steps. "
        "Do not claim you fetched the live page."
    )
    return call_xai_chat_sync(
        api_key,
        msg,
        system_prompt=(
            "You are a senior Python web scraping engineer (BeautifulSoup, lxml, Playwright). "
            "Give concise actionable guidance."
        ),
        temperature=0.2,
        timeout_seconds=90.0,
    )


def grok_tournament_qa(api_key: str, notes_json: str) -> str:
    notes_json = (notes_json or "")[:40_000]
    msg = (
        "Review the following tournament/bracket/ranking anomaly notes (JSON or free text). "
        "List likely data issues, duplicates, or rule violations and recommended admin checks.\n\n"
        f"{notes_json}"
    )
    return call_xai_chat_sync(
        api_key,
        msg,
        system_prompt="You assist billiards tournament data QA. Be concise; use markdown lists.",
        temperature=0.2,
        timeout_seconds=90.0,
    )


def grok_docs_assist(api_key: str, question: str) -> Tuple[str, str]:
    ctx = load_docs_excerpt()
    msg = f"Documentation excerpts:\n\n{ctx}\n\n---\nQuestion: {question}"
    answer = call_xai_chat_sync(
        api_key,
        msg,
        system_prompt=DOCS_ASSIST_SYSTEM,
        temperature=0.2,
        timeout_seconds=90.0,
    )
    return answer, ctx[:2000] + ("…" if len(ctx) > 2000 else "")


def grok_email_draft(
    api_key: str,
    purpose: str,
    audience: str,
    key_facts: str,
    tone: str = "professional",
) -> str:
    msg = (
        f"Purpose: {purpose}\nAudience: {audience}\nTone: {tone}\n\nKey facts / bullets:\n{key_facts[:6000]}\n\n"
        "Draft a short email body (subject line on first line as Subject: ...). No placeholders like [name] unless necessary."
    )
    return call_xai_chat_sync(
        api_key,
        msg,
        system_prompt="You write clear operational emails for a billiards rankings platform.",
        temperature=0.35,
        timeout_seconds=60.0,
    )


def grok_merge_hints(api_key: str, player_names: List[str], context: str) -> str:
    names_lines = "\n".join(f"- {n}" for n in player_names[:80])
    msg = (
        f"Player names (possible duplicates or merge candidates):\n{names_lines}\n\n"
        f"Extra context from admin:\n{(context or '')[:4000]}\n\n"
        "Suggest pairs or clusters that might be the same person, with confidence (low/med/high) and rationale. "
        "Advisory only — human must confirm before any merge."
    )
    return call_xai_chat_sync(
        api_key,
        msg,
        system_prompt="You assist deduplicating sports ranking rosters. Output markdown.",
        temperature=0.15,
        timeout_seconds=90.0,
    )


def grok_ci_log_triage(api_key: str, log_excerpt: str, workflow_hint: str = "") -> str:
    msg = build_ci_failure_user_message(
        log_excerpt[:100_000],
        workflow_name=workflow_hint or "manual",
        branch="(local)",
        commit_sha="(n/a)",
    )
    return call_xai_chat_sync(api_key, msg, temperature=0.2, timeout_seconds=120.0)
