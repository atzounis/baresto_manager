/**
 * Waiter alerts: WebSocket from kitchen + sound + browser notification + on-screen toast.
 */
(function () {
  const staffId = window.BARESTO_WAITER_ID;
  if (!staffId) return;

  const i18n = window.BARESTO_ALERT_I18N || {};
  let audioCtx = null;

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

  function playItemReadySound() {
    try {
      const ctx = getAudioContext();
      const t = ctx.currentTime;
      playTone(880, t, 0.12, 0.12);
      playTone(1046.5, t + 0.1, 0.15, 0.1);
    } catch (e) {
      /* ignore */
    }
  }

  function playOrderReadySound() {
    try {
      const ctx = getAudioContext();
      const t = ctx.currentTime;
      playTone(880, t, 0.1, 0.14);
      playTone(1174.66, t + 0.12, 0.1, 0.14);
      playTone(1318.51, t + 0.24, 0.2, 0.12);
      if (navigator.vibrate) {
        navigator.vibrate([120, 60, 120, 60, 200]);
      }
    } catch (e) {
      /* ignore */
    }
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

  function showToast(message, isOrderReady) {
    let el = document.getElementById("waiter-kitchen-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "waiter-kitchen-toast";
      el.setAttribute("role", "alert");
      el.className =
        "fixed bottom-4 left-4 right-4 z-[100] mx-auto max-w-md rounded-xl border px-4 py-4 text-center text-sm font-semibold shadow-lg transition";
      document.body.appendChild(el);
    }
    el.className =
      "fixed bottom-4 left-4 right-4 z-[100] mx-auto max-w-md rounded-xl border px-4 py-4 text-center text-sm font-semibold shadow-lg " +
      (isOrderReady
        ? "border-order bg-order text-kitchen"
        : "border-new-order bg-new-order text-kitchen");
    el.textContent = message;
    el.style.display = "block";
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => {
      el.style.display = "none";
    }, isOrderReady ? 8000 : 5000);
  }

  function showBrowserNotification(title, body) {
    if (!("Notification" in window) || Notification.permission !== "granted") {
      return;
    }
    try {
      const n = new Notification(title, {
        body,
        tag: "baresto-kitchen-" + (body || "").slice(0, 40),
        requireInteraction: false,
      });
      n.onclick = () => {
        window.focus();
        n.close();
      };
    } catch (e) {
      /* ignore */
    }
  }

  function requestNotificationPermission() {
    if (!("Notification" in window) || Notification.permission !== "default") {
      return;
    }
    Notification.requestPermission();
  }

  function handleKitchenAlert(data) {
    if (!data || !data.event) return;
    if (data.event !== "order.ready" && data.event !== "order.item_ready") {
      return;
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
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(proto + "://" + location.host + "/ws/waiter/" + staffId + "/");

    ws.onmessage = (ev) => {
      try {
        handleKitchenAlert(JSON.parse(ev.data));
      } catch (e) {
        /* ignore */
      }
    };

    ws.onclose = () => {
      setTimeout(connect, 3000);
    };
  }

  document.addEventListener(
    "click",
    () => {
      getAudioContext();
      requestNotificationPermission();
    },
    { once: true, passive: true }
  );

  connect();
})();
