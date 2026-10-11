"""
Shared prompts and xAI (Grok) text calls for CI failure triage.

Used by scripts/ci_grok_suggest_fix.py (sync) and optionally by admin tooling.
Does not import FastAPI.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

XAI_API_BASE = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4"

CI_FAILURE_SYSTEM_PROMPT = """You are a senior Python/FastAPI engineer helping fix CI test failures for the rankings-bot project.

Rules:
- Output concise, actionable guidance. Do NOT claim you ran tests or saw files not in the log.
- Prefer minimal diffs: name files and show suggested code blocks as markdown.
- If the log is truncated or unclear, say what additional information would help.
- Never suggest committing secrets; use GitHub Actions secrets for API keys.
- End with a short "Suggested PR title" line."""

DOCS_ASSIST_SYSTEM = """You answer questions about the Rankings-Bot project using ONLY the provided documentation excerpts.
If the answer is not in the excerpts, say you do not have that in the provided docs and suggest which doc file might exist.
Be concise. Use markdown lists where helpful."""


def build_ci_failure_user_message(log_excerpt: str, workflow_name: str, branch: str, commit_sha: str) -> str:
    return (
        f"Workflow: {workflow_name}\n"
        f"Branch: {branch}\n"
        f"Commit: {commit_sha}\n\n"
        f"--- CI log excerpt (may be truncated) ---\n{log_excerpt}\n"
        "--- end ---\n\n"
        "Analyze failures and suggest concrete code or config fixes for a pull request."
    )


def call_xai_chat_sync(
    api_key: str,
    user_message: str,
    *,
    system_prompt: str = CI_FAILURE_SYSTEM_PROMPT,
    model: str = DEFAULT_MODEL,
    timeout_seconds: float = 120.0,
    temperature: float = 0.2,
) -> str:
    """Synchronous Grok chat completion; raises on HTTP/API errors."""
    body: Dict[str, Any] = {
        "model": model,
        "stream": False,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        r = client.post(
            f"{XAI_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if r.status_code != 200:
            raise RuntimeError(f"xAI HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("xAI response missing choices")
    msg = (choices[0].get("message") or {}).get("content") or ""
    return msg.strip()


def parse_rankings_assist_json(raw: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from Grok response (handles markdown fences)."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
