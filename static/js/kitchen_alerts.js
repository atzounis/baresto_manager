/**
 * Kitchen display alerts: WebSocket + HTTP poll fallback, sound, modal, ticket refresh.
 */
(function () {
  const pollUrl = window.BARESTO_KITCHEN_ALERTS_POLL_URL;
  if (!pollUrl) return;

  const i18n = window.BARESTO_KITCHEN_ALERT_I18N || {};
  const SEEN_STORAGE_KEY = "baresto_kitchen_seen_alerts";
  let audioCtx = null;
  let audioUnlocked = false;
  let ws = null;
  let pollTimer = null;
  let reloadTimer = null;
  let alertsBooted = false;
  const seenAlerts = new Set();
  const pendingTickets = [];

  function isKitchenPage() {
    return /^\/kitchen\/?$/.test(location.pathname);
  }

  function loadSeenFromStorage() {
    try {
      const raw = sessionStorage.getItem(SEEN_STORAGE_KEY);
      if (!raw) return;
      JSON.parse(raw).forEach((key) => seenAlerts.add(key));
    } catch (e) {
      /* ignore */
    }
  }

  function persistSeen(key) {
    seenAlerts.add(key);
    if (seenAlerts.size > 100) {
      const trimmed = [...seenAlerts].slice(-50);
      seenAlerts.clear();
      trimmed.forEach((k) => seenAlerts.add(k));
    }
    try {
      sessionStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify([...seenAlerts]));
    } catch (e) {
      /* ignore */
    }
  }

  function bootAlerts() {
    if (alertsBooted) return;
    alertsBooted = true;
    showEnableBanner();
    connectWebSocket();
    startPolling();
  }

  function getAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playTone(freq, start, duration, volume) {
    const ctx = getAudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(volume, start);
    gain.gain.exponentialRampToValueAtTime(0.01, start + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(start);
    osc.stop(start + duration);
  }

  function playNewTicketSound() {
    try {
      const ctx = getAudioContext();
      let t = ctx.currentTime;
      [523.25, 659.25, 783.99, 1046.5].forEach((freq) => {
        playTone(freq, t, 0.18, 0.22);
        t += 0.12;
      });
    } catch (e) {
      /* ignore */
    }
    if (navigator.vibrate) {
      navigator.vibrate([120, 60, 120, 60, 180]);
    }
  }

  function alertKey(data) {
    return [data.event, data.order_id, data.sent_at || data.table || ""].join("|");
  }

  function cancelScheduledReload() {
    clearTimeout(reloadTimer);
    reloadTimer = null;
  }

  function showToast(message) {
    let el = document.getElementById("kitchen-new-ticket-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "kitchen-new-ticket-toast";
      el.setAttribute("role", "alert");
      document.body.appendChild(el);
    }
    el.className =
      "fixed bottom-4 left-3 right-3 z-[100] mx-auto max-w-md rounded-xl border-2 border-new-order bg-new-order px-4 py-4 text-center text-base font-bold text-kitchen shadow-xl";
    el.textContent = message;
    el.style.display = "block";
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => {
      el.style.display = "none";
    }, 8000);
  }

  function showBrowserNotification(title, body) {
    if (!("Notification" in window) || Notification.permission !== "granted") {
      return;
    }
    try {
      const n = new Notification(title, { body, tag: "baresto-kitchen-" + Date.now() });
      n.onclick = () => {
        window.focus();
        n.close();
      };
    } catch (e) {
      /* ignore */
    }
  }

  function scheduleReload(delay) {
    if (window.__barestoKitchenModalOpen) return;
    cancelScheduledReload();
    reloadTimer = setTimeout(() => location.reload(), delay);
  }

  function formatTicketMessage(data) {
    const tableLbl = i18n.tableLabel || "Table";
    const itemsLbl = i18n.itemsLabel || "items";
    const table = data.table || tableLbl;
    return table + " — " + (data.item_count || 0) + " " + itemsLbl;
  }

  function deliverNewTicket(data, options) {
    const playSound = !(options && options.silent);
    if (playSound) {
      playNewTicketSound();
    }
    window.__barestoKitchenModalOpen = true;
    cancelScheduledReload();
    window.dispatchEvent(new CustomEvent("baresto-kitchen-new-ticket", { detail: data }));
    const title = i18n.newTicketTitle || "New order from waiter";
    showToast(title + ": " + formatTicketMessage(data));
    showBrowserNotification(title, formatTicketMessage(data));
  }

  function handleNewTicket(data) {
    if (!data || data.event !== "order.new_ticket") return;

    const key = alertKey(data);
    if (seenAlerts.has(key)) return;
    persistSeen(key);

    if (isKitchenPage() && !window.__barestoKitchenReady) {
      pendingTickets.push(data);
      return;
    }

    deliverNewTicket(data);
  }

  function handleKitchenUpdate(data) {
    if (!data || !data.event) return;
    // order.confirmed always pairs with order.new_ticket — reload only after modal dismiss.
    if (data.event === "order.new_ticket" || data.event === "order.confirmed") return;
    if (window.__barestoKitchenModalOpen) return;
    scheduleReload(400);
  }

  function enableAlerts(fromBanner) {
    if (audioUnlocked) return;
    audioUnlocked = true;
    try {
      getAudioContext();
      if (fromBanner) {
        playNewTicketSound();
      }
    } catch (e) {
      /* ignore */
    }
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    const btn = document.getElementById("kitchen-enable-alerts");
    if (btn) btn.style.display = "none";
    try {
      localStorage.setItem("baresto_kitchen_alerts_enabled", "1");
    } catch (e) {
      /* ignore */
    }
  }

  function showEnableBanner() {
    if (localStorage.getItem("baresto_kitchen_alerts_enabled") === "1") {
      return;
    }
    if (document.getElementById("kitchen-enable-alerts")) return;

    const bar = document.createElement("button");
    bar.type = "button";
    bar.id = "kitchen-enable-alerts";
    bar.className =
      "fixed top-14 left-3 right-3 z-[90] mx-auto max-w-md rounded-xl border-2 border-new-order bg-new-order px-4 py-3 text-center text-sm font-bold text-kitchen shadow-lg";
    bar.textContent = i18n.enableAlerts || "Tap to enable sound & alerts";
    bar.addEventListener("click", () => enableAlerts(true));
    document.body.appendChild(bar);
  }

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws/kitchen/");

    ws.onopen = () => {};

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        handleNewTicket(data);
        handleKitchenUpdate(data);
      } catch (e) {
        /* ignore */
      }
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 2500);
    };
  }

  async function pollAlerts() {
    try {
      const res = await fetch(pollUrl, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) return;
      const body = await res.json();
      (body.alerts || []).forEach((alert) => {
        handleNewTicket(alert);
      });
    } catch (e) {
      /* ignore */
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollAlerts();
    pollTimer = setInterval(pollAlerts, 2000);
  }

  window.barestoKitchenDismissTicket = function () {
    window.__barestoKitchenModalOpen = false;
    scheduleReload(150);
  };

  loadSeenFromStorage();

  document.addEventListener("click", () => enableAlerts(false), { once: true, passive: true });
  document.addEventListener("touchstart", () => enableAlerts(false), { once: true, passive: true });

  window.addEventListener("baresto-kitchen-ready", () => {
    window.__barestoKitchenReady = true;
    const queued = pendingTickets.splice(0);
    if (queued.length) {
      deliverNewTicket(queued[queued.length - 1]);
    }
    bootAlerts();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (isKitchenPage() && !window.__barestoKitchenReady) return;
    if (alertsBooted) {
      connectWebSocket();
      pollAlerts();
    }
  });

  if (isKitchenPage()) {
    window.setTimeout(bootAlerts, 8000);
  } else {
    bootAlerts();
  }
})();
