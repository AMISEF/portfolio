/* مدیریت سرمایه — ردیاب سبد (خلاصه، دونات تخصیص، جدول دارایی، نمودار روند)
   + انتخابگر افزودن دارایی (همهٔ ارزهای Toobit + طلا/سکه/نقره/نفت) + دستیار چت. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  const PALETTE = ["#2D63B0", "#19C3B3", "#F59E0B", "#EA3943", "#6F95C8",
                   "#4ED9CC", "#128F84", "#A6F0E8", "#214E8A", "#16C784"];
  const GROUP_ICON = { gold: "🥇", coin: "🪙", silver: "⚪", oil: "🛢️", cash: "₮" };

  function esc(v) {
    return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function hueOf(s) { let h = 0; for (const c of (s || "?")) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }

  function assetIcon(it) {
    if (it.group === "crypto" || it.kind === "crypto") {
      const h = hueOf(it.symbol);
      return '<span class="pf2-ic" style="background:linear-gradient(135deg,hsl(' + h +
        ' 70% 52%),hsl(' + h + ' 65% 38%))">' + esc((it.symbol || "?")[0]) + "</span>";
    }
    return '<span class="pf2-ic pf2-ic--metal">' + (GROUP_ICON[it.group] || "💠") + "</span>";
  }

  // ───────────────────────── چت دستیار ─────────────────────────
  const chat = $("chat"), inputArea = $("chatInput");
  let convId = null, waiting = false;

  function bubble(html, who) {
    const d = document.createElement("div");
    d.className = "chat__msg chat__msg--" + who;
    d.innerHTML = '<div class="chat__bubble">' + html + "</div>";
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d;
  }
  const bot = (t) => bubble(t, "bot");
  function mdToHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/^\|(.+)\|$/gm, (line) => {
        const cols = line.slice(1, -1).split("|").map(c => c.trim());
        return "<tr>" + cols.map(c => "<td>" + c + "</td>").join("") + "</tr>";
      })
      .replace(/(<tr>.*<\/tr>\n?)+/gs, (rows) => {
        const lines = rows.trim().split("\n").filter(l => l.startsWith("<tr>"));
        if (lines.length < 2) return "<table>" + rows + "</table>";
        const head = lines[0].replace(/<td>/g, "<th>").replace(/<\/td>/g, "</th>");
        return '<table class="dify-table"><thead>' + head + "</thead><tbody>" + lines.slice(2).join("\n") + "</tbody></table>";
      })
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^###\s(.+)$/gm, "<h3>$1</h3>").replace(/^##\s(.+)$/gm, "<h4>$1</h4>")
      .replace(/\n{2,}/g, "<br><br>").replace(/\n/g, "<br>");
  }
  function showTyping() {
    const d = document.createElement("div"); d.id = "typingBubble";
    d.className = "chat__msg chat__msg--bot";
    d.innerHTML = '<div class="chat__bubble chat__typing"><span></span><span></span><span></span></div>';
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  }
  function hideTyping() { const d = $("typingBubble"); if (d) d.remove(); }
  function setWaiting(on) {
    waiting = on;
    if ($("chatSend")) $("chatSend").disabled = on;
    if ($("chatTextInput")) $("chatTextInput").disabled = on;
  }
  async function sendMessage(text) {
    if (waiting || !text.trim()) return;
    bubble(esc(text), "me"); setWaiting(true); showTyping();
    try {
      const res = await fetch("/api/portfolio/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation_id: convId || null }),
      });
      const data = await res.json(); hideTyping();
      if (data.error) bot("⚠️ " + data.error);
      else {
        if (data.conversation_id) convId = data.conversation_id;
        bot(mdToHtml(data.answer || ""));
        if (data.assets_saved) await loadPortfolio();
      }
    } catch (e) { hideTyping(); bot("⚠️ خطا در ارتباط با سرور: " + e.message); }
    finally { setWaiting(false); }
  }
  function buildInput() {
    inputArea.innerHTML = "";
    const form = document.createElement("form"); form.className = "chat__form";
    const inp = document.createElement("input");
    inp.id = "chatTextInput"; inp.className = "chat__field"; inp.type = "text";
    inp.placeholder = "دارایی‌هایتان را بنویسید یا سؤال بپرسید..."; inp.autocomplete = "off"; inp.dir = "rtl";
    const btn = document.createElement("button");
    btn.id = "chatSend"; btn.className = "btn btn--brand"; btn.type = "submit"; btn.textContent = "ارسال";
    form.appendChild(inp); form.appendChild(btn); inputArea.appendChild(form);
    form.addEventListener("submit", (e) => {
      e.preventDefault(); const v = inp.value.trim(); if (!v) return; inp.value = ""; sendMessage(v);
    });
  }
  let chatReady = false;
  $("aiToggle").addEventListener("click", function () {
    const card = $("aiCard");
    card.hidden = !card.hidden;
    if (!card.hidden) {
      if (!chatReady) {
        chatReady = true; buildInput();
        bot("سلام! می‌توانید دارایی‌هایتان را به زبان ساده بنویسید (مثلاً «۰.۵ بیت‌کوین روی ۶۰ هزار دلار») یا سؤال سرمایه‌گذاری بپرسید.");
      }
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // ───────────────────────── سبد: خلاصه/دونات/جدول ─────────────────────────
  let allItems = [];

  function donut(items) {
    const svg = $("donut"); svg.innerHTML = "";
    const r = 46, cx = 60, cy = 60, C = 2 * Math.PI * r;
    if (!items.length) {
      svg.innerHTML = '<circle cx="60" cy="60" r="46" fill="none" stroke="var(--border-strong)" stroke-width="15"/>';
      return;
    }
    let off = 0;
    items.forEach((it, i) => {
      const seg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      seg.setAttribute("cx", cx); seg.setAttribute("cy", cy); seg.setAttribute("r", r);
      seg.setAttribute("fill", "none"); seg.setAttribute("stroke", PALETTE[i % PALETTE.length]);
      seg.setAttribute("stroke-width", "15");
      const len = (it.weight || 0) / 100 * C;
      seg.setAttribute("stroke-dasharray", len + " " + (C - len));
      seg.setAttribute("stroke-dashoffset", -off);
      seg.setAttribute("transform", "rotate(-90 60 60)");
      seg.setAttribute("stroke-linecap", "butt");
      svg.appendChild(seg); off += len;
    });
  }
  function legend(items) {
    $("portLegend").innerHTML = items.map((it, i) =>
      '<div class="pf2-legend__row"><span class="pf2-legend__dot" style="background:' +
      PALETTE[i % PALETTE.length] + '"></span><span class="pf2-legend__name">' + esc(it.name) +
      '</span><span class="pf2-legend__pct">' + CS.toFa((it.weight || 0).toFixed(1)) + "٪</span></div>"
    ).join("");
  }

  function holdings(items) {
    const body = $("holdBody");
    const q = ($("holdSearch").value || "").trim().toLowerCase();
    const list = q ? items.filter(it => ((it.name || "") + (it.symbol || "")).toLowerCase().indexOf(q) !== -1) : items;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="8" class="pf2-empty">' +
        (items.length ? "دارایی‌ای با این فیلتر یافت نشد." : "هنوز دارایی‌ای اضافه نشده است. روی «افزودن دارایی» بزنید.") + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(it => {
      const c24 = chgCell(it.change_24h), c30 = chgCell(it.change_30d);
      const pnl = (it.pnl_pct == null) ? '<span class="pf2-dim">—</span>'
        : '<span class="chg ' + CS.chgClass(it.pnl_pct) + '">' + CS.faPct(it.pnl_pct) + "</span>";
      return '<tr data-id="' + it.id + '">' +
        '<td><div class="pf2-asset">' + assetIcon(it) +
          '<span class="pf2-asset__txt"><span class="pf2-asset__name">' + esc(it.name) +
          '</span><span class="pf2-asset__sym">' + esc(symLabel(it)) + "</span></span></div></td>" +
        '<td class="pf2-num">' + CS.faNum(it.unit_price_toman) + " ت</td>" +
        "<td>" + c24 + "</td><td>" + c30 + "</td>" +
        '<td class="pf2-num">' + CS.faNum(it.amount) + "</td>" +
        '<td class="pf2-num"><b>' + CS.faNum(it.value_toman) + " ت</b><span class=\"pf2-usd\">" + CS.faPriceUsd(it.value_usd) + "</span></td>" +
        "<td>" + pnl + "</td>" +
        '<td><button class="pf2-del" title="حذف" aria-label="حذف">×</button></td>' +
        "</tr>";
    }).join("");
    body.querySelectorAll(".pf2-del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const tr = e.target.closest("tr"); const id = tr.dataset.id;
        if (!confirm("این دارایی از سبد حذف شود؟")) return;
        await fetch("/api/portfolio/assets/" + id, { method: "DELETE" });
        await loadPortfolio();
      });
    });
  }
  function symLabel(it) {
    if (it.kind === "crypto") return it.symbol;
    if (it.kind === "gold") return it.purity === "24" ? "۲۴ عیار · هر گرم" : "۱۸ عیار · هر گرم";
    if (it.kind === "coin") return "عدد";
    if (it.kind === "silver") return "هر گرم";
    if (it.kind === "oil") return "بشکه";
    if (it.kind === "usdt") return "USDT";
    return "نقد";
  }
  function chgCell(v) {
    if (v == null) return '<span class="pf2-dim">—</span>';
    return '<span class="chg ' + CS.chgClass(v) + '">' + CS.faPct(v) + "</span>";
  }

  function summary(d) {
    const items = d.items || [];
    $("sumToman").textContent = items.length ? CS.faNum(d.total_toman) + " ت" : "—";
    $("sumUsd").textContent = items.length ? CS.faPriceUsd(d.total_usd) : "";
    $("donutTotal").textContent = items.length ? CS.faNum(d.total_toman) + " ت" : "—";
    // تغییر ۲۴ساعتهٔ وزنی کل سبد
    let wsum = 0, w = 0;
    items.forEach(it => { if (it.change_24h != null) { wsum += it.change_24h * (it.value_toman || 0); w += (it.value_toman || 0); } });
    const el = $("sumChg");
    if (w > 0) { const avg = wsum / w; el.className = "pf2-chg chg " + CS.chgClass(avg); el.textContent = CS.faPct(avg) + " (۲۴س)"; }
    else { el.textContent = ""; }
  }

  async function loadPortfolio() {
    try {
      const d = await CS.fetchJSON("/api/portfolio/assets");
      allItems = d.items || [];
      summary(d); donut(allItems); legend(allItems); holdings(allItems);
    } catch (e) { console.warn("portfolio:", e); }
  }
  $("holdSearch").addEventListener("input", () => holdings(allItems));

  // ───────────────────────── نمودار روند ارزش ─────────────────────────
  async function loadHistory(days) {
    const box = $("pfChart");
    try {
      const d = await CS.fetchJSON("/api/portfolio/history?days=" + days);
      const h = (d.history || []).map(p => ({ t: Date.parse(p.ts.replace(" ", "T") + "Z"), v: p.total_toman }))
        .filter(p => p.v > 0);
      if (h.length < 2) {
        box.innerHTML = '<div class="pf2-chart-empty">روند ارزش پس از چند بار به‌روزرسانی نمایش داده می‌شود.<br>(هر ساعت یک نقطه ثبت می‌شود)</div>';
        return;
      }
      box.innerHTML = areaChart(h);
    } catch (e) { box.innerHTML = '<div class="pf2-chart-empty">خطا در بارگذاری روند.</div>'; }
  }
  function areaChart(pts) {
    const W = 760, H = 240, padL = 8, padR = 64, padT = 14, padB = 22;
    const xs = pts.map(p => p.t), vs = pts.map(p => p.v);
    const xmin = Math.min(...xs), xmax = Math.max(...xs) || xmin + 1;
    let vmin = Math.min(...vs), vmax = Math.max(...vs); if (vmax === vmin) { vmax = vmin * 1.01 + 1; }
    const pw = W - padL - padR, ph = H - padT - padB;
    const X = t => padL + (xmax === xmin ? pw / 2 : (t - xmin) / (xmax - xmin) * pw);
    const Y = v => padT + (vmax - v) / (vmax - vmin) * ph;
    let line = "", area = "M" + X(xs[0]).toFixed(1) + "," + (padT + ph).toFixed(1);
    pts.forEach((p, i) => { const x = X(p.t).toFixed(1), y = Y(p.v).toFixed(1); line += (i ? "L" : "M") + x + "," + y; area += "L" + x + "," + y; });
    area += "L" + X(xs[xs.length - 1]).toFixed(1) + "," + (padT + ph).toFixed(1) + "Z";
    let grid = "";
    for (let g = 0; g <= 4; g++) {
      const gy = padT + ph * g / 4, gv = vmax - (vmax - vmin) * g / 4;
      grid += '<line x1="' + padL + '" y1="' + gy.toFixed(1) + '" x2="' + (padL + pw) + '" y2="' + gy.toFixed(1) +
        '" stroke="var(--border)" stroke-width="1"/>' +
        '<text x="' + (padL + pw + 6) + '" y="' + (gy + 3).toFixed(1) + '" fill="var(--text-dim)" font-size="9">' +
        CS.faNum(Math.round(gv)) + "</text>";
    }
    const last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" preserveAspectRatio="none" class="pf2-area">' +
      '<defs><linearGradient id="pfg" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="var(--brand)" stop-opacity=".35"/>' +
      '<stop offset="1" stop-color="var(--brand)" stop-opacity="0"/></linearGradient></defs>' +
      grid + '<path d="' + area + '" fill="url(#pfg)"/>' +
      '<path d="' + line + '" fill="none" stroke="var(--brand)" stroke-width="2"/>' +
      '<circle cx="' + X(last.t).toFixed(1) + '" cy="' + Y(last.v).toFixed(1) + '" r="3.5" fill="var(--brand)"/>' +
      "</svg>";
  }
  $("pfTf").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("pfTf").querySelectorAll("button").forEach(x => x.classList.remove("is-active"));
    b.classList.add("is-active"); loadHistory(b.dataset.d);
  });

  // ───────────────────────── انتخابگر افزودن دارایی ─────────────────────────
  let catalog = [], catGroup = "", picked = null;

  async function loadCatalog() {
    try {
      const d = await CS.fetchJSON("/api/portfolio/instruments");
      catalog = d.instruments || [];
    } catch (e) { catalog = []; }
  }
  function renderInst() {
    const q = ($("instSearch").value || "").trim().toLowerCase();
    let list = catalog.filter(it => !catGroup || it.group === catGroup);
    if (q) list = list.filter(it => ((it.name || "") + (it.symbol || "")).toLowerCase().indexOf(q) !== -1);
    list = list.slice(0, 120);
    const box = $("instList");
    if (!list.length) { box.innerHTML = '<p class="pf2-empty">موردی یافت نشد.</p>'; return; }
    box.innerHTML = list.map((it, i) => {
      const price = it.price_toman ? CS.faNum(it.price_toman) + " ت" : (it.price_usd ? CS.faPriceUsd(it.price_usd) : "—");
      const chg = it.change_24h == null ? "" : '<span class="chg ' + CS.chgClass(it.change_24h) + '">' + CS.faPct(it.change_24h) + "</span>";
      return '<button class="pf2-inst" data-i="' + catalog.indexOf(it) + '">' + assetIcon(it) +
        '<span class="pf2-inst__txt"><span class="pf2-inst__name">' + esc(it.name) + '</span>' +
        '<span class="pf2-inst__sym">' + esc(it.symbol) + (it.estimated ? " · تخمینی" : "") + "</span></span>" +
        '<span class="pf2-inst__price">' + price + " " + chg + "</span></button>";
    }).join("");
    box.querySelectorAll(".pf2-inst").forEach(b => b.addEventListener("click", () => pick(catalog[+b.dataset.i])));
  }
  function pick(it) {
    picked = it;
    $("addStep1").hidden = true; $("addStep2").hidden = false;
    $("addStepHint").textContent = "مقدار و (اختیاری) قیمت خرید را وارد کنید.";
    const price = it.price_toman ? CS.faNum(it.price_toman) + " ت" : CS.faPriceUsd(it.price_usd);
    $("pickedInst").innerHTML = assetIcon(it) +
      '<div><div class="pf2-picked__name">' + esc(it.name) + ' <span>' + esc(it.symbol) + "</span></div>" +
      '<div class="pf2-picked__price">قیمت فعلی: ' + price + "</div></div>";
    $("addAmount").value = ""; $("addBuy").value = ""; $("addMsg").hidden = true;
    $("addAmount").focus();
  }
  function openAdd() {
    picked = null; $("addStep1").hidden = false; $("addStep2").hidden = true;
    $("addStepHint").textContent = "یک دارایی را از فهرست انتخاب کنید (ارز دیجیتال، طلا، سکه، نقره، نفت).";
    $("instSearch").value = ""; renderInst();
    $("addAssetModal").hidden = false; $("instSearch").focus();
    if (!catalog.length) loadCatalog().then(renderInst);
  }
  function closeAdd() { $("addAssetModal").hidden = true; }

  async function saveAsset() {
    if (!picked) return;
    const amount = parseFloat($("addAmount").value);
    if (!(amount > 0)) { showAddMsg("مقدار را درست وارد کنید.", "err"); return; }
    const buy = parseFloat($("addBuy").value);
    const body = {
      kind: picked.kind, symbol: picked.symbol, name: picked.name,
      amount: amount, purity: picked.purity || null,
      buy_price: isNaN(buy) ? null : buy,
    };
    const r = await fetch("/api/portfolio/assets", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const d = await r.json().catch(() => ({}));
    if (r.ok && d.ok) { closeAdd(); await loadPortfolio(); }
    else showAddMsg(d.error || "خطا در افزودن دارایی.", "err");
  }
  function showAddMsg(t, k) { const m = $("addMsg"); m.hidden = false; m.className = "auth-msg auth-msg--" + k; m.textContent = t; }

  $("addAssetBtn").addEventListener("click", openAdd);
  $("addClose").addEventListener("click", closeAdd);
  $("addAssetModal").addEventListener("click", (e) => { if (e.target === $("addAssetModal")) closeAdd(); });
  $("instSearch").addEventListener("input", renderInst);
  $("addBack").addEventListener("click", () => { $("addStep1").hidden = false; $("addStep2").hidden = true; });
  $("addSave").addEventListener("click", saveAsset);
  $("instCats").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("instCats").querySelectorAll("button").forEach(x => x.classList.remove("is-active"));
    b.classList.add("is-active"); catGroup = b.dataset.g; renderInst();
  });

  // ───────────────────────── راه‌اندازی ─────────────────────────
  loadPortfolio();
  loadHistory(30);
  loadCatalog();
  setInterval(loadPortfolio, 20000);
})(window);
