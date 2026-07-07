/* یکپارچه‌سازی مینی‌اپ تلگرام + ناوبریِ اپ‌گونه.
   هم به‌عنوان وب‌سایت کار می‌کند و هم مینی‌اپ تلگرام:
   - داخل تلگرام: ready()/expand()، دکمهٔ «بازگشت»ِ بومی روی صفحه‌های غیرخانه، و
     بازگردانی آخرین مسیر پس از رفرش (چون تلگرام هنگام رفرش به صفحهٔ خانه می‌رود).
   - خارج از تلگرام: هیچ رفتاری تغییر نمی‌کند. */
(function (w, d) {
  "use strict";

  var path = location.pathname + location.search;
  var isHome = location.pathname === "/" || location.pathname === "";

  // آخرین مسیرِ غیرخانه را ذخیره کن تا بعد از رفرشِ مینی‌اپ بتوان بازگرداند.
  try {
    if (!isHome && location.pathname.indexOf("/admin") !== 0) {
      localStorage.setItem("cs_route", path);
    }
  } catch (e) { /* ignore */ }

  function boot() {
    var tg = w.Telegram && w.Telegram.WebApp;
    if (!tg) return;
    try { tg.ready(); } catch (e) {}
    try { tg.expand(); } catch (e) {}
    d.documentElement.classList.add("in-telegram");

    // بازگردانیِ آخرین مسیر: فقط وقتی روی خانه هستیم و بارگذاری از نوعِ رفرش/باز
    // شدنِ مجدد است (بدون referrer). کلیک روی «خانه» referrer دارد و بازگردانی
    // نمی‌شود، پس حلقه ایجاد نمی‌شود.
    try {
      if (isHome && !d.referrer) {
        var last = localStorage.getItem("cs_route");
        if (last && last !== "/" && last.charAt(0) === "/") {
          location.replace(last);
          return;
        }
      }
    } catch (e) {}

    // دکمهٔ بازگشتِ بومیِ تلگرام روی صفحه‌های غیرخانه.
    try {
      var bb = tg.BackButton;
      if (bb) {
        if (!isHome) {
          bb.show();
          bb.onClick(function () {
            if (w.history.length > 1) w.history.back();
            else location.href = "/";
          });
        } else {
          bb.hide();
        }
      }
    } catch (e) {}
  }

  if (w.Telegram && w.Telegram.WebApp) boot();
  else w.addEventListener("load", boot);
})(window, document);
