/* موتور دادهٔ صفحهٔ خانه: فراخوانی بک‌اند، رندر بخش‌ها و به‌روزرسانی دوره‌ای. */
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

  /* ---------- تیکر شاخص‌های کلان ---------- */
  const TICKER = [
    ["ارزش کل بازار", "total_market_cap", CS.faBig],
    ["حجم ۲۴ساعته", "total_volume_24h", CS.faBig],
    ["دامیننس بیت‌کوین", "btc_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["دامیننس اتریوم", "eth_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
    ["ارزش بازار اتریوم", "eth_market_cap", CS.faBig],
    ["ارزش بازار آلت‌کوین‌ها", "alt_market_cap", CS.faBig],
    ["دامیننس تتر", "usdt_dominance", (v) => CS.toFa(v.toFixed(2)) + "٪"],
  ];

  function renderTicker(stats) {
    const items = TICKER.map(([label, key, fmt]) => {
      const s = stats[key] || {};
      const ch = s.change_24h;
      const chHtml = (ch === undefined || ch === null || ch === 0) ? "" :
        `<span class="chg ${CS.chgClass(ch)}">${CS.faPct(ch)}</span>`;
      return `<span class="ticker__item"><span class="live-dot live-dot--brand"></span><b>${label}</b><span class="val">${fmt(s.value || 0)}</span>${chHtml}</span>`;
    }).join("");
    $("tickerTrack").innerHTML = items + items; // تکرار برای حرکت پیوسته
  }

  async function loadMacro() {
    try {
      const d = await CS.fetchJSON("/api/market/macro");
      renderTicker(d.stats);
      window.CSHeatmap.render($("heatmap"), d.heatmap);
      if (d.fear_greed) window.CSGauge.render($("fngGauge"), d.fear_greed);
      srcTag($("macroSrc"), d.source);
      srcTag($("heatmapSrc"), d.source);
    } catch (e) { console.warn("macro:", e); }
  }

  /* ---------- بیشترین رشد (با آیکون ارز) ---------- */
  function coinIcon(icon, sym) {
    const short = (sym || "?").slice(0, 4);
    return `<span class="coin">
      <img class="coin__img" src="${icon}" alt="${sym}" loading="lazy"
           onerror="this.style.display='none';this.nextElementSibling.style.display='grid'">
      <span class="coin__badge" style="display:none">${short}</span>
    </span>`;
  }

  async function loadGainers() {
    try {
      const d = await CS.fetchJSON("/api/market/gainers");
      $("gainers").innerHTML = d.gainers.map((g) => `
        <div class="rowitem">
          ${coinIcon(g.icon, g.symbol)}
          <div class="rowitem__main">
            <div class="rowitem__name">${g.symbol}</div>
            <div class="rowitem__sub">حجم: ${CS.faBig(g.volume_24h)}</div>
          </div>
          <div class="rowitem__price">
            <div class="p">${CS.faPrice(g.price)}</div>
            <span class="chg ${CS.chgClass(g.change_24h)}">${CS.faPct(g.change_24h)}</span>
          </div>
        </div>`).join("");
      srcTag($("gainersSrc"), d.source);
    } catch (e) { console.warn("gainers:", e); }
  }

  /* ---------- قیمت‌های کلیدی (با نماد) ---------- */
  const ICONS = {
    usdt: `<span class="kp-ic" style="background:linear-gradient(135deg,#26A17B,#1c7a5c)">₮</span>`,
    gold: `<span class="kp-ic" style="background:linear-gradient(135deg,#f6d365,#d4a017);color:#5a3e00">Au</span>`,
    xau:  `<span class="kp-ic" style="background:linear-gradient(135deg,#f6d365,#d4a017);color:#5a3e00">Au</span>`,
    xag:  `<span class="kp-ic" style="background:linear-gradient(135deg,#e8e8ee,#aab0bd);color:#3a3f4a">Ag</span>`,
    oil:  `<span class="kp-ic" style="background:linear-gradient(135deg,#3a4654,#1c2530)">
             <svg viewBox="0 0 24 24" width="16" height="16" fill="#ffd166"><path d="M12 2s6 7 6 12a6 6 0 1 1-12 0c0-5 6-12 6-12z"/></svg></span>`,
  };

  function kpRow(iconKey, name, priceHtml, ch, note) {
    const chHtml = (ch && ch !== 0) ? `<span class="chg ${CS.chgClass(ch)}">${CS.faPct(ch)}</span>` : "";
    return `<div class="keyprice">
      ${ICONS[iconKey] || ""}
      <div class="keyprice__main">
        <div class="keyprice__name">${name}<span class="live-dot live-dot--brand"></span></div>
        ${note ? `<div class="keyprice__note">${note}</div>` : ""}
      </div>
      <div class="keyprice__right">
        <div class="keyprice__price">${priceHtml}</div>
        ${chHtml}
      </div>
    </div>`;
  }

  async function loadInternal() {
    try {
      const d = await CS.fetchJSON("/api/market/internal");
      const rows = [];
      rows.push(kpRow("usdt", "تتر / تومان", CS.faNum(d.usdt_irt.price) + " <small>تومان</small>", d.usdt_irt.change_24h));
      rows.push(kpRow("gold", d.gold_18k.name, CS.faNum(d.gold_18k.price) + " <small>تومان</small>", d.gold_18k.change_24h, "به‌روزرسانی هر ۳۰ دقیقه"));
      const f = d.futures || {};
      if (f.XAUUSDT) rows.push(kpRow("xau", f.XAUUSDT.name, CS.faPrice(f.XAUUSDT.price), f.XAUUSDT.change_24h));
      if (f.XAGUSDT) rows.push(kpRow("xag", f.XAGUSDT.name, CS.faPrice(f.XAGUSDT.price), f.XAGUSDT.change_24h));
      if (f.OILBRENTUSDT) rows.push(kpRow("oil", f.OILBRENTUSDT.name, CS.faPrice(f.OILBRENTUSDT.price), f.OILBRENTUSDT.change_24h));
      $("internalPrices").innerHTML = rows.join("");
    } catch (e) { console.warn("internal:", e); }
  }

  /* ---------- راه‌اندازی + پایش دوره‌ای ---------- */
  loadMacro();    setInterval(loadMacro, 10 * 60 * 1000);   // CryptoRank: هر ۱۰ دقیقه
  loadGainers();  setInterval(loadGainers, 15 * 1000);      // توبیت: هر ۱۵ ثانیه
  loadInternal(); setInterval(loadInternal, 20 * 1000);     // داخلی: هر ۲۰ ثانیه
})();
