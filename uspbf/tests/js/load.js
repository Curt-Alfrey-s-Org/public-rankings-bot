"use strict";
// Load a browser IIFE from nginx-config/site/js into an isolated vm context (no DOM needed).
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SITE_JS = path.join(__dirname, "..", "..", "nginx-config", "site", "js");

function loadSiteScript(file, globals) {
  const context = vm.createContext(
    Object.assign(
      { AbortController, URL, setTimeout, clearTimeout, console },
      globals || {}
    )
  );
  vm.runInContext(fs.readFileSync(path.join(SITE_JS, file), "utf8"), context, { filename: file });
  return context;
}

module.exports = { loadSiteScript, SITE_JS };
