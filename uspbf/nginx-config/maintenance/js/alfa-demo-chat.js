/**
 * ALFa AI public demo dock — example.com homepage (same-origin POST /api/ai-narrative/demo-ask).
 *
 * All viewports: fixed bottom-right overlay slides off the right edge when collapsed,
 * with a right-edge reopen handle (localStorage persisted).
 */
(function () {
  "use strict";

  var DEMO_PATH = "/api/ai-narrative/demo-ask";
  var AI_TIMEOUT_MS = 120000;
  var COLLAPSE_STORAGE_KEY = "alfa_chat_collapsed";
  var COLLAPSED_CLASS = "alfa-demo--collapsed";

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function mount() {
    if (!window.UspbfApi || typeof window.UspbfApi.postJson !== "function") {
      console.warn("ALFa demo: UspbfApi.postJson missing — load api.js first.");
      return;
    }

    var root = document.createElement("div");
    root.className = "alfa-demo";
    root.id = "alfa-demo-root";
    root.setAttribute("aria-live", "polite");

    root.innerHTML =
      '<div class="alfa-demo__slider">' +
      '  <div class="alfa-demo__panel" id="alfa-demo-panel" role="dialog" aria-label="ALFa AI demo">' +
      '    <div class="alfa-demo__head">' +
      '      <img class="alfa-demo__avatar" src="/branding/alfa-ai-avatar.png?v=20260714" alt="" width="28" height="28" />' +
      '      <div class="alfa-demo__head-text">' +
      '        <div class="alfa-demo__title">ALFa AI</div>' +
      '        <div class="alfa-demo__subtitle">Demo — ask about USPBF, accounts, Pro Billiards Software &amp; tiers</div>' +
      "      </div>" +
      '      <button type="button" class="alfa-demo__close" id="alfa-demo-close" aria-label="Close ALFa AI">✕</button>' +
      "    </div>" +
      '    <div class="alfa-demo__messages" id="alfa-demo-messages"></div>' +
      '    <form class="alfa-demo__form" id="alfa-demo-form">' +
      '      <label class="sr-only" for="alfa-demo-input">Your question</label>' +
      '      <input type="text" id="alfa-demo-input" class="alfa-demo__input" maxlength="500" placeholder="Ask ALFa…" autocomplete="off" />' +
      '      <button type="submit" class="alfa-demo__send" id="alfa-demo-send">Send</button>' +
      "    </form>" +
      "  </div>" +
      '  <button type="button" class="alfa-demo__collapse" id="alfa-demo-collapse" title="Hide chat" aria-label="Hide ALFa AI chat">&rsaquo;</button>' +
      "</div>" +
      '<button type="button" class="alfa-demo__handle" id="alfa-demo-handle" title="Show chat" aria-label="Show ALFa AI chat">' +
      '  <span class="alfa-demo__handle-arrow">&lsaquo;</span>' +
      '  <span class="alfa-demo__handle-label">ALFa</span>' +
      "</button>" +
      '<button type="button" class="alfa-demo__fab" id="alfa-demo-fab" aria-hidden="true" tabindex="-1" hidden></button>';

    document.body.appendChild(root);

    var panel = root.querySelector("#alfa-demo-panel");
    var collapseBtn = root.querySelector("#alfa-demo-collapse");
    var closeBtn = root.querySelector("#alfa-demo-close");
    var handleBtn = root.querySelector("#alfa-demo-handle");
    var form = root.querySelector("#alfa-demo-form");
    var input = root.querySelector("#alfa-demo-input");
    var messagesEl = root.querySelector("#alfa-demo-messages");
    var sendBtn = root.querySelector("#alfa-demo-send");

    panel.hidden = false;

    function applyCollapsed(collapsed) {
      if (collapsed) {
        root.classList.add(COLLAPSED_CLASS);
        panel.setAttribute("aria-hidden", "true");
      } else {
        root.classList.remove(COLLAPSED_CLASS);
        panel.setAttribute("aria-hidden", "false");
      }
    }

    function persistCollapsed(collapsed) {
      try {
        window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed));
      } catch (e) {
        /* ignore */
      }
    }

    var initial = false;
    try {
      initial = window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
    } catch (e) {
      /* default expanded */
    }
    applyCollapsed(initial);

    function collapse() {
      applyCollapsed(true);
      persistCollapsed(true);
      handleBtn.focus();
    }

    // Both the header close button and the side collapse tab hide the panel
    // (the close button was previously never wired up; review 2026-09-25).
    collapseBtn.addEventListener("click", collapse);
    closeBtn.addEventListener("click", collapse);
    handleBtn.addEventListener("click", function () {
      applyCollapsed(false);
      persistCollapsed(false);
      input.focus();
    });

    function appendBubble(role, htmlOrText, isHtml) {
      var wrap = document.createElement("div");
      wrap.className = "alfa-demo__bubble alfa-demo__bubble--" + role;
      if (isHtml) {
        wrap.innerHTML = htmlOrText;
      } else {
        wrap.textContent = htmlOrText;
      }
      messagesEl.appendChild(wrap);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function welcome() {
      if (messagesEl.children.length) return;
      appendBubble(
        "assistant",
        "Hi — I'm ALFa. Ask me about USPBF, how player accounts work, or Pro Billiards Software (tiers, deals, and features). This is a public demo — I don't see your private stats; sign in at probilliardssoftware.com for that.",
        false
      );
    }

    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var q = (input.value || "").trim();
      if (!q) return;

      welcome();
      appendBubble("user", q, false);
      input.value = "";
      sendBtn.disabled = true;
      input.disabled = true;

      var loading = document.createElement("div");
      loading.className = "alfa-demo__bubble alfa-demo__bubble--assistant alfa-demo__bubble--loading";
      loading.textContent = "Thinking…";
      messagesEl.appendChild(loading);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      try {
        /** @type {{ answer?: string; error?: string }} */
        var data = await window.UspbfApi.postJson(DEMO_PATH, { question: q }, { timeoutMs: AI_TIMEOUT_MS });
        loading.remove();
        var text = (data && data.answer) || "";
        var err = (data && data.error) || "";
        if (err && !text) {
          appendBubble("assistant", "Sorry — " + esc(err), true);
        } else {
          appendBubble("assistant", esc(text).replace(/\n/g, "<br/>"), true);
        }
      } catch (e) {
        loading.remove();
        var msg = e && e.message ? String(e.message) : "Something went wrong.";
        appendBubble("assistant", esc(msg), true);
      } finally {
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
