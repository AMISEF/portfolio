/* نقشهٔ حرارتی بازار به‌سبک CryptoRank:
   ارزها بر اساس دسته (ارز / بلاکچین / استیبل‌کوین / دیفای / میم‌کوین / سی‌فای)
   گروه‌بندی می‌شوند؛ اندازهٔ هر دسته و هر خانه ∝ ارزش بازار، رنگ ∝ تغییر ۲۴ساعته. */
(function (w) {
  "use strict";

  const CAT_ORDER = ["Currency", "Blockchain", "Stablecoin", "DeFi", "Meme", "CeFi"];
  const CAT_FA = {
    Currency: "ارز", Blockchain: "بلاکچین", Stablecoin: "استیبل‌کوین",
    DeFi: "دیفای", Meme: "میم‌کوین", CeFi: "سی‌فای",
  };

  function heatColor(ch) {
    const x = Math.max(-8, Math.min(8, ch || 0)) / 8;
    if (Math.abs(x) < 0.02) return "hsl(220 8% 38%)";        // بی‌تغییر: خاکستری
    if (x > 0) return `hsl(152 58% ${42 - x * 16}%)`;        // سبز (رشد)
    return `hsl(353 65% ${44 + x * 16}%)`;                   // قرمز (افت)
  }

  // وزن فشرده‌شده برای جلوگیری از غول‌شدن بیت‌کوین در شبکه
  const weight = (mc) => Math.pow(Math.max(mc, 1), 0.62);

  function render(el, items) {
    if (!items || !items.length) {
      el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>';
      return;
    }
    // رتبهٔ سراسری بر اساس ارزش بازار (برای تصمیم نمایش قیمت/اندازه)
    const ranked = items.slice().sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
    const rank = new Map(ranked.map((it, i) => [it.symbol, i]));

    // گروه‌بندی بر اساس دسته
    const groups = {};
    items.forEach((it) => {
      const c = CAT_ORDER.includes(it.category) ? it.category : "Currency";
      (groups[c] = groups[c] || []).push(it);
    });

    const cats = Object.keys(groups).sort((a, b) => {
      const ai = CAT_ORDER.indexOf(a), bi = CAT_ORDER.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    });

    el.innerHTML = cats.map((cat) => {
      const list = groups[cat].sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
      const catMc = list.reduce((s, it) => s + (it.market_cap || 0), 0);
      const tiles = list.map((it) => {
        const r = rank.get(it.symbol) ?? 99;
        const cls = r === 0 ? "heat--xl" : r < 3 ? "heat--lg" : r < 8 ? "heat--md" : "";
        const showPrice = r < 9;
        return `<div class="heat ${cls}" style="flex-grow:${weight(it.market_cap)};background:${heatColor(it.change_24h)}"
                  title="${it.name} • ${w.CS.faPrice(it.price)} • ${w.CS.faPct(it.change_24h)}">
                  <b>${it.symbol}</b>
                  <span class="pct">${w.CS.faPct(it.change_24h)}</span>
                  ${showPrice ? `<span class="nm">${w.CS.faPrice(it.price)}</span>` : ""}
                </div>`;
      }).join("");
      return `<div class="heat-cat" style="flex-grow:${weight(catMc)}">
                <div class="heat-cat__label">${CAT_FA[cat] || cat}</div>
                <div class="heat-cat__tiles">${tiles}</div>
              </div>`;
    }).join("");
  }

  w.CSHeatmap = { render };
})(window);
