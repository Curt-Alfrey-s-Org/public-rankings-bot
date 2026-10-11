"""
Rankings Assistant: role-scoped natural-language Q&A over DB-derived JSON + Ollama.

Access control is enforced by `rankings_assistant_context.build_assistant_context`;
the model is only given that payload.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.rate_limiter import check_rankings_assistant_limit
from api.services.ollama_client import get_ollama_client, is_ollama_enabled
from api.services.rankings_assistant_context import (
    build_assistant_context,
    system_prompt_for_tier,
    _safe_json,
)
from database import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rankings-assistant", tags=["rankings-assistant"])


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    assistant_tier: str
    context_keys: list[str]
    disclaimer: str


@router.post("/ask", response_model=AskResponse)
async def ask_rankings_assistant(
    body: AskBody,
    user: dict = Depends(get_current_user),
):
    if not is_ollama_enabled():
        raise HTTPException(
            status_code=503,
            detail="Rankings Assistant is disabled. Set OLLAMA_ENABLED=true and configure Ollama.",
        )

    sub = (user.get("sub") or "").strip()
    role = (user.get("role") or "").strip()
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    allowed, retry_after = check_rankings_assistant_limit(sub, role)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many assistant requests. Retry after {int(retry_after)} seconds.",
        )

    try:
        engine = get_engine()
        tier, ctx, keys = build_assistant_context(role=role, username=sub, engine=engine)
    except Exception as e:
        logger.exception("Rankings assistant context build failed: %s", e)
        raise HTTPException(status_code=500, detail="Could not build assistant context.") from e

    system = system_prompt_for_tier(tier)
    context_block = _safe_json(ctx)
    user_message = (
        "CONTEXT_JSON (authoritative; do not invent facts beyond this object):\n"
        f"{context_block}\n\n"
        f"User question:\n{body.question.strip()}"
    )

    client = get_ollama_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Ollama client is not available.")

    resp = await client.chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        model=client.model_chat,
        temperature=0.2,
        feature="rankings_assistant",
        log_metadata={"trust_zone": "app_authenticated"},
    )

    if resp.error:
        logger.warning("Rankings assistant Ollama error: %s", resp.error)
        raise HTTPException(
            status_code=502,
            detail=f"Assistant model error: {resp.error[:400]}",
        )

    answer = (resp.content or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Assistant returned an empty response.")

    return AskResponse(
        answer=answer,
        assistant_tier=tier,
        context_keys=keys,
        disclaimer=(
            "Generated from a role-limited snapshot of app data. "
            "Not legal, medical, or professional advice. Verify important facts in the app."
        ),
    )
