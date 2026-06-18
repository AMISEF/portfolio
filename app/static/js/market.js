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

  /* ---------- کارت فصل آلت‌کوین (نوار رنگی + نشانگر) ---------- */
  function renderAltseason(d) {
    const a = d.altcoin_season || { value: 0, label_fa: "" };
    const v = Math.max(0, Math.min(100, a.value || 0));
    $("boxAltseason").innerHTML =
      '<div class="alt__top"><span class="alt__num">' + CS.toFa(v) + '</span><span class="alt__den">/۱۰۰</span>' +
        '<span class="alt__label">' + (a.label_fa || "") + '</span></div>' +
      '<div class="alt__bar"><span class="alt__knob" style="right:calc(' + v + '% - 9px)"></span></div>' +
      '<div class="alt__ends"><span>فصل بیت‌کوین</span><span>فصل آلت‌کوین</span></div>';
  }

  async function loadMacro() {
    try {
      const d = await CS.fetchJSON("/api/market/macro");
      renderTicker(d); renderMarketCap(d); renderDominance(d); renderAltseason(d);
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
      srcTag($("macroSrc"), d.source);
    } catch (e) { console.warn("macro:", e); }
  }

  /* ---------- نقشهٔ حرارتی زنده (توبیت) ---------- */
  async function loadHeatmap() {
    try {
      const d = await CS.fetchJSON("/api/market/heatmap");
      w.CSHeatmap.render($("heatmap"), d.heatmap);
      srcTag($("heatmapSrc"), d.source);
    } catch (e) { console.warn("heatmap:", e); }
  }

  /* ---------- نمودار جریان خالص ETFها (ستونی انباشته، btc + eth) ---------- */
  function renderEtf(d) {
    const el = $("etfChart");
    if (!el) return;
    const pts = (d && d.points) || [];
    if (!pts.length) { el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>'; return; }

    const W = 760, H = 240, padT = 18, padB = 26, padX = 6;
    const plotH = H - padT - padB;
    // بیشینهٔ بخش مثبت و منفیِ هر روز (انباشت btc+eth هم‌علامت)
    let maxPos = 0, maxNeg = 0;
    pts.forEach((p) => {
      const pos = Math.max(0, p.btc) + Math.max(0, p.eth);
      const neg = Math.min(0, p.btc) + Math.min(0, p.eth);
      if (pos > maxPos) maxPos = pos;
      if (neg < maxNeg) maxNeg = neg;
    });
    const range = (maxPos - maxNeg) || 1;
    const y0 = padT + (maxPos / range) * plotH;            // خط صفر
    const sc = plotH / range;                               // مقیاس عمودی
    const n = pts.length;
    const slot = (W - padX * 2) / n;
    const bw = Math.max(3, Math.min(18, slot * 0.62));

    const seg = (x, vTop, vBot, color) => {
      // مستطیل از vBot تا vTop (مقادیر دلاری، نسبت به صفر)
      const yTop = y0 - vTop * sc, yBot = y0 - vBot * sc;
      const h = Math.max(0.6, Math.abs(yBot - yTop));
      return '<rect x="' + (x - bw / 2).toFixed(1) + '" y="' + Math.min(yTop, yBot).toFixed(1) +
        '" width="' + bw.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="1" fill="' + color + '"/>';
    };

    let bars = "";
    pts.forEach((p, i) => {
      const x = padX + slot * (i + 0.5);
      // بخش مثبت: btc از صفر، سپس eth انباشته
      let up = 0;
      if (p.btc > 0) { bars += seg(x, up + p.btc, up, "#F7931A"); up += p.btc; }
      if (p.eth > 0) { bars += seg(x, up + p.eth, up, "#3861FB"); up += p.eth; }
      // بخش منفی: رو به پایین
      let dn = 0;
      if (p.btc < 0) { bars += seg(x, dn, dn + p.btc, "#F7931A"); dn += p.btc; }
      if (p.eth < 0) { bars += seg(x, dn, dn + p.eth, "#3861FB"); dn += p.eth; }
    });

    // برچسب‌های محور افقی (حدود ۶ تا، برای جلوگیری از شلوغی)
    let labels = "";
    const step = Math.max(1, Math.round(n / 6));
    for (let i = 0; i < n; i += step) {
      const x = padX + slot * (i + 0.5);
      labels += '<text x="' + x.toFixed(1) + '" y="' + (H - 8) +
        '" text-anchor="middle" class="etf__xlbl">' + pts[i].label + '</text>';
    }

    const last = pts[pts.length - 1];
    const totalCls = last.total >= 0 ? "up" : "down";
    const sign = last.total >= 0 ? "+" : "−";
    const head = '<div class="etf__head"><span class="etf__total ' + totalCls + '">' + sign + '$' +
      CS.toFa(Math.abs(last.total).toLocaleString("en-US")) + 'M</span>' +
      '<span class="etf__date" dir="ltr">' + last.label + '</span></div>';

    el.innerHTML = head +
      '<svg class="etf__svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">' +
      '<line x1="' + padX + '" y1="' + y0.toFixed(1) + '" x2="' + (W - padX) + '" y2="' + y0.toFixed(1) +
      '" stroke="var(--border)" stroke-width="1"/>' + bars + labels + '</svg>';
  }

  async function loadEtf() {
    try {
      const d = await CS.fetchJSON("/api/market/etf");
      renderEtf(d);
      srcTag($("etfSrc"), d.source);
    } catch (e) { console.warn("etf:", e); }
  }

  /* ---------- ۵ ارز برتر بازار (کارت افقی، زنده هر ۵ ثانیه) ---------- */
  async function loadCoins() {
    try {
      const d = await CS.fetchJSON("/api/market/coins");
      $("topCoins").innerHTML = d.coins.map((g) =>
        '<div class="coincard" data-sym="' + g.symbol + '">' +
        '<div class="coincard__head">' + coinIcon(g.symbol, "coincard__icon") +
          '<span class="coincard__name">' + g.symbol + '</span></div>' +
        '<div class="coincard__price" data-price>' + CS.faPriceUsd(g.price) + '</div>' +
        '<span class="chg ' + CS.chgClass(g.change_24h) + '">' + CS.faPct(g.change_24h) + '</span>' +
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
  function keyRow(id, ic, color, name, sub, priceStr, ch) {
    const chHtml = (ch === undefined || ch === null) ? "" :
      '<span class="chg ' + CS.chgClass(ch) + '">' + CS.faPct(ch) + '</span>';
    return '<div class="rowitem" data-kp="' + id + '"><span class="kp-ic" style="background:' + color + '">' + ic + '</span>' +
      '<div class="rowitem__main"><div class="rowitem__name">' + name + '</div>' +
      '<div class="rowitem__sub">' + sub + '</div></div>' +
      '<div class="rowitem__right"><div class="rowitem__price" data-price>' + priceStr + '</div>' + chHtml + '</div></div>';
  }

  async function loadPrices() {
    try {
      const d = await CS.fetchJSON("/api/market/prices");
      const rows = [];
      if (d.usdt_irt)
        rows.push(keyRow("usdt", "₮", "#26A17B", d.usdt_irt.name || "تتر / تومان", "تومان",
          CS.faNum(d.usdt_irt.price) + " ت", d.usdt_irt.change_24h));
      if (d.gold_18k)
        rows.push(keyRow("g18", "ط", "#D4AF37", "طلای ۱۸ عیار", d.gold_18k.sub || "هر گرم",
          CS.faNum(d.gold_18k.price) + " ت", d.gold_18k.change_24h));
      const c = d.commodities || {};
      if (c.XAU) rows.push(keyRow("xau", "Au", "#C9A227", c.XAU.name || "طلای جهانی", c.XAU.sub || "اونس", CS.faPriceUsd(c.XAU.price), c.XAU.change_24h));
      if (c.XAG) rows.push(keyRow("xag", "Ag", "#9AA3AC", c.XAG.name || "نقره", c.XAG.sub || "اونس", CS.faPriceUsd(c.XAG.price), c.XAG.change_24h));
      if (c.OIL) rows.push(keyRow("oil", "O", "#1B1B1B", c.OIL.name || "نفت خام", c.OIL.sub || "بشکه", CS.faPriceUsd(c.OIL.price), c.OIL.change_24h));
      $("keyPrices").innerHTML = rows.join("") || '<span class="src-tag">داده‌ای موجود نیست</span>';

      if (d.usdt_irt) flash(document.querySelector('#keyPrices .rowitem[data-kp="usdt"] [data-price]'), "usdt", d.usdt_irt.price);
      if (d.fear_greed) w.CSGauge.render($("fngGauge"), d.fear_greed);
    } catch (e) { console.warn("prices:", e); }
  }

  /* ---------- راه‌اندازی + پایش لحظه‌ای ---------- */
  loadMacro();   setInterval(loadMacro, 60 * 1000);    // ۶۰ ثانیه (CoinMarketCap)
  loadHeatmap(); setInterval(loadHeatmap, 12 * 1000);  // ۱۲ ثانیه (زنده)
  loadCoins();   setInterval(loadCoins, 5 * 1000);     // ۵ ثانیه (زنده — توبیت)
  loadPrices();  setInterval(loadPrices, 8 * 1000);    // ۸ ثانیه (زنده)
  loadEtf();     setInterval(loadEtf, 30 * 60 * 1000); // ۳۰ دقیقه (دادهٔ روزانه)
})(window);
