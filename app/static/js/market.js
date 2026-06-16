/* موتور دادهٔ صفحهٔ خانه:
   فراخوانی اندپوینت‌های بک‌اند، رندر بخش‌ها و به‌روزرسانی دوره‌ای.
   فاصله‌های پایش متناسب با TTL سمت سرور تنظیم شده‌اند. */
(function () {
  "use strict";
  const CS = window.CS;
  const $ = (id) => document.getElementById(id);

  function srcTag(el, source) {
    if (!el) return;
    const live = source === "live";
    el.className = "src-tag" + (live ? " live" : "");
    el.textContent = live ? "● زنده" : "● نمونه";
  }

  /* ---------- شاخص‌های کلان + تیکر ---------- */
  const TICKER = [
    ["ارزش کل بازار", "total_market_cap", CS.faBig],
    ["حجم ۲۴ساعته", "total_volume_24h", CS.faBig],
    ["دامیننس بیت‌کوین", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["دامیننس اتریوم", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["ارزش بازار اتریوم", "eth_market_cap", CS.faBig],
    ["ارزش بازار آلت‌کوین‌ها", "alt_market_cap", CS.faBig],
    ["دامیننس تتر", "usdt_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
  ];

  // آیکون دایره‌ای ارز از CDN (spothq) با نشان حرفی در صورت نبود تصویر
  function coinIcon(symbol) {
    const sym = String(symbol || "").toLowerCase().replace(/usdt$|usd$/i, "");
    const url = `https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@latest/128/color/${sym}.png`;
    const letter = String(symbol || "?").slice(0, 1).toUpperCase();
    return `<div class="rowitem__icon is-img">
      <img src="${url}" alt="${symbol}" loading="lazy"
           onerror="this.parentNode.classList.remove('is-img');this.parentNode.textContent='${letter}'">
    </div>`;
  }

  function renderStats(stats) {
    const order = [
      ["ارزش کل بازار", "total_market_cap", CS.faBig],
      ["حجم ۲۴ ساعته", "total_volume_24h", CS.faBig],
      ["دامیننس BTC", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
      ["دامیننس ETH", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ];
    $("statGrid").innerHTML = order
      .map(([label, key, fmt]) => {
        const s = stats[key] || {};
        const ch = s.change_24h;
        const chHtml = ch === undefined || ch === null ? "" :
          `<div class="stat__chg ${CS.chgClass(ch)}" style="color:var(--${CS.chgClass(ch) === "up" ? "up" : "down"})">${CS.faPct(ch)}</div>`;
        return `<div class="stat">
          <div class="stat__label">${label}<span class="live-dot live-dot--brand"></span></div>
          <div class="stat__value">${fmt(s.value || 0)}</div>
          ${chHtml}
        </div>`;
      })
      .join("");
  }

  function renderTicker(stats) {
    const items = TICKER.map(([label, key, fmt]) => {
      const s = stats[key] || {};
      const ch = s.change_24h;
      const chHtml = ch === undefined || ch === null ? "" :
        `<span class="chg ${CS.chgClass(ch)}">${CS.faPct(ch)}</span>`;
      return `<span class="ticker__item"><span class="live-dot live-dot--brand"></span><b>${label}</b><span class="val">${fmt(s.value || 0)}</span>${chHtml}</span>`;
    }).join("");
    // دوبار تکرار برای حرکت پیوسته (مطابق انیمیشن ۵۰٪)
    $("tickerTrack").innerHTML = items + items;
  }

  async function loadMacro() {
    try {
      const d = await CS.fetchJSON("/api/market/macro");
      renderStats(d.stats);
      renderTicker(d.stats);
      window.CSHeatmap.render($("heatmap"), d.heatmap);
      if (d.fear_greed) window.CSGauge.render($("fngGauge"), d.fear_greed);
      srcTag($("macroSrc"), d.source);
      srcTag($("heatmapSrc"), d.source);
    } catch (e) { console.warn("macro:", e); }
  }

  /* ---------- گینرها ---------- */
  async function loadGainers() {
    try {
      const d = await CS.fetchJSON("/api/market/gainers");
      $("gainers").innerHTML = d.gainers
        .map((g) => `
          <div class="rowitem">
            ${coinIcon(g.symbol)}
            <div class="rowitem__main">
              <div class="rowitem__name">${g.symbol}</div>
              <div class="rowitem__sub">${g.pair || g.symbol + "USDT"}</div>
            </div>
            <div class="rowitem__price">
              <div class="p">${CS.faPrice(g.price)}</div>
            </div>
            <span class="chg ${CS.chgClass(g.change_24h)}">${CS.faPct(g.change_24h)}</span>
          </div>`)
        .join("");
      srcTag($("gainersSrc"), d.source);
    } catch (e) { console.warn("gainers:", e); }
  }

  /* ---------- قیمت‌های کلیدی داخلی + کالا ---------- */
  async function loadInternal() {
    try {
      const d = await CS.fetchJSON("/api/market/internal");
      const rows = [];
      rows.push(keyRow("₮", "#26A17B", "تتر / تومان", "USDT",
        CS.toFa(CS.faNum(Math.round(d.usdt_irt.price))) + " ت", d.usdt_irt.change_24h));
      rows.push(keyRow("ط", "#D4AF37", "طلای ۱۸ عیار", "هر گرم",
        CS.toFa(CS.faNum(Math.round(d.gold_18k.price))) + " ت", d.gold_18k.change_24h));
      const f = d.futures || {};
      if (f.XAUUSDT) rows.push(keyRow("Au", "#C9A227", "طلای جهانی", "اونس", CS.faPrice(f.XAUUSDT.price), f.XAUUSDT.change_24h));
      if (f.XAGUSDT) rows.push(keyRow("Ag", "#9AA3AC", "نقره", "اونس", CS.faPrice(f.XAGUSDT.price), f.XAGUSDT.change_24h));
      if (f.OILBRENTUSDT) rows.push(keyRow("O", "#1B1B1B", "نفت برنت", "بشکه", CS.faPrice(f.OILBRENTUSDT.price), f.OILBRENTUSDT.change_24h));
      $("internalPrices").innerHTML = rows.join("");
    } catch (e) { console.warn("internal:", e); }
  }

  function keyRow(ic, color, name, sub, priceStr, ch) {
    const chHtml = (ch === undefined || ch === null) ? "" :
      `<span class="chg ${CS.chgClass(ch)}">${CS.faPct(ch)}</span>`;
    return `<div class="rowitem">
      <span class="kp-ic" style="background:${color}">${ic}</span>
      <div class="rowitem__main">
        <div class="rowitem__name">${name}</div>
        <div class="rowitem__sub">${sub}</div>
      </div>
      <div class="rowitem__price"><div class="p">${priceStr}</div></div>
      ${chHtml}
    </div>`;
  }

  /* ---------- راه‌اندازی + پایش دوره‌ای ---------- */
  loadMacro();    setInterval(loadMacro, 10 * 60 * 1000);   // ۱۰ دقیقه (هماهنگ با کش CryptoRank)
  loadGainers();  setInterval(loadGainers, 15 * 1000);      // ۱۵ ثانیه
  loadInternal(); setInterval(loadInternal, 20 * 1000);     // ۲۰ ثانیه
})();
