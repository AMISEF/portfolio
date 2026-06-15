/* ساعت زندهٔ ثانیه‌شمار + تاریخ شمسی و میلادی */
(function () {
  "use strict";
  const elClock = document.getElementById("clock");
  const elShamsi = document.getElementById("dateShamsi");
  const elGreg = document.getElementById("dateGregorian");
  if (!elClock) return;

  function pad(n) { return String(n).padStart(2, "0"); }

  function tick() {
    const d = new Date();
    elClock.textContent = window.CS.toFa(`${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`);
    if (elShamsi) elShamsi.textContent = window.CS.shamsiString(d);
    if (elGreg) elGreg.textContent = window.CS.gregorianString(d);
  }

  tick();
  setInterval(tick, 1000);
})();
