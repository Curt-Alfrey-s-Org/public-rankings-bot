"use strict";
// Unit tests for nginx-config/site/js/api.js (run: node --test tests/js/)
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { loadSiteScript, SITE_JS } = require("./load");

/** fetch stub that never resolves until its signal aborts; records the signal it got. */
function hangingFetch(calls) {
  return function (url, init) {
    calls.push({ url, init });
    return new Promise(function (_resolve, reject) {
      function fail() {
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      }
      if (init.signal.aborted) return fail(); // like real fetch
      init.signal.addEventListener("abort", fail);
    });
  };
}

for (const fn of ["fetch", "postJson"]) {
  const call = (api, opts) => (fn === "fetch" ? api.fetch("/api/news", opts) : api.postJson("/api/ai-narrative/demo-ask", { q: 1 }, opts));

  test(`${fn}: timeout still applies when the caller passes its own signal`, async () => {
    const calls = [];
    const ctx = loadSiteScript("api.js", { fetch: hangingFetch(calls) });
    const caller = new AbortController(); // never aborted by the caller
    const started = Date.now();
    await assert.rejects(call(ctx.UspbfApi, { timeoutMs: 50, signal: caller.signal }), { name: "AbortError" });
    assert.ok(Date.now() - started < 2000, "request should be aborted by the timeout");
    assert.equal(caller.signal.aborted, false, "caller signal must not be aborted by us");
  });

  test(`${fn}: caller abort still cancels the request`, async () => {
    const calls = [];
    const ctx = loadSiteScript("api.js", { fetch: hangingFetch(calls) });
    const caller = new AbortController();
    const p = call(ctx.UspbfApi, { timeoutMs: 60000, signal: caller.signal });
    setTimeout(() => caller.abort(), 10);
    await assert.rejects(p, { name: "AbortError" });
  });

  test(`${fn}: already-aborted caller signal aborts immediately`, async () => {
    const calls = [];
    const ctx = loadSiteScript("api.js", { fetch: hangingFetch(calls) });
    const caller = new AbortController();
    caller.abort();
    await assert.rejects(call(ctx.UspbfApi, { timeoutMs: 60000, signal: caller.signal }), { name: "AbortError" });
    assert.equal(calls[0].init.signal.aborted, true);
  });

  test(`${fn}: default timeout without caller signal`, async () => {
    const calls = [];
    const ctx = loadSiteScript("api.js", { fetch: hangingFetch(calls) });
    await assert.rejects(call(ctx.UspbfApi, { timeoutMs: 20 }), { name: "AbortError" });
  });
}

test("json: parses a successful response", async () => {
  const ctx = loadSiteScript("api.js", {
    fetch: async () => ({ ok: true, status: 200, statusText: "OK", text: async () => '{"a":1}' }),
  });
  const data = await ctx.UspbfApi.json("/api/news");
  assert.equal(data.a, 1);
});

test("maintenance/js/api.js is identical to site/js/api.js", () => {
  const maint = path.join(SITE_JS, "..", "..", "maintenance", "js", "api.js");
  assert.equal(fs.readFileSync(maint, "utf8"), fs.readFileSync(path.join(SITE_JS, "api.js"), "utf8"));
});
