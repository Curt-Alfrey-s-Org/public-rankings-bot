/**
 * USPBF site — fetch helpers. Same-origin /api/* proxied by nginx with server-side X-API-Key.
 */
(function (global) {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 25000;

  /**
   * AbortController that fires after timeoutMs OR when the caller's signal aborts.
   * Previously a caller-supplied signal replaced the timeout signal, so the timeout
   * never applied (review 2026-09-25). Call cleanup() when the request settles.
   * @param {number} timeoutMs
   * @param {AbortSignal | undefined} callerSignal
   * @returns {{ signal: AbortSignal, cleanup: () => void }}
   */
  function timeoutSignal(timeoutMs, callerSignal) {
    const controller = new AbortController();
    const t = setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    function onCallerAbort() {
      controller.abort();
    }
    if (callerSignal) {
      if (callerSignal.aborted) {
        controller.abort();
      } else {
        callerSignal.addEventListener("abort", onCallerAbort);
      }
    }
    return {
      signal: controller.signal,
      cleanup: function () {
        clearTimeout(t);
        if (callerSignal) callerSignal.removeEventListener("abort", onCallerAbort);
      },
    };
  }

  /**
   * @param {string} path - e.g. "/api/rankings" (with leading slash)
   * @param {{ timeoutMs?: number, signal?: AbortSignal }} [opts]
   * @returns {Promise<Response>}
   */
  async function apiFetch(path, opts) {
    const timeoutMs = opts && opts.timeoutMs != null ? opts.timeoutMs : DEFAULT_TIMEOUT_MS;
    const ts = timeoutSignal(timeoutMs, opts && opts.signal ? opts.signal : undefined);
    try {
      const signal = ts.signal;
      const res = await fetch(path, {
        method: "GET",
        credentials: "same-origin",
        signal: signal,
        headers: { Accept: "application/json" },
      });
      return res;
    } finally {
      ts.cleanup();
    }
  }

  /**
   * @param {string} path
   * @param {{ timeoutMs?: number }} [opts]
   * @returns {Promise<unknown>}
   */
  async function apiJson(path, opts) {
    const res = await apiFetch(path, opts);
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (e) {
      console.error("USPBF apiJson parse error", path, e);
      throw new Error("Invalid JSON from API");
    }
    if (!res.ok) {
      const detail =
        data && typeof data === "object" && data.detail != null
          ? String(data.detail)
          : res.statusText;
      const err = new Error(detail || "Request failed");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  /**
   * POST JSON to same-origin /api/* (nginx injects API key server-side).
   * @param {string} path
   * @param {unknown} body
   * @param {{ timeoutMs?: number, signal?: AbortSignal }} [opts]
   * @returns {Promise<unknown>}
   */
  async function apiPostJson(path, body, opts) {
    const timeoutMs = opts && opts.timeoutMs != null ? opts.timeoutMs : DEFAULT_TIMEOUT_MS;
    const ts = timeoutSignal(timeoutMs, opts && opts.signal ? opts.signal : undefined);
    try {
      const signal = ts.signal;
      const res = await fetch(path, {
        method: "POST",
        credentials: "same-origin",
        signal: signal,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch (e) {
        console.error("USPBF apiPostJson parse error", path, e);
        throw new Error("Invalid JSON from API");
      }
      if (!res.ok) {
        const detail =
          data && typeof data === "object" && data.detail != null
            ? String(data.detail)
            : res.statusText;
        const err = new Error(detail || "Request failed");
        err.status = res.status;
        throw err;
      }
      return data;
    } finally {
      ts.cleanup();
    }
  }

  global.UspbfApi = {
    fetch: apiFetch,
    json: apiJson,
    postJson: apiPostJson,
    DEFAULT_TIMEOUT_MS: DEFAULT_TIMEOUT_MS,
  };
})(typeof window !== "undefined" ? window : globalThis);
