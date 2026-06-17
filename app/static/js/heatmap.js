/* نقشهٔ حرارتی به‌سبک CryptoRank: گروه‌بندی بر اساس دسته، اندازهٔ هر خانه ∝
   ارزش بازار، رنگ ∝ تغییر ۲۴ساعته. */
(function (w) {
  "use strict";
  const CS = w.CS;

  // برچسب‌ها انگلیسی (طبق درخواست) — همان دستهٔ سرور نمایش داده می‌شود
  const CAT_ORDER = ["Currency", "Smart Contract", "Stablecoin", "DeFi", "Meme", "Other"];
  const CAT_FA = {};  // بدون ترجمه؛ نام دسته همان انگلیسی است

  function heatColor(ch) {
    const x = Math.max(-8, Math.min(8, ch || 0)) / 8;
    if (Math.abs(x) < 0.02) return "hsl(220 8% 42%)";        // بی‌تغییر: خاکستری
    if (x > 0) return "hsl(152 58% " + (42 - x * 16) + "%)"; // سبز
    return "hsl(353 65% " + (44 + x * 16) + "%)";            // قرمز
  }

  const weight = (mc) => Math.pow(Math.max(mc, 1), 0.62);

  function render(el, items) {
    if (!el) return;
    if (!items || !items.length) { el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>'; return; }

    const ranked = items.slice().sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
    const rank = new Map(ranked.map((it, i) => [it.symbol, i]));

    const groups = {};
    items.forEach((it) => {
      const c = CAT_ORDER.includes(it.category) ? it.category : "Other";
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
        return '<div class="heat ' + cls + '" style="flex-grow:' + weight(it.market_cap) + ';background:' + heatColor(it.change_24h) + '"' +
               ' title="' + it.name + ' • ' + CS.faPriceUsd(it.price) + ' • ' + CS.faPct(it.change_24h) + '">' +
               '<b>' + it.symbol + '</b>' +
               '<span class="pct">' + CS.faPct(it.change_24h) + '</span>' +
               (showPrice ? '<span class="nm">' + CS.faPriceUsd(it.price) + '</span>' : '') +
               '</div>';
      }).join("");
      return '<div class="heat-cat" style="flex-grow:' + weight(catMc) + '">' +
             '<div class="heat-cat__label">' + (CAT_FA[cat] || cat) + '</div>' +
             '<div class="heat-cat__tiles">' + tiles + '</div></div>';
    }).join("");
  }

  w.CSHeatmap = { render };
})(window);
