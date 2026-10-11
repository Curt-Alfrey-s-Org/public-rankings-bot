"""
Ollama LLM client for local inference via network-hosted Ollama server.

Provides async HTTP client for Ollama's REST API with:
- chat() for multi-turn conversations
- generate() for single-prompt completions
- health() for readiness probes
- Configurable timeouts, retries, and graceful degradation
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

try:
    from api.routes.metrics import (
        ollama_requests_total,
        ollama_request_duration_seconds,
        ollama_tokens_total,
        PROMETHEUS_AVAILABLE,
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    ollama_requests_total = None
    ollama_request_duration_seconds = None
    ollama_tokens_total = None


def _record_metrics(model: str, endpoint: str, status: str, duration: float, eval_count: int, prompt_count: int) -> None:
    if not PROMETHEUS_AVAILABLE or ollama_requests_total is None:
        return
    try:
        ollama_requests_total.labels(model=model, endpoint=endpoint, status=status).inc()
        ollama_request_duration_seconds.labels(model=model, endpoint=endpoint).observe(duration)
        if eval_count > 0:
            ollama_tokens_total.labels(model=model, token_type="eval").inc(eval_count)
        if prompt_count > 0:
            ollama_tokens_total.labels(model=model, token_type="prompt").inc(prompt_count)
    except Exception:
        pass


@dataclass
class OllamaResponse:
    """Structured response from an Ollama API call."""

    content: str
    model: str
    done: bool = True
    total_duration_ns: int = 0
    eval_count: int = 0
    prompt_eval_count: int = 0
    error: Optional[str] = None

    @property
    def eval_tokens(self) -> int:
        return self.eval_count

    @property
    def prompt_tokens(self) -> int:
        return self.prompt_eval_count

    @property
    def duration_seconds(self) -> float:
        return self.total_duration_ns / 1e9 if self.total_duration_ns else 0.0


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def is_ollama_enabled() -> bool:
    return _get_env("OLLAMA_ENABLED", "false").lower() in ("true", "1", "yes")


def get_ollama_base_url() -> str:
    return _get_env("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaClient:
    """
    Async client for Ollama REST API running on a network host (e.g. Windows PC).

    All public methods degrade gracefully: callers receive an OllamaResponse
    with error set (and empty content) rather than raising on network issues.
    """

    MAX_RETRIES = 2
    RETRY_BACKOFF_SECONDS = 1.5

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        model_structured: Optional[str] = None,
        model_chat: Optional[str] = None,
    ):
        self.base_url = (base_url or get_ollama_base_url()).rstrip("/")
        self.timeout = timeout or float(_get_env("OLLAMA_TIMEOUT", "60"))
        self.model_structured = model_structured or _get_env(
            "OLLAMA_MODEL_STRUCTURED", "mistral:7b"
        )
        self.model_chat = model_chat or _get_env("OLLAMA_MODEL_CHAT", "llama3.1:8b")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health(self) -> Dict[str, Any]:
        """Probe Ollama readiness. Returns dict with status and latency."""
        start = time.perf_counter()
        try:
            client = await self._get_client()
            resp = await client.get("/", timeout=5.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "healthy" if resp.status_code == 200 else "degraded",
                "latency_ms": latency_ms,
                "base_url": self.base_url,
                "models": {
                    "structured": self.model_structured,
                    "chat": self.model_chat,
                },
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning("Ollama health check failed: %s", e)
            return {
                "status": "unreachable",
                "latency_ms": latency_ms,
                "base_url": self.base_url,
                "error": str(e)[:200],
            }

    async def list_models(self) -> List[str]:
        """Return list of model names currently available on the Ollama server."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning("Ollama list_models failed: %s", e)
            return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.1,
        format_json: bool = False,
        feature: str = "generate",
        log_metadata: Optional[Dict[str, Any]] = None,
    ) -> OllamaResponse:
        """
        Single-turn generation via /api/generate.

        Args:
            prompt: The user prompt.
            model: Override model (defaults to model_structured).
            system: Optional system prompt.
            temperature: Sampling temperature.
            format_json: Request JSON-mode output from Ollama.
            feature: Label for AI Monitor (e.g. "name_resolution", "bracket_extraction").
        """
        model = model or self.model_structured
        body: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            body["system"] = system
        if format_json:
            body["format"] = "json"

        resp = await self._post_with_retry("/api/generate", body, model)
        _log_activity(feature, model, prompt, resp, log_metadata)
        return resp

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        format_json: bool = False,
        feature: str = "chat",
        log_metadata: Optional[Dict[str, Any]] = None,
    ) -> OllamaResponse:
        """
        Multi-turn chat via /api/chat.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}.
            model: Override model (defaults to model_chat).
            temperature: Sampling temperature.
            format_json: Request JSON-mode output from Ollama.
            feature: Label for AI Monitor (e.g. "name_resolution", "text_coaching").
        """
        model = model or self.model_chat
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            body["format"] = "json"

        request_text = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')}" for m in messages
        )
        resp = await self._post_with_retry("/api/chat", body, model)
        _log_activity(feature, model, request_text, resp, log_metadata)
        return resp

    async def _post_with_retry(
        self, endpoint: str, body: Dict[str, Any], model: str
    ) -> OllamaResponse:
        """Execute POST with exponential backoff retries."""
        last_error: Optional[str] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                start = time.perf_counter()
                resp = await client.post(endpoint, json=body)
                elapsed = time.perf_counter() - start

                if resp.status_code != 200:
                    error_text = resp.text[:300]
                    logger.warning(
                        "Ollama %s returned %d (attempt %d/%d): %s",
                        endpoint,
                        resp.status_code,
                        attempt,
                        self.MAX_RETRIES,
                        error_text,
                    )
                    last_error = f"HTTP {resp.status_code}: {error_text}"
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)
                        continue
                    return OllamaResponse(
                        content="", model=model, done=False, error=last_error
                    )

                data = resp.json()
                content = ""
                if endpoint == "/api/chat":
                    content = (data.get("message") or {}).get("content", "")
                else:
                    content = data.get("response", "")

                eval_count = data.get("eval_count", 0)
                prompt_count = data.get("prompt_eval_count", 0)

                logger.info(
                    "Ollama %s [%s] completed in %.1fs (eval_count=%d)",
                    endpoint,
                    model,
                    elapsed,
                    eval_count,
                )

                _record_metrics(model, endpoint, "success", elapsed, eval_count, prompt_count)

                return OllamaResponse(
                    content=content,
                    model=data.get("model", model),
                    done=data.get("done", True),
                    total_duration_ns=data.get("total_duration", 0),
                    eval_count=eval_count,
                    prompt_eval_count=prompt_count,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "Ollama %s attempt %d/%d failed: %s",
                    endpoint,
                    attempt,
                    self.MAX_RETRIES,
                    last_error,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.error("Ollama %s unexpected error: %s", endpoint, last_error)
                break

        _record_metrics(model, endpoint, "error", 0.0, 0, 0)
        return OllamaResponse(content="", model=model, done=False, error=last_error)


# ---------------------------------------------------------------------------
# Activity logging (writes to ollama_activity_log table for AI Monitor)
# ---------------------------------------------------------------------------


def _log_activity(
    feature: str,
    model: str,
    request_text: str,
    resp: "OllamaResponse",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort log to DB. Never raises."""
    try:
        from api.services.ollama_activity_log import log_ollama_activity

        zone = (metadata or {}).get("trust_zone")
        req = request_text
        resp_text = resp.content
        if zone == "public_web":
            req = (request_text or "")[:2000]
            resp_text = (resp.content or "")[:5000]

        log_ollama_activity(
            feature=feature,
            model=model,
            request_text=req,
            response_text=resp_text,
            duration_seconds=resp.duration_seconds,
            eval_tokens=resp.eval_count,
            prompt_tokens=resp.prompt_eval_count,
            status="success" if not resp.error else "error",
            error_message=resp.error,
            metadata=metadata,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_instance: Optional[OllamaClient] = None


def get_ollama_client() -> Optional[OllamaClient]:
    """
    Return a shared OllamaClient if OLLAMA_ENABLED=true, else None.
    Callers should check for None and fall back to deterministic logic.
    """
    global _instance
    if not is_ollama_enabled():
        return None
    if _instance is None:
        _instance = OllamaClient()
        logger.info(
            "OllamaClient initialized: base_url=%s structured=%s chat=%s",
            _instance.base_url,
            _instance.model_structured,
            _instance.model_chat,
        )
    return _instance
