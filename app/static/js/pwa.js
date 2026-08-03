/*
 * نصب اپ الگو هاب روی صفحهٔ اصلی گوشی (PWA) + اعلان‌ها.
 *
 * این فایل در همهٔ صفحات هاب لود می‌شود؛ سرویس‌وورکر را با دامنهٔ «/» ثبت
 * می‌کند (پس ژورنال در /journal هم پوشش داده می‌شود) و یک نوار توصیهٔ
 * نصب نمایش می‌دهد (با راهنمای جداگانه برای آیفون).
 */
(function () {
  "use strict";

  var DISMISS_KEY = "ah-pwa-dismissed-at";
  var DISMISS_DAYS = 7;

  function isStandalone() {
    return (
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true
    );
  }

  function inTelegram() {
    return !!(window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData);
  }

  function isIos() {
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  }

  function dismissedRecently() {
    try {
      var at = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
      return at > 0 && Date.now() - at < DISMISS_DAYS * 86400000;
    } catch (e) {
      return false;
    }
  }

  function remember() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch (e) {}
  }

  /* ── ثبت سرویس‌وورکر ────────────────────────────── */
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }

  /* ── نوار توصیهٔ نصب ────────────────────────────── */
  var deferred = null;
  var bar = null;

  function styleTag() {
    if (document.getElementById("ah-pwa-style")) return;
    var css =
      ".ah-pwa{position:fixed;z-index:9999;right:12px;left:12px;bottom:calc(78px + env(safe-area-inset-bottom));" +
      "border-radius:18px;padding:14px 16px;display:flex;align-items:center;gap:12px;direction:rtl;" +
      "background:var(--surface,#0f2336);color:var(--text,#e6eef7);border:1px solid var(--border,#1e3a52);" +
      "box-shadow:0 18px 44px -18px rgba(0,0,0,.55);animation:ah-pwa-in .35s ease}" +
      "@keyframes ah-pwa-in{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}" +
      ".ah-pwa__icon{width:44px;height:44px;border-radius:14px;flex:0 0 auto;" +
      "background:linear-gradient(135deg,#4ED9CC,#19C3B3 45%,#128F84);display:grid;place-items:center;" +
      "color:#04201d;font-weight:800;font-size:15px}" +
      ".ah-pwa__txt{flex:1 1 auto;min-width:0}" +
      ".ah-pwa__t{font-weight:800;font-size:14px}" +
      ".ah-pwa__d{font-size:12px;opacity:.75;line-height:1.9;margin-top:2px}" +
      ".ah-pwa__btn{border:0;cursor:pointer;border-radius:12px;padding:9px 16px;font-weight:800;font-size:13px;" +
      "font-family:inherit;color:#04201d;background:linear-gradient(135deg,#4ED9CC,#19C3B3 45%,#128F84)}" +
      ".ah-pwa__x{border:0;background:transparent;color:inherit;opacity:.55;cursor:pointer;font-size:18px;" +
      "line-height:1;padding:4px 6px;font-family:inherit}" +
      "@media(min-width:768px){.ah-pwa{right:auto;left:20px;bottom:20px;max-width:380px}}";
    var s = document.createElement("style");
    s.id = "ah-pwa-style";
    s.textContent = css;
    document.head.appendChild(s);
  }

  function close() {
    remember();
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
    bar = null;
  }

  function showBar(mode) {
    if (bar || isStandalone() || inTelegram() || dismissedRecently()) return;
    styleTag();

    bar = document.createElement("div");
    bar.className = "ah-pwa";

    var icon = document.createElement("div");
    icon.className = "ah-pwa__icon";
    icon.textContent = "AH";

    var txt = document.createElement("div");
    txt.className = "ah-pwa__txt";

    var t = document.createElement("div");
    t.className = "ah-pwa__t";
    t.textContent = "الگو هاب را روی صفحهٔ اصلی گوشی‌تان نصب کنید";

    var d = document.createElement("div");
    d.className = "ah-pwa__d";
    d.textContent =
      mode === "ios"
        ? "در سافاری، دکمهٔ «اشتراک‌گذاری» را بزنید و گزینهٔ «افزودن به صفحهٔ اصلی» را انتخاب کنید."
        : "ژورنال تریدینگ و مدیریت سرمایه، در یک اپ — سریع‌تر، تمام‌صفحه و همیشه دم‌دست.";

    txt.appendChild(t);
    txt.appendChild(d);

    bar.appendChild(icon);
    bar.appendChild(txt);

    if (mode === "prompt") {
      var btn = document.createElement("button");
      btn.className = "ah-pwa__btn";
      btn.type = "button";
      btn.textContent = "نصب اپ";
      btn.addEventListener("click", function () {
        if (!deferred) return close();
        deferred.prompt();
        deferred.userChoice.finally(function () {
          deferred = null;
          close();
        });
      });
      bar.appendChild(btn);
    }

    var x = document.createElement("button");
    x.className = "ah-pwa__x";
    x.type = "button";
    x.setAttribute("aria-label", "بستن");
    x.textContent = "✕";
    x.addEventListener("click", close);
    bar.appendChild(x);

    document.body.appendChild(bar);
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferred = e;
    setTimeout(function () {
      showBar("prompt");
    }, 2500);
  });

  window.addEventListener("appinstalled", function () {
    remember();
    if (bar) close();
  });

  // آیفون/آیپد: مرورگر پرامپت نصب ندارد؛ راهنمای دستی نمایش می‌دهیم.
  if (isIos()) {
    window.addEventListener("load", function () {
      setTimeout(function () {
        showBar("ios");
      }, 3000);
    });
  }

  /* ── اعلان‌ها ───────────────────────────────────── */
  function enableNotifications() {
    if (!("Notification" in window) || !navigator.serviceWorker) {
      return Promise.resolve("unsupported");
    }
    return Notification.requestPermission().then(function (perm) {
      if (perm === "granted") {
        navigator.serviceWorker.ready.then(function (reg) {
          reg.showNotification("الگو هاب", {
            body: "اعلان‌ها فعال شد — هشدارهای بازار و یادآوری ثبت ژورنال را دریافت می‌کنید.",
            icon: "/static/img/pwa-icon.svg",
            dir: "rtl",
            lang: "fa",
            data: { url: "/" },
          });
        });
      }
      return perm;
    });
  }

  window.AlgoHubPWA = {
    isStandalone: isStandalone,
    showInstallBar: function () {
      try {
        localStorage.removeItem(DISMISS_KEY);
      } catch (e) {}
      showBar(deferred ? "prompt" : isIos() ? "ios" : "prompt");
    },
    enableNotifications: enableNotifications,
  };
})();
