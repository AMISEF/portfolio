/* ساعت زنده + تاریخ شمسی و میلادی (هر ثانیه به‌روزرسانی می‌شود). */
(function (w) {
  "use strict";
  const CS = w.CS;
  const clockEl = document.getElementById("clock");
  const shamsiEl = document.getElementById("dateShamsi");
  const gregEl = document.getElementById("dateGregorian");
  if (!clockEl) return;

  const fmtShamsi = new Intl.DateTimeFormat("fa-IR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const fmtGreg = new Intl.DateTimeFormat("en-GB", { year: "numeric", month: "long", day: "numeric" });

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  // «جمعه، ۲۹ خرداد، ۱۴۰۵»
  function shamsi(now) {
    const p = fmtShamsi.formatToParts(now);
    const g = (t) => { const x = p.find((e) => e.type === t); return x ? x.value : ""; };
    return g("weekday") + "، " + g("day") + " " + g("month") + "، " + g("year");
  }

  function tick() {
    const now = new Date();
    clockEl.textContent = CS.toFa(pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds()));
    if (shamsiEl) shamsiEl.textContent = shamsi(now);
    // میلادی: «19 June 2026»
    if (gregEl) gregEl.textContent = fmtGreg.format(now);
  }

  tick();
  setInterval(tick, 1000);
})(window);
