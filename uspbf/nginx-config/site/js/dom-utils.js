/**
 * Shared DOM helpers for USPBF static pages (single copy; no duplicated utilities per page).
 */
(function (global) {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  /**
   * Return an absolute http(s) URL for use in href, or "" if the value is empty or uses any
   * other scheme (javascript:, data:, vbscript:, ...). API-supplied links (event / news URLs)
   * must go through this before being placed in an href (review 2026-09-25).
   * @param {unknown} value
   * @returns {string}
   */
  function safeHttpUrl(value) {
    if (value == null) return "";
    var s = String(value).trim();
    if (!s) return "";
    try {
      var base = global.location && global.location.href ? global.location.href : "http://localhost/";
      var u = new URL(s, base);
      if (u.protocol === "http:" || u.protocol === "https:") return u.href;
    } catch (e) {
      /* invalid URL */
    }
    return "";
  }

  global.UspbfDom = {
    el: el,
    escapeHtml: escapeHtml,
    safeHttpUrl: safeHttpUrl,
  };
})(typeof window !== "undefined" ? window : globalThis);
