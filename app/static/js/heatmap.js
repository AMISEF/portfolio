/* رندر نقشهٔ حرارتی بازار — اندازهٔ هر خانه بر اساس ارزش بازار،
   رنگ بر اساس درصد تغییر ۲۴ ساعته (سبز/قرمز با شدت متغیر). */
(function (w) {
  "use strict";

  // رنگ بر اساس درصد تغییر
  function heatColor(ch) {
    const x = Math.max(-8, Math.min(8, ch)) / 8; // نرمال‌سازی
    if (x >= 0) {
      const l = 26 + (1 - x) * 22; // سبز تیره‌تر برای رشد بیشتر
      return `hsl(152 65% ${l}%)`;
    }
    const l = 26 + (1 + x) * 22;
    return `hsl(353 70% ${l}%)`;
  }

  // تخصیص span ستون/ردیف بر اساس رتبهٔ ارزش بازار
  function spanFor(i) {
    if (i === 0) return { c: 6, r: 4, cls: "heat--xl" };  // BTC
    if (i === 1) return { c: 4, r: 3, cls: "heat--lg" };  // ETH
    if (i < 4) return { c: 2, r: 2, cls: "" };
    if (i < 8) return { c: 2, r: 1, cls: "" };
    return { c: 1, r: 1, cls: "" };
  }

  function render(el, items) {
    if (!items || !items.length) { el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>'; return; }
    const sorted = items.slice().sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
    el.innerHTML = sorted
      .map((it, i) => {
        const s = spanFor(i);
        const showPrice = i < 6;
        return `<div class="heat ${s.cls}" style="grid-column:span ${s.c};grid-row:span ${s.r};background:${heatColor(it.change_24h)}"
                  title="${it.name} • ${w.CS.faPrice(it.price)}">
                  <b>${it.symbol}</b>
                  <span class="pct">${w.CS.faPct(it.change_24h)}</span>
                  ${showPrice ? `<span class="nm">${w.CS.faPrice(it.price)}</span>` : ""}
                </div>`;
      })
      .join("");
  }

  w.CSHeatmap = { render };
})(window);
