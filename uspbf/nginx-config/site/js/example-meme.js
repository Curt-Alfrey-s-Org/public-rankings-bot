/**
 * Example Example "box of scraps" meme clip — homepage easter egg.
 * Autoplays muted/inline and replays from the start every 10s
 * (mirrors rankings-bot CurtisAlfreyMeme.tsx).
 *
 * All viewports: fixed bottom-left overlay slides off the left edge when collapsed,
 * with a left-edge reopen handle (localStorage persisted).
 */
(function () {
  "use strict";

  var REPLAY_INTERVAL_MS = 10000;
  var COLLAPSE_STORAGE_KEY = "example_meme_collapsed";
  var COLLAPSED_CLASS = "example-meme--collapsed";

  function setupReplay(video) {
    if (!video) return;

    function replay() {
      try {
        video.currentTime = 0;
      } catch (e) {
        /* seeking before metadata is loaded is harmless */
      }
      var p = video.play();
      if (p && typeof p.catch === "function") {
        p.catch(function () {});
      }
    }

    replay();
    window.setInterval(replay, REPLAY_INTERVAL_MS);
  }

  function setupCollapse(root) {
    if (!root) return;
    var collapseBtn = document.getElementById("example-meme-collapse");
    var handleBtn = document.getElementById("example-meme-handle");

    function apply(collapsed) {
      if (collapsed) {
        root.classList.add(COLLAPSED_CLASS);
      } else {
        root.classList.remove(COLLAPSED_CLASS);
      }
    }

    function persist(collapsed) {
      try {
        window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed));
      } catch (e) {
        /* localStorage unavailable (private mode) — ignore */
      }
    }

    var initial = false;
    try {
      initial = window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
    } catch (e) {
      /* default expanded */
    }
    apply(initial);

    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        apply(true);
        persist(true);
      });
    }
    if (handleBtn) {
      handleBtn.addEventListener("click", function () {
        apply(false);
        persist(false);
      });
    }
  }

  function boot() {
    setupReplay(document.getElementById("example-meme-video"));
    setupCollapse(document.getElementById("example-meme"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
