/* نقشهٔ حرارتی به‌سبک CryptoRank: treemap مربعی (squarified)، گروه‌بندی بر اساس
   دسته با برچسب و کادر، اندازهٔ کاشی ∝ مارکت‌کپ/حجم، رنگ ∝ تغییر دورهٔ انتخابی،
   و تول‌تیپِ شناورِ دسته (مثل CryptoRank). کنترل‌ها: بازهٔ زمانی (24H..3M)، معیار
   اندازه، حذف بیت‌کوین/استیبل‌کوین. داده از CoinMarketCap؛ قیمت/۲۴ساعته زنده از توبیت. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const STABLE = new Set(["USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "TUSD",
    "USD1", "BUSD", "PYUSD", "USDP", "GUSD", "USDD", "FRAX", "LUSD", "USDG"]);
  let _items = [];
  let _wired = false;
  let _sig = "";
  let _tiles = {};            // symbol → عنصر کاشی (برای به‌روزرسانی بدون بازچینش)
  let _cats = {};             // نام دسته → فهرست ارزها (برای تول‌تیپ)
  let _tip = null;            // عنصر تول‌تیپ شناور
  const state = { period: "h24", size: "mcap", top: "100", exBTC: false, exStable: true };

  // سطل‌های رنگ به‌سبک CryptoRank — پالت اشباع‌شده و یکدست (-12/-7/-3/<0/0/>0/+3/+7/+12)
  function colorFor(ch) {
    ch = ch || 0;
    if (ch <= -12) return { bg: "#7a271a", fg: "#fff" };
    if (ch <= -7) return { bg: "#d92d20", fg: "#fff" };
    if (ch <= -3) return { bg: "#ef6351", fg: "#fff" };
    if (ch < 0) return { bg: "#f5bcb4", fg: "#8a1c11" };
    if (ch === 0) return { bg: "#9aa7b6", fg: "#1e293b" };
    if (ch < 3) return { bg: "#b4e5c9", fg: "#14603a" };
    if (ch < 7) return { bg: "#4ecb8d", fg: "#0b3f25" };
    if (ch < 12) return { bg: "#1fa864", fg: "#fff" };
    return { bg: "#127a45", fg: "#fff" };
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
        const j = i + row.length;              // اندیس را قبل از push ثابت نگه دار
        const nextArea = items[j].area;
        if (worstRatio(row.concat(nextArea), side) > worstRatio(row, side)) break;
        row.push(nextArea); refs.push(items[j]);
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
    // فشرده‌سازی توانی (√) مثل CryptoRank تا BTC/ETH کل نقشه را نبلعند و
    // ارزهای کوچک هم دیده شوند؛ نسبت‌ها حفظ ولی اختلاف‌ها ملایم می‌شود.
    let v;
    if (state.size === "volume") v = it.volume || it.market_cap || 0;
    else if (state.size === "equal") return 1;
    else v = it.market_cap || 0;
    return v > 0 ? Math.sqrt(v) : 0;
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

  function chOf(it) { return (it.changes || {})[state.period] || 0; }

  function tileHTML(it, rc) {
    const ch = chOf(it);
    const c = colorFor(ch);
    // حاشیهٔ داخلی تطبیقی: کاشی‌های کوچک حاشیهٔ کمتری می‌گیرند تا نامِ ارز جا شود
    const padW = rc.w > 44 ? 10 : (rc.w > 26 ? 4 : 2);
    const padH = rc.h > 40 ? 8 : (rc.h > 22 ? 4 : 2);
    const iw = Math.max(0, rc.w - padW), ih = Math.max(0, rc.h - padH);
    const showPct = rc.h > 36 && rc.w > 48;
    const showPrice = rc.h > 64 && rc.w > 74;
    const lines = 1 + (showPct ? 0.62 : 0) + (showPrice ? 0.55 : 0);
    let fs = Math.min((iw * 1.32) / Math.max(3, it.symbol.length), (ih / lines) * 0.86, 40);
    // نام ارز تا جای ممکن نمایش داده شود؛ فقط کاشی‌های واقعاً ریز خالی می‌مانند
    // (آن‌ها با لمس/هاور، تول‌تیپِ دسته را با نام و قیمت نشان می‌دهند).
    const showSym = rc.w > 15 && rc.h > 9 && fs >= 5;
    fs = Math.max(6, Math.min(fs, rc.h - 2));
    const inner = !showSym ? "" :
      '<span class="hm__sym" style="font-size:' + fs.toFixed(0) + 'px">' + it.symbol + '</span>' +
      (showPct ? '<span class="hm__pct" style="font-size:' + Math.max(8, Math.min(20, fs * 0.48)).toFixed(0) + 'px">' + CS.faPct(ch) + '</span>' : "") +
      (showPrice ? '<span class="hm__nm" style="font-size:' + Math.max(8, Math.min(14, fs * 0.34)).toFixed(0) + 'px">' + CS.faPriceUsd(it.price) + '</span>' : "");
    return '<div class="hm" data-sym="' + it.symbol + '" data-cat="' + it.category + '"' +
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
    // موبایل: نقشهٔ بلندتر تا کاشی‌ها بزرگ‌تر شوند و نامِ ارزهای بیشتری جا شود
    const H = W < 600 ? 700 : Math.min(660, Math.round(W * 0.58));
    el.style.height = H + "px";

    // امضای چیدمان: اگر فقط رنگ/قیمت عوض شده، بازچینش نمی‌کنیم (بدون پرش)
    const sig = state.size + "|" + state.exBTC + "|" + state.exStable + "|" + Math.round(W) + "|" +
      list.map((it) => it.symbol).join(",");
    if (sig === _sig && Object.keys(_tiles).length) { patch(list); return; }
    _sig = sig;

    // گروه‌بندی بر اساس دسته
    const groups = {};
    list.forEach((it) => { (groups[it.category] = groups[it.category] || []).push(it); });
    _cats = {};
    const cats = Object.keys(groups).map((name) => {
      const arr = groups[name].slice().sort((a, b) => valueOf(b) - valueOf(a));
      _cats[name] = arr;
      return { name: name, items: arr, value: arr.reduce((s, it) => s + valueOf(it), 0) };
    }).filter((c) => c.value > 0).sort((a, b) => b.value - a.value);

    const catRects = squarify(cats.map((c) => ({ value: c.value, ref: c })), 0, 0, W, H);
    let html = "";
    catRects.forEach((cr) => {
      const cat = cr.ref;
      const lblH = (cr.h > 40 && cr.w > 52) ? 17 : 0;
      html += '<div class="hm-cat" data-cat="' + cat.name + '" style="left:' + cr.x.toFixed(1) + 'px;top:' + cr.y.toFixed(1) +
        'px;width:' + cr.w.toFixed(1) + 'px;height:' + cr.h.toFixed(1) + 'px">';
      if (lblH) html += '<div class="hm-cat__lbl">' + cat.name + "</div>";
      const iw = Math.max(0, cr.w - 4), ih = Math.max(0, cr.h - lblH - 3);
      const coinRects = squarify(cat.items.map((it) => ({ value: valueOf(it), ref: it })), 2, lblH + 1, iw, ih);
      coinRects.forEach((rc) => { html += tileHTML(rc.ref, rc); });
      html += "</div>";
    });
    el.innerHTML = html;
    _tiles = {};
    el.querySelectorAll(".hm").forEach((t) => { _tiles[t.getAttribute("data-sym")] = t; });
    ensureTip(el);
  }

  // به‌روزرسانی سریع رنگ/درصد/قیمت بدون بازچینش (برای پولینگ ۵ثانیه‌ای)
  function patch(list) {
    list.forEach((it) => {
      const t = _tiles[it.symbol];
      if (!t) return;
      const ch = chOf(it);
      const c = colorFor(ch);
      t.style.background = c.bg; t.style.color = c.fg;
      const pct = t.querySelector(".hm__pct"); if (pct) pct.textContent = CS.faPct(ch);
      const nm = t.querySelector(".hm__nm"); if (nm) nm.textContent = CS.faPriceUsd(it.price);
    });
    // داده‌های دسته را هم تازه نگه دار تا تول‌تیپ به‌روز باشد
    list.forEach((it) => { _cats[it.category] = _cats[it.category] || []; });
  }

  // ---- تول‌تیپ شناورِ دسته (به‌سبک CryptoRank) ----
  function ensureTip(el) {
    if (_tip && _tip.parentNode) return;
    _tip = document.createElement("div");
    _tip.className = "hm-tip";
    _tip.hidden = true;
    el.appendChild(_tip);
  }

  function tipHTML(catName, hoverSym) {
    const all = _cats[catName] || [];
    let arr = all.slice(0, 12);
    // اگر ارزِ انتخاب‌شده جزو ۱۲ تای اول نبود، حتماً به فهرست اضافه شود
    if (hoverSym && !arr.some((it) => it.symbol === hoverSym)) {
      const hit = all.find((it) => it.symbol === hoverSym);
      if (hit) arr = arr.slice(0, 11).concat(hit);
    }
    if (!arr.length) return "";
    const rows = arr.map((it) => {
      const ch = chOf(it);
      const cls = ch > 0 ? "up" : (ch < 0 ? "down" : "");
      const hi = (it.symbol === hoverSym) ? " is-hi" : "";
      return '<div class="hm-tip__row' + hi + '">' +
        '<span class="hm-tip__sym">' + it.symbol + '</span>' +
        '<span class="hm-tip__price">' + CS.faPriceUsd(it.price) + '</span>' +
        '<span class="hm-tip__ch ' + cls + '">' + CS.faPct(ch) + '</span></div>';
    }).join("");
    return '<div class="hm-tip__head">' + catName + '</div>' + rows;
  }

  function showTip(el, catName, hoverSym, ev) {
    if (!_tip) return;
    const html = tipHTML(catName, hoverSym);
    if (!html) { _tip.hidden = true; return; }
    _tip.innerHTML = html;
    _tip.hidden = false;
    const box = el.getBoundingClientRect();
    const tw = _tip.offsetWidth, th = _tip.offsetHeight;
    let x = ev.clientX - box.left + 14;
    let y = ev.clientY - box.top + 14;
    if (x + tw > box.width) x = ev.clientX - box.left - tw - 14;
    if (y + th > box.height) y = Math.max(4, box.height - th - 4);
    if (x < 0) x = 4;
    _tip.style.left = x.toFixed(0) + "px";
    _tip.style.top = y.toFixed(0) + "px";
  }

  function buildLegend() {
    const el = document.getElementById("hmLegend");
    if (!el) return;
    const stops = [["−۱۲٪", -12], ["−۷٪", -7], ["−۳٪", -3], ["<۰٪", -1], ["۰٪", 0], [">۰٪", 1], ["+۳٪", 3], ["+۷٪", 7], ["+۱۲٪", 12]];
    el.innerHTML = stops.map(([lbl, v]) => {
      const c = colorFor(v);
      return '<span class="hm-leg" style="background:' + c.bg + ';color:' + c.fg + '">' + lbl + "</span>";
    }).join("");
  }

  function wire(el) {
    if (_wired) return;
    _wired = true;
    buildLegend();

    // تول‌تیپِ دسته با حرکت ماوس
    el.addEventListener("mousemove", (e) => {
      const cat = e.target.closest(".hm-cat");
      if (!cat) { if (_tip) _tip.hidden = true; return; }
      const tile = e.target.closest(".hm");
      showTip(el, cat.getAttribute("data-cat"), tile ? tile.getAttribute("data-sym") : null, e);
    });
    el.addEventListener("mouseleave", () => { if (_tip) _tip.hidden = true; });

    // لمس/کلیک روی کاشی (موبایل هاور ندارد): تول‌تیپِ دسته با نام، قیمت و درصدِ
    // همان ارز هایلایت‌شده نشان داده می‌شود — برای کاشی‌های ریزِ بدون برچسب.
    el.addEventListener("click", (e) => {
      const tile = e.target.closest(".hm");
      const cat = e.target.closest(".hm-cat");
      if (!tile || !cat) { if (_tip) _tip.hidden = true; return; }
      showTip(el, cat.getAttribute("data-cat"), tile.getAttribute("data-sym"), e);
    });

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
