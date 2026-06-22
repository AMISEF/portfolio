/* ابزارهای مشترک فرانت‌اند: قالب‌بندی فارسی اعداد، درصد، قیمت و واکشی JSON. */
(function (w) {
  "use strict";
  const FA = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

  const toFa = (s) => String(s).replace(/[0-9]/g, (d) => FA[+d]);

  // جداکنندهٔ هزارگان فارسی (٬)
  function faNum(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const neg = n < 0; n = Math.abs(n);
    const s = Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
    return (neg ? "−" : "") + toFa(s);
  }

  // اعداد دلاری بزرگ به $T / $B / $M
  function faBig(n) {
    if (!n || isNaN(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e12) return "$" + toFa((n / 1e12).toFixed(2)) + "T";
    if (abs >= 1e9) return "$" + toFa((n / 1e9).toFixed(2)) + "B";
    if (abs >= 1e6) return "$" + toFa((n / 1e6).toFixed(2)) + "M";
    if (abs >= 1e3) return "$" + toFa((n / 1e3).toFixed(2)) + "K";
    return "$" + toFa(n.toFixed(2));
  }

  // قیمت دلاری ارز (تعداد رقم اعشار متناسب با بزرگی عدد)
  function faPriceUsd(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    let d = 2;
    const abs = Math.abs(n);
    if (abs >= 1000) d = 0; else if (abs >= 1) d = 2; else if (abs >= 0.01) d = 4; else d = 6;
    const s = n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
    return "$" + toFa(s);
  }

  function faPct(n) {
    if (n === null || n === undefined || isNaN(n)) return "";
    const sign = n >= 0 ? "+" : "−";
    // ⁦ = LTR ISOLATE, ⁩ = POP DIRECTIONAL ISOLATE
    // prevents bidi algorithm from reversing sign/percent order in RTL context
    return "⁦" + sign + toFa(Math.abs(n).toFixed(2)) + "٪" + "⁩";
  }

  const chgClass = (n) => (n >= 0 ? "up" : "down");

  async function fetchJSON(url) {
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  w.CS = { toFa, faNum, faBig, faPriceUsd, faPct, chgClass, fetchJSON };
})(window);
