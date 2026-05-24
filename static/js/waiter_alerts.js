/**
 * Kitchen-ready alerts: WebSocket + HTTP poll fallback (mobile), sound, toast, notification.
 */
(function () {
  const staffId = window.BARESTO_WAITER_ID;
  const pollUrl = window.BARESTO_ALERTS_POLL_URL;
  if (!staffId) return;

  const i18n = window.BARESTO_ALERT_I18N || {};
  let audioCtx = null;
  let audioUnlocked = false;
  let ws = null;
  let wsConnected = false;
  let pollTimer = null;
  const seenAlerts = new Set();
  let alertsBooted = false;
  const pendingGuestCalls = [];

  function bootAlerts() {
    if (alertsBooted) return;
    alertsBooted = true;
    showEnableBanner();
    connectWebSocket();
    startPolling();
  }

  function alertKey(data) {
    return [data.event, data.order_id, data.item_name || "", data.table || ""].join("|");
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

  function playBeepSequence(freqs) {
    try {
      const ctx = getAudioContext();
      let t = ctx.currentTime;
      freqs.forEach((freq, i) => {
        playTone(freq, t, 0.14, 0.2);
        t += 0.13;
      });
    } catch (e) {
      /* ignore */
    }
  }

  function playItemReadySound() {
    playBeepSequence([880, 1046.5]);
    if (navigator.vibrate) {
      navigator.vibrate(120);
    }
  }

  function playOrderReadySound() {
    playBeepSequence([880, 1174.66, 1318.51]);
    if (navigator.vibrate) {
      navigator.vibrate([150, 80, 150, 80, 250]);
    }
  }

  function playGuestCallSound() {
    playBeepSequence([659.25, 783.99, 987.77]);
    if (navigator.vibrate) {
      navigator.vibrate([100, 60, 100, 60, 200]);
    }
  }

  function formatGuestCallMessage(data) {
    const tableLbl = i18n.tableLabel || "Table";
    if (data.table_id && data.table) {
      return tableLbl + " " + data.table;
    }
    if (data.table_label) {
      return tableLbl + " " + data.table_label;
    }
    return i18n.guestCallNoTable || "Guest menu (no table on QR)";
  }

  function isTablesPage() {
    return /^\/tables\/?$/.test(location.pathname);
  }

  function deliverGuestCallToTables(data) {
    window.dispatchEvent(new CustomEvent("baresto-guest-waiter-call", { detail: data }));
    const title = i18n.guestCallTitle || "Customer requests a waiter";
    const message = formatGuestCallMessage(data);
    showToast(title + ": " + message, false);
  }

  function handleGuestWaiterCall(data) {
    if (!data || data.event !== "guest.waiter_call") return;

    const key = [
      data.event,
      data.table_id || "shared",
      data.requested_at || data.table || "",
    ].join("|");
    if (seenAlerts.has(key)) return;
    seenAlerts.add(key);
    if (seenAlerts.size > 100) {
      seenAlerts.clear();
      seenAlerts.add(key);
    }

    playGuestCallSound();

    const title = i18n.guestCallTitle || "Customer requests a waiter";
    const message = formatGuestCallMessage(data);
    showBrowserNotification(title, message);

    if (isTablesPage()) {
      if (!window.__barestoTablesReady) {
        pendingGuestCalls.push(data);
        return;
      }
      deliverGuestCallToTables(data);
      return;
    }

    showToast(title + ": " + message, false);
  }

  function formatMessage(data) {
    const tableLbl = i18n.tableLabel || "Table";
    const table = data.table || data.message || "";
    if (data.event === "order.ready") {
      const suffix = i18n.orderReadySuffix || "order is ready to serve";
      return tableLbl + " " + table + ": " + suffix;
    }
    if (data.event === "order.item_ready") {
      const suffix = i18n.itemReadySuffix || "is ready";
      return tableLbl + " " + table + ": " + (data.item_name || "") + " " + suffix;
    }
    return data.message || table;
  }

  function normalizeKitchenAlert(data) {
    if (!data || !data.event) return null;
    if (data.event === "order.ready" || data.event === "order.item_ready") {
      return data;
    }
    if (data.event === "order_item.updated" && data.status === "ready") {
      return {
        event: "order.item_ready",
        order_id: data.order_id,
        table: data.table,
        item_name: data.item_name || "",
      };
    }
    return null;
  }

  function showToast(message, isOrderReady) {
    let el = document.getElementById("waiter-kitchen-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "waiter-kitchen-toast";
      el.setAttribute("role", "alert");
      document.body.appendChild(el);
    }
    el.className =
      "fixed bottom-20 left-3 right-3 z-[100] mx-auto max-w-md rounded-xl border-2 px-4 py-4 text-center text-base font-bold shadow-xl md:bottom-4 " +
      (isOrderReady
        ? "border-order bg-order text-kitchen"
        : "border-new-order bg-new-order text-kitchen");
    el.textContent = message;
    el.style.display = "block";
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => {
      el.style.display = "none";
    }, isOrderReady ? 10000 : 6000);
  }

  function showBrowserNotification(title, body) {
    if (!("Notification" in window) || Notification.permission !== "granted") {
      return;
    }
    try {
      const n = new Notification(title, { body, tag: "baresto-" + Date.now() });
      n.onclick = () => {
        window.focus();
        n.close();
      };
    } catch (e) {
      /* ignore */
    }
  }

  function handleKitchenAlert(raw) {
    const data = normalizeKitchenAlert(raw);
    if (!data) return;

    const key = alertKey(data);
    if (seenAlerts.has(key)) return;
    seenAlerts.add(key);
    if (seenAlerts.size > 100) {
      seenAlerts.clear();
      seenAlerts.add(key);
    }

    const message = formatMessage(data);
    const isOrderReady = data.event === "order.ready";

    if (isOrderReady) {
      playOrderReadySound();
    } else {
      playItemReadySound();
    }

    const title = isOrderReady
      ? i18n.notificationOrderTitle || "Order ready"
      : i18n.notificationItemTitle || "Dish ready";
    showBrowserNotification(title, message);
    showToast(message, isOrderReady);
    window.dispatchEvent(new CustomEvent("baresto-kitchen-ready", { detail: data }));
  }

  function enableAlerts(fromBanner) {
    if (audioUnlocked) return;
    audioUnlocked = true;
    try {
      getAudioContext();
      if (fromBanner) {
        playItemReadySound();
      }
    } catch (e) {
      /* ignore */
    }
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    const btn = document.getElementById("waiter-enable-alerts");
    if (btn) btn.style.display = "none";
    try {
      localStorage.setItem("baresto_alerts_enabled", "1");
    } catch (e) {
      /* ignore */
    }
  }

  function showEnableBanner() {
    if (localStorage.getItem("baresto_alerts_enabled") === "1") {
      return;
    }
    if (document.getElementById("waiter-enable-alerts")) return;

    const bar = document.createElement("button");
    bar.type = "button";
    bar.id = "waiter-enable-alerts";
    bar.className =
      "fixed top-14 left-3 right-3 z-[90] mx-auto max-w-md rounded-xl border-2 border-order bg-order px-4 py-3 text-center text-sm font-bold text-kitchen shadow-lg";
    bar.textContent = i18n.enableAlerts || "Tap to enable sound & alerts";
    bar.addEventListener("click", () => enableAlerts(true));
    document.body.appendChild(bar);
  }

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws/waiter/" + staffId + "/");

    ws.onopen = () => {
      wsConnected = true;
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        handleGuestWaiterCall(data);
        handleKitchenAlert(data);
      } catch (e) {
        /* ignore */
      }
    };

    ws.onclose = () => {
      wsConnected = false;
      setTimeout(connectWebSocket, 2500);
    };

    ws.onerror = () => {
      wsConnected = false;
    };
  }

  async function pollAlerts() {
    if (!pollUrl) return;
    try {
      const res = await fetch(pollUrl, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) return;
      const body = await res.json();
      (body.alerts || []).forEach((alert) => {
        handleGuestWaiterCall(alert);
        handleKitchenAlert(alert);
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

  document.addEventListener("click", () => enableAlerts(false), { once: true, passive: true });
  document.addEventListener("touchstart", () => enableAlerts(false), { once: true, passive: true });

  window.addEventListener("baresto-tables-ready", () => {
    window.__barestoTablesReady = true;
    pendingGuestCalls.splice(0).forEach(deliverGuestCallToTables);
    bootAlerts();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (isTablesPage() && !window.__barestoTablesReady) return;
    if (alertsBooted) {
      connectWebSocket();
      pollAlerts();
    }
  });

  if (isTablesPage()) {
  // Wait for Alpine tables UI before polling — otherwise alerts are consumed with no listener.
    window.setTimeout(bootAlerts, 8000);
  } else {
    bootAlerts();
  }
})();
