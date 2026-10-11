/**
 * Turns native <select> elements into type-to-filter comboboxes (good for long lists).
 * Add data-no-searchable on a <select> to keep the native control (e.g. short pickers).
 * Keeps the real <select> in sync and dispatches "change" for existing listeners.
 * Uses MutationObserver so async option updates (e.g. tournament years) stay in sync.
 */
(function () {
  "use strict";

  function escapeAttr(s) {
    return String(s || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function getOptions(select) {
    return Array.prototype.slice.call(select.options).map(function (o) {
      return { value: o.value, text: o.text || o.textContent || "" };
    });
  }

  function selectedLabel(select) {
    var o = select.options[select.selectedIndex];
    return o ? o.text || o.textContent || "" : "";
  }

  function enhance(select) {
    if (!select || select.tagName !== "SELECT" || select.dataset.uspbfSearchable) return;
    if (select.hasAttribute("data-no-searchable")) return;

    select.dataset.uspbfSearchable = "1";
    select.classList.add("uspbf-select-native");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");

    var wrap = document.createElement("div");
    wrap.className = "searchable-select-wrap";
    var parent = select.parentNode;
    parent.insertBefore(wrap, select);
    wrap.appendChild(select);

    var listId = (select.id || "uspbf-sel") + "-listbox";
    var input = document.createElement("input");
    input.type = "text";
    input.className = "searchable-select__input";
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listId);

    if (select.id) {
      var lbl = document.querySelector('label[for="' + escapeAttr(select.id) + '"]');
      if (lbl) {
        if (!lbl.id) {
          lbl.id = select.id + "-label";
        }
        input.setAttribute("aria-labelledby", lbl.id);
      }
    }

    var list = document.createElement("ul");
    list.className = "searchable-select__list";
    list.id = listId;
    list.setAttribute("role", "listbox");
    list.hidden = true;

    wrap.appendChild(input);
    wrap.appendChild(list);

    var open = false;
    var activeIndex = -1;
    var flatOpts = [];
    /** Until the user types, show every option (easier to browse after focus). */
    var browseAll = false;

    function norm(s) {
      return String(s || "")
        .toLowerCase()
        .replace(/\s+/g, " ")
        .trim();
    }

    function setOpen(v) {
      open = v;
      list.hidden = !v;
      input.setAttribute("aria-expanded", v ? "true" : "false");
    }

    function syncInputFromSelect() {
      input.value = selectedLabel(select);
    }

    function renderList() {
      var q = browseAll ? "" : norm(input.value);
      flatOpts = getOptions(select).filter(function (o) {
        return !q || norm(o.text).indexOf(q) !== -1;
      });
      list.innerHTML = "";
      activeIndex = flatOpts.length ? 0 : -1;
      if (!flatOpts.length) {
        var empty = document.createElement("li");
        empty.className = "searchable-select__empty";
        empty.setAttribute("role", "presentation");
        empty.textContent = "No matches";
        list.appendChild(empty);
        return;
      }
      flatOpts.forEach(function (o, i) {
        var li = document.createElement("li");
        li.className = "searchable-select__option";
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", i === activeIndex ? "true" : "false");
        li.dataset.value = o.value;
        li.textContent = o.text;
        if (i === activeIndex) {
          li.classList.add("is-active");
        }
        list.appendChild(li);
      });
    }

    function applyValue(value) {
      select.value = value;
      if (select.value !== value) {
        for (var i = 0; i < select.options.length; i++) {
          if (select.options[i].value === value) {
            select.selectedIndex = i;
            break;
          }
        }
      }
      browseAll = false;
      syncInputFromSelect();
      setOpen(false);
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function highlightActive() {
      var items = list.querySelectorAll(".searchable-select__option");
      items.forEach(function (li, i) {
        var on = i === activeIndex;
        li.classList.toggle("is-active", on);
        li.setAttribute("aria-selected", on ? "true" : "false");
        if (on) {
          li.scrollIntoView({ block: "nearest" });
        }
      });
    }

    list.addEventListener("mousedown", function (e) {
      e.preventDefault();
    });

    list.addEventListener("click", function (e) {
      var li = e.target && e.target.closest(".searchable-select__option");
      if (!li || !wrap.contains(li)) return;
      applyValue(li.dataset.value);
    });

    input.addEventListener("focus", function () {
      syncInputFromSelect();
      browseAll = true;
      renderList();
      setOpen(true);
      try {
        input.select();
      } catch (ignore) {}
    });

    input.addEventListener("input", function () {
      browseAll = false;
      renderList();
      setOpen(true);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        browseAll = false;
        syncInputFromSelect();
        setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!open) {
          browseAll = true;
          renderList();
          setOpen(true);
        }
        if (flatOpts.length) {
          activeIndex = Math.min(activeIndex + 1, flatOpts.length - 1);
          highlightActive();
        }
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!open) {
          browseAll = true;
          renderList();
          setOpen(true);
        }
        if (flatOpts.length) {
          activeIndex = Math.max(activeIndex - 1, 0);
          highlightActive();
        }
        return;
      }
      if (e.key === "Enter") {
        if (open && activeIndex >= 0 && flatOpts[activeIndex]) {
          e.preventDefault();
          applyValue(flatOpts[activeIndex].value);
        }
        return;
      }
      if (e.key === "Tab") {
        setOpen(false);
        syncInputFromSelect();
      }
    });

    input.addEventListener("blur", function () {
      window.setTimeout(function () {
        if (!wrap.contains(document.activeElement)) {
          browseAll = false;
          setOpen(false);
          syncInputFromSelect();
        }
      }, 0);
    });

    var mo = new MutationObserver(function () {
      syncInputFromSelect();
      if (open) {
        renderList();
      }
    });
    mo.observe(select, { childList: true, subtree: true, characterData: true });

    syncInputFromSelect();
  }

  function scan() {
    document.querySelectorAll("select").forEach(enhance);
  }

  function run() {
    scan();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }

  window.UspbfSearchableSelect = { scan: scan, enhance: enhance };
})();
