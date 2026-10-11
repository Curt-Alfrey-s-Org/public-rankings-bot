/**
 * About page: load capability list from API; refresh on live signal.
 */
(function () {
  "use strict";

  async function refresh() {
    if (typeof window.UspbfLoadCapabilities === "function") {
      await window.UspbfLoadCapabilities("about-capabilities");
    }
  }

  function boot() {
    void refresh();
    if (window.UspbfLive && typeof window.UspbfLive.subscribe === "function") {
      window.UspbfLive.subscribe(function () {
        void refresh();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
