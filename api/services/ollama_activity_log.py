"""
Ollama activity logger -- writes every Ollama call to the ollama_activity_log table.

Used by:
- OllamaClient (auto-logged via _post_with_retry)
- AI Monitor admin page (reads via /api/admin/ai-monitor endpoint)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def log_ollama_activity(
    feature: str,
    model: str,
    request_text: str,
    response_text: str,
    duration_seconds: float,
    eval_tokens: int = 0,
    prompt_tokens: int = 0,
    status: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write an Ollama activity log row. Runs in a fresh connection to avoid
    interfering with any ongoing transaction in the calling context.
    """
    try:
        from database import get_engine

        engine = get_engine()
        prompt_summary = request_text[:200] if request_text else ""

        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO ollama_activity_log
                        (feature, model, prompt_summary, request_text, response_text,
                         duration_seconds, eval_tokens, prompt_tokens, status,
                         error_message, metadata)
                    VALUES
                        (:feature, :model, :prompt_summary, :request_text, :response_text,
                         :duration_seconds, :eval_tokens, :prompt_tokens, :status,
                         :error_message, :metadata)
                """),
                {
                    "feature": feature,
                    "model": model,
                    "prompt_summary": prompt_summary,
                    "request_text": request_text[:10000] if request_text else "",
                    "response_text": response_text[:10000] if response_text else "",
                    "duration_seconds": duration_seconds,
                    "eval_tokens": eval_tokens,
                    "prompt_tokens": prompt_tokens,
                    "status": status,
                    "error_message": (error_message or "")[:1000] if error_message else None,
                    "metadata": json.dumps(metadata or {}),
                },
            )
            conn.commit()
    except Exception as e:
        logger.debug("Could not write ollama activity log: %s", e)
