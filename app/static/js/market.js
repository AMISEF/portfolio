/* موتور دادهٔ صفحهٔ خانه: واکشی اندپوینت‌ها، رندر و به‌روزرسانی لحظه‌ای (بدون رفرش).
   ۵ ارز برتر از توبیت هر ۵ ثانیه، شاخص‌های کلان از CoinMarketCap، نقشهٔ حرارتی
   و قیمت‌های کلیدی زنده پایش می‌شوند و هنگام تغییر «چشمک» می‌خورند. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  function srcTag(el, source) {
    if (!el) return;
    const live = source === "live";
    el.className = "src-tag" + (live ? " live" : "");
    el.textContent = live ? "● live" : "● sample";
  }

  // افکت چشمک هنگام تغییر قیمت
  const _last = {};
  function flash(el, key, val) {
    if (!el) return;
    if (_last[key] !== undefined && _last[key] !== val) {
      const cls = val > _last[key] ? "flash-up" : "flash-down";
      el.classList.remove("flash-up", "flash-down");
      void el.offsetWidth;            // ری‌استارت انیمیشن
      el.classList.add(cls);
    }
    _last[key] = val;
  }

  function coinIcon(symbol, cls) {
    const sym = String(symbol || "").toLowerCase().replace(/usdt$|usd$/i, "");
    const url = "https://cdn.jsdelivr.net/npm/cryptocurrency-icons@0.18.1/128/color/" + sym + ".png";
    const letter = String(symbol || "?").slice(0, 3).toUpperCase();
    return '<div class="' + (cls || "rowitem__icon") + '">' +
      '<img src="' + url + '" alt="' + symbol + '" loading="lazy" ' +
      'onerror="this.parentNode.classList.add(\'badge\');this.parentNode.textContent=\'' + letter + '\'"></div>';
  }

  /* ---------- تیکر متحرک شاخص‌ها ---------- */
  function renderTicker(d) {
    const items = [];
    const push = (label, valStr, ch) => {
      const chHtml = (ch === undefined || ch === null || ch === 0) ? "" :
        '<span class="' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
      items.push('<span class="ticker__item"><span class="live-dot live-dot--brand"></span><b>' +
        label + '</b><span class="val">' + valStr + '</span>' + chHtml + '</span>');
    };
    if (d.market_cap) push("ارزش کل بازار", CS.faBig(d.market_cap.value), d.market_cap.change_24h);
    if (d.volume_24h) push("حجم ۲۴ساعته", CS.faBig(d.volume_24h.value), d.volume_24h.change_24h);
    if (d.dominance) {
      push("دامیننس بیت‌کوین", CS.toFa(d.dominance.btc.toFixed(2)) + "٪", d.dominance.btc_change_24h);
      push("دامیننس اتریوم", CS.toFa(d.dominance.eth.toFixed(2)) + "٪");
      if (d.dominance.usdt !== undefined && d.dominance.usdt !== null)
        push("دامیننس تتر", CS.toFa(d.dominance.usdt.toFixed(2)) + "٪");
    }
    if (d.altcoin_season) push("فصل آلت‌کوین", CS.toFa(d.altcoin_season.value) + "/۱۰۰");
    if (d.fear_greed) push("ترس و طمع", CS.toFa(d.fear_greed.value) + " · " + (d.fear_greed.label_fa || ""));
    const html = items.join("");
    $("tickerTrack").innerHTML = html + html;
  }

  /* ---------- کارت ارزش کل بازار ---------- */
  function renderMarketCap(d) {
    const mc = d.market_cap || {}, vol = d.volume_24h || {};
    const chHtml = (ch) => (ch === undefined || ch === null || ch === 0) ? "" :
      '<span class="chg ' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
    $("boxMarketCap").innerHTML =
      '<div class="mcap__item"><div class="mcap__label">ارزش بازار</div>' +
        '<div class="mcap__value">' + CS.faBig(mc.value || 0) + '</div>' + chHtml(mc.change_24h) + '</div>' +
      '<div class="mcap__item"><div class="mcap__label">حجم ۲۴ساعته</div>' +
        '<div class="mcap__value">' + CS.faBig(vol.value || 0) + '</div>' + chHtml(vol.change_24h) + '</div>';
  }

  /* ---------- کارت دامیننس (نوار سه‌بخشی) ---------- */
  function renderDominance(d) {
    const dom = d.dominance || { btc: 0, eth: 0, others: 0 };
    const pct = (v) => CS.toFa((v || 0).toFixed(1)) + "٪";
    $("boxDominance").innerHTML =
      '<div class="dom__legend">' +
        '<span><i style="background:#F7931A"></i>بیت‌کوین</span>' +
        '<span><i style="background:#627EEA"></i>اتریوم</span>' +
        '<span><i style="background:var(--text-dim)"></i>سایر</span>' +
      '</div>' +
      '<div class="dom__values">' +
        '<b style="color:#F7931A">' + pct(dom.btc) + '</b>' +
        '<b style="color:#627EEA">' + pct(dom.eth) + '</b>' +
        '<b style="color:var(--text-dim)">' + pct(dom.others) + '</b>' +
      '</div>' +
      '<div class="dom__bar">' +
        '<span style="width:' + (dom.btc || 0) + '%;background:#F7931A"></span>' +
        '<span style="width:' + (dom.eth || 0) + '%;background:#627EEA"></span>' +
        '<span style="width:' + (dom.others || 0) + '%;background:var(--gray-500)"></span>' +
      '</div>';
  }

  /* ---------- شِماتیک قیمت (اسپارک‌لاین) ---------- */
  function sparkSVG(arr, up) {
    if (!arr || arr.length < 2) return "";
    const W = 120, H = 40, p = 3;
    let min = Infinity, max = -Infinity;
    arr.forEach((v) => { if (v < min) min = v; if (v > max) max = v; });
    const rng = (max - min) || 1;
    const pts = arr.map((v, i) => {
      const x = p + (i / (arr.length - 1)) * (W - 2 * p);
      const y = p + (1 - (v - min) / rng) * (H - 2 * p);
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    const col = up ? "var(--up)" : "var(--down)";
    return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      '<polyline points="' + pts + '" fill="none" stroke="' + col +
      '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>';
  }

  /* ---------- کارت میانگین RSI بازار ---------- */
  function renderRsi(d) {
    const r = d.rsi || {};
    if (!r.value) return;
    const v = Math.max(0, Math.min(100, r.value));
    const col = v < 30 ? "var(--up)" : v > 70 ? "var(--down)" : "var(--heading)";
    $("boxRsi").innerHTML =
      '<div class="rsi__top"><span class="rsi__num" style="color:' + col + '">' + CS.toFa(v.toFixed(2)) + '</span></div>' +
      '<div class="rsi__ends" dir="ltr"><span>Oversold</span><span>Overbought</span></div>' +
      '<div class="rsi__bar"><span class="rsi__knob" style="left:calc(' + v + '% - 9px)"></span></div>';
  }

  /* ---------- کارت فصل آلت‌کوین (نوار رنگی + نشانگر) ---------- */
  function renderAltseason(d) {
    const a = d.altcoin_season || { value: 0, label_fa: "" };
    const v = Math.max(0, Math.min(100, a.value || 0));
    $("boxAltseason").innerHTML =
      '<div class="alt__top"><span class="alt__num">' + CS.toFa(v) + '</span><span class="alt__den">/۱۰۰</span>' +
        '<span class="alt__label">' + (a.label_fa || "") + '</span></div>' +
      '<div class="alt__ends"><span>فصل بیت‌کوین</span><span>فصل آلت‌کوین</span></div>' +
      '<div class="alt__bar"><span class="alt__knob" style="right:calc(' + v + '% - 9px)"></span></div>';
  }

  async function loadMacro() {
    try {
      const d = await CS.fetchJSON("/api/market/macro");
      renderTicker(d); renderMarketCap(d); renderDominance(d); renderAltseason(d); renderRsi(d);
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
      srcTag($("macroSrc"), d.source);
    } catch (e) { console.warn("macro:", e); }
  }

  /* نقشهٔ حرارتی اکنون از ویجت رسمی CryptoRank در قالب صفحه بارگذاری می‌شود. */

  /* ---------- ۵ ارز برتر بازار (کارت افقی، زنده هر ۵ ثانیه) ---------- */
  async function loadCoins() {
    try {
      const d = await CS.fetchJSON("/api/market/coins");
      $("topCoins").innerHTML = d.coins.map((g) =>
        '<div class="coincard" data-sym="' + g.symbol + '">' +
        '<div class="coincard__head">' + coinIcon(g.symbol, "coincard__icon") +
          '<span class="coincard__name">' + g.symbol + '</span></div>' +
        '<div class="coincard__body">' +
          '<div class="coincard__left">' +
            '<div class="coincard__price" data-price>' + CS.faPriceUsd(g.price) + '</div>' +
            '<span class="chg ' + CS.chgClass(g.change_24h) + '">' + CS.faPct(g.change_24h) + '</span>' +
          '</div>' +
          sparkSVG(g.spark, g.change_24h >= 0) +
        '</div>' +
        '</div>'
      ).join("");
      d.coins.forEach((g) => {
        const el = document.querySelector('#topCoins .coincard[data-sym="' + g.symbol + '"] [data-price]');
        flash(el, "c_" + g.symbol, g.price);
      });
      srcTag($("coinsSrc"), d.source);
    } catch (e) { console.warn("coins:", e); }
  }

  /* ---------- قیمت‌های کلیدی (تتر/طلا/نقره/نفت) ---------- */
  // آیکون تصویری هر ردیف (فایل‌ها در app/static/img/)
  const _KP = {
    usdt: "/static/img/usdt.png",   // تتر
    g18:  "/static/img/gold18.png", // طلای ۱۸ عیار (تکه‌های طلا)
    xau:  "/static/img/xau.png",    // انس طلای جهانی (شمش طلا)
    xag:  "/static/img/xag.png",    // نقره (شمش نقره)
    oil:  "/static/img/oil.png",    // نفت خام (بشکه)
  };

  function keyRow(id, img, name, sub, priceStr, ch, spark) {
    const chHtml = (ch === undefined || ch === null) ? "" :
      '<span class="chg ' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
    const sp = (spark && spark.length > 1) ?
      '<div class="kp-spark">' + sparkSVG(spark, (ch || 0) >= 0) + '</div>' : "";
    return '<div class="rowitem" data-kp="' + id + '"><span class="kp-ic kp-ic--img"><img src="' + img + '" alt="" loading="lazy"></span>' +
      '<div class="rowitem__main"><div class="rowitem__name">' + name + '</div>' +
      '<div class="rowitem__sub">' + sub + '</div></div>' + sp +
      '<div class="rowitem__right"><div class="rowitem__price" data-price>' + priceStr + '</div>' + chHtml + '</div></div>';
  }

  // آخرین داده‌های قیمت (برای به‌روزرسانی جداگانهٔ تتر)
  let _lastPriceData = null;

  async function loadPrices() {
    try {
      const d = await CS.fetchJSON("/api/market/prices");
      _lastPriceData = d;
      const rows = [];
      if (d.usdt_irt)
        rows.push(keyRow("usdt", _KP.usdt, d.usdt_irt.name || "تتر / تومان", "تومان",
          CS.faNum(d.usdt_irt.price) + " ت", d.usdt_irt.change_24h));
      if (d.gold_18k)
        rows.push(keyRow("g18", _KP.g18, "طلای ۱۸ عیار", d.gold_18k.sub || "هر گرم",
          CS.faNum(d.gold_18k.price) + " ت", d.gold_18k.change_24h));
      const c = d.commodities || {};
      if (c.XAU) rows.push(keyRow("xau", _KP.xau, c.XAU.name || "طلای جهانی", c.XAU.sub || "اونس", CS.faPriceUsd(c.XAU.price), c.XAU.change_24h, c.XAU.spark));
      if (c.XAG) rows.push(keyRow("xag", _KP.xag, c.XAG.name || "نقره", c.XAG.sub || "اونس", CS.faPriceUsd(c.XAG.price), c.XAG.change_24h, c.XAG.spark));
      if (c.OIL) rows.push(keyRow("oil", _KP.oil, c.OIL.name || "نفت خام", c.OIL.sub || "بشکه", CS.faPriceUsd(c.OIL.price), c.OIL.change_24h, c.OIL.spark));
      $("keyPrices").innerHTML = rows.join("") || '<span class="src-tag">داده‌ای موجود نیست</span>';

      if (d.usdt_irt) flash(document.querySelector('#keyPrices .rowitem[data-kp="usdt"] [data-price]'), "usdt", d.usdt_irt.price);
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
    } catch (e) { console.warn("prices:", e); }
  }

  // تتر + طلای جهانی + نقره + نفت را هر ۱۵ ثانیه in-place به‌روز می‌کند
  function _updateRow(kp, priceText, ch) {
    const row = document.querySelector('#keyPrices .rowitem[data-kp="' + kp + '"]');
    if (!row) return;
    const priceEl = row.querySelector('[data-price]');
    if (priceEl) priceEl.textContent = priceText;
    const chEl = row.querySelector('.chg');
    if (chEl && ch !== undefined && ch !== null) {
      chEl.className = 'chg ' + CS.chgClass(ch);
      chEl.textContent = CS.faPct(ch);
    }
  }

  async function refreshLive() {
    try {
      const d = await CS.fetchJSON("/api/market/prices");
      if (d.usdt_irt) {
        const el = document.querySelector('#keyPrices .rowitem[data-kp="usdt"] [data-price]');
        if (el) { el.textContent = CS.faNum(d.usdt_irt.price) + " ت"; flash(el, "usdt", d.usdt_irt.price); }
      }
    } catch (e) { /* silent */ }
  }

  // انس طلا / نقره / نفت از SWAP توبیت هر ۵ ثانیه (زنده)
  async function loadLiveCommodities() {
    try {
      const d = await CS.fetchJSON("/api/market/live-commodities");
      const c = d.commodities || {};
      if (c.XAU) _updateRow("xau", CS.faPriceUsd(c.XAU.price), c.XAU.change_24h);
      if (c.XAG) _updateRow("xag", CS.faPriceUsd(c.XAG.price), c.XAG.change_24h);
      if (c.OIL) _updateRow("oil", CS.faPriceUsd(c.OIL.price), c.OIL.change_24h);
    } catch (e) { /* silent */ }
  }

  /* ---------- راه‌اندازی + پایش لحظه‌ای ---------- */
  loadMacro();   setInterval(loadMacro, 60 * 1000);               // ۶۰ ثانیه (CoinMarketCap)
  loadCoins();   setInterval(loadCoins, 5 * 1000);                // ۵ ثانیه (زنده — توبیت)
  loadPrices();  setInterval(loadPrices, 15 * 60 * 1000);         // ۱۵ دقیقه (طلای ۱۸ع / SourceArena)
  setTimeout(function() { setInterval(refreshLive, 15 * 1000); }, 3000);         // ۱۵ ثانیه (تتر)
  setTimeout(function() { loadLiveCommodities(); setInterval(loadLiveCommodities, 5 * 1000); }, 1500); // ۵ ثانیه (طلا/نقره/نفت)
})(window);
