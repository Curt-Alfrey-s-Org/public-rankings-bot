"use strict";
// Out-of-order API responses must not overwrite newer results (review 2026-09-26).
// rankings.js / tournaments.js run against a tiny fake DOM; UspbfApi.json is stubbed with
// promises the test resolves in reverse order.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { SITE_JS } = require("./load");

function fakeElement() {
  let text = "";
  return {
    // escapeHtml() (dom-utils.js) relies on textContent -> innerHTML escaping.
    get textContent() { return text; },
    set textContent(v) {
      text = String(v);
      this.innerHTML = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },
    innerHTML: "", hidden: false, disabled: false, value: "", max: "",
    children: [], listeners: {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); this.innerHTML += c.innerHTML || ""; return c; },
  };
}

function setup(files) {
  const els = {};
  const pending = [];
  const window = {
    UspbfApi: {
      json(url) {
        return new Promise((resolve, reject) => pending.push({ url, resolve, reject }));
      },
    },
  };
  const document = {
    readyState: "complete",
    getElementById: (id) => (els[id] = els[id] || fakeElement()),
    createElement: () => fakeElement(),
    addEventListener() {},
  };
  window.document = document;
  const ctx = vm.createContext({ window, document, setTimeout, clearTimeout, console: { error() {}, warn() {}, log() {} } });
  for (const f of files) vm.runInContext(fs.readFileSync(path.join(SITE_JS, f), "utf8"), ctx, { filename: f });
  return { els, pending, el: document.getElementById };
}

const flush = () => new Promise((r) => setImmediate(r));

test("rankings: a late response for an old filter does not replace the newer table", async () => {
  const { pending, el } = setup(["dom-utils.js", "rankings-systems.js", "rankings.js"]);
  await flush();
  // init() started player-name hints + first table load
  const first = pending.find((p) => p.url.startsWith("/api/rankings/wpba-women"));
  first.resolve({ rankings: [], total: 0 });
  await flush();
  const input = el("rankings-player-search");
  input.value = "Smi";
  input.listeners.input[0]();
  await new Promise((r) => setTimeout(r, 320));
  input.value = "Smith";
  input.listeners.input[0]();
  await new Promise((r) => setTimeout(r, 320));
  const old = pending.find((p) => p.url.includes("search=Smi&") || p.url.endsWith("search=Smi"));
  const newer = pending.find((p) => p.url.includes("search=Smith"));
  assert.ok(old && newer, "both searches were requested");
  newer.resolve({ rankings: [{ rank: 1, player_name: "Jane Smith", points: 10 }], total: 1 });
  await flush();
  old.resolve({ rankings: [{ rank: 7, player_name: "Bob Smiley", points: 3 }], total: 1 });
  await flush();
  const html = el("rankings-body").innerHTML;
  assert.match(html, /Jane Smith/);
  assert.doesNotMatch(html, /Bob Smiley/);
});

test("tournaments: a late search response does not replace newer history rows", async () => {
  const { pending, el } = setup(["dom-utils.js", "tournaments.js"]);
  // refreshAll(): years -> upcoming -> leaderboard -> history, sequentially
  for (const key of ["/years", "/upcoming", "/leaderboard-results", "/tournaments?"]) {
    await flush();
    const p = pending.find((x) => x.url.includes(key) && !x.done);
    p.done = true;
    p.resolve(key === "/years" ? { years: [] } : key === "/upcoming" ? { events: [] } : { tournaments: [] });
  }
  await flush();
  await flush();
  const search = el("tournament-search");
  search.value = "open";
  search.listeners.input[0]();
  await new Promise((r) => setTimeout(r, 330));
  search.value = "";
  search.listeners.input[0]();
  await new Promise((r) => setTimeout(r, 330));
  const old = pending.find((p) => p.url.includes("/search?q=open"));
  const newer = pending.filter((p) => p.url.includes("/tournaments?")).pop();
  assert.ok(old && newer && !newer.done, "both requests were made");
  newer.resolve({ tournaments: [{ name: "Newest Cup", date: "2026-09-01" }] });
  await flush();
  old.resolve({ results: [{ name: "Stale Open", date: "2020-01-01" }] });
  await flush();
  const html = el("tournaments-history-body").innerHTML;
  assert.match(html, /Newest Cup/);
  assert.doesNotMatch(html, /Stale Open/);
});
