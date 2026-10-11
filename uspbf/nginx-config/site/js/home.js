/**
 * Home: upcoming events, news.
 */
(function () {
  "use strict";

  var el = window.UspbfDom.el;
  var escapeHtml = window.UspbfDom.escapeHtml;
  var safeHttpUrl = window.UspbfDom.safeHttpUrl;

  function showError(msg) {
    var box = el("home-error");
    if (!box) return;
    box.className = "msg-error";
    box.textContent = msg;
    box.hidden = false;
  }

  async function load() {
    var errBox = el("home-error");
    if (errBox) {
      errBox.hidden = true;
      errBox.textContent = "";
    }
    var api = window.UspbfApi;
    if (!api) {
      showError("API helper not loaded.");
      return;
    }

    try {
      var upcoming = await api.json("/api/tournament-history/upcoming?limit=8");
      var events = (upcoming && upcoming.events) || [];
      var wrap = el("home-upcoming");
      if (wrap) {
        wrap.innerHTML = "";
        if (!events.length) {
          wrap.innerHTML = '<p class="msg-muted">No upcoming events in the feed right now.</p>';
        } else {
          var first = events[0];
          var firstUrl = safeHttpUrl(first.url);
          var card = document.createElement("div");
          card.className = "card";
          card.innerHTML =
            '<span class="badge">Next up</span>' +
            "<h3>" +
            escapeHtml(first.name || "Event") +
            "</h3>" +
            "<p>" +
            escapeHtml(formatEventDate(first)) +
            (first.location ? " · " + escapeHtml(String(first.location)) : "") +
            "</p>" +
            (firstUrl
              ? '<p><a href="' +
                escapeAttr(firstUrl) +
                '" target="_blank" rel="noopener noreferrer">Details ↗</a></p>'
              : "");
          wrap.appendChild(card);
          if (events.length > 1) {
            var list = document.createElement("ul");
            list.className = "msg-muted";
            list.style.marginTop = "1rem";
            list.style.paddingLeft = "1.25rem";
            events.slice(1, 5).forEach(function (ev) {
              var li = document.createElement("li");
              li.textContent = (ev.name || "") + " — " + formatEventDate(ev);
              list.appendChild(li);
            });
            wrap.appendChild(list);
          }
        }
      }
    } catch (e) {
      console.error(e);
      var w = el("home-upcoming");
      if (w) w.innerHTML = '<p class="msg-muted">Upcoming events unavailable.</p>';
    }

    await loadNews();
  }

  async function loadNews() {
    var wrap = el("home-news");
    if (!wrap) return;
    var api = window.UspbfApi;
    if (!api) {
      wrap.innerHTML = '<p class="msg-muted">News unavailable.</p>';
      return;
    }
    try {
      var data = await api.json("/api/news?limit=6");
      var articles = (data && data.articles) || [];
      wrap.innerHTML = "";
      if (!articles.length) {
        wrap.innerHTML = '<p class="msg-muted">No headlines at the moment.</p>';
        return;
      }
      articles.forEach(function (a) {
        var title = a.title || "Article";
        var url = safeHttpUrl(a.url) || "#";
        var source = a.source || "";
        var published = formatNewsDate(a.published);
        var summary = (a.summary || "").trim();
        var item = document.createElement("article");
        item.className = "news-item card";
        var meta = document.createElement("div");
        meta.className = "news-item__meta";
        if (source) {
          var badge = document.createElement("span");
          badge.className = "news-source";
          badge.textContent = source;
          meta.appendChild(badge);
        }
        if (published) {
          var timeEl = document.createElement("time");
          timeEl.className = "news-item__date";
          timeEl.setAttribute("datetime", a.published || "");
          timeEl.textContent = published;
          meta.appendChild(timeEl);
        }
        var h = document.createElement("h3");
        h.className = "news-item__title";
        var link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = title;
        h.appendChild(link);
        item.appendChild(meta);
        item.appendChild(h);
        if (summary) {
          var p = document.createElement("p");
          p.className = "news-item__summary msg-muted";
          p.textContent = summary;
          item.appendChild(p);
        }
        wrap.appendChild(item);
      });
    } catch (e) {
      console.error(e);
      wrap.innerHTML = '<p class="msg-muted">News unavailable.</p>';
    }
  }

  function formatNewsDate(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch (err) {
      return "";
    }
  }

  function formatEventDate(ev) {
    return String(ev.start_date || ev.date || ev.event_date || "").trim() || "TBA";
  }

  function escapeAttr(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function boot() {
    load();
    if (window.UspbfLive && typeof window.UspbfLive.subscribe === "function") {
      window.UspbfLive.subscribe(function () {
        load();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
