/* مدیریت سرمایه — ردیاب سبد (خلاصه، پای‌چارت، جدول دارایی، نمودار روند)
   + انتخابگر افزودن دارایی + دستیار چت. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  const PALETTE = ["#2D63B0", "#19C3B3", "#F59E0B", "#EA3943", "#6F95C8",
                   "#4ED9CC", "#128F84", "#A6F0E8", "#214E8A", "#16C784",
                   "#e07b39", "#9b59b6", "#1abc9c", "#c0392b", "#d35400"];
  const GROUP_ICON = { gold: "🥇", coin: "🪙", silver: "⚪", oil: "🛢️", cash: "₮" };

  function esc(v) {
    return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function hueOf(s) { let h = 0; for (const c of (s || "?")) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }

  // آیکون دارایی: تصویر CDN برای کریپتو + حرف اول برای بقیه
  function assetIcon(it) {
    if (it.group === "crypto" || it.kind === "crypto") {
      const sym = (it.symbol || "").toLowerCase();
      const h = hueOf(it.symbol);
      const bg = "linear-gradient(135deg,hsl(" + h + " 70% 52%),hsl(" + h + " 65% 38%))";
      const letter = esc((it.symbol || "?")[0]);
      return '<span class="pf2-ic" style="background:' + bg + ';position:relative;overflow:hidden">' +
        '<img src="https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/32/color/' + sym + '.png" ' +
        'alt="" onerror="this.style.display=\'none\'" ' +
        'style="position:absolute;inset:0;width:100%;height:100%;border-radius:50%;object-fit:cover">' +
        '<span style="position:relative;z-index:1">' + letter + "</span>" +
        "</span>";
    }
    return '<span class="pf2-ic pf2-ic--metal">' + (GROUP_ICON[it.group] || "💠") + "</span>";
  }

  // ─────────────────────────── تبدیل ارز ───────────────────────────
  let currencyMode = "toman"; // "toman" | "usd"
  let lastUsdRate = 0;

  const curToggleBtn = $("curToggle");
  const curToggleLabel = $("curToggleLabel");

  if (curToggleBtn) {
    curToggleBtn.addEventListener("click", function () {
      currencyMode = currencyMode === "toman" ? "usd" : "toman";
      curToggleBtn.classList.toggle("is-usd", currencyMode === "usd");
      if (curToggleLabel) curToggleLabel.textContent = currencyMode === "usd" ? "USDT" : "تومان";
      renderAll();
    });
  }

  function valDisplay(toman, usd) {
    if (currencyMode === "usd") {
      return usd > 0 ? CS.faPriceUsd(usd) : (toman > 0 && lastUsdRate > 0 ? CS.faPriceUsd(toman / lastUsdRate) : "—");
    }
    return CS.faNum(toman) + " ت";
  }
  function unitDisplay(priceToman, priceUsd) {
    if (currencyMode === "usd") {
      return priceUsd > 0 ? CS.faPriceUsd(priceUsd) : (priceToman > 0 && lastUsdRate > 0 ? CS.faPriceUsd(priceToman / lastUsdRate) : "—");
    }
    return CS.faNum(priceToman) + " ت";
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
        // سلام اولیه همراه با دارایی‌های موجود
        const assetSummary = allItems.length
          ? "دارایی‌های فعلی شما: " + allItems.map(it => CS.faNum(it.amount) + " " + (it.name || it.symbol)).join("، ") + "."
          : "";
        bot("سلام! " + (assetSummary ? assetSummary + "<br><br>" : "") +
          "می‌توانید دارایی‌های جدید را به زبان ساده وارد کنید یا سؤال سرمایه‌گذاری بپرسید.");
      }
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // ───────────────────────── سبد: داده ─────────────────────────
  let allItems = [];

  function renderAll() {
    pieChart(allItems);
    legend(allItems);
    holdings(allItems);
    updateSummaryDisplay();
  }

  // ───────────────────────── پای‌چارت (توپر) ─────────────────────────
  function pieChart(items) {
    const svg = $("pieChart");
    if (!svg) return;
    svg.innerHTML = "";
    const total = $("pieTotal");
    if (total) {
      if (currencyMode === "usd") {
        const totalUsd = items.reduce((s, it) => s + (it.value_usd || 0), 0);
        total.textContent = totalUsd > 0 ? CS.faPriceUsd(totalUsd) : (lastUsdRate > 0 ? CS.faPriceUsd(items.reduce((s, it) => s + (it.value_toman || 0), 0) / lastUsdRate) : "—");
      } else {
        const totalToman = items.reduce((s, it) => s + (it.value_toman || 0), 0);
        total.textContent = totalToman > 0 ? CS.faNum(Math.round(totalToman)) + " ت" : "—";
      }
    }
    if (!items.length) {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", "100"); circle.setAttribute("cy", "100"); circle.setAttribute("r", "90");
      circle.setAttribute("fill", "var(--border)");
      svg.appendChild(circle);
      return;
    }
    const cx = 100, cy = 100, r = 90;
    let startAngle = -Math.PI / 2;
    items.forEach((it, i) => {
      const weight = it.weight || 0;
      if (weight <= 0) return;
      const angle = (weight / 100) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      const x1 = cx + r * Math.cos(startAngle), y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle),   y2 = cy + r * Math.sin(endAngle);
      const largeArc = angle > Math.PI ? 1 : 0;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d",
        "M " + cx + " " + cy +
        " L " + x1.toFixed(2) + " " + y1.toFixed(2) +
        " A " + r + " " + r + " 0 " + largeArc + " 1 " + x2.toFixed(2) + " " + y2.toFixed(2) +
        " Z"
      );
      path.setAttribute("fill", PALETTE[i % PALETTE.length]);
      path.setAttribute("stroke", "var(--surface-solid)");
      path.setAttribute("stroke-width", "1.5");
      svg.appendChild(path);
      startAngle = endAngle;
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
      const price = unitDisplay(it.unit_price_toman, it.unit_price_usd);
      const val = valDisplay(it.value_toman, it.value_usd);
      return '<tr data-id="' + it.id + '">' +
        '<td><div class="pf2-asset">' + assetIcon(it) +
          '<span class="pf2-asset__txt"><span class="pf2-asset__name">' + esc(it.name) +
          '</span><span class="pf2-asset__sym">' + esc(symLabel(it)) + "</span></span></div></td>" +
        '<td class="pf2-num">' + price + "</td>" +
        "<td>" + c24 + "</td><td>" + c30 + "</td>" +
        '<td class="pf2-num">' + CS.faNum(it.amount) + "</td>" +
        '<td class="pf2-num"><b>' + val + "</b></td>" +
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

  // ───────────────────────── خلاصه ─────────────────────────
  let lastSummaryData = null;

  function updateSummaryDisplay() {
    if (!lastSummaryData) return;
    const d = lastSummaryData;
    const items = d.items || [];
    if (currencyMode === "usd") {
      const totalUsd = d.total_usd || 0;
      $("sumToman").textContent = totalUsd > 0 ? CS.faPriceUsd(totalUsd) : "—";
      $("sumUsd").textContent = "";
    } else {
      $("sumToman").textContent = items.length ? CS.faNum(d.total_toman) + " ت" : "—";
      $("sumUsd").textContent = items.length ? CS.faPriceUsd(d.total_usd) : "";
    }
    // تغییر ۲۴ساعتهٔ وزنی
    let wsum = 0, w = 0;
    items.forEach(it => { if (it.change_24h != null) { wsum += it.change_24h * (it.value_toman || 0); w += (it.value_toman || 0); } });
    const el = $("sumChg");
    if (w > 0) { const avg = wsum / w; el.className = "pf2-chg chg " + CS.chgClass(avg); el.textContent = CS.faPct(avg) + " (۲۴س)"; }
    else { el.textContent = ""; }
  }

  function summary(d) {
    lastSummaryData = d;
    if (d.usd_toman > 0) lastUsdRate = d.usd_toman;
    updateSummaryDisplay();
  }

  async function loadPortfolio() {
    try {
      const d = await CS.fetchJSON("/api/portfolio/assets");
      allItems = d.items || [];
      summary(d); renderAll();
    } catch (e) { console.warn("portfolio:", e); }
  }
  $("holdSearch").addEventListener("input", () => holdings(allItems));

  // ───────────────────────── نمودار روند ─────────────────────────
  let chartType = "area";
  let historyPts = [];

  const pfChartTypeEl = $("pfChartType");
  if (pfChartTypeEl) {
    pfChartTypeEl.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      pfChartTypeEl.querySelectorAll("button").forEach(x => x.classList.remove("is-active"));
      b.classList.add("is-active"); chartType = b.dataset.type;
      renderChart();
    });
  }

  function renderChart() {
    const box = $("pfChart");
    if (historyPts.length < 2) {
      box.innerHTML = '<div class="pf2-chart-empty">روند ارزش پس از چند بار به‌روزرسانی نمایش داده می‌شود.<br>(هر ساعت یک نقطه ثبت می‌شود)</div>';
      return;
    }
    box.innerHTML = chartType === "bar" ? barChart(historyPts) : areaChart(historyPts);
  }

  async function loadHistory(days) {
    const box = $("pfChart");
    try {
      const d = await CS.fetchJSON("/api/portfolio/history?days=" + days);
      historyPts = (d.history || []).map(p => ({ t: Date.parse(p.ts.replace(" ", "T") + "Z"), v: p.total_toman }))
        .filter(p => p.v > 0);
      renderChart();
    } catch (e) { box.innerHTML = '<div class="pf2-chart-empty">خطا در بارگذاری روند.</div>'; }
  }

  // نمودار ناحیه‌ای (خطی)
  function areaChart(pts) {
    const W = 760, H = 240, padL = 8, padR = 72, padT = 18, padB = 32;
    const xs = pts.map(p => p.t), vs = pts.map(p => p.v);
    const xmin = Math.min(...xs), xmax = Math.max(...xs) || xmin + 1;
    let vmin = Math.min(...vs), vmax = Math.max(...vs);
    // پدینگ ۵٪ برای دید بهتر
    const vpad = Math.max((vmax - vmin) * 0.08, vmax * 0.005);
    if (vmax === vmin) { vmax = vmin * 1.02 + 1000; vmin = Math.max(0, vmin * 0.98); }
    else { vmax += vpad; vmin = Math.max(0, vmin - vpad); }
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
        '<text x="' + (padL + pw + 6) + '" y="' + (gy + 4).toFixed(1) + '" fill="var(--text-dim)" font-size="9" text-anchor="start">' +
        CS.faNum(Math.round(gv / 1e6) > 0 ? Math.round(gv / 1e6) + "M" : Math.round(gv)) + "</text>";
    }
    // برچسب تاریخ محور x
    const tickCount = Math.min(pts.length, 5);
    let xLabels = "";
    for (let k = 0; k < tickCount; k++) {
      const idx = Math.round(k * (pts.length - 1) / (tickCount - 1 || 1));
      const p = pts[idx];
      const d = new Date(p.t);
      const label = (d.getMonth() + 1) + "/" + d.getDate();
      xLabels += '<text x="' + X(p.t).toFixed(1) + '" y="' + (padT + ph + 14) + '" fill="var(--text-dim)" font-size="8.5" text-anchor="middle">' + label + "</text>";
    }
    const last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="pf2-area">' +
      '<defs><linearGradient id="pfg" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="var(--brand)" stop-opacity=".35"/>' +
      '<stop offset="1" stop-color="var(--brand)" stop-opacity="0"/></linearGradient></defs>' +
      grid + xLabels +
      '<path d="' + area + '" fill="url(#pfg)"/>' +
      '<path d="' + line + '" fill="none" stroke="var(--brand)" stroke-width="2"/>' +
      '<circle cx="' + X(last.t).toFixed(1) + '" cy="' + Y(last.v).toFixed(1) + '" r="3.5" fill="var(--brand)"/>' +
      "</svg>";
  }

  // نمودار میله‌ای
  function barChart(pts) {
    const W = 760, H = 240, padL = 8, padR = 72, padT = 18, padB = 32;
    const vs = pts.map(p => p.v);
    let vmin = Math.min(...vs), vmax = Math.max(...vs);
    const vpad = Math.max((vmax - vmin) * 0.08, vmax * 0.005);
    if (vmax === vmin) { vmax = vmin * 1.02 + 1000; vmin = Math.max(0, vmin * 0.98); }
    else { vmax += vpad; vmin = Math.max(0, vmin - vpad); }
    const pw = W - padL - padR, ph = H - padT - padB;
    const Y = v => padT + (vmax - v) / (vmax - vmin) * ph;
    const barW = Math.max(3, Math.min(28, pw / pts.length * 0.65));
    const step = pw / pts.length;
    let bars = "", grid = "", xLabels = "";
    for (let g = 0; g <= 4; g++) {
      const gy = padT + ph * g / 4, gv = vmax - (vmax - vmin) * g / 4;
      grid += '<line x1="' + padL + '" y1="' + gy.toFixed(1) + '" x2="' + (padL + pw) + '" y2="' + gy.toFixed(1) +
        '" stroke="var(--border)" stroke-width="1"/>' +
        '<text x="' + (padL + pw + 6) + '" y="' + (gy + 4).toFixed(1) + '" fill="var(--text-dim)" font-size="9" text-anchor="start">' +
        CS.faNum(Math.round(gv / 1e6) > 0 ? Math.round(gv / 1e6) + "M" : Math.round(gv)) + "</text>";
    }
    pts.forEach((p, i) => {
      const cx = padL + (i + 0.5) * step;
      const y = Y(p.v), barH = padT + ph - y;
      bars += '<rect x="' + (cx - barW / 2).toFixed(1) + '" y="' + y.toFixed(1) +
        '" width="' + barW.toFixed(1) + '" height="' + Math.max(0, barH).toFixed(1) +
        '" rx="3" fill="var(--brand)" opacity="0.85"/>';
    });
    const tickCount = Math.min(pts.length, 5);
    for (let k = 0; k < tickCount; k++) {
      const idx = Math.round(k * (pts.length - 1) / (tickCount - 1 || 1));
      const p = pts[idx];
      const d = new Date(p.t);
      const cx = padL + (idx + 0.5) * step;
      xLabels += '<text x="' + cx.toFixed(1) + '" y="' + (padT + ph + 14) + '" fill="var(--text-dim)" font-size="8.5" text-anchor="middle">' +
        (d.getMonth() + 1) + "/" + d.getDate() + "</text>";
    }
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="pf2-bar-svg">' +
      grid + bars + xLabels + "</svg>";
  }

  $("pfTf").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("pfTf").querySelectorAll("button").forEach(x => x.classList.remove("is-active"));
    b.classList.add("is-active"); loadHistory(b.dataset.d);
  });

  // ───────────────────────── انتخابگر افزودن دارایی ─────────────────────────
  let catalog = [], catGroup = "", picked = null, buyCurMode = "toman";

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
    box.innerHTML = list.map((it) => {
      const price = it.price_toman ? CS.faNum(it.price_toman) + " ت" : (it.price_usd ? CS.faPriceUsd(it.price_usd) : "—");
      const chg = it.change_24h == null ? "" : '<span class="chg ' + CS.chgClass(it.change_24h) + '">' + CS.faPct(it.change_24h) + "</span>";
      return '<button class="pf2-inst" data-i="' + catalog.indexOf(it) + '">' + assetIcon(it) +
        '<span class="pf2-inst__txt"><span class="pf2-inst__name">' + esc(it.name) + '</span>' +
        '<span class="pf2-inst__sym">' + esc(it.symbol) + (it.estimated ? " · تخمینی" : "") + "</span></span>" +
        '<span class="pf2-inst__price">' + price + " " + chg + "</span></button>";
    }).join("");
    box.querySelectorAll(".pf2-inst").forEach(b => b.addEventListener("click", () => pick(catalog[+b.dataset.i])));
  }

  // برچسب هوشمند مقدار بر اساس نوع دارایی
  function amountLabel(it) {
    if (!it) return "مقدار";
    if (it.group === "gold" || it.kind === "gold") return "چند گرم";
    if (it.group === "coin" || it.kind === "coin") return "چند عدد";
    return "چه مقدار";
  }

  function pick(it) {
    picked = it;
    $("addStep1").hidden = true; $("addStep2").hidden = false;
    $("addStepHint").textContent = "مقدار و (اختیاری) قیمت خرید را وارد کنید.";
    const price = it.price_toman ? CS.faNum(it.price_toman) + " ت" : CS.faPriceUsd(it.price_usd);
    $("pickedInst").innerHTML = assetIcon(it) +
      '<div><div class="pf2-picked__name">' + esc(it.name) + ' <span>' + esc(it.symbol) + "</span></div>" +
      '<div class="pf2-picked__price">قیمت فعلی: ' + price + "</div></div>";
    // برچسب هوشمند
    const aLbl = $("addAmountLbl");
    if (aLbl) aLbl.textContent = amountLabel(it);
    $("addAmount").value = ""; $("addBuy").value = ""; $("addMsg").hidden = true;
    // reset buy currency
    buyCurMode = "toman";
    $("buyCurToman").classList.add("is-active"); $("buyCurUsd").classList.remove("is-active");
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
    let buyRaw = parseFloat($("addBuy").value);
    let buyToman = isNaN(buyRaw) ? null : buyRaw;
    // تبدیل دلار به تومان با نرخ کنونی
    if (buyToman !== null && buyCurMode === "usd" && lastUsdRate > 0) {
      buyToman = buyToman * lastUsdRate;
    } else if (buyToman !== null && buyCurMode === "usd" && lastUsdRate <= 0) {
      showAddMsg("نرخ دلار در دسترس نیست. لطفاً قیمت را به تومان وارد کنید.", "err"); return;
    }
    const body = {
      kind: picked.kind, symbol: picked.symbol, name: picked.name,
      amount: amount, purity: picked.purity || null,
      buy_price: buyToman,
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

  // تاگل ارز قیمت خرید
  const buyCurTomanBtn = $("buyCurToman"), buyCurUsdBtn = $("buyCurUsd");
  if (buyCurTomanBtn) buyCurTomanBtn.addEventListener("click", () => {
    buyCurMode = "toman"; buyCurTomanBtn.classList.add("is-active"); buyCurUsdBtn.classList.remove("is-active");
  });
  if (buyCurUsdBtn) buyCurUsdBtn.addEventListener("click", () => {
    buyCurMode = "usd"; buyCurUsdBtn.classList.add("is-active"); buyCurTomanBtn.classList.remove("is-active");
  });

  // ───────────────────────── راه‌اندازی ─────────────────────────
  loadPortfolio();
  loadHistory(30);
  loadCatalog();
  setInterval(loadPortfolio, 20000);
})(window);
