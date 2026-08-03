/*
 * نصب اپ ALGO HUB روی صفحهٔ اصلی گوشی (PWA) + اسپلشِ شروع + اعلان‌ها.
 *
 * این فایل در همهٔ صفحات هاب لود می‌شود؛ سرویس‌وورکر را با دامنهٔ «/» ثبت
 * می‌کند (پس ژورنال در /journal هم پوشش داده می‌شود)، هنگامِ بازشدنِ اپ لوگوی
 * ALGO HUB را نشان می‌دهد و یک نوار توصیهٔ نصب نمایش می‌دهد.
 *
 *   /app-icon    → آیکن اپ با پس‌زمینهٔ آبی (صفحهٔ اصلی گوشی، اعلان‌ها)
 *   /app-splash  → لوگوی شفاف (صفحهٔ شروع، نمایش درونِ اپ)
 */
(function () {
  "use strict";

  var DISMISS_KEY = "ah-pwa-dismissed-at";
  var DISMISS_DAYS = 7;
  var APP_ICON = "/app-icon?size=192";
  var APP_SPLASH = "/app-splash?size=512";

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

  /* ── ثبت سرویس‌وورکر ───────────────────────── */
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }

  /* ── اسپلشِ شروعِ اپ ───────────────────────
     فقط وقتی اپ نصب‌شده باز می‌شود (standalone) و یک‌بار در هر اجرا.        */
  var SPLASH_KEY = "ah-splash-shown";

  function splashSeenThisSession() {
    try {
      if (sessionStorage.getItem(SPLASH_KEY)) return true;
      sessionStorage.setItem(SPLASH_KEY, "1");
      return false;
    } catch (e) {
      return false;
    }
  }

  function showSplash() {
    if (!isStandalone() || inTelegram() || splashSeenThisSession()) return;

    var css =
      ".ah-splash{position:fixed;inset:0;z-index:100000;display:flex;flex-direction:column;" +
      "align-items:center;justify-content:center;gap:18px;background:#0A1622;" +
      "transition:opacity .45s ease;opacity:1}" +
      ".ah-splash--out{opacity:0;pointer-events:none}" +
      ".ah-splash img{width:min(46vw,190px);height:auto;animation:ah-splash-pop .6s ease}" +
      ".ah-splash__t{color:#cfe3f5;font-size:12px;letter-spacing:.22em;opacity:.7}" +
      "@keyframes ah-splash-pop{from{opacity:0;transform:scale(.88)}to{opacity:1;transform:none}}";
    var s = document.createElement("style");
    s.textContent = css;
    document.head.appendChild(s);

    var el = document.createElement("div");
    el.className = "ah-splash";

    var img = document.createElement("img");
    img.src = APP_SPLASH;
    img.alt = "ALGO HUB";

    var cap = document.createElement("div");
    cap.className = "ah-splash__t";
    cap.textContent = "ALGO HUB";

    el.appendChild(img);
    el.appendChild(cap);
    document.body.appendChild(el);

    setTimeout(function () {
      el.className = "ah-splash ah-splash--out";
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 500);
    }, 1300);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showSplash);
  } else {
    showSplash();
  }

  /* ── نوار توصیهٔ نصب ──────────────────────── */
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
      ".ah-pwa__icon{width:46px;height:46px;border-radius:14px;flex:0 0 auto;object-fit:cover}" +
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

    var icon = document.createElement("img");
    icon.className = "ah-pwa__icon";
    icon.src = APP_ICON;
    icon.alt = "ALGO HUB";

    var txt = document.createElement("div");
    txt.className = "ah-pwa__txt";

    var t = document.createElement("div");
    t.className = "ah-pwa__t";
    t.textContent = "اپ ALGO HUB را روی صفحهٔ اصلی گوشی‌تان نصب کنید";

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

  /* ── اعلان‌ها ─────────────────────────────── */
  function enableNotifications() {
    if (!("Notification" in window) || !navigator.serviceWorker) {
      return Promise.resolve("unsupported");
    }
    return Notification.requestPermission().then(function (perm) {
      if (perm === "granted") {
        navigator.serviceWorker.ready.then(function (reg) {
          reg.showNotification("ALGO HUB", {
            body: "اعلان‌ها فعال شد — هشدارهای بازار و یادآوری ثبت ژورنال را دریافت می‌کنید.",
            icon: APP_ICON,
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
