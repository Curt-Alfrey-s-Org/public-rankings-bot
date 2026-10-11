"use strict";
// Unit tests for UspbfDom.safeHttpUrl in nginx-config/site/js/dom-utils.js (run: node --test tests/js/)
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadSiteScript } = require("./load");

const ctx = loadSiteScript("dom-utils.js", { location: { href: "https://example.com/tournaments.html" } });
const safe = ctx.UspbfDom.safeHttpUrl;

test("allows absolute http and https URLs", () => {
  assert.equal(safe("https://example.com/event?id=1"), "https://example.com/event?id=1");
  assert.equal(safe("  http://example.com/a  "), "http://example.com/a");
});

test("resolves relative URLs against the page origin", () => {
  assert.equal(safe("/news/1"), "https://example.com/news/1");
});

test("rejects script and other non-http schemes", () => {
  for (const bad of [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    " javascript:alert(1)",
    "java\tscript:alert(1)",
    "\u0001javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "ftp://example.com/x",
  ]) {
    assert.equal(safe(bad), "", JSON.stringify(bad));
  }
});

test("empty / missing values give empty string", () => {
  assert.equal(safe(null), "");
  assert.equal(safe(undefined), "");
  assert.equal(safe(""), "");
  assert.equal(safe("   "), "");
});

test("escapes quotes/angle brackets via URL serialisation", () => {
  const out = safe('https://example.com/"><img src=x onerror=alert(1)>');
  assert.ok(!out.includes('"') && !out.includes("<") && !out.includes(">"), out);
});
