/**
 * Shared ranking system definitions — keep in sync with rankings-bot public routes.
 */
(function (global) {
  "use strict";

  var SYSTEMS = [
    { id: "wpba-women", label: "WPBA Women", path: "/api/rankings/wpba-women", profileKey: "wpba_women" },
    { id: "wpa-women", label: "WPA Women", path: "/api/rankings/wpa-women", profileKey: "wpa_women" },
    { id: "wpa-men", label: "WPA Men", path: "/api/rankings/wpa-men", profileKey: "wpa_men" },
    { id: "wpa-heyball-men", label: "WPA Heyball Men", path: "/api/rankings/wpa-heyball-men", profileKey: "wpa_heyball_men" },
    { id: "wpa-heyball-women", label: "WPA Heyball Women", path: "/api/rankings/wpa-heyball-women", profileKey: "wpa_heyball_women" },
    { id: "fargo-global", label: "Fargo Global", path: "/api/rankings/fargo-global", profileKey: "fargo_global" },
    { id: "wpa-artistic", label: "WPA Artistic", path: "/api/rankings/wpa-artistic", profileKey: "wpa_artistic" },
    { id: "cp-9ball", label: "9-Ball", path: "/api/rankings/cp-9ball", profileKey: "cp_9ball" },
    { id: "cp-10ball", label: "10-Ball", path: "/api/rankings/cp-10ball", profileKey: "cp_10ball" },
    { id: "cp-8ball", label: "8-Ball", path: "/api/rankings/cp-8ball", profileKey: "cp_8ball" },
  ];

  /** Public UI: never show the legacy vendor phrase (internal IDs stay cp-*). */
  function stripCompetitorsPoolPhrase(text) {
    var t = String(text || "")
      .replace(/\bcompetitors\s+pool\s*/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();
    return t || String(text || "").trim();
  }

  function displayLabel(system) {
    return stripCompetitorsPoolPhrase(system && system.label);
  }

  function formatCurrent(block) {
    if (!block || !block.current) return "—";
    var c = block.current;
    var parts = [];
    if (c.rank != null) parts.push("Rank " + c.rank);
    if (c.points != null) parts.push(c.points + " pts");
    return parts.length ? parts.join(" · ") : "—";
  }

  function renderProfileCards(data, escapeHtml) {
    if (!data) return "";
    var html = '<div class="card-grid rankings-profile-grid">';
    SYSTEMS.forEach(function (sys) {
      var block = data[sys.profileKey];
      var current = block && block.current;
      if (!current) return;
      html +=
        '<div class="card rankings-profile-card">' +
        "<h3>" +
        escapeHtml(displayLabel(sys)) +
        "</h3><p>" +
        escapeHtml(formatCurrent(block)) +
        "</p></div>";
    });
    html += "</div>";
    return html;
  }

  global.UspbfRankingsSystems = {
    list: SYSTEMS,
    stripCompetitorsPoolPhrase: stripCompetitorsPoolPhrase,
    displayLabel: displayLabel,
    formatCurrent: formatCurrent,
    renderProfileCards: renderProfileCards,
  };
})(typeof window !== "undefined" ? window : globalThis);
