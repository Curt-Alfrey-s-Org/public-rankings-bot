/**
 * Tournaments — upcoming + history with year filter, search, and pagination.
 */
(function () {
  "use strict";

  var el = window.UspbfDom.el;
  var escapeHtml = window.UspbfDom.escapeHtml;
  var safeHttpUrl = window.UspbfDom.safeHttpUrl;

  var allYears = [];
  var historyRows = [];
  var historyPage = 1;
  var historyPageSize = 50;
  var historySearchQuery = "";

  async function loadYears() {
    var api = window.UspbfApi;
    var sel = el("tournament-year");
    try {
      var data = await api.json("/api/tournament-history/years");
      var years = (data && data.years) || [];
      allYears = years
        .map(function (y) {
          return parseInt(String(y), 10);
        })
        .filter(function (y) {
          return !isNaN(y);
        })
        .sort(function (a, b) {
          return b - a;
        });
      sel.innerHTML = '<option value="">All years</option>';
      allYears.forEach(function (y) {
        var opt = document.createElement("option");
        opt.value = String(y);
        opt.textContent = String(y);
        sel.appendChild(opt);
      });
    } catch (e) {
      console.error(e);
      sel.innerHTML = '<option value="">All years</option>';
    }
  }

  async function loadLeaderboardResults() {
    var api = window.UspbfApi;
    var tbody = el("tournaments-leaderboard-body");
    if (!tbody) return;
    try {
      var lb = await api.json("/api/tournament-history/leaderboard-results?limit=15");
      var rows = (lb && lb.tournaments) || [];
      tbody.innerHTML = "";
      if (!rows.length) {
        var tr0 = document.createElement("tr");
        tr0.innerHTML = '<td colspan="5" class="msg-muted">No recent results.</td>';
        tbody.appendChild(tr0);
        return;
      }
      rows.forEach(function (r) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          escapeHtml(String(r.tournament_date || "")) +
          "</td><td>" +
          escapeHtml(String(r.tournament_name || "")) +
          "</td><td>" +
          escapeHtml(String(r.association || "")) +
          "</td><td>" +
          escapeHtml(String(r.first_place_name || "—")) +
          "</td><td>" +
          escapeHtml(String(r.second_place_name || "—")) +
          "</td>";
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
      tbody.innerHTML = '<tr><td colspan="5" class="msg-muted">Results unavailable.</td></tr>';
    }
  }

  async function loadUpcoming() {
    var api = window.UspbfApi;
    var wrap = el("tournaments-upcoming");
    try {
      var data = await api.json("/api/tournament-history/upcoming?limit=50");
      var events = (data && data.events) || [];
      wrap.innerHTML = "";
      if (!events.length) {
        wrap.innerHTML = '<p class="msg-muted">No upcoming events listed.</p>';
        return;
      }
      var ul = document.createElement("ul");
      ul.className = "rules-list";
      events.forEach(function (ev) {
        var li = document.createElement("li");
        var name = ev.name || "Event";
        var when = ev.start_date || ev.date || ev.event_date || "";
        var loc = ev.location ? " · " + ev.location : "";
        var evUrl = safeHttpUrl(ev.url);
        li.innerHTML =
          "<strong>" +
          escapeHtml(name) +
          "</strong><br><span class=\"msg-muted\">" +
          escapeHtml(String(when) + loc) +
          "</span>" +
          (evUrl
            ? ' <a href="' +
              evUrl
                .replace(/&/g, "&amp;")
                .replace(/"/g, "&quot;") +
              '" target="_blank" rel="noopener noreferrer">Link ↗</a>'
            : "");
        ul.appendChild(li);
      });
      wrap.appendChild(ul);
    } catch (e) {
      console.error(e);
      wrap.innerHTML = '<p class="msg-muted">Could not load upcoming events.</p>';
    }
  }

  function normalizeHistoryRow(r) {
    return {
      date: r.date || r.tournament_date || "",
      name: r.name || r.tournament_name || "",
      association: r.association || "",
      location: r.location || "",
    };
  }

  function renderHistoryPagination(total, totalPages) {
    var wrap = el("tournaments-history-pagination");
    var info = el("tournaments-history-page-info");
    var prev = el("tournaments-history-prev");
    var next = el("tournaments-history-next");
    if (!wrap) return;
    if (!totalPages || totalPages <= 1) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    if (info) {
      info.textContent =
        "Page " + historyPage + " of " + totalPages + " (" + total + " events)";
    }
    if (prev) prev.disabled = historyPage <= 1;
    if (next) next.disabled = historyPage >= totalPages;
  }

  function renderHistory() {
    var tbody = el("tournaments-history-body");
    tbody.innerHTML = "";
    var filtered = historyRows.map(normalizeHistoryRow);
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="msg-muted">No matches.</td></tr>';
      renderHistoryPagination(0, 0);
      return;
    }
    var totalPages = Math.ceil(filtered.length / historyPageSize);
    if (historyPage > totalPages) historyPage = totalPages;
    if (historyPage < 1) historyPage = 1;
    var start = (historyPage - 1) * historyPageSize;
    filtered.slice(start, start + historyPageSize).forEach(function (r) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        escapeHtml(String(r.date)) +
        "</td><td>" +
        escapeHtml(String(r.name)) +
        "</td><td>" +
        escapeHtml(String(r.association)) +
        "</td><td>" +
        escapeHtml(String(r.location)) +
        "</td>";
      tbody.appendChild(tr);
    });
    renderHistoryPagination(filtered.length, totalPages);
  }

  // Only the newest history request may render (search typing / year change / live refresh
  // overlap; a slow older response used to overwrite newer results).
  var historySeq = 0;

  async function loadHistory() {
    var api = window.UspbfApi;
    var seq = ++historySeq;
    var year = el("tournament-year").value;
    var q = (el("tournament-search").value || "").trim();
    var tbody = el("tournaments-history-body");
    tbody.innerHTML = '<tr><td colspan="4">Loading…</td></tr>';
    historySearchQuery = q;
    try {
      if (q.length >= 2) {
        var searchData = await api.json(
          "/api/tournament-history/search?q=" +
            encodeURIComponent(q) +
            "&limit=50"
        );
        if (seq !== historySeq) return;
        historyRows = (searchData && searchData.results) || [];
      } else {
        var url = "/api/tournament-history/tournaments?limit=100";
        if (year) {
          url += "&year=" + encodeURIComponent(year);
        }
        var data = await api.json(url);
        if (seq !== historySeq) return;
        historyRows = (data && data.tournaments) || [];
      }
      historyPage = 1;
      renderHistory();
    } catch (e) {
      if (seq !== historySeq) return;
      console.error(e);
      tbody.innerHTML = '<tr><td colspan="4" class="msg-muted">History unavailable.</td></tr>';
    }
  }

  var searchDebounce = null;

  async function refreshAll() {
    await loadYears();
    await loadUpcoming();
    await loadLeaderboardResults();
    await loadHistory();
  }

  async function init() {
    await refreshAll();
    el("tournament-year").addEventListener("change", loadHistory);
    el("tournament-search").addEventListener("input", function () {
      if (searchDebounce) clearTimeout(searchDebounce);
      searchDebounce = setTimeout(function () {
        searchDebounce = null;
        loadHistory();
      }, 300);
    });
    var prev = el("tournaments-history-prev");
    var next = el("tournaments-history-next");
    if (prev) {
      prev.addEventListener("click", function () {
        if (historyPage > 1) {
          historyPage--;
          renderHistory();
        }
      });
    }
    if (next) {
      next.addEventListener("click", function () {
        historyPage++;
        renderHistory();
      });
    }
    if (window.UspbfLive && typeof window.UspbfLive.subscribe === "function") {
      window.UspbfLive.subscribe(function () {
        refreshAll();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
