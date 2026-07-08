/* یکپارچه‌سازی مینی‌اپ تلگرام + ناوبریِ اپ‌گونه.
   هم به‌عنوان وب‌سایت کار می‌کند و هم مینی‌اپ تلگرام:
   - داخل تلگرام: ready()/expand()، دکمهٔ «بازگشت»ِ بومی روی صفحه‌های غیرخانه، و
     بازگردانی آخرین مسیر پس از رفرش (چون تلگرام هنگام رفرش به صفحهٔ خانه می‌رود).
   - داخل تلگرام: ناوبریِ داخلی (کلیک روی لینک‌های هم‌مبدأ) هرگز یک رفرشِ کاملِ
     صفحه انجام نمی‌دهد -- چون وب‌ویوِ تلگرام گاهی رفرشِ کامل را درست مدیریت
     نمی‌کند و خطای «Failed to load» می‌دهد. به‌جایش صفحهٔ مقصد با fetch گرفته و
     بدنه جایگزین می‌شود (بدونِ ناوبریِ واقعیِ مرورگر).
   - خارج از تلگرام: هیچ رفتاری تغییر نمی‌کند (رفتارِ عادیِ لینک‌ها). */
(function (w, d) {
  "use strict";

  // این فایل به‌عنوانِ یک <script src> عادی داخلِ body است، پس با هر سواپِ
  // بدونِ‌رفرشِ ناوبری دوباره اجرا می‌شود (چون اسکریپت‌های داخلِ بدنه دوباره
  // ساخته/اجرا می‌شوند تا صفحاتِ خاص کار کنند). این گارد جلوی ثبتِ چندبارهٔ
  // لیسنرهای سطحِ document/window را می‌گیرد (که در غیرِ این صورت با هر
  // ناوبری تکرار و انباشته می‌شدند).
  if (w.__csTelegramNavInit) return;
  w.__csTelegramNavInit = true;

  // ⚠️ بنرِ موقتِ دیباگ -- روی صفحه ثابت می‌ماند (نه alert، چون تلگرام گاهی
  // دیالوگ‌های بومی را غیرفعال می‌کند) تا خطای واقعی را ببینیم. بعد از رفعِ
  // باگ حذف می‌شود.
  function debugBanner(msg) {
    try {
      var el = d.getElementById("csNavDebug");
      if (!el) {
        el = d.createElement("div");
        el.id = "csNavDebug";
        el.style.cssText = "position:fixed;inset:auto 8px 8px 8px;z-index:99999;background:#c0392b;color:#fff;" +
          "font:12px/1.5 monospace;padding:10px 12px;border-radius:10px;max-height:40vh;overflow:auto;" +
          "white-space:pre-wrap;direction:ltr;text-align:left;box-shadow:0 8px 24px rgba(0,0,0,.4)";
        el.addEventListener("click", function () { el.remove(); });
        (d.body || d.documentElement).appendChild(el);
      }
      el.textContent += (el.textContent ? "\n---\n" : "") + msg;
      var tg = w.Telegram && w.Telegram.WebApp;
      if (tg && tg.showAlert) { try { tg.showAlert(msg); } catch (e3) {} }
    } catch (e4) {}
  }
  w.addEventListener("error", function (e) {
    debugBanner("window.onerror: " + (e && e.message) + " @ " + (e && e.filename) + ":" + (e && e.lineno));
  });
  w.addEventListener("unhandledrejection", function (e) {
    var r = e && e.reason;
    debugBanner("unhandledrejection: " + (r && r.message ? r.message : String(r)));
  });

  var path = location.pathname + location.search;
  var isHome = location.pathname === "/" || location.pathname === "";

  // ردیابیِ همهٔ setInterval های صفحه تا پیش از هر سواپِ بدنه پاک شوند --
  // وگرنه اسکریپت‌های هر صفحه (مثلاً پولینگِ داده‌های بازار) با هر بازدیدِ
  // مجددِ همان صفحه، تایمرهای جدید روی تایمرهای قبلی انباشته می‌کنند.
  var _intervals = [];
  var _origSetInterval = w.setInterval;
  w.setInterval = function () {
    var id = _origSetInterval.apply(w, arguments);
    _intervals.push(id);
    return id;
  };
  function clearTrackedIntervals() {
    for (var i = 0; i < _intervals.length; i++) {
      try { w.clearInterval(_intervals[i]); } catch (e) {}
    }
    _intervals = [];
  }

  // آخرین مسیرِ غیرخانه را ذخیره کن تا بعد از رفرشِ مینی‌اپ بتوان بازگرداند.
  function saveRoute(p) {
    try {
      var home = p === "/" || p === "";
      if (!home && p.indexOf("/admin") !== 0) {
        localStorage.setItem("cs_route", p);
      }
    } catch (e) { /* ignore */ }
  }
  saveRoute(path);

  // ── ناوبریِ بدونِ رفرشِ کامل (فقط داخلِ تلگرام فعال می‌شود) ──
  function isEligibleHref(hrefAttr) {
    if (!hrefAttr) return false;
    if (hrefAttr.charAt(0) === "#") return false;
    if (/^(javascript|mailto|tel):/i.test(hrefAttr)) return false;
    var url;
    try { url = new URL(hrefAttr, location.href); } catch (e) { return false; }
    if (url.origin !== location.origin) return false;
    if (url.pathname.indexOf("/journal") === 0) return false; // اپِ جداگانه است
    if (url.pathname.indexOf("/admin") === 0) return false; // پنلِ پیچیده -- ناوبریِ عادی
    return true;
  }
  function isEligibleLink(a) {
    if (!a) return false;
    if (a.target && a.target !== "" && a.target !== "_self") return false;
    if (a.hasAttribute("download")) return false;
    if (a.dataset && "noSpa" in a.dataset) return false;
    var raw = a.dataset && a.dataset.csHref ? a.dataset.csHref : a.getAttribute("href");
    return isEligibleHref(raw);
  }

  /** href هایِ داخلیِ واجدشرایط را از خودِ <a> برمی‌دارد (در data-cs-href نگه
   *  می‌دارد) تا لایهٔ بومیِ تلگرام آن‌ها را به‌عنوانِ «لینک» تشخیص و مدیریت
   *  نکند -- که باعثِ رفرشِ کامل و شکستِ ناوبری می‌شد، حتی با وجودِ
   *  e.preventDefault() در کلیک‌هندلرِ جاوااسکریپت. */
  function neutralizeLinks(root) {
    var links = (root || d).querySelectorAll("a[href]");
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var href = a.getAttribute("href");
      if (isEligibleHref(href) && !(a.dataset && "noSpa" in a.dataset) &&
          !(a.target && a.target !== "" && a.target !== "_self")) {
        a.dataset.csHref = href;
        a.removeAttribute("href");
        a.style.cursor = "pointer";
      }
    }
  }

  /** اسکریپت‌های داخلِ کانتینر را دوباره می‌سازد تا واقعاً اجرا شوند
   *  (innerHTML اسکریپت‌ها را اجرا نمی‌کند). به‌ترتیب و پشتِ سرِ هم. */
  function runScripts(container, done) {
    var scripts = Array.prototype.slice.call(container.querySelectorAll("script"));
    (function next(i) {
      if (i >= scripts.length) { if (done) done(); return; }
      var old = scripts[i];
      var s = d.createElement("script");
      for (var j = 0; j < old.attributes.length; j++) {
        var attr = old.attributes[j];
        s.setAttribute(attr.name, attr.value);
      }
      if (old.src) {
        s.onload = s.onerror = function () { next(i + 1); };
        d.body.appendChild(s);
      } else {
        s.textContent = old.textContent;
        d.body.appendChild(s);
        next(i + 1);
      }
    })(0);
  }

  function swapTo(url, push) {
    fetch(url, { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) throw new Error("http " + res.status);
        return res.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        if (!doc.body) throw new Error("no body");
        clearTrackedIntervals();
        d.title = doc.title;
        d.body.innerHTML = doc.body.innerHTML;
        var u;
        try { u = new URL(url, location.href); } catch (e) { u = null; }
        if (push) {
          try { w.history.pushState({ cs: true }, "", url); } catch (e) {}
        }
        saveRoute(u ? u.pathname + u.search : url);
        w.scrollTo(0, 0);
        neutralizeLinks(d.body);
        runScripts(d.body);
      })
      .catch(function (err) {
        debugBanner("swapTo(" + url + ") failed: " + (err && err.message ? err.message : String(err)));
        // اگر ناوبریِ بدونِ رفرش شکست خورد، به روشِ معمولیِ مرورگر برو.
        location.href = url;
      });
  }

  function enableSpaNav() {
    neutralizeLinks(d);
    d.addEventListener("click", function (e) {
      try {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target && e.target.closest ? e.target.closest("a") : null;
        if (!isEligibleLink(a)) return;
        var raw = a.dataset && a.dataset.csHref ? a.dataset.csHref : a.getAttribute("href");
        var url;
        try { url = new URL(raw, location.href).href; } catch (e2) { return; }
        if (url === location.href) return;
        e.preventDefault();
        swapTo(url, true);
      } catch (err) {
        debugBanner("click handler failed: " + (err && err.message ? err.message : String(err)));
      }
    });

    w.addEventListener("popstate", function () {
      swapTo(location.href, false);
    });
  }

  function boot() {
    var tg = w.Telegram && w.Telegram.WebApp;
    if (!tg) return;
    try { tg.ready(); } catch (e) {}
    try { tg.expand(); } catch (e) {}
    d.documentElement.classList.add("in-telegram");
    enableSpaNav();
    debugBanner("cs-nav ready (v2, href-neutralized). path=" + path + " ua=" + (navigator.userAgent || "").slice(0, 60));

    // بازگردانیِ آخرین مسیر: فقط وقتی روی خانه هستیم و بارگذاری از نوعِ رفرش/باز
    // شدنِ مجدد است (بدون referrer). کلیک روی «خانه» referrer دارد و بازگردانی
    // نمی‌شود، پس حلقه ایجاد نمی‌شود.
    try {
      if (isHome && !d.referrer) {
        var last = localStorage.getItem("cs_route");
        if (last && last !== "/" && last.charAt(0) === "/") {
          swapTo(last, true);
          return;
        }
      }
    } catch (e) {}

    // دکمهٔ بازگشتِ بومیِ تلگرام روی صفحه‌های غیرخانه.
    try {
      var bb = tg.BackButton;
      if (bb) {
        var updateBb = function () {
          var home = location.pathname === "/" || location.pathname === "";
          if (!home) bb.show();
          else bb.hide();
        };
        updateBb();
        w.addEventListener("popstate", updateBb);
        bb.onClick(function () {
          if (w.history.length > 1) w.history.back();
          else swapTo("/", true);
        });
      }
    } catch (e) {}
  }

  if (w.Telegram && w.Telegram.WebApp) boot();
  else w.addEventListener("load", boot);
})(window, document);
