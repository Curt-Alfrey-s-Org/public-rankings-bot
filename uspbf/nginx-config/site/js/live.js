/**
 * Singleton WebSocket client for rankings-bot live_update messages (same /ws as Pro Billiards app).
 * Debounced refetch callbacks; reconnect with backoff; slow polling if WS stays down.
 */
(function (global) {
  "use strict";

  var TRIGGER_EVENTS = {
    ranking_updated: true,
    cache_invalidated: true,
    tournament_created: true,
    match_score_updated: true,
    rack_completed: true,
  };

  var DEBOUNCE_MS = 400;
  var MAX_RECONNECT = 8;
  var INITIAL_DELAY_MS = 1000;
  var MAX_DELAY_MS = 30000;
  var POLL_MS = 90000;
  var CONNECT_TIMEOUT_MS = 10000;

  var socket = null;
  var callbacks = [];
  var debounceTimer = null;
  var reconnectAttempt = 0;
  var reconnectTimer = null;
  var pollTimer = null;
  var gaveUpWs = false;

  function notifyAll() {
    callbacks.slice().forEach(function (fn) {
      try {
        fn();
      } catch (e) {
        console.error("UspbfLive callback error", e);
      }
    });
  }

  function scheduleRefetch() {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(function () {
      debounceTimer = null;
      notifyAll();
    }, DEBOUNCE_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPolling() {
    if (pollTimer) {
      return;
    }
    pollTimer = setInterval(notifyAll, POLL_MS);
  }

  function scheduleReconnect() {
    if (reconnectTimer) {
      return;
    }
    if (reconnectAttempt >= MAX_RECONNECT) {
      gaveUpWs = true;
      startPolling();
      return;
    }
    var delay = Math.min(INITIAL_DELAY_MS * Math.pow(2, reconnectAttempt), MAX_DELAY_MS);
    delay += Math.random() * 500;
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function connect() {
    if (!global.location || !global.location.host) {
      return;
    }
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    var protocol = global.location.protocol === "https:" ? "wss:" : "ws:";
    var url = protocol + "//" + global.location.host + "/ws";

    try {
      socket = new WebSocket(url);
    } catch (e) {
      console.warn("UspbfLive: WebSocket create failed", e);
      scheduleReconnect();
      return;
    }

    var connectTimeout = setTimeout(function () {
      if (socket && socket.readyState === WebSocket.CONNECTING) {
        try {
          socket.close(1000, "connect timeout");
        } catch (err) {
          /* ignore */
        }
      }
    }, CONNECT_TIMEOUT_MS);

    socket.onopen = function () {
      clearTimeout(connectTimeout);
      reconnectAttempt = 0;
      gaveUpWs = false;
      stopPolling();
    };

    socket.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.type === "ping") {
          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "pong", timestamp: Date.now() }));
          }
          return;
        }
        if (msg.type === "live_update" && msg.event && TRIGGER_EVENTS[msg.event]) {
          scheduleRefetch();
        }
      } catch (err) {
        /* ignore malformed messages */
      }
    };

    socket.onclose = function () {
      clearTimeout(connectTimeout);
      socket = null;
      scheduleReconnect();
    };

    socket.onerror = function () {
      clearTimeout(connectTimeout);
    };
  }

  /**
   * @param {() => void} fn
   * @returns {() => void} unsubscribe
   */
  function subscribe(fn) {
    if (typeof fn !== "function") {
      return function () {};
    }
    callbacks.push(fn);
    if (gaveUpWs) {
      startPolling();
    } else {
      connect();
    }
    return function unsubscribe() {
      var i = callbacks.indexOf(fn);
      if (i !== -1) {
        callbacks.splice(i, 1);
      }
    };
  }

  global.UspbfLive = {
    subscribe: subscribe,
  };
})(typeof window !== "undefined" ? window : globalThis);
