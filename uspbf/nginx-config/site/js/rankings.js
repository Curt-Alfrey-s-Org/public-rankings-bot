/**
 * Rankings page — system picker, player search, cross-association profile, paginated table.
 */
(function () {
  "use strict";

  var systemsApi = window.UspbfRankingsSystems;
  var SYSTEMS = systemsApi.list;
  var stripCompetitorsPoolPhrase = systemsApi.stripCompetitorsPoolPhrase;
  var renderProfileCards = systemsApi.renderProfileCards;

  var state = {
    system: SYSTEMS[0],
    limit: 100,
    offset: 0,
    playerSearch: "",
    profilePlayer: "",
    total: 0,
  };

  var el = window.UspbfDom.el;
  var escapeHtml = window.UspbfDom.escapeHtml;
  var searchDebounce = null;
  // Request sequence numbers: typing, paging and live updates can start overlapping requests;
  // only the newest one may render (older responses arriving late showed stale rows).
  var tableSeq = 0;
  var profileSeq = 0;

  function rowCells(r) {
    var rank = r.rank != null ? r.rank : r.position != null ? r.position : "—";
    var name = r.player_name || r.name || "—";
    var pts = r.points != null ? r.points : r.total_points != null ? r.total_points : "—";
    var country = r.country || r.nation || "";
    return (
      "<td>" +
      escapeHtml(String(rank)) +
      '</td><td><a href="/players.html?player=' +
      encodeURIComponent(name) +
      '">' +
      escapeHtml(name) +
      "</a></td><td>" +
      escapeHtml(String(pts)) +
      "</td><td>" +
      escapeHtml(String(country)) +
      "</td>"
    );
  }

  function totalPages() {
    return Math.max(1, Math.ceil(state.total / state.limit));
  }

  function currentPage() {
    return Math.floor(state.offset / state.limit) + 1;
  }

  function updatePaginationUi(rowCount) {
    var pages = totalPages();
    var page = currentPage();
    var meta = el("rankings-meta");
    var info = el("rankings-page-info");
    if (meta) {
      var searchNote = state.playerSearch.trim()
        ? ' · filter "' + state.playerSearch.trim() + '"'
        : "";
      meta.textContent =
        "Showing " +
        (state.total ? state.offset + 1 : 0) +
        "–" +
        (state.offset + rowCount) +
        " of " +
        state.total +
        " · " +
        stripCompetitorsPoolPhrase(state.system.label) +
        searchNote;
    }
    if (info) {
      info.textContent = "Page " + page + " of " + pages;
    }
    var first = el("btn-first");
    var prev = el("btn-prev");
    var next = el("btn-next");
    var last = el("btn-last");
    var jump = el("rankings-page-jump");
    if (first) first.disabled = page <= 1;
    if (prev) prev.disabled = state.offset <= 0;
    if (next) next.disabled = state.offset + state.limit >= state.total;
    if (last) last.disabled = page >= pages;
    if (jump) jump.max = String(pages);
  }

  async function loadPlayerProfile(playerName) {
    var section = el("rankings-player-profile");
    var detail = el("rankings-player-profile-detail");
    if (!section || !detail) return;
    var name = (playerName || "").trim();
    var seq = ++profileSeq;
    if (!name) {
      section.hidden = true;
      state.profilePlayer = "";
      return;
    }
    section.hidden = false;
    detail.innerHTML = "<p class=\"msg-muted\">Loading player…</p>";
    try {
      var api = window.UspbfApi;
      var data = await api.json("/api/rankings/player/" + encodeURIComponent(name));
      if (seq !== profileSeq) return;
      state.profilePlayer = data.player_name || name;
      var cards = renderProfileCards(data, escapeHtml);
      if (!cards || cards.indexOf("rankings-profile-card") === -1) {
        detail.innerHTML =
          '<p class="msg-muted">No rankings found for "' +
          escapeHtml(state.profilePlayer) +
          '" across tracked systems.</p>';
        return;
      }
      detail.innerHTML =
        "<h3>" +
        escapeHtml(state.profilePlayer) +
        "</h3>" +
        '<p class="msg-muted">Rankings across all associations where this player appears.</p>' +
        cards +
        '<p class="msg-muted" style="margin-top:1rem">Full ALFa / Fargo detail — <a href="https://www.probilliardssoftware.com/" target="_blank" rel="noopener noreferrer">probilliardssoftware.com</a> (sign in).</p>';
    } catch (e) {
      if (seq !== profileSeq) return;
      console.error(e);
      detail.innerHTML =
        '<p class="msg-error">' +
        escapeHtml("Could not load player profile. Try another spelling or open the Players page.") +
        "</p>";
    }
  }

  async function loadTable() {
    var api = window.UspbfApi;
    var errEl = el("rankings-error");
    var tbody = el("rankings-body");
    if (!tbody) return;
    var seq = ++tableSeq;
    tbody.innerHTML = '<tr><td colspan="4">Loading…</td></tr>';
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }
    try {
      var q =
        state.system.path +
        "?limit=" +
        encodeURIComponent(String(state.limit)) +
        "&offset=" +
        encodeURIComponent(String(state.offset));
      var filter = state.playerSearch.trim();
      if (filter) {
        q += "&search=" + encodeURIComponent(filter);
      }
      var data = await api.json(q);
      if (seq !== tableSeq) return;
      var rows = (data && data.rankings) || [];
      state.total = (data && data.total) != null ? data.total : rows.length + state.offset;
      tbody.innerHTML = "";
      if (!rows.length) {
        tbody.innerHTML =
          '<tr><td colspan="4" class="msg-muted">No rows for this view.</td></tr>';
      } else {
        rows.forEach(function (r) {
          var tr = document.createElement("tr");
          tr.innerHTML = rowCells(r);
          tbody.appendChild(tr);
        });
      }
      updatePaginationUi(rows.length);
    } catch (e) {
      if (seq !== tableSeq) return;
      console.error(e);
      tbody.innerHTML = "";
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = "Could not load rankings.";
      }
    }
  }

  function goToPage(pageNum) {
    var pages = totalPages();
    var p = Math.max(1, Math.min(pages, pageNum));
    state.offset = (p - 1) * state.limit;
    loadTable();
  }

  async function loadPlayerNameHints() {
    var list = el("rankings-player-names");
    if (!list) return;
    try {
      var data = await window.UspbfApi.json("/api/rankings/player-names?limit=5000");
      var names = (data && data.names) || [];
      list.innerHTML = "";
      names.slice(0, 5000).forEach(function (n) {
        var opt = document.createElement("option");
        opt.value = n;
        list.appendChild(opt);
      });
    } catch (e) {
      console.warn("Player name hints unavailable", e);
    }
  }

  function scheduleTableReload(resetOffset) {
    if (searchDebounce) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(function () {
      searchDebounce = null;
      if (resetOffset) state.offset = 0;
      loadTable();
    }, 280);
  }

  function init() {
    var sel = el("rankings-system");
    if (!sel) return;
    SYSTEMS.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = stripCompetitorsPoolPhrase(s.label);
      sel.appendChild(opt);
    });

    sel.addEventListener("change", function () {
      var id = sel.value;
      state.system =
        SYSTEMS.find(function (x) {
          return x.id === id;
        }) || SYSTEMS[0];
      state.offset = 0;
      loadTable();
    });

    var pageSize = el("rankings-page-size");
    if (pageSize) {
      pageSize.value = String(state.limit);
      pageSize.addEventListener("change", function () {
        state.limit = parseInt(pageSize.value, 10) || 100;
        state.offset = 0;
        loadTable();
      });
    }

    el("btn-first").addEventListener("click", function () {
      goToPage(1);
    });
    el("btn-prev").addEventListener("click", function () {
      goToPage(currentPage() - 1);
    });
    el("btn-next").addEventListener("click", function () {
      goToPage(currentPage() + 1);
    });
    el("btn-last").addEventListener("click", function () {
      goToPage(totalPages());
    });

    var jumpBtn = el("btn-go-page");
    var jumpInput = el("rankings-page-jump");
    if (jumpBtn && jumpInput) {
      jumpBtn.addEventListener("click", function () {
        goToPage(parseInt(jumpInput.value, 10) || 1);
      });
      jumpInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          goToPage(parseInt(jumpInput.value, 10) || 1);
        }
      });
    }

    var playerInput = el("rankings-player-search");
    if (playerInput) {
      playerInput.addEventListener("input", function () {
        state.playerSearch = playerInput.value;
        scheduleTableReload(true);
      });
      playerInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          var v = playerInput.value.trim();
          if (v) loadPlayerProfile(v);
        }
      });
    }

    var findBtn = el("btn-rankings-find-player");
    if (findBtn && playerInput) {
      findBtn.addEventListener("click", function () {
        var v = playerInput.value.trim();
        if (v) loadPlayerProfile(v);
      });
    }

    loadPlayerNameHints();
    loadTable();

    if (window.UspbfLive && typeof window.UspbfLive.subscribe === "function") {
      window.UspbfLive.subscribe(function () {
        loadTable();
        if (state.profilePlayer) loadPlayerProfile(state.profilePlayer);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
