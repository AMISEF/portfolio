/* ابزارهای مشترک: ارقام فارسی، قالب‌بندی اعداد/قیمت، تبدیل تاریخ شمسی */
(function (w) {
  "use strict";

  const FA = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

  // تبدیل ارقام لاتین به فارسی
  function toFa(s) {
    return String(s).replace(/\d/g, (d) => FA[+d]);
  }

  // جداکنندهٔ هزارگان + ارقام فارسی
  function faNum(n, digits = 0) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const fixed = Number(n).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    return toFa(fixed);
  }

  // قیمت دلاری با دقت هوشمند بر اساس بزرگی عدد
  function faPrice(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    let d = 2;
    if (n >= 1000) d = 0;
    else if (n >= 1) d = 2;
    else if (n >= 0.01) d = 4;
    else d = 6;
    return "$" + faNum(n, d);
  }

  // ارزش بزرگ بازار/حجم به تریلیون/میلیارد/میلیون
  function faBig(n) {
    if (!n || isNaN(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e12) return "$" + faNum(n / 1e12, 2) + " تریلیون";
    if (abs >= 1e9) return "$" + faNum(n / 1e9, 2) + " میلیارد";
    if (abs >= 1e6) return "$" + faNum(n / 1e6, 2) + " میلیون";
    return "$" + faNum(n, 0);
  }

  // مبلغ تومانی
  function faToman(n) {
    if (!n || isNaN(n)) return "—";
    return faNum(Math.round(n), 0) + " تومان";
  }

  // درصد تغییر با علامت
  function faPct(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const sign = n > 0 ? "+" : n < 0 ? "−" : "";
    return sign + toFa(Math.abs(Number(n)).toFixed(2)) + "٪";
  }

  function chgClass(n) {
    return Number(n) >= 0 ? "up" : "down";
  }

  // ---- تبدیل میلادی به شمسی (الگوریتم استاندارد، بدون کتابخانه) ----
  function gregorianToJalali(gy, gm, gd) {
    const gDM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let jy = gy <= 1600 ? 0 : 979;
    gy -= gy <= 1600 ? 621 : 1600;
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days =
      365 * gy +
      Math.floor((gy2 + 3) / 4) -
      Math.floor((gy2 + 99) / 100) +
      Math.floor((gy2 + 399) / 400) -
      80 +
      gd +
      gDM[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      jy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    let jm, jd;
    if (days < 186) {
      jm = 1 + Math.floor(days / 31);
      jd = 1 + (days % 31);
    } else {
      jm = 7 + Math.floor((days - 186) / 30);
      jd = 1 + ((days - 186) % 30);
    }
    return [jy, jm, jd];
  }

  const FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
  const FA_WEEKDAYS = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه"];
  const EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function shamsiString(d) {
    const [jy, jm, jd] = gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
    const wd = FA_WEEKDAYS[d.getDay()];
    return `${wd} ${toFa(jd)} ${FA_MONTHS[jm - 1]} ${toFa(jy)}`;
  }

  function gregorianString(d) {
    return `${toFa(d.getDate())} ${EN_MONTHS[d.getMonth()]} ${toFa(d.getFullYear())}`;
  }

  async function fetchJSON(url) {
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  w.CS = {
    toFa, faNum, faPrice, faBig, faToman, faPct, chgClass,
    shamsiString, gregorianString, fetchJSON,
  };
})(window);
