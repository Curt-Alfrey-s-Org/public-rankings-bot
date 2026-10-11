/**
 * Players — directory + profile from ?player=
 */
(function () {
  "use strict";

  var systemsApi = window.UspbfRankingsSystems;
  var renderProfileCards = systemsApi.renderProfileCards;
  var formatCurrent = systemsApi.formatCurrent;
  var displayLabel = systemsApi.displayLabel;

  var el = window.UspbfDom.el;
  var escapeHtml = window.UspbfDom.escapeHtml;

  var names = [];
  var pageSize = 200;
  var currentPage = 1;

  function refreshFromLive() {
    loadNames().then(function () {
      var params = new URLSearchParams(window.location.search);
      var fromUrl = params.get("player");
      var searchEl = el("player-search");
      var v = (searchEl && searchEl.value.trim()) || fromUrl;
      if (v) {
        loadProfile(v);
      }
    });
  }

  async function loadNames() {
    var api = window.UspbfApi;
    var tbody = el("players-directory-body");
    var err = el("players-error");
    tbody.innerHTML = '<tr><td colspan="2">Loading…</td></tr>';
    if (err) {
      err.hidden = true;
    }
    try {
      var data = await api.json("/api/rankings/player-names?limit=5000");
      names = (data && data.names) || [];
      renderDirectory("");
      var params = new URLSearchParams(window.location.search);
      var p = params.get("player");
      if (p) {
        el("player-search").value = p;
        loadProfile(p);
      }
    } catch (e) {
      console.error(e);
      tbody.innerHTML = '<tr><td colspan="2" class="msg-muted">Directory unavailable.</td></tr>';
      if (err) {
        err.hidden = false;
        err.textContent = "Could not load player directory.";
      }
    }
  }

  function renderDirectory(filter) {
    var tbody = el("players-directory-body");
    var f = (filter || "").trim().toLowerCase();
    tbody.innerHTML = "";
    var list = names.filter(function (n) {
      return !f || String(n).toLowerCase().indexOf(f) !== -1;
    });

    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="2" class="msg-muted">No matches.</td></tr>';
      renderPagination(0, 0, 0);
      return;
    }

    var totalPages = Math.ceil(list.length / pageSize);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    var start = (currentPage - 1) * pageSize;
    list.slice(start, start + pageSize).forEach(function (n) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><a href="/players.html?player=' +
        encodeURIComponent(n) +
        '">' +
        escapeHtml(n) +
        "</a></td>";
      tbody.appendChild(tr);
    });

    renderPagination(currentPage, totalPages, list.length);
  }

  function renderPagination(page, totalPages, total) {
    var wrap = el("players-pagination");
    var info = el("players-page-info");
    var prev = el("players-prev");
    var next = el("players-next");
    if (!wrap || !info || !prev || !next) return;
    if (!totalPages || totalPages <= 1) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    info.textContent = "Page " + page + " of " + totalPages + " (" + total + " players)";
    prev.disabled = page <= 1;
    next.disabled = page >= totalPages;
  }

  // Only the newest profile request may render (a slow earlier lookup could overwrite it).
  var profileSeq = 0;

  async function loadProfile(playerName) {
    var api = window.UspbfApi;
    var seq = ++profileSeq;
    var section = el("player-profile");
    var detail = el("player-profile-detail");
    if (!playerName || !playerName.trim()) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    detail.innerHTML = "<p>Loading…</p>";
    try {
      var path =
        "/api/rankings/player/" + encodeURIComponent(playerName.trim());
      var data = await api.json(path);
      if (seq !== profileSeq) return;
      var cards = renderProfileCards(data, escapeHtml);
      var summaryLines = systemsApi.list
        .map(function (sys) {
          var block = data[sys.profileKey];
          if (!block || !block.current) return null;
          return displayLabel(sys) + ": " + formatCurrent(block);
        })
        .filter(Boolean);

      detail.innerHTML =
        "<h3>" +
        escapeHtml(data.player_name || playerName) +
        "</h3>" +
        (summaryLines.length
          ? '<p class="msg-muted">' + escapeHtml(summaryLines.join(" · ")) + "</p>"
          : "") +
        (cards.indexOf("rankings-profile-card") !== -1
          ? cards
          : '<p class="msg-muted">No ranked positions found in tracked systems.</p>') +
        '<p class="msg-muted" style="margin-top:1rem">Full ALFa / Fargo detail in Pro Billiards Software &mdash; <a href="https://www.probilliardssoftware.com/" target="_blank" rel="noopener noreferrer">probilliardssoftware.com</a> (sign in).</p>';
    } catch (e) {
      if (seq !== profileSeq) return;
      console.error(e);
      detail.innerHTML =
        '<p class="msg-error">' +
        escapeHtml("Could not load player profile.") +
        "</p>";
    }
  }

  function init() {
    loadNames();
    if (window.UspbfLive && typeof window.UspbfLive.subscribe === "function") {
      window.UspbfLive.subscribe(refreshFromLive);
    }
    el("player-search").addEventListener("input", function () {
      currentPage = 1;
      renderDirectory(el("player-search").value);
    });
    el("players-prev").addEventListener("click", function () {
      if (currentPage > 1) {
        currentPage--;
        renderDirectory(el("player-search").value);
      }
    });
    el("players-next").addEventListener("click", function () {
      currentPage++;
      renderDirectory(el("player-search").value);
    });
    el("player-search").addEventListener("change", function () {
      var v = el("player-search").value.trim();
      if (v) {
        window.history.replaceState({}, "", "/players.html?player=" + encodeURIComponent(v));
        loadProfile(v);
      }
    });
    el("btn-player-go").addEventListener("click", function () {
      var v = el("player-search").value.trim();
      if (v) {
        window.location.href = "/players.html?player=" + encodeURIComponent(v);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
