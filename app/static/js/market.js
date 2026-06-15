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

  function renderStats(stats) {
    const order = [
      ["ارزش کل بازار", "total_market_cap", CS.faBig],
      ["حجم ۲۴ ساعته", "total_volume_24h", CS.faBig],
      ["دامیننس بیت‌کوین", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
      ["دامیننس اتریوم", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
      ["ارزش بازار آلت‌کوین‌ها", "alt_market_cap", CS.faBig],
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
            <div class="rowitem__icon">${g.symbol.slice(0, 4)}</div>
            <div class="rowitem__main">
              <div class="rowitem__name">${g.symbol}</div>
              <div class="rowitem__sub">حجم: ${CS.faBig(g.volume_24h)}</div>
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
      const boxes = [];
      boxes.push(priceBox(d.usdt_irt.name, CS.faToman(d.usdt_irt.price), "تومان", d.usdt_irt.change_24h));
      boxes.push(priceBox(d.gold_18k.name, CS.faToman(d.gold_18k.price), d.gold_18k.unit || "تومان", d.gold_18k.change_24h, true));
      const f = d.futures || {};
      if (f.XAUUSDT) boxes.push(priceBox(f.XAUUSDT.name, CS.faPrice(f.XAUUSDT.price), "USDT", f.XAUUSDT.change_24h));
      if (f.XAGUSDT) boxes.push(priceBox(f.XAGUSDT.name, CS.faPrice(f.XAGUSDT.price), "USDT", f.XAGUSDT.change_24h));
      if (f.OILBRENTUSDT) boxes.push(priceBox(f.OILBRENTUSDT.name, CS.faPrice(f.OILBRENTUSDT.price), "USDT", f.OILBRENTUSDT.change_24h));
      $("internalPrices").innerHTML = boxes.join("");
    } catch (e) { console.warn("internal:", e); }
  }

  function priceBox(name, priceStr, unit, ch, halfHour) {
    const chHtml = ch ? `<span class="chg ${CS.chgClass(ch)}">${CS.faPct(ch)}</span>` : "";
    const note = halfHour ? '<span class="pricebox__unit"> • به‌روزرسانی هر ۳۰ دقیقه</span>' : "";
    return `<div class="pricebox">
      <div class="pricebox__name">${name}<span class="live-dot"></span></div>
      <div class="pricebox__price">${priceStr}</div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:6px">
        <span class="pricebox__unit">${unit}${note}</span>${chHtml}
      </div>
    </div>`;
  }

  /* ---------- راه‌اندازی + پایش دوره‌ای ---------- */
  loadMacro();    setInterval(loadMacro, 10 * 60 * 1000);   // ۱۰ دقیقه (هماهنگ با کش CryptoRank)
  loadGainers();  setInterval(loadGainers, 15 * 1000);      // ۱۵ ثانیه
  loadInternal(); setInterval(loadInternal, 20 * 1000);     // ۲۰ ثانیه
})();
