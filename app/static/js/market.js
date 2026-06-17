/* موتور دادهٔ صفحهٔ خانه: واکشی اندپوینت‌ها، رندر بخش‌ها و به‌روزرسانی دوره‌ای
   (بدون نیاز به رفرش). فاصله‌های پایش هماهنگ با TTL سمت سرور تنظیم شده‌اند. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  function srcTag(el, source) {
    if (!el) return;
    const live = source === "live";
    el.className = "src-tag" + (live ? " live" : "");
    el.textContent = live ? "● زنده" : "● نمونه";
  }

  // آیکون دایره‌ای ارز از CDN با نشان حرفی در صورت نبود تصویر
  function coinIcon(symbol) {
    const sym = String(symbol || "").toLowerCase().replace(/usdt$|usd$/i, "");
    const url = "https://cdn.jsdelivr.net/npm/cryptocurrency-icons@0.18.1/128/color/" + sym + ".png";
    const letter = String(symbol || "?").slice(0, 3).toUpperCase();
    return '<div class="rowitem__icon">' +
      '<img src="' + url + '" alt="' + symbol + '" loading="lazy" ' +
      'onerror="this.parentNode.classList.add(\'badge\');this.parentNode.textContent=\'' + letter + '\'"></div>';
  }

  /* ---------- شاخص‌های کلان + تیکر ---------- */
  const TICKER_KEYS = [
    ["ارزش کل بازار", "total_market_cap", CS.faBig],
    ["حجم ۲۴ساعته", "total_volume_24h", CS.faBig],
    ["دامیننس بیت‌کوین", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["دامیننس اتریوم", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["ارزش بازار اتریوم", "eth_market_cap", CS.faBig],
    ["ارزش بازار آلت‌کوین‌ها", "alt_market_cap", CS.faBig],
    ["دامیننس تتر", "usdt_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
  ];
  const STAT_KEYS = [
    ["ارزش کل بازار", "total_market_cap", CS.faBig],
    ["حجم ۲۴ساعته", "total_volume_24h", CS.faBig],
    ["دامیننس BTC", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["دامیننس ETH", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
  ];

  function renderStats(stats) {
    $("statGrid").innerHTML = STAT_KEYS.map(([label, key, fmt]) => {
      const s = stats[key] || {};
      const ch = s.change_24h;
      const chHtml = (ch === undefined || ch === null) ? "" :
        '<div class="stat__chg ' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</div>';
      return '<div class="stat"><div class="stat__label">' + label + '<span class="live-dot live-dot--brand"></span></div>' +
        '<div class="stat__value">' + fmt(s.value || 0) + '</div>' + chHtml + '</div>';
    }).join("");
  }

  function renderTicker(stats) {
    const items = TICKER_KEYS.map(([label, key, fmt]) => {
      const s = stats[key] || {};
      const ch = s.change_24h;
      const chHtml = (ch === undefined || ch === null) ? "" :
        '<span class="' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
      return '<span class="ticker__item"><span class="live-dot live-dot--brand"></span><b>' + label +
        '</b><span class="val">' + fmt(s.value || 0) + '</span>' + chHtml + '</span>';
    }).join("");
    $("tickerTrack").innerHTML = items + items; // دوبار برای حرکت پیوسته
  }

  async function loadMacro() {
    try {
      const d = await CS.fetchJSON("/api/market/macro");
      renderStats(d.stats); renderTicker(d.stats);
      w.CSHeatmap.render($("heatmap"), d.heatmap);
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
      srcTag($("macroSrc"), d.source); srcTag($("heatmapSrc"), d.source);
    } catch (e) { console.warn("macro:", e); }
  }

  /* ---------- ارزهای برتر بازار (۵ ارز اصلی از توبیت) ---------- */
  async function loadCoins() {
    try {
      const d = await CS.fetchJSON("/api/market/coins");
      $("topCoins").innerHTML = d.coins.map((g, i) =>
        '<div class="rowitem"><span class="rowitem__rank">' + CS.toFa(i + 1) + '</span>' +
        coinIcon(g.symbol) +
        '<div class="rowitem__main"><div class="rowitem__name">' + g.symbol + '</div>' +
        '<div class="rowitem__sub">' + (g.pair || g.symbol + "USDT") + '</div></div>' +
        '<div class="rowitem__right"><span class="rowitem__price">' + CS.faPriceUsd(g.price) + '</span>' +
        '<span class="rowitem__vol">حجم ' + CS.faBig(g.volume_24h) + '</span></div>' +
        '<span class="chg ' + CS.chgClass(g.change_24h) + '">' + CS.faPct(g.change_24h) + '</span></div>'
      ).join("");
      srcTag($("coinsSrc"), d.source);
    } catch (e) { console.warn("coins:", e); }
  }

  /* ---------- قیمت‌های کلیدی ---------- */
  function keyRow(ic, color, name, sub, priceStr, ch) {
    const chHtml = (ch === undefined || ch === null) ? "" :
      '<span class="chg ' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
    return '<div class="rowitem"><span class="kp-ic" style="background:' + color + '">' + ic + '</span>' +
      '<div class="rowitem__main"><div class="rowitem__name">' + name + '</div>' +
      '<div class="rowitem__sub">' + sub + '</div></div>' +
      '<div class="rowitem__right"><span class="rowitem__price">' + priceStr + '</span>' + chHtml + '</div></div>';
  }

  async function loadPrices() {
    try {
      const d = await CS.fetchJSON("/api/market/prices");
      const rows = [];
      if (d.usdt_irt)
        rows.push(keyRow("₮", "#26A17B", d.usdt_irt.name || "تتر / تومان", "تومان",
          CS.faNum(d.usdt_irt.price) + " ت", d.usdt_irt.change_24h));
      if (d.gold_18k)
        rows.push(keyRow("ط", "#D4AF37", "طلای ۱۸ عیار", d.gold_18k.sub || "هر گرم",
          CS.faNum(d.gold_18k.price) + " ت", d.gold_18k.change_24h));
      const c = d.commodities || {};
      if (c.XAU) rows.push(keyRow("Au", "#C9A227", c.XAU.name || "طلای جهانی", c.XAU.sub || "اونس", CS.faPriceUsd(c.XAU.price), c.XAU.change_24h));
      if (c.XAG) rows.push(keyRow("Ag", "#9AA3AC", c.XAG.name || "نقره", c.XAG.sub || "اونس", CS.faPriceUsd(c.XAG.price), c.XAG.change_24h));
      if (c.OIL) rows.push(keyRow("O", "#1B1B1B", c.OIL.name || "نفت خام", c.OIL.sub || "بشکه", CS.faPriceUsd(c.OIL.price), c.OIL.change_24h));
      $("keyPrices").innerHTML = rows.join("") || '<span class="src-tag">داده‌ای موجود نیست</span>';
      // گیج ترس و طمع را هم در همین چرخهٔ سریع به‌روزرسانی کن تا «ثابت» نماند
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
    } catch (e) { console.warn("prices:", e); }
  }

  /* ---------- راه‌اندازی + پایش دوره‌ای ---------- */
  loadMacro();  setInterval(loadMacro, 10 * 60 * 1000); // ۱۰ دقیقه (هماهنگ با کش CryptoRank)
  loadCoins();  setInterval(loadCoins, 15 * 1000);      // ۱۵ ثانیه
  loadPrices(); setInterval(loadPrices, 20 * 1000);     // ۲۰ ثانیه
})(window);
