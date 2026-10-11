"""
Page-scoped one-shot AI Q&A using Ollama/LiteLLM. Same access rules as player performance data
when a player context is provided; general questions use tier/app knowledge only unless the
question names a player (server resolves from DB — docs/ALFA_AI_HOW_TO_USE.md).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.client_ip import get_client_ip
from api.routes.player_performance import _can_access_player
from api.services.ai_demo_rate_limit import apply_ai_narrative_demo_rate_limit
from api.services.ai_narrative_llm import complete_narrative_chat
from api.services.ask_ai_context import (
    build_alfa_knowledge_bundle,
    build_demo_alfa_knowledge_bundle,
    build_server_ask_ai_bundle,
    resolve_player_name_from_question,
)
from api.services.litellm_client import is_litellm_enabled, litellm_model_for_trust_zone
from api.services.ollama_client import get_ollama_client, is_ollama_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-narrative", tags=["ai-narrative"])

_MAX_QUESTION_LEN = 500
_MAX_CONTEXT_JSON = 32_000

_DEMO_LAST_BY_IP: dict[str, float] = {}
_DEMO_COOLDOWN_SEC = float(os.getenv("AI_NARRATIVE_DEMO_IP_COOLDOWN_SEC", "25"))


def _get_client_ip(request: Request) -> str:
    """
    Client IP for demo rate limiting.

    Uses the proxy-resolved client address (api/client_ip.py): Uvicorn only honours
    X-Forwarded-For from trusted proxies (FORWARDED_ALLOW_IPS) and ignores client-supplied
    hops, so the first X-Forwarded-For value is no longer trusted (review 2026-09-25).
    AI_NARRATIVE_TRUST_FORWARDED_FOR is obsolete and ignored.
    """
    return get_client_ip(request) or "unknown"


def _apply_demo_rate_limit(ip: str) -> None:
    if _DEMO_COOLDOWN_SEC <= 0:
        return
    now = time.monotonic()
    last = _DEMO_LAST_BY_IP.get(ip)
    if last is not None and (now - last) < _DEMO_COOLDOWN_SEC:
        raise HTTPException(
            status_code=429,
            detail="Too many demo requests. Please wait a moment and try again.",
        )
    _DEMO_LAST_BY_IP[ip] = now
    if len(_DEMO_LAST_BY_IP) > 20_000:
        cutoff = now - max(_DEMO_COOLDOWN_SEC, 60.0)
        stale = [k for k, v in _DEMO_LAST_BY_IP.items() if v < cutoff]
        for k in stale[:5000]:
            _DEMO_LAST_BY_IP.pop(k, None)

# Personality + rules; tier/deals/features arrive in a JSON block appended at call time.
_ASK_AI_SYSTEM_BASE = """You are ALFa — the in-app guide for this billiards rankings and tournament platform.

## Voice and presence
- Warm, confident, and a little witty when it fits (think Cortana from Halo: capable, personable, never smug).
- Sound like a teammate who knows the system inside out — not a corporate script, not a lecture.
- Short paragraphs; conversational; plain language.

## What you must never do
- Never say you "do not have that information", "I cannot access that", or similar dead-ends.
- If something is outside the data you were given, pivot: offer what you *can* show (rankings snapshot, tournament history, head-to-head context, tier benefits, where to tap in the app) and invite them to ask a sharper follow-up.
- Do not invent player statistics, placements, prices, or discounts that are not in the provided JSON. For numbers, only use tier_catalog, active_deals, server_authoritative, page_client_snapshot, and app_identity.

## Two modes (blend as needed)
1) **Coach mode** — questions about a player, tournaments, rankings, head-to-head: be helpful and specific. If the user is below PRO and the topic touches PRO-only app features (see premium_notes and app_identity), give a useful teaser from what you *do* have, then briefly mention what PRO adds (live estimated rating, ALFa rating in premium views) with a light touch — not a sales pitch.
2) **Guide / sales mode** — questions about pay levels, AI Coach tiers, what the app does, deals, or "why here vs other apps": be an enthusiastic ambassador. Explain tiers clearly using tier_catalog. Mention active_deals when relevant (title, discount_percent, deal_price, tagline, expiry). Calculate savings vs list price_monthly when you cite a deal (e.g. list minus deal, or percent off). If the user has account_discount_percent in the JSON, you may mention their existing discount politely.
- Be convincing but never pushy or annoying. One upgrade mention in coach mode is enough unless they asked about pricing.

