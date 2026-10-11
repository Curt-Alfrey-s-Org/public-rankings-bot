"""
LLM completion for ALFa narrative endpoints: LiteLLM (trust-zone keys/models) or Ollama direct.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from api.services.litellm_client import (
    get_litellm_client_for_trust_zone,
    is_litellm_enabled,
    litellm_model_for_trust_zone,
)
from api.services.ollama_client import OllamaResponse, get_ollama_client


def _ollama_chat_model() -> str:
    return os.getenv("OLLAMA_MODEL_CHAT", "llama3.1:8b").strip() or "llama3.1:8b"


async def complete_narrative_chat(
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    feature: str,
    trust_zone: str,
) -> OllamaResponse:
    """
    trust_zone: "public_web" | "app_authenticated"
    """
    log_metadata: Dict[str, Any] = {"trust_zone": trust_zone}

    if is_litellm_enabled():
        client = get_litellm_client_for_trust_zone(trust_zone)
        if client is not None:
            model = litellm_model_for_trust_zone(trust_zone)
            return await client.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                feature=feature,
                log_metadata=log_metadata,
            )
        # Client missing (e.g. empty API key): fail closed unless break-glass.
        allow_fb = os.getenv("LITELLM_ALLOW_OLLAMA_FALLBACK", "false").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        if not allow_fb:
            return OllamaResponse(
                content="",
                model="",
                done=False,
                error="LiteLLM is enabled but not configured (set LITELLM_API_KEY). "
                "Ollama fallback is off (LITELLM_ALLOW_OLLAMA_FALLBACK=false).",
            )

    # LiteLLM disabled, or explicit break-glass fallback after enabled+misconfig.
    allow_ollama = (not is_litellm_enabled()) or os.getenv(
        "LITELLM_ALLOW_OLLAMA_FALLBACK", "false"
    ).strip().lower() in ("true", "1", "yes")
    if not allow_ollama:
        return OllamaResponse(
            content="",
            model="",
            done=False,
            error="AI assistant is not available (LiteLLM required).",
        )

    ollama = get_ollama_client()
    if ollama is None:
        return OllamaResponse(
            content="",
            model="",
            done=False,
            error="AI assistant is not available.",
        )

    return await ollama.chat(
        messages=messages,
        model=_ollama_chat_model(),
        temperature=temperature,
        feature=feature,
        log_metadata=log_metadata,
    )
