/* رندر نقشهٔ حرارتی بازار — دسته‌بندی‌شده بر اساس بخش (Layer1/DeFi/…)؛
   رنگ بر اساس درصد تغییر ۲۴ساعته، اندازهٔ خانه بر اساس ارزش بازار. */
(function (w) {
  "use strict";
  const CS = w.CS;

  // رنگ سبز/قرمز با شدت متناسب با بزرگی تغییر
  function heatColor(chg) {
    const m = Math.min(Math.abs(chg) / 8, 1);
    if (chg >= 0) return `rgba(22,199,132,${(0.35 + m * 0.55).toFixed(3)})`;
    return `rgba(234,57,67,${(0.35 + m * 0.55).toFixed(3)})`;
  }

  function render(el, items) {
    if (!items || !items.length) {
      el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>';
      return;
    }

    // رتبهٔ ارزش بازار سراسری → برای تعیین اندازهٔ خانه‌ها (xl/lg)
    const ranked = items.slice().sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
    const sizeOf = new Map();
    ranked.forEach((it, i) => sizeOf.set(it.symbol, i === 0 ? "xl" : i < 4 ? "lg" : ""));

    // گروه‌بندی بر اساس دسته
    const groups = new Map();
    for (const it of items) {
      const cat = it.category || "سایر";
      if (!groups.has(cat)) groups.set(cat, []);
      groups.get(cat).push(it);
    }

    // مرتب‌سازی دسته‌ها بر اساس مجموع ارزش بازار (بزرگ‌ترین اول → پیشرو RTL)
    const cats = [...groups.entries()].sort((a, b) =>
      b[1].reduce((s, x) => s + (x.market_cap || 0), 0) -
      a[1].reduce((s, x) => s + (x.market_cap || 0), 0));

    el.innerHTML = cats.map(([cat, coins]) => {
      coins.sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
      const tiles = coins.map((c) => {
        const size = sizeOf.get(c.symbol) || "";
        const cls = size === "xl" ? " heat--xl" : size === "lg" ? " heat--lg" : "";
        return `<div class="heat${cls}" style="background:${heatColor(c.change_24h)}"
                  title="${c.name || c.symbol} • ${CS.faPrice(c.price)}">
                  <b>${c.symbol}</b>
                  <span class="pct">${CS.faPct(c.change_24h)}</span>
                </div>`;
      }).join("");
      return `<div class="heat-cat">
                <div class="heat-cat__label">${cat}</div>
                <div class="heat-cat__tiles">${tiles}</div>
              </div>`;
    }).join("");
  }

  w.CSHeatmap = { render };
})(window);