## Tier gating (teaser rule)
- The user's subscription tier is user_tier (see Alfa knowledge JSON). tier_order shows FREEBIE → ROOKIE → WEEKEND_WARRIOR → POOL_SHARK → PRO.
- When they ask for something that belongs to a higher tier or PRO-only app features, give a **teaser**: something genuinely useful from server_authoritative or page_client_snapshot, then explain what upgrading unlocks, with concrete numbers from tier_catalog (price_monthly, limits, max_video_duration_seconds) and savings if a deal applies.
- super_admin users are treated as PRO in the knowledge JSON for messaging.

## Rankings and data
- When player context exists: user message includes JSON with server_authoritative (database snapshot) and page_client_snapshot (browser). Prefer server_authoritative for rankings, placements, career aggregates, tournament finishes. Use page_client_snapshot when the question is clearly screen-specific.
- The server may resolve a player name from the question itself (even on Rankings home). When server_authoritative has performance or tournament_finishes, answer with those facts — do not claim you lack access.
- paid_ratings_included true means alfa_rating / est_rating in the snapshot are authorized for this user (PRO or staff). If false, teaser PRO for those fields only.
- Lower placement numbers are better (1 = first place).

## Safety
- Stay on billiards, this app, and account/tier topics. No medical, legal, or unrelated rabbit holes.
"""

_DEMO_SYSTEM_BASE = """You are ALFa — the same AI guide personality as inside Pro Billiards Software, but this is a **public demo** on **example.com** (no login).

## Voice
- Warm, confident, concise — teammate energy, not corporate boilerplate.

## Scope (strict)
- Answer only about: **USPBF** (United States Pro Billiards Federation), **this public website’s purpose**, **how accounts work** (pro / top-level amateur / other players), **Pro Billiards Software** features at a high level, **AI Coach tiers**, **deals** (from active_deals in JSON), and **billiards** topics tied to those.
- Use **uspbf_site**, **app_identity**, **tier_catalog**, and **active_deals** in the JSON. Do not invent prices, discounts, or player-specific stats.
- **No private data:** you cannot see any user’s rankings, matches, or subscription. If asked for personal stats, say they need to **sign in at probilliardssoftware.com** (or use links in uspbf_site).

## Off-topic
- Politely decline unrelated topics (medical, legal, politics, other sports, coding homework, etc.) and suggest a USPBF or Pro Billiards Software question instead.

