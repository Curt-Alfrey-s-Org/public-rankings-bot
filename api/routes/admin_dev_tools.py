"""
Super-admin Grok-backed dev tools: scraper triage, tournament QA, safe rankings NL assist,
internal docs Q&A, email drafts, merge hints, CI log triage.

Requires XAI_API_KEY. Does not apply code or mutate rankings automatically.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_super_admin
from api.services import admin_dev_tools_service as ads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/dev-tools", tags=["admin-dev-tools"])


def _xai_key() -> str:
    key = os.getenv("XAI_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="XAI_API_KEY is not configured. Set it for Grok-backed dev tools.",
        )
    return key


class ScraperDiagnoseBody(BaseModel):
    error_message: str = Field(..., max_length=16_000)
    html_snippet: str = Field("", max_length=32_000)
    page_url: str = Field("", max_length=2048)


class TournamentQABody(BaseModel):
    notes: str = Field(..., max_length=48_000)


class RankingsAssistBody(BaseModel):
    question: str = Field(..., max_length=2000)


class DocsAssistBody(BaseModel):
    question: str = Field(..., max_length=4000)


class EmailDraftBody(BaseModel):
    purpose: str = Field(..., max_length=2000)
    audience: str = Field(..., max_length=500)
    key_facts: str = Field(..., max_length=8000)
    tone: str = Field("professional", max_length=80)


class MergeHintsBody(BaseModel):
    player_names: List[str] = Field(..., min_length=1, max_length=200)
    context: str = Field("", max_length=8000)


class CILogTriageBody(BaseModel):
    log_excerpt: str = Field(..., max_length=120_000)
    workflow_hint: str = Field("", max_length=200)


@router.post("/scraper-diagnose")
async def scraper_diagnose(
    body: ScraperDiagnoseBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        text_out = ads.grok_scraper_diagnose(
            key,
            body.error_message,
            body.html_snippet,
            body.page_url,
        )
    except Exception as e:
        logger.exception("scraper-diagnose Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {"analysis": text_out, "provider": "grok"}


@router.post("/tournament-qa")
async def tournament_qa(
    body: TournamentQABody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        text_out = ads.grok_tournament_qa(key, body.notes)
    except Exception as e:
        logger.exception("tournament-qa Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {"analysis": text_out, "provider": "grok"}


@router.post("/rankings-assist")
async def rankings_assist(
    body: RankingsAssistBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    from database import get_engine

    try:
        filters = ads.grok_rankings_assist_parse(body.question, key)
    except Exception as e:
        logger.exception("rankings-assist parse failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    try:
        engine = get_engine()
        rows = ads.run_rankings_assist(engine, filters)
    except Exception as e:
        logger.exception("rankings-assist query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:500]) from e
    return {
        "filters_applied": filters.model_dump(),
        "row_count": len(rows),
        "rows": rows,
        "provider": "grok",
    }


@router.post("/docs-assist")
async def docs_assist(
    body: DocsAssistBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        answer, excerpt_preview = ads.grok_docs_assist(key, body.question)
    except Exception as e:
        logger.exception("docs-assist Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {
        "answer": answer,
        "docs_excerpt_preview": excerpt_preview,
        "provider": "grok",
    }


@router.post("/email-draft")
async def email_draft(
    body: EmailDraftBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        draft = ads.grok_email_draft(
            key,
            body.purpose,
            body.audience,
            body.key_facts,
            body.tone,
        )
    except Exception as e:
        logger.exception("email-draft Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {"draft": draft, "provider": "grok"}


@router.post("/merge-hints")
async def merge_hints(
    body: MergeHintsBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        text_out = ads.grok_merge_hints(key, body.player_names, body.context)
    except Exception as e:
        logger.exception("merge-hints Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {"hints": text_out, "provider": "grok"}


@router.post("/ci-log-triage")
async def ci_log_triage(
    body: CILogTriageBody,
    _user: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    key = _xai_key()
    try:
        text_out = ads.grok_ci_log_triage(key, body.log_excerpt, body.workflow_hint)
    except Exception as e:
        logger.exception("ci-log-triage Grok failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)[:500]) from e
    return {"suggestion": text_out, "provider": "grok"}
