/**
 * Load public-facing capability cards from /api/login-features (full list, admin rows omitted).
 */
(function (global) {
  "use strict";

  var HIDDEN_TITLES = {
    "Covert Ops": true,
    "User management & roles": true,
    "Refresh, export & backup": true,
    "Health & logs": true,
    "Data input": true,
  };

  global.UspbfLoadCapabilities = async function loadCapabilities(containerId) {
    var wrap = document.getElementById(containerId);
    if (!wrap) return;
    var api = global.UspbfApi;
    if (!api) {
      wrap.innerHTML = '<p class="msg-muted">Feature list unavailable.</p>';
      return;
    }
    try {
      var data = await api.json("/api/login-features?variant=full");
      var full = (data && data.full) || [];
      var visible = full.filter(function (item) {
        var t = item && item.title;
        return t && !HIDDEN_TITLES[t];
      });
      wrap.innerHTML = "";
      if (!visible.length) {
        wrap.innerHTML = '<p class="msg-muted">No public highlights available.</p>';
        return;
      }
      var grid = document.createElement("div");
      grid.className = "capabilities-grid";
      visible.forEach(function (item) {
        var div = document.createElement("div");
        div.className = "capability-item card";
        var h = document.createElement("h3");
        h.className = "capability-item__title";
        h.textContent = item.title || "";
        var p = document.createElement("p");
        p.className = "capability-item__desc msg-muted";
        p.textContent = item.description || "";
        div.appendChild(h);
        div.appendChild(p);
        grid.appendChild(div);
      });
      wrap.appendChild(grid);
    } catch (e) {
      console.error(e);
      wrap.innerHTML = '<p class="msg-muted">Feature list unavailable.</p>';
    }
  };
})(typeof window !== "undefined" ? window : globalThis);