## Safety
- No harassment, no instructions for cheating, no claiming certainty about unpublished release dates — point to the app and official pages when specifics are unknown.
"""


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class AskNarrativeRequest(BaseModel):
    page: str = Field(..., description="Logical page id: player-performance, head-to-head, tournament-history, general")
    player_name: str = Field(default="", max_length=300)
    question: str = Field(..., min_length=1, max_length=_MAX_QUESTION_LEN)
    context: Dict[str, Any] = Field(default_factory=dict)
    history: List[HistoryTurn] = Field(default_factory=list, max_length=40)


class ChatModelOption(BaseModel):
    id: str
    label: str
    description: str = ""
    available: bool
    reason: Optional[str] = None


class ModelsResponse(BaseModel):
    models: List[ChatModelOption]
    litellm_enabled: bool


@router.get("/models", response_model=ModelsResponse)
async def list_chat_models(
    current_user: dict = Depends(get_current_user),
):
    """Return the single central ALFa model (no client-side picker)."""
    del current_user
    model_id = (
        litellm_model_for_trust_zone("app_authenticated")
        if is_litellm_enabled()
        else "app-chat"
    )
    ai_on = is_ollama_enabled() or is_litellm_enabled()
    ollama_ok = not is_ollama_enabled() or get_ollama_client() is not None
    available = bool(ai_on and ollama_ok)
    return ModelsResponse(
        models=[
            ChatModelOption(
                id=model_id,
                label="ALFa AI (via ALFa brain)",
                description="Central tier controlled by ALFa brain admin",
                available=available,
                reason=None if available else "ai_not_ready",
            )
        ],
        litellm_enabled=is_litellm_enabled(),
    )


class AskNarrativeResponse(BaseModel):
    answer: str
    error: Optional[str] = None


def _build_system_content(alfa_knowledge: Dict[str, Any]) -> str:
    try:
        know_raw = json.dumps(alfa_knowledge, default=str, sort_keys=True)
    except (TypeError, ValueError) as e:
        logger.warning("ask: failed to serialize alfa knowledge: %s", e)
        know_raw = "{}"
    return (
        _ASK_AI_SYSTEM_BASE
        + "\n\n## Alfa knowledge (JSON — use for tiers, deals, app copy, user tier/role)\n"
        + know_raw
    )


def _build_demo_system_content(alfa_knowledge: Dict[str, Any]) -> str:
    try:
        know_raw = json.dumps(alfa_knowledge, default=str, sort_keys=True)
    except (TypeError, ValueError) as e:
        logger.warning("demo-ask: failed to serialize knowledge: %s", e)
        know_raw = "{}"
    return (
        _DEMO_SYSTEM_BASE
        + "\n\n## Knowledge JSON (USPBF site + app tiers/deals — only source of truth)\n"
        + know_raw
    )


class DemoAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=_MAX_QUESTION_LEN)


@router.post("/ask", response_model=AskNarrativeResponse)
async def ask_page_question(
    body: AskNarrativeRequest,
    current_user: dict = Depends(get_current_user),
):
    player_raw = (body.player_name or "").strip()
    resolved_from_question = False

    if not player_raw:
        try:
            inferred = await asyncio.to_thread(
                resolve_player_name_from_question,
                body.question,
                current_user,
            )
        except Exception as e:
            logger.warning("ask_page_question: name resolve from question failed: %s", e)
            inferred = None
        if inferred:
            player_raw = inferred
            resolved_from_question = True

    has_player = bool(player_raw)

    if has_player and not _can_access_player(current_user, player_raw):
        raise HTTPException(
            status_code=403,
            detail="You can only ask about players you are allowed to view.",
        )

    if not is_ollama_enabled() and not is_litellm_enabled():
        raise HTTPException(status_code=503, detail="AI assistant is not enabled.")
    if is_ollama_enabled() and get_ollama_client() is None and not is_litellm_enabled():
        raise HTTPException(status_code=503, detail="AI assistant is not available.")

    try:
        json.dumps(body.context, default=str)
    except (TypeError, ValueError) as e:
        logger.warning("ask_page_question: invalid context: %s", e)
        raise HTTPException(status_code=400, detail="Context must be JSON-serializable.") from e

    try:
        alfa_knowledge = await asyncio.to_thread(build_alfa_knowledge_bundle, current_user)
    except Exception as e:
        logger.exception("ask_page_question: failed alfa knowledge: %s", e)
        alfa_knowledge = {"error": "knowledge_bundle_failed"}

    server_bundle: Dict[str, Any]
    if has_player:
        try:
            server_bundle = await asyncio.to_thread(
                build_server_ask_ai_bundle,
                player_raw,
                current_user,
            )
            if resolved_from_question:
                server_bundle = dict(server_bundle)
                server_bundle["resolved_from_question"] = True
        except Exception as e:
            logger.exception("ask_page_question: failed to load server context: %s", e)
            raise HTTPException(status_code=500, detail="Could not load player data for this question.") from e
    else:
        server_bundle = {
            "note": (
                "No player filter — answer from Alfa knowledge JSON only unless page_client_snapshot helps. "
                "If the user names a player, invite them to ask again with the full name "
                "(e.g. show stats for First Last)."
            ),
        }

    # Tier/deals/app copy live only in the system message (avoid duplicating large JSON).
    merged: Dict[str, Any] = {
        "server_authoritative": server_bundle,
        "page_client_snapshot": body.context or {},
        "ui_page_id": (body.page or "").strip() or None,
    }

    try:
        ctx_raw = json.dumps(merged, default=str, sort_keys=True)
    except (TypeError, ValueError) as e:
        logger.warning("ask_page_question: failed to serialize merged context: %s", e)
        raise HTTPException(status_code=500, detail="Could not build question context.") from e

    if len(ctx_raw) > _MAX_CONTEXT_JSON:
        merged["page_client_snapshot"] = {"_truncated": True}
        ctx_raw = json.dumps(merged, default=str, sort_keys=True)
    if len(ctx_raw) > _MAX_CONTEXT_JSON:
        tf = merged.get("server_authoritative", {}).get("tournament_finishes")
        if isinstance(tf, list) and len(tf) > 40:
            merged["server_authoritative"]["tournament_finishes"] = tf[:40]
            merged["server_authoritative"]["tournament_finishes_truncated"] = True
        ctx_raw = json.dumps(merged, default=str, sort_keys=True)
    if len(ctx_raw) > _MAX_CONTEXT_JSON:
        ctx_raw = ctx_raw[:_MAX_CONTEXT_JSON] + "…"

    system_content = _build_system_content(alfa_knowledge)

    history_msgs: List[Dict[str, str]] = []
    for turn in body.history or []:
        role = turn.role if turn.role in ("user", "assistant") else "user"
        content = (turn.content or "").strip()
        if content:
            history_msgs.append({"role": role, "content": content[:8000]})

    user_turn = {
        "role": "user",
        "content": (
            f"Player (request): {player_raw or '(none — general / app question)'}\n"
            f"Context (JSON):\n{ctx_raw}\n\n"
            f"Question: {body.question.strip()}"
        ),
    }

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
        *history_msgs,
        user_turn,
    ]

    try:
        resp = await complete_narrative_chat(
            messages,
            temperature=0.35,
            feature="page_question",
            trust_zone="app_authenticated",
        )
    except Exception as e:
        logger.exception("ask_page_question LLM error: %s", e)
        raise HTTPException(status_code=502, detail="AI request failed.") from e

    if resp.error:
        logger.warning("ask_page_question LLM returned error: %s", resp.error)
        return AskNarrativeResponse(answer="", error=resp.error)

    text = (resp.content or "").strip()
    if not text:
        return AskNarrativeResponse(answer="", error="Empty response from model.")

    return AskNarrativeResponse(answer=text)


@router.post("/demo-ask", response_model=AskNarrativeResponse)
async def ask_demo_public(body: DemoAskRequest, request: Request):
    """
    Public ALFa demo for example.com — no auth. Rate-limited per IP; scoped to USPBF + PBS marketing knowledge only.
    """
    ip = _get_client_ip(request)
    apply_ai_narrative_demo_rate_limit(ip)
    _apply_demo_rate_limit(ip)

    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is required.")

    if not is_ollama_enabled() and not is_litellm_enabled():
        raise HTTPException(status_code=503, detail="AI assistant is not enabled.")
    if is_ollama_enabled() and get_ollama_client() is None and not is_litellm_enabled():
        raise HTTPException(status_code=503, detail="AI assistant is not available.")

    try:
        alfa_knowledge = await asyncio.to_thread(build_demo_alfa_knowledge_bundle)
    except Exception as e:
        logger.exception("demo-ask: knowledge bundle failed: %s", e)
        alfa_knowledge = {"error": "knowledge_bundle_failed"}

    system_content = _build_demo_system_content(alfa_knowledge)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Visitor question: {q}"},
    ]

    try:
        resp = await complete_narrative_chat(
            messages,
            temperature=0.35,
            feature="uspbf_demo",
            trust_zone="public_web",
        )
    except Exception as e:
        logger.exception("demo-ask LLM error: %s", e)
        raise HTTPException(status_code=502, detail="AI request failed.") from e

    if resp.error:
        logger.warning("demo-ask Ollama returned error: %s", resp.error)
        return AskNarrativeResponse(answer="", error=resp.error)

    text = (resp.content or "").strip()
    if not text:
        return AskNarrativeResponse(answer="", error="Empty response from model.")

    return AskNarrativeResponse(answer=text)
