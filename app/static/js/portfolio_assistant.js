/* مدیریت سرمایه — ردیاب سبد (خلاصه، نمودار دارایی، جدول دارایی، نمودار روند)
   + انتخابگر افزودن دارایی + دستیار چت. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  // در حالت ادمین، pfRoot یک data-admin-uid دارد؛ در غیر این صورت رشتهٔ خالی است.
  const ADMIN_UID = (function () {
    const el = document.getElementById("pfRoot");
    return el ? (el.dataset.adminUid || "") : "";
  })();

  const PALETTE = ["#2D63B0", "#19C3B3", "#F59E0B", "#EA3943", "#6F95C8",
                   "#4ED9CC", "#128F84", "#A6F0E8", "#214E8A", "#16C784",
                   "#e07b39", "#9b59b6", "#1abc9c", "#c0392b", "#d35400"];

  // آیکون‌های محلی (شمش/فلز/نقد) — همان فایل‌هایی که در ریپو هستند
  const IMG_ICON = {
    gold: "/static/img/gold18.png",
    silver: "/static/img/xag.png",
    oil: "/static/img/oil.png",
    usdt: "/static/img/usdt.png",
  };
  const EMOJI_ICON = { coin: "🪙", toman: "﷼", usd_cash: "💵", cash: "₮" };

  function esc(v) {
    return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function hueOf(s) { let h = 0; for (const c of (s || "?")) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }

  // قالب‌بندی مقدار با حفظ اعشار (برخلاف faNum که رند می‌کند و 0.1 را «۰» نشان می‌داد)
  function amtFmt(n) {
    if (n == null || isNaN(n)) return "—";
    const num = Number(n), abs = Math.abs(num);
    let str;
    if (abs >= 1000 || Number.isInteger(num)) str = Math.round(num).toString();
    else if (abs >= 1) str = String(Math.round(num * 10000) / 10000);
    else str = String(parseFloat(num.toPrecision(6)));   // کسرهای کوچک: تا ۶ رقم بامعنا
    const parts = str.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
    return CS.toFa(parts.length > 1 ? parts[0] + "٫" + parts[1] : parts[0]);
  }

  // آیکون دارایی: فقط تصویر ارز (با fallback حرف اول فقط هنگام خطای بارگذاری)
  function assetIcon(it) {
    const kind = it.kind || it.group;
    if (kind === "crypto") {
      const sym = (it.symbol || "").toLowerCase();
      const h = hueOf(it.symbol);
      const bg = "linear-gradient(135deg,hsl(" + h + " 70% 52%),hsl(" + h + " 65% 38%))";
      const letter = esc((it.symbol || "?")[0]);
      // حرف اول زیر تصویر است؛ با بارگذاری موفقِ تصویر پنهان می‌شود (بدون روی‌هم‌افتادگی).
      return '<span class="pf2-ic" style="background:' + bg + ';position:relative;overflow:hidden">' +
        '<span class="pf2-ic__letter">' + letter + "</span>" +
        '<img src="https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/32/color/' + sym + '.png" ' +
        'alt="" loading="lazy" ' +
        'onload="var p=this.previousElementSibling; if(p) p.style.display=\'none\'" ' +
        'onerror="this.remove()" ' +
        'style="position:absolute;inset:0;width:100%;height:100%;border-radius:50%;object-fit:cover">' +
        "</span>";
    }
    const img = IMG_ICON[kind];
    if (img) {
      return '<span class="pf2-ic pf2-ic--img"><img src="' + img + '" alt="" loading="lazy"></span>';
    }
    return '<span class="pf2-ic pf2-ic--metal">' + (EMOJI_ICON[kind] || EMOJI_ICON[it.group] || "💠") + "</span>";
  }

  // ─────────────────────────── تبدیل ارز ───────────────────────────
  let currencyMode = "toman"; // "toman" | "usd"
  let lastUsdRate = 0;
  let usdChange24 = 0;        // تغییر ۲۴ساعتهٔ دلار/تتر

  const curToggleBtn = $("curToggle");
  const curToggleLabel = $("curToggleLabel");

  if (curToggleBtn) {
    curToggleBtn.addEventListener("click", function () {
      currencyMode = currencyMode === "toman" ? "usd" : "toman";
      curToggleBtn.classList.toggle("is-usd", currencyMode === "usd");
      if (curToggleLabel) curToggleLabel.textContent = currencyMode === "usd" ? "دلار" : "تومان";
      renderAll();
    });
  }

  // ارزشِ نمایشی هر دارایی (تومان یا دلار)
  function valDisplay(it) {
    const toman = it.value_toman || 0, usd = it.value_usd || 0;
    if (currencyMode === "usd") {
      return usd > 0 ? CS.faPriceUsd(usd) : (toman > 0 && lastUsdRate > 0 ? CS.faPriceUsd(toman / lastUsdRate) : "—");
    }
    return CS.faNum(toman) + " تومان";
  }

  // قیمت واحد — برای تتر/تومان/دلار نقدی هرگز نماد $ نمایش داده نمی‌شود
  function unitDisplay(it) {
    const pt = it.unit_price_toman || 0, pu = it.unit_price_usd || 0;
    if (it.kind === "toman") return currencyMode === "usd" ? "—" : "۱ تومان";
    if (it.kind === "usdt") return currencyMode === "usd" ? "۱ تتر" : CS.faNum(pt) + " تومان";
    if (it.kind === "usd_cash") return currencyMode === "usd" ? "۱ دلار" : CS.faNum(pt) + " تومان";
    if (currencyMode === "usd") {
      return pu > 0 ? CS.faPriceUsd(pu) : (pt > 0 && lastUsdRate > 0 ? CS.faPriceUsd(pt / lastUsdRate) : "—");
    }
    return CS.faNum(pt) + " تومان";
  }

  // میانگین قیمت خرید (هماهنگ با حالت ارز)
  function buyDisplay(it) {
    const b = it.buy_price;
    if (b == null || !(b > 0)) return '<span class="pf2-dim">—</span>';
    if (currencyMode === "usd") return lastUsdRate > 0 ? CS.faPriceUsd(b / lastUsdRate) : "—";
    return CS.faNum(b) + " تومان";
  }

  // تغییر ۲۴ساعته با درنظرگرفتن حالت ارز:
  //  • تومان نقد: در حالت تومان ثابت (۰)؛ در حالت تتر، معکوسِ تغییر تتر (تتر بالا ⇒ قرمز)
  //  • تتر: در حالت تومان با نرخ دلار حرکت می‌کند؛ در حالت تتر ثابت (۰)
  function change24(it) {
    if (it.kind === "toman") return currencyMode === "usd" ? -(usdChange24 || 0) : 0;
    if (it.kind === "usd_cash") return currencyMode === "usd" ? 0 : (usdChange24 || it.change_24h || 0);
    if (it.kind === "usdt") return currencyMode === "usd" ? 0 : (usdChange24 != null ? usdChange24 : (it.change_24h || 0));
    return it.change_24h;
  }
  function change30(it) {
    if (it.kind === "toman" || it.kind === "usdt" || it.kind === "usd_cash") return null;
    return it.change_30d;
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
        const assetSummary = allItems.length
          ? "دارایی‌های فعلی شما: " + allItems.map(it => amtFmt(it.amount) + " " + (it.name || it.symbol)).join("، ") + "."
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
    renderAlloc(allItems);
    legend(allItems);
    holdings(allItems);
    updateSummaryDisplay();
  }

  // ───────────────────────── نمودار دارایی (دایره‌ای/میله‌ای) ─────────────────────────
  let allocType = "pie"; // "pie" | "bar"
  const allocToggle = $("allocChartType");
  if (allocToggle) {
    allocToggle.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      allocToggle.querySelectorAll("button").forEach(x => x.classList.remove("is-active"));
      b.classList.add("is-active"); allocType = b.dataset.type;
      renderAlloc(allItems);
    });
  }

  function renderAlloc(items) {
    const box = $("allocChart");
    if (!box) return;
    const list = (items || []).filter(it => (it.weight || 0) > 0);
    if (!list.length) {
      box.innerHTML = '<div class="pf2-chart-empty">هنوز دارایی‌ای ثبت نشده است.</div>';
      box.onmousemove = null;
      return;
    }
    if (allocType === "bar") {
      box.innerHTML = allocBar(list);
      box.onmousemove = null;
      return;
    }
    box.innerHTML = allocPie(list) + '<div class="pf2-alloc-tip" id="allocTip" hidden></div>';
    wireAllocPie(box, list);
  }

  function allocPie(items) {
    const cx = 100, cy = 100, r = 86;   // کمی کوچک‌تر تا فضای «بیرون‌زدن» قطعه بماند
    let startAngle = -Math.PI / 2, paths = "";
    items.forEach((it, i) => {
      const weight = it.weight || 0;
      if (weight <= 0) return;
      const angle = (weight / 100) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      const mid = (startAngle + endAngle) / 2;
      const dx = (Math.cos(mid) * 10).toFixed(2), dy = (Math.sin(mid) * 10).toFixed(2);
      const x1 = cx + r * Math.cos(startAngle), y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle), y2 = cy + r * Math.sin(endAngle);
      const largeArc = angle > Math.PI ? 1 : 0;
      // قطعهٔ کامل (دایره) با یک نماد، تا حلقه‌ساز نباشد
      const d = (weight >= 99.999)
        ? ("M " + cx + " " + (cy - r) + " A " + r + " " + r + " 0 1 1 " + cx + " " + (cy + r) +
           " A " + r + " " + r + " 0 1 1 " + cx + " " + (cy - r) + " Z")
        : ("M " + cx + " " + cy + " L " + x1.toFixed(2) + " " + y1.toFixed(2) +
           " A " + r + " " + r + " 0 " + largeArc + " 1 " + x2.toFixed(2) + " " + y2.toFixed(2) + " Z");
      paths += '<path class="pf2-slice" data-i="' + i + '" data-dx="' + dx + '" data-dy="' + dy + '" ' +
        'd="' + d + '" fill="' + PALETTE[i % PALETTE.length] + '" stroke="var(--surface-solid)" stroke-width="1.5"/>';
      startAngle = endAngle;
    });
    return '<svg viewBox="0 0 200 200" class="pf2-pie" id="allocPieSvg" width="180" height="180" ' +
      'style="margin:0 auto;display:block;overflow:visible">' + paths + "</svg>";
  }

  // تعامل هاوِر: تنها قطعهٔ زیر نشانگر بیرون می‌زند، بقیه برمی‌گردند، و خروج موس همه‌چیز را می‌بندد.
  // با تفویض رویداد روی SVG و یک «اندیس فعال» مدیریت می‌شود (بدون جابه‌جایی DOM که رویدادها را می‌شکست).
  function wireAllocPie(box, list) {
    const svg = box.querySelector("#allocPieSvg");
    const tip = box.querySelector("#allocTip");
    if (!svg || !tip) return;
    const slices = Array.prototype.slice.call(svg.querySelectorAll(".pf2-slice"));
    let active = -1;

    function setActive(idx) {
      if (idx === active) return;
      active = idx;
      slices.forEach((p, j) => {
        p.classList.toggle("is-on", j === idx);
        p.style.transform = (j === idx) ? ("translate(" + p.dataset.dx + "px," + p.dataset.dy + "px)") : "";
      });
      const it = idx >= 0 ? list[idx] : null;
      if (it) {
        tip.innerHTML =
          '<div class="pf2-alloc-tip__name"><span class="pf2-alloc-tip__dot" style="background:' +
          PALETTE[idx % PALETTE.length] + '"></span>' + esc(it.name) + "</div>" +
          '<div class="pf2-alloc-tip__row"><span>مقدار</span><b>' + amtFmt(it.amount) + " " + esc(unitWord(it)) + "</b></div>" +
          '<div class="pf2-alloc-tip__row"><span>ارزش</span><b>' + valDisplay(it) + "</b></div>" +
          '<div class="pf2-alloc-tip__row"><span>سهم</span><b>' + CS.toFa((it.weight || 0).toFixed(1)) + "٪</b></div>";
        tip.hidden = false;
      } else {
        tip.hidden = true;
      }
    }

    svg.addEventListener("mousemove", (e) => {
      const slice = (e.target && e.target.closest) ? e.target.closest(".pf2-slice") : null;
      setActive(slice ? (+slice.dataset.i) : -1);
    });
    svg.addEventListener("mouseleave", () => setActive(-1));

    // جای‌گذاری تول‌تیپ نزدیک نشانگر
    box.onmousemove = (e) => {
      if (tip.hidden) return;
      const rect = box.getBoundingClientRect();
      let x = e.clientX - rect.left + 14, y = e.clientY - rect.top + 14;
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      if (x + tw > rect.width) x = rect.width - tw - 4;
      if (y + th > rect.height) y = Math.max(4, e.clientY - rect.top - th - 10);
      if (x < 0) x = 4;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    };
  }

  // واحد کوتاهِ هر دارایی برای نمایش در تول‌تیپ
  function unitWord(it) {
    if (it.kind === "gold") return "گرم";
    if (it.kind === "coin") return "عدد";
    if (it.kind === "silver") return "گرم";
    if (it.kind === "oil") return "بشکه";
    if (it.kind === "usdt") return "تتر";
    if (it.kind === "toman") return "تومان";
    if (it.kind === "usd_cash") return "دلار";
    return it.symbol || "";
  }

  function allocBar(items) {
    const W = 320, H = 200, padL = 8, padR = 8, padT = 14, padB = 30;
    const max = Math.max.apply(null, items.map(it => it.weight || 0).concat([1]));
    const n = items.length;
    const pw = W - padL - padR, ph = H - padT - padB;
    const step = pw / n;
    const bw = Math.min(42, step * 0.62);
    let bars = "";
    items.forEach((it, i) => {
      const weight = it.weight || 0;
      const h = ph * (weight / max);
      const x = padL + (i + 0.5) * step;
      const y = padT + ph - h;
      bars += '<rect x="' + (x - bw / 2).toFixed(1) + '" y="' + y.toFixed(1) +
        '" width="' + bw.toFixed(1) + '" height="' + Math.max(0, h).toFixed(1) +
        '" rx="4" fill="' + PALETTE[i % PALETTE.length] + '"/>' +
        '<text x="' + x.toFixed(1) + '" y="' + (y - 4).toFixed(1) + '" fill="var(--text-soft)" font-size="9" text-anchor="middle">' +
        CS.toFa(weight.toFixed(weight < 10 ? 1 : 0)) + "٪</text>" +
        '<text x="' + x.toFixed(1) + '" y="' + (padT + ph + 13).toFixed(1) + '" fill="var(--text-dim)" font-size="9" text-anchor="middle">' +
        esc((it.symbol || it.name || "").toString().slice(0, 5)) + "</text>";
    });
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="pf2-bar-svg" style="height:200px">' + bars + "</svg>";
  }

  function legend(items) {
    $("portLegend").innerHTML = items.map((it, i) =>
      '<div class="pf2-legend__row"><span class="pf2-legend__dot" style="background:' +
      PALETTE[i % PALETTE.length] + '"></span><span class="pf2-legend__name">' + esc(it.name) +
      '</span><span class="pf2-legend__pct">' + CS.toFa((it.weight || 0).toFixed(1)) + "٪</span></div>"
    ).join("");
  }

  // ───────────────────────── جدول دارایی‌ها ─────────────────────────
  function holdings(items) {
    const body = $("holdBody");
    const q = ($("holdSearch").value || "").trim().toLowerCase();
    const list = q ? items.filter(it => ((it.name || "") + (it.symbol || "")).toLowerCase().indexOf(q) !== -1) : items;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="9" class="pf2-empty">' +
        (items.length ? "دارایی‌ای با این فیلتر یافت نشد." : "هنوز دارایی‌ای اضافه نشده است. روی «افزودن دارایی» بزنید.") + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(it => {
      const c24 = chgCell(change24(it)), c30 = chgCell(change30(it));
      const pnl = (it.pnl_pct == null) ? '<span class="pf2-dim">—</span>'
        : '<span class="chg ' + CS.chgClass(it.pnl_pct) + '">' + CS.faPct(it.pnl_pct) + "</span>";
      const price = unitDisplay(it);
      const val = valDisplay(it);
      return '<tr data-id="' + it.id + '">' +
        '<td><div class="pf2-asset">' + assetIcon(it) +
          '<span class="pf2-asset__txt"><span class="pf2-asset__name">' + esc(it.name) +
          '</span><span class="pf2-asset__sym">' + esc(symLabel(it)) + "</span></span></div></td>" +
        '<td class="pf2-num">' + price + "</td>" +
        '<td class="pf2-num"><b>' + val + "</b></td>" +
        '<td class="pf2-num">' + amtFmt(it.amount) + "</td>" +
        "<td>" + c24 + "</td><td>" + c30 + "</td>" +
        '<td class="pf2-num">' + buyDisplay(it) + "</td>" +
        "<td>" + pnl + "</td>" +
        (ADMIN_UID ? '<td></td>' : '<td class="pf2-actions-cell"><button class="pf2-menu__btn" data-id="' + it.id + '" title="عملیات" aria-label="عملیات">⋯</button></td>') +
        "</tr>";
    }).join("");
  }
  function symLabel(it) {
    if (it.kind === "crypto") return it.symbol;
    if (it.kind === "gold") return it.purity === "24" ? "۲۴ عیار · هر گرم" : "۱۸ عیار · هر گرم";
    if (it.kind === "coin") return "عدد";
    if (it.kind === "silver") return "هر گرم";
    if (it.kind === "oil") return "بشکه";
    if (it.kind === "usdt") return "تتر";
    if (it.kind === "usd_cash") return "دلار نقدی";
    return "تومان";
  }
  function chgCell(v) {
    if (v == null) return '<span class="pf2-dim">—</span>';
    return '<span class="chg ' + CS.chgClass(v) + '">' + CS.faPct(v) + "</span>";
  }

  // ───────────────────────── مودال عملیات (ویرایش/افزودن/حذف) ─────────────────────────
  let actState = null;
  const actModal = $("assetActionModal");

  function openAssetAction(it) {
    actState = { id: it.id, amount: it.amount, buy_price: it.buy_price, name: it.name, mode: null };
    $("actTitle").textContent = "عملیات — " + (it.name || "");
    $("actSub").textContent = "مقدار فعلی: " + amtFmt(it.amount);
    $("actStepChoose").hidden = false;
    $("actStepInput").hidden = true;
    $("actMsg").hidden = true;
    actModal.hidden = false;
  }
  function setActMode(mode) {
    if (!actState) return;
    actState.mode = mode;
    const inp = $("actInput");
    $("actDeleteAll").hidden = (mode !== "remove");
    $("actMsg").hidden = true;
    if (mode === "buyprice") {
      const cur = actState.buy_price, inUsd = currencyMode === "usd";
      $("actLabel").textContent = inUsd ? "میانگین قیمت خرید (دلار)" : "میانگین قیمت خرید (تومان)";
      inp.value = (cur != null && cur > 0)
        ? (inUsd && lastUsdRate > 0 ? +(cur / lastUsdRate).toFixed(6) : cur) : "";
      $("actSub").textContent = "برای پاک‌کردن، خالی بگذارید و «تأیید» را بزنید.";
    } else {
      const titles = { edit: "مقدار جدید را وارد کنید", add: "چه مقدار اضافه شود؟", remove: "چه مقدار حذف شود؟" };
      const labels = { edit: "مقدار جدید", add: "مقدار افزوده", remove: "مقدار حذف" };
      $("actLabel").textContent = labels[mode];
      $("actSub").textContent = titles[mode] + " — مقدار فعلی: " + amtFmt(actState.amount);
      inp.value = mode === "edit" ? actState.amount : "";
    }
    $("actStepChoose").hidden = true;
    $("actStepInput").hidden = false;
    inp.focus();
  }
  function showActMsg(t) { const m = $("actMsg"); m.hidden = false; m.className = "auth-msg auth-msg--err"; m.textContent = t; }
  async function patchAsset(id, body) {
    if (ADMIN_UID) return;
    try {
      const r = await fetch("/api/portfolio/assets/" + id, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok && d.ok !== false) { actModal.hidden = true; await loadPortfolio(); }
      else showActMsg(d.error || "خطا در ثبت تغییر.");
    } catch (e) { showActMsg("خطا در ارتباط با سرور."); }
  }
  function confirmAction() {
    if (!actState || !actState.mode) return;
    if (actState.mode === "buyprice") {
      const raw = $("actInput").value.trim();
      let bp = raw === "" ? null : parseFloat(raw);
      if (raw !== "" && !(bp >= 0)) return showActMsg("قیمت را درست وارد کنید.");
      if (bp && currencyMode === "usd") {
        if (lastUsdRate <= 0) return showActMsg("نرخ دلار در دسترس نیست؛ قیمت را به تومان وارد کنید.");
        bp = bp * lastUsdRate;   // ذخیره همیشه به تومان
      }
      patchAsset(actState.id, { buy_price: bp });
      return;
    }
    const x = parseFloat($("actInput").value);
    let newAmount;
    if (actState.mode === "edit") {
      if (!(x > 0)) return showActMsg("مقدار را درست وارد کنید.");
      newAmount = x;
    } else if (actState.mode === "add") {
      if (!(x > 0)) return showActMsg("مقدار افزوده را وارد کنید.");
      newAmount = actState.amount + x;
    } else { // remove
      if (!(x > 0)) return showActMsg("مقدار حذف را وارد کنید.");
      newAmount = actState.amount - x;   // ≤ ۰ ⇒ بک‌اند کل دارایی را حذف می‌کند
    }
    patchAsset(actState.id, { amount: newAmount });
  }

  if (actModal) {
    $("actClose").addEventListener("click", () => { actModal.hidden = true; });
    actModal.addEventListener("click", (e) => { if (e.target === actModal) actModal.hidden = true; });
    $("actStepChoose").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-mode]"); if (b) setActMode(b.dataset.mode);
    });
    $("actBack").addEventListener("click", () => {
      $("actStepInput").hidden = true; $("actStepChoose").hidden = false;
      $("actSub").textContent = "مقدار فعلی: " + CS.faNum(actState ? actState.amount : 0);
    });
    $("actConfirm").addEventListener("click", confirmAction);
    $("actDeleteAll").addEventListener("click", () => { if (actState) patchAsset(actState.id, { amount: 0 }); });
    $("actInput").addEventListener("keydown", (e) => { if (e.key === "Enter") confirmAction(); });
  }

  // باز کردن منوی عملیات (تفویض رویداد روی بدنهٔ جدول)
  $("holdBody").addEventListener("click", (e) => {
    const btn = e.target.closest(".pf2-menu__btn");
    if (!btn) return;
    const id = btn.dataset.id;
    const it = allItems.find(x => String(x.id) === String(id));
    if (it) openAssetAction(it);
  });
  $("holdSearch").addEventListener("input", () => holdings(allItems));

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
      $("sumToman").textContent = items.length ? CS.faNum(d.total_toman) + " تومان" : "—";
      $("sumUsd").textContent = items.length ? CS.faPriceUsd(d.total_usd) : "";
    }
    // تغییر ۲۴ساعتهٔ وزنی (با درنظرگرفتن حالت ارز)
    let wsum = 0, w = 0;
    items.forEach(it => {
      const c = change24(it);
      if (c != null) { wsum += c * (it.value_toman || 0); w += (it.value_toman || 0); }
    });
    const el = $("sumChg");
    if (w > 0) { const avg = wsum / w; el.className = "pf2-chg chg " + CS.chgClass(avg); el.textContent = CS.faPct(avg) + " (۲۴ ساعته)"; }
    else { el.textContent = ""; }
  }

  function summary(d) {
    lastSummaryData = d;
    if (d.usd_toman > 0) lastUsdRate = d.usd_toman;
    if (d.usd_change_24h != null) usdChange24 = d.usd_change_24h;
    updateSummaryDisplay();
  }

  async function loadPortfolio() {
    try {
      const url = ADMIN_UID
        ? "/api/admin/users/" + ADMIN_UID + "/portfolio/value"
        : "/api/portfolio/assets";
      const d = await CS.fetchJSON(url);
      allItems = d.items || [];
      summary(d); renderAll();
    } catch (e) { console.warn("portfolio:", e); }
  }

  // ───────────────────────── نمودار روند (فقط ناحیه‌ای) ─────────────────────────
  let historyPts = [];

  // قالب تاریخِ شمسی برای برچسب محور افقی
  function jalaliLabel(ts) {
    try {
      return new Date(ts).toLocaleDateString("fa-IR", { month: "numeric", day: "numeric" });
    } catch (e) {
      const d = new Date(ts);
      return CS.toFa((d.getMonth() + 1) + "/" + d.getDate());
    }
  }

  function renderChart() {
    const box = $("pfChart");
    if (historyPts.length < 2) {
      box.innerHTML = '<div class="pf2-chart-empty">روند ارزش پس از چند بار به‌روزرسانی نمایش داده می‌شود.<br>(هر ساعت یک نقطه ثبت می‌شود)</div>';
      return;
    }
    box.innerHTML = areaChart(historyPts);
  }

  async function loadHistory(days) {
    const box = $("pfChart");
    try {
      const url = ADMIN_UID
        ? "/api/admin/users/" + ADMIN_UID + "/portfolio/history?days=" + days
        : "/api/portfolio/history?days=" + days;
      const d = await CS.fetchJSON(url);
      historyPts = (d.history || []).map(p => ({ t: Date.parse(p.ts.replace(" ", "T") + "Z"), v: p.total_toman }))
        .filter(p => p.v > 0);
      renderChart();
    } catch (e) { box.innerHTML = '<div class="pf2-chart-empty">خطا در بارگذاری روند.</div>'; }
  }

  function areaChart(pts) {
    const W = 760, H = 240, padL = 8, padR = 72, padT = 18, padB = 32;
    const xs = pts.map(p => p.t), vs = pts.map(p => p.v);
    const xmin = Math.min(...xs), xmax = Math.max(...xs) || xmin + 1;
    let vmin = Math.min(...vs), vmax = Math.max(...vs);
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
    // برچسب تاریخ شمسی محور افقی
    const tickCount = Math.min(pts.length, 5);
    let xLabels = "";
    for (let k = 0; k < tickCount; k++) {
      const idx = Math.round(k * (pts.length - 1) / (tickCount - 1 || 1));
      const p = pts[idx];
      xLabels += '<text x="' + X(p.t).toFixed(1) + '" y="' + (padT + ph + 14) + '" fill="var(--text-dim)" font-size="8.5" text-anchor="middle">' + jalaliLabel(p.t) + "</text>";
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
      const price = it.price_toman ? CS.faNum(it.price_toman) + " تومان" : (it.price_usd ? CS.faPriceUsd(it.price_usd) : "—");
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
    const price = it.price_toman ? CS.faNum(it.price_toman) + " تومان" : CS.faPriceUsd(it.price_usd);
    $("pickedInst").innerHTML = assetIcon(it) +
      '<div><div class="pf2-picked__name">' + esc(it.name) + ' <span>' + esc(it.symbol) + "</span></div>" +
      '<div class="pf2-picked__price">قیمت فعلی: ' + price + "</div></div>";
    const aLbl = $("addAmountLbl");
    if (aLbl) aLbl.textContent = amountLabel(it);
    $("addAmount").value = ""; $("addBuy").value = ""; $("addMsg").hidden = true;
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
  if (ADMIN_UID) {
    if ($("addAssetBtn")) $("addAssetBtn").hidden = true;
    if ($("aiToggle")) $("aiToggle").hidden = true;
  }
  if (!window.IS_AUTHED && !ADMIN_UID) {
    // گیت احراز هویت نمایش داده شده — نیازی به فراخوانی API نیست
  } else {
    // نمایش بنر محرمانگی در اولین بازدید (کاربر واقعی، نه ادمین)
    if (!ADMIN_UID && !sessionStorage.getItem("pf_pb")) {
      const b = $("pfPrivBanner");
      if (b) b.hidden = false;
    }
    loadPortfolio();
    loadHistory(30);
    if (!ADMIN_UID) loadCatalog();
    setInterval(loadPortfolio, 20000);
  }
})(window);
