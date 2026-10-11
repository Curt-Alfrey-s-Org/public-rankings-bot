"""
LiteLLM client for distributed inference via the ALFa AI stack's LiteLLM proxy.

Provides an async client that talks to the LiteLLM proxy (OpenAI-compatible API)
on the ALFa AI brain (pool27 / llama.cpp RPC via LiteLLM aliases).

Returns OllamaResponse objects for compatibility with existing call sites.

Environment:
    LITELLM_ENABLED           true/1/yes to enable (default: false)
    LITELLM_BASE_URL          LiteLLM proxy URL (default: http://192.0.2.30:8413)
    LITELLM_API_KEY           Required when enabled (no shared dev default)
    LITELLM_API_KEY_PUBLIC    Optional key for public_web demo (else LITELLM_API_KEY)
    LITELLM_API_KEY_APP       Optional key for app_authenticated (else LITELLM_API_KEY)
    LITELLM_MODEL_PUBLIC      Model alias for demo-ask (default: public-chat)
    LITELLM_MODEL_PAGE_QUESTION Model alias for /ask (else LITELLM_MODEL_CHAT)
    LITELLM_MODEL_CHAT        Fallback chat model (default: app-chat in code)
    LITELLM_TIMEOUT           Request timeout in seconds (default: 600)
    LITELLM_ALLOW_OLLAMA_FALLBACK  true to allow Ollama when LiteLLM enabled but fails (default: false, prod fail-closed)
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from api.services.ollama_client import OllamaResponse

logger = logging.getLogger(__name__)

# Trust zones for LiteLLM routing (see docs/ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md)
TRUST_ZONE_PUBLIC_WEB = "public_web"
TRUST_ZONE_APP = "app_authenticated"


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def is_litellm_enabled() -> bool:
    return _get_env("LITELLM_ENABLED", "false").lower() in ("true", "1", "yes")


# Brain LiteLLM on hub (hub). Rankings runs on probilliards — never default to localhost.
_DEFAULT_LITELLM_BASE = "http://192.0.2.30:8413"


def get_litellm_base_url() -> str:
    return _get_env("LITELLM_BASE_URL", _DEFAULT_LITELLM_BASE) or _DEFAULT_LITELLM_BASE


def get_litellm_api_key() -> str:
    """Require explicit key when LiteLLM is used (audit D-003)."""
    return _get_env("LITELLM_API_KEY", "")


class LiteLLMClient:
    """
    Async client for LiteLLM proxy (OpenAI-compatible API).

    Prefer LiteLLM for all narrative trust zones. Ollama remains for non-LiteLLM
    features (coach/vision) only.

    All public methods degrade gracefully and return OllamaResponse with
    error set rather than raising.
    """

    MAX_RETRIES = 2
    RETRY_BACKOFF_SECONDS = 2.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        model_chat: Optional[str] = None,
    ):
        self.base_url = (base_url or get_litellm_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else get_litellm_api_key()
        if not self.api_key:
            raise ValueError(
                "LITELLM_API_KEY is required when using LiteLLMClient "
                "(no shared sk-alfa-ai-litellm-dev default)"
            )
        self.timeout = timeout or float(_get_env("LITELLM_TIMEOUT", "600"))
        self.model_chat = model_chat or _get_env(
            "LITELLM_MODEL_CHAT", "app-chat"
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            client = await self._get_client()
            resp = await client.get("/health/liveliness", timeout=10.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "healthy" if resp.status_code == 200 else "degraded",
                "latency_ms": latency_ms,
                "base_url": self.base_url,
                "model_chat": self.model_chat,
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning("LiteLLM health check failed: %s", e)
            return {
                "status": "unreachable",
                "latency_ms": latency_ms,
                "base_url": self.base_url,
                "error": str(e)[:200],
            }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        feature: str = "litellm_chat",
        log_metadata: Optional[Dict[str, Any]] = None,
    ) -> OllamaResponse:
        """
        Chat completion via LiteLLM proxy (OpenAI format).

        Returns OllamaResponse for compatibility with existing call sites.
        """
        model = model or self.model_chat
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        request_text = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')}" for m in messages
        )
        resp = await self._post_with_retry("/v1/chat/completions", body, model)
        _log_activity(feature, model, request_text, resp, log_metadata)
        return resp

    async def _post_with_retry(
        self, endpoint: str, body: Dict[str, Any], model: str
    ) -> OllamaResponse:
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
                        "LiteLLM %s returned %d (attempt %d/%d): %s",
                        endpoint,
                        resp.status_code,
                        attempt,
                        self.MAX_RETRIES,
                        error_text,
                    )
                    last_error = f"HTTP {resp.status_code}: {error_text}"
                    if attempt < self.MAX_RETRIES:
                        import asyncio
                        await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)
                        continue
                    return OllamaResponse(
                        content="",
                        model=model,
                        done=False,
                        error=last_error,
                        total_duration_ns=int(elapsed * 1e9),
                    )

                data = resp.json()
                choices = data.get("choices", [])
                content = ""
                if choices:
                    content = choices[0].get("message", {}).get("content", "")

                usage = data.get("usage", {})
                eval_count = usage.get("completion_tokens", 0)
                prompt_count = usage.get("prompt_tokens", 0)

                logger.info(
                    "LiteLLM %s [%s] completed in %.1fs (tokens=%d)",
                    endpoint,
                    model,
                    elapsed,
                    eval_count,
                )

                return OllamaResponse(
                    content=content,
                    model=data.get("model", model),
                    done=True,
                    total_duration_ns=int(elapsed * 1e9),
                    eval_count=eval_count,
                    prompt_eval_count=prompt_count,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "LiteLLM %s attempt %d/%d failed: %s",
                    endpoint,
                    attempt,
                    self.MAX_RETRIES,
                    last_error,
                )
                if attempt < self.MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.error("LiteLLM %s unexpected error: %s", endpoint, last_error)
                break

        return OllamaResponse(content="", model=model, done=False, error=last_error)


def _log_activity(
    feature: str,
    model: str,
    request_text: str,
    resp: OllamaResponse,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort log to the ollama_activity_log table (reuses existing infrastructure)."""
    try:
        from api.services.ollama_activity_log import log_ollama_activity

        zone = (metadata or {}).get("trust_zone")
        req = request_text
        if zone == TRUST_ZONE_PUBLIC_WEB:
            # Minimize retention surface for anonymous public demo traffic
            req = (request_text or "")[:2000]

        log_ollama_activity(
            feature=feature,
            model=f"litellm/{model}",
            request_text=req,
            response_text=(resp.content or "")[:5000] if zone == TRUST_ZONE_PUBLIC_WEB else resp.content,
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
# Per–trust-zone clients (optional separate API keys for public vs app)
# ---------------------------------------------------------------------------

_clients_by_zone: Dict[str, LiteLLMClient] = {}


def _api_key_for_trust_zone(zone: str) -> str:
    if zone == TRUST_ZONE_PUBLIC_WEB:
        return _get_env("LITELLM_API_KEY_PUBLIC") or get_litellm_api_key()
    return _get_env("LITELLM_API_KEY_APP") or get_litellm_api_key()


def litellm_model_for_trust_zone(zone: str) -> str:
    """Model alias names must exist in ALFa AI deploy/litellm_config.yaml (repo: alfa-ai/)."""
    if zone == TRUST_ZONE_PUBLIC_WEB:
        m = _get_env("LITELLM_MODEL_PUBLIC", "public-chat")
        return m or "public-chat"
    page = _get_env("LITELLM_MODEL_PAGE_QUESTION", "")
    if page:
        return page
    m = _get_env("LITELLM_MODEL_CHAT", "app-chat")
    return m or "app-chat"


def get_litellm_client_for_trust_zone(zone: str) -> Optional[LiteLLMClient]:
    """
    Return a LiteLLM client for the given trust zone if LITELLM_ENABLED=true.

    public_web and app_authenticated may use different LITELLM_API_KEY_* values
    so the proxy can apply different virtual-key policies when configured.
    """
    if not is_litellm_enabled():
        return None
    if zone not in _clients_by_zone:
        key = _api_key_for_trust_zone(zone)
        if not key:
            logger.error(
                "LITELLM_ENABLED but no API key for zone=%s "
                "(set LITELLM_API_KEY or zone-specific key)",
                zone,
            )
            return None
        try:
            _clients_by_zone[zone] = LiteLLMClient(api_key=key)
        except ValueError as exc:
            logger.error("LiteLLMClient init failed zone=%s: %s", zone, exc)
            return None
        logger.info(
            "LiteLLMClient initialized for zone=%s base_url=%s default_model=%s",
            zone,
            _clients_by_zone[zone].base_url,
            _clients_by_zone[zone].model_chat,
        )
    return _clients_by_zone[zone]


def get_litellm_client() -> Optional[LiteLLMClient]:
    """
    Shared app-trust-zone client (backward compatible).

    Use get_litellm_client_for_trust_zone for explicit public vs app routing.
    """
    return get_litellm_client_for_trust_zone(TRUST_ZONE_APP)
