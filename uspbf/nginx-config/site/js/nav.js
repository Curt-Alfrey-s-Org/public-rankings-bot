/**
 * Inject shared header + footer. Expects #site-nav and #site-footer.
 */
(function () {
  "use strict";

  var path = window.location.pathname || "/";
  function active(href) {
    if (href === "/" || href === "/index.html") {
      return path === "/" || path.endsWith("/index.html") ? " is-active" : "";
    }
    var file = href.replace(/^\//, "");
    return path.endsWith("/" + file) || path.endsWith(file) ? " is-active" : "";
  }

  var noticeHtml =
    '<div class="site-notice" role="status" aria-live="polite">' +
    '<p class="site-notice__text">' +
    "<strong>Account creation is not open yet.</strong> " +
    "This site is live for news, rankings, and information only. " +
    'Please do not register for a new account&mdash;see <a href="/join.html">Join &amp; sign in</a> for what is available today.' +
    "</p>" +
    "</div>";

  var navHtml =
    '<div class="site-header__inner">' +
    '<div class="site-brand">' +
    '<span class="site-brand__org">United States Pro Billiards Federation</span>' +
    '<a class="site-brand__name" href="/">USPBF</a>' +
    "</div>" +
    '<nav class="site-nav" aria-label="Main">' +
    '<a class="' +
    active("/") +
    '" href="/">Home</a>' +
    '<a class="' +
    active("/rankings.html") +
    '" href="/rankings.html">Rankings</a>' +
    '<a class="' +
    active("/tournaments.html") +
    '" href="/tournaments.html">Tournaments</a>' +
    '<a class="' +
    active("/players.html") +
    '" href="/players.html">Players</a>' +
    '<a class="' +
    active("/join.html") +
    '" href="/join.html">Join</a>' +
    '<a class="' +
    active("/rules.html") +
    '" href="/rules.html">Rules</a>' +
    '<a class="' +
    active("/about.html") +
    '" href="/about.html">About</a>' +
    "</nav>" +
    "</div>";

  var footerHtml =
    "<p>" +
    '<a href="https://www.probilliardssoftware.com/" target="_blank" rel="noopener noreferrer">Pro Billiards Software</a>' +
    " — USPBF tournament &amp; rankings platform · " +
    '<a href="/join.html">Join</a>' +
    "</p>";

  function run() {
    var navEl = document.getElementById("site-nav");
    var footEl = document.getElementById("site-footer");
    if (navEl) {
      navEl.className = "site-header";
      navEl.innerHTML = noticeHtml + navHtml;
    }
    if (footEl) {
      footEl.innerHTML = footerHtml;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
