/* نقشهٔ حرارتی به‌سبک CryptoRank: treemap مربعی (squarified)، گروه‌بندی بر اساس
   دسته، اندازهٔ کاشی ∝ مارکت‌کپ/حجم، رنگ ∝ تغییر دورهٔ انتخابی.
   کنترل‌ها: بازهٔ زمانی (24H..YTD)، معیار اندازه (مارکت‌کپ/حجم/دسته)، حذف
   بیت‌کوین/استیبل‌کوین. داده از CryptoRank؛ قیمت/۲۴ساعته زنده از توبیت. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const STABLE = new Set(["USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "TUSD",
    "USD1", "BUSD", "PYUSD", "USDP", "GUSD", "USDD", "FRAX", "LUSD", "USDG"]);
  let _items = [];
  let _wired = false;
  let _sig = "";
  let _tiles = {};            // symbol → عنصر کاشی (برای به‌روزرسانی بدون بازچینش)
  const state = { period: "h24", size: "mcap", top: "100", exBTC: false, exStable: true };

  // سطل‌های رنگ مطابق راهنمای CryptoRank (-12/-7/-3/<0/0/>0/+3/+7/+12)
  function colorFor(ch) {
    ch = ch || 0;
    if (ch <= -12) return { bg: "#8b1a1a", fg: "#fff" };
    if (ch <= -7) return { bg: "#c0392b", fg: "#fff" };
    if (ch <= -3) return { bg: "#e2675e", fg: "#fff" };
    if (ch < 0) return { bg: "#f6cfcc", fg: "#b3261e" };
    if (ch === 0) return { bg: "#d6dbe1", fg: "#5b6470" };
    if (ch < 3) return { bg: "#bfe9d1", fg: "#1c7a47" };
    if (ch < 7) return { bg: "#74cf9b", fg: "#0c3d24" };
    if (ch < 12) return { bg: "#33a866", fg: "#fff" };
    return { bg: "#1a7a45", fg: "#fff" };
  }

  // ---- treemap مربعی (squarified) ----
  function worstRatio(row, side) {
    let sum = 0, mx = -Infinity, mn = Infinity;
    for (const a of row) { sum += a; if (a > mx) mx = a; if (a < mn) mn = a; }
    const s2 = sum * sum, l2 = side * side;
    return Math.max((l2 * mx) / s2, s2 / (l2 * mn));
  }
  function squarify(data, x, y, w, h) {
    // data: [{value, ref}] — خروجی: [{ref, x, y, w, h}]
    const out = [];
    const total = data.reduce((s, d) => s + (d.value > 0 ? d.value : 0), 0) || 1;
    const scale = (w * h) / total;
    const items = data.filter((d) => d.value > 0).map((d) => ({ ref: d.ref, area: d.value * scale }));
    let rx = x, ry = y, rw = w, rh = h, i = 0;
    while (i < items.length) {
      const side = Math.min(rw, rh) || 1;
      const row = [items[i].area];
      const refs = [items[i]];
      while (i + row.length < items.length) {
        const nextArea = items[i + row.length].area;
        if (worstRatio(row.concat(nextArea), side) > worstRatio(row, side)) break;
        row.push(nextArea); refs.push(items[i + row.length]);
      }
      const rowArea = row.reduce((s, a) => s + a, 0);
      if (rw >= rh) {
        const colW = rowArea / rh;
        let yy = ry;
        refs.forEach((d) => { const hh = d.area / colW; out.push({ ref: d.ref, x: rx, y: yy, w: colW, h: hh }); yy += hh; });
        rx += colW; rw -= colW;
      } else {
        const rowH = rowArea / rw;
        let xx = rx;
        refs.forEach((d) => { const ww = d.area / rowH; out.push({ ref: d.ref, x: xx, y: ry, w: ww, h: rowH }); xx += ww; });
        ry += rowH; rh -= rowH;
      }
      i += refs.length;
    }
    return out;
  }

  function valueOf(it) {
    if (state.size === "volume") return it.volume || it.market_cap || 0;
    if (state.size === "equal") return 1;
    return it.market_cap || 0;
  }
  function filtered() {
    let list = _items.filter((it) => {
      if (state.exStable && (it.category === "Stablecoin" || STABLE.has((it.symbol || "").toUpperCase()))) return false;
      if (state.exBTC && (it.symbol || "").toUpperCase() === "BTC") return false;
      if (state.top === "coins" && (it.type || "") !== "coin") return false;
      if (state.top === "tokens" && (it.type || "") !== "token") return false;
      return (it.market_cap || 0) > 0;
    });
    list.sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
    const n = parseInt(state.top, 10);
    if (!isNaN(n)) list = list.slice(0, n);
    return list;
  }

  function tileHTML(it, rc) {
    const ch = (it.changes || {})[state.period] || 0;
    const c = colorFor(ch);
    const fs = Math.max(8, Math.min(40, Math.min((rc.w * 1.7) / Math.max(3, it.symbol.length), rc.h * 0.42)));
    const showPct = rc.h > 34 && rc.w > 40;
    const showPrice = rc.h > 56 && rc.w > 54;
    const inner =
      '<span class="hm__sym" style="font-size:' + fs.toFixed(0) + 'px">' + it.symbol + '</span>' +
      (showPct ? '<span class="hm__pct" style="font-size:' + Math.max(8, fs * 0.42).toFixed(0) + 'px">' + CS.faPct(ch) + '</span>' : "") +
      (showPrice ? '<span class="hm__nm">' + CS.faPriceUsd(it.price) + '</span>' : "");
    return '<div class="hm" data-sym="' + it.symbol + '" title="' + it.name + " • " + CS.faPriceUsd(it.price) + " • " + CS.faPct(ch) + '"' +
      ' style="left:' + rc.x.toFixed(1) + 'px;top:' + rc.y.toFixed(1) + 'px;width:' + rc.w.toFixed(1) + 'px;height:' + rc.h.toFixed(1) +
      'px;background:' + c.bg + ';color:' + c.fg + '">' + inner + "</div>";
  }

  function render(el, items) {
    if (!el) return;
    if (items) _items = items;
    wire(el);
    const list = filtered();
    if (!list.length) { el.innerHTML = '<span class="src-tag">داده‌ای موجود نیست</span>'; return; }

    const W = el.clientWidth || 900;
    const H = W < 600 ? 560 : Math.min(640, Math.round(W * 0.56));
    el.style.height = H + "px";

    // امضای چیدمان: اگر فقط رنگ/قیمت عوض شده، بازچینش نمی‌کنیم (بدون پرش)
    const sig = state.size + "|" + state.exBTC + "|" + state.exStable + "|" + Math.round(W) + "|" +
      list.map((it) => it.symbol).join(",");
    if (sig === _sig && Object.keys(_tiles).length) { patch(list); return; }
    _sig = sig;

    // گروه‌بندی بر اساس دسته
    const groups = {};
    list.forEach((it) => { (groups[it.category] = groups[it.category] || []).push(it); });
    const cats = Object.keys(groups).map((name) => {
      const arr = groups[name].slice().sort((a, b) => valueOf(b) - valueOf(a));
      return { name: name, items: arr, value: arr.reduce((s, it) => s + valueOf(it), 0) };
    }).filter((c) => c.value > 0).sort((a, b) => b.value - a.value);

    const catRects = squarify(cats.map((c) => ({ value: c.value, ref: c })), 0, 0, W, H);
    let html = "";
    catRects.forEach((cr) => {
      const cat = cr.ref;
      const lblH = (cr.h > 54 && cr.w > 64) ? 15 : 0;
      html += '<div class="hm-cat" style="left:' + cr.x.toFixed(1) + 'px;top:' + cr.y.toFixed(1) +
        'px;width:' + cr.w.toFixed(1) + 'px;height:' + cr.h.toFixed(1) + 'px">';
      if (lblH) html += '<div class="hm-cat__lbl">' + cat.name + "</div>";
      const iw = Math.max(0, cr.w - 3), ih = Math.max(0, cr.h - lblH - 2);
      const coinRects = squarify(cat.items.map((it) => ({ value: valueOf(it), ref: it })), 1, lblH + 1, iw, ih);
      coinRects.forEach((rc) => { html += tileHTML(rc.ref, rc); });
      html += "</div>";
    });
    el.innerHTML = html;
    _tiles = {};
    el.querySelectorAll(".hm").forEach((t) => { _tiles[t.getAttribute("data-sym")] = t; });
  }

  // به‌روزرسانی سریع رنگ/درصد/قیمت بدون بازچینش (برای پولینگ ۵ثانیه‌ای)
  function patch(list) {
    list.forEach((it) => {
      const t = _tiles[it.symbol];
      if (!t) return;
      const ch = (it.changes || {})[state.period] || 0;
      const c = colorFor(ch);
      t.style.background = c.bg; t.style.color = c.fg;
      t.title = it.name + " • " + CS.faPriceUsd(it.price) + " • " + CS.faPct(ch);
      const pct = t.querySelector(".hm__pct"); if (pct) pct.textContent = CS.faPct(ch);
      const nm = t.querySelector(".hm__nm"); if (nm) nm.textContent = CS.faPriceUsd(it.price);
    });
  }

  function buildLegend() {
    const el = document.getElementById("hmLegend");
    if (!el) return;
    const stops = [["−۱۲٪", -12], ["−۷٪", -7], ["−۳٪", -3], ["<۰٪", -1], ["۰٪", 0], [">۰٪", 1], ["+۳٪", 3], ["+۷٪", 7], ["+۱۲٪", 12]];
    el.innerHTML = stops.map(([lbl, v]) =>
      '<span class="hm-leg"><i style="background:' + colorFor(v).bg + '"></i>' + lbl + "</span>").join("") +
      '<span class="heatmap-legend__src">Source: CoinMarketCap · live: Toobit</span>';
  }

  function wire(el) {
    if (_wired) return;
    _wired = true;
    buildLegend();
    const seg = (id, attr, key, after) => {
      const box = document.getElementById(id);
      if (!box) return;
      box.addEventListener("click", (e) => {
        const b = e.target.closest("button"); if (!b) return;
        box.querySelectorAll("button").forEach((x) => x.classList.remove("is-active"));
        b.classList.add("is-active");
        state[key] = b.getAttribute(attr);
        if (after) after();
        _sig = ""; render(el);
      });
    };
    seg("hmPeriod", "data-p", "period");
    seg("hmSize", "data-s", "size");
    const top = document.getElementById("hmTop");
    if (top) top.addEventListener("change", () => { state.top = top.value; _sig = ""; render(el); });
    const exB = document.getElementById("hmExBtc"), exS = document.getElementById("hmExStable");
    if (exB) exB.addEventListener("change", () => { state.exBTC = exB.checked; _sig = ""; render(el); });
    if (exS) exS.addEventListener("change", () => { state.exStable = exS.checked; _sig = ""; render(el); });
    let t;
    w.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { _sig = ""; render(el); }, 200); });
  }

  w.CSHeatmap = { render };
})(window);
