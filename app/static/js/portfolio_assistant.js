/* دستیار چت‌بات «کریپتو اسمارت» — اتصال به Dify + نمایش زنده‌ی سبد دارایی. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);
  const chat = $("chat"), inputArea = $("chatInput");

  const PALETTE = ["#2D63B0", "#19C3B3", "#F59E0B", "#EA3943", "#6F95C8",
                   "#4ED9CC", "#128F84", "#A6F0E8", "#214E8A", "#16C784"];

  // ───── ابزار چت ─────
  function bubble(html, who) {
    const d = document.createElement("div");
    d.className = "chat__msg chat__msg--" + who;
    d.innerHTML = '<div class="chat__bubble">' + html + "</div>";
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
  }
  const bot = (t) => bubble(t, "bot");
  const me = (t) => bubble(t, "me");

  // تبدیل markdown ساده → HTML (برای پاسخ Dify)
  function mdToHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      // جداول markdown
      .replace(/^\|(.+)\|$/gm, (line) => {
        const cols = line.slice(1, -1).split("|").map(c => c.trim());
        return "<tr>" + cols.map(c => "<td>" + c + "</td>").join("") + "</tr>";
      })
      .replace(/(<tr>.*<\/tr>\n?)+/gs, (rows) => {
        // اولین سطر = سرستون
        const lines = rows.trim().split("\n").filter(l => l.startsWith("<tr>"));
        if (lines.length < 2) return "<table>" + rows + "</table>";
        const head = lines[0].replace(/<td>/g, "<th>").replace(/<\/td>/g, "</th>");
        const body = lines.slice(2).join("\n"); // سطر ۲ (جداکننده) را حذف کن
        return '<table class="dify-table"><thead>' + head + "</thead><tbody>" + body + "</tbody></table>";
      })
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^###\s(.+)$/gm, "<h3>$1</h3>")
      .replace(/^##\s(.+)$/gm, "<h4>$1</h4>")
      .replace(/^>\s(.+)$/gm, "<blockquote>$1</blockquote>")
      .replace(/\n{2,}/g, "<br><br>")
      .replace(/\n/g, "<br>");
  }

  // ───── وضعیت مکالمه ─────
  let convId = null;
  let waiting = false;

  function setWaiting(on) {
    waiting = on;
    const send = $("chatSend");
    const inp = $("chatTextInput");
    if (send) send.disabled = on;
    if (inp) inp.disabled = on;
  }

  function showTyping() {
    const d = document.createElement("div");
    d.id = "typingBubble";
    d.className = "chat__msg chat__msg--bot";
    d.innerHTML = '<div class="chat__bubble chat__typing"><span></span><span></span><span></span></div>';
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
  }

  function hideTyping() {
    const d = $("typingBubble");
    if (d) d.remove();
  }

  // ───── ارسال پیام به Dify ─────
  async function sendMessage(text) {
    if (waiting || !text.trim()) return;
    me(text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));
    setWaiting(true);
    showTyping();
    try {
      const res = await fetch("/api/portfolio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation_id: convId || null }),
      });
      const data = await res.json();
      hideTyping();
      if (data.error) {
        bot("⚠️ " + data.error);
      } else {
        if (data.conversation_id) convId = data.conversation_id;
        bot(mdToHtml(data.answer || ""));
        if (data.assets_saved) {
          await loadPortfolio();
        }
      }
    } catch (e) {
      hideTyping();
      bot("⚠️ خطا در ارتباط با سرور: " + e.message);
    } finally {
      setWaiting(false);
    }
  }

  // ───── ورودی چت ─────
  function buildInput() {
    inputArea.innerHTML = "";
    const form = document.createElement("form");
    form.className = "chat__form";

    const inp = document.createElement("input");
    inp.id = "chatTextInput";
    inp.className = "chat__field";
    inp.placeholder = "دارایی‌هایتان را بنویسید...";
    inp.type = "text";
    inp.autocomplete = "off";
    inp.dir = "rtl";

    const btn = document.createElement("button");
    btn.id = "chatSend";
    btn.className = "btn btn--brand";
    btn.type = "submit";
    btn.textContent = "ارسال";

    form.appendChild(inp);
    form.appendChild(btn);
    inputArea.appendChild(form);
    inp.focus();

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = inp.value.trim();
      if (!v) return;
      inp.value = "";
      sendMessage(v);
    });

    // دکمهٔ پیشنهادی
    const suggestions = [
      "۵۰۰ تتر روی ۷۵ هزار تومان دارم",
      "۰.۵ اتریوم روی ۲۵۰۰ دلار دارم",
      "۱۰۰ گرم طلای ۱۸ عیار روی ۴۰ میلیون تومان",
    ];
    const sg = document.createElement("div");
    sg.className = "chat__suggestions";
    suggestions.forEach(s => {
      const b = document.createElement("button");
      b.className = "chip-btn chip-btn--sm";
      b.type = "button";
      b.textContent = s;
      b.addEventListener("click", () => { inp.value = s; inp.focus(); });
      sg.appendChild(b);
    });
    inputArea.appendChild(sg);
  }

  // ───── سبد دارایی + نمودار ─────
  function donutSegments(items) {
    const svg = $("donut");
    svg.innerHTML = "";
    const r = 46, cx = 60, cy = 60, C = 2 * Math.PI * r;
    if (!items.length) {
      svg.innerHTML = '<circle cx="60" cy="60" r="46" fill="none" stroke="var(--border-strong)" stroke-width="16"/>';
      return;
    }
    let off = 0;
    items.forEach((it, i) => {
      const seg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      seg.setAttribute("cx", cx); seg.setAttribute("cy", cy); seg.setAttribute("r", r);
      seg.setAttribute("fill", "none");
      seg.setAttribute("stroke", PALETTE[i % PALETTE.length]);
      seg.setAttribute("stroke-width", "16");
      const len = (it.weight || 0) / 100 * C;
      seg.setAttribute("stroke-dasharray", len + " " + (C - len));
      seg.setAttribute("stroke-dashoffset", -off);
      seg.setAttribute("transform", "rotate(-90 60 60)");
      svg.appendChild(seg);
      off += len;
    });
  }

  function renderLegend(items) {
    const el = $("portLegend");
    el.innerHTML = items.map((it, i) =>
      '<div class="port-legend__row"><span class="port-legend__dot" style="background:' +
      PALETTE[i % PALETTE.length] + '"></span>' +
      '<span class="port-legend__name">' + it.name + '</span>' +
      '<span class="port-legend__pct">' + CS.toFa((it.weight || 0).toFixed(1)) + '٪</span></div>'
    ).join("");
  }

  function renderList(items) {
    const el = $("portList");
    if (!items.length) { el.innerHTML = '<p class="port-empty">هنوز دارایی‌ای اضافه نشده است.</p>'; return; }
    el.innerHTML = items.map(it => {
      const pnl = (it.pnl_pct === null || it.pnl_pct === undefined) ? "" :
        '<span class="chg ' + CS.chgClass(it.pnl_pct) + '">' + CS.faPct(it.pnl_pct) + '</span>';
      const sub = it.kind === "gold" && it.purity ?
        (it.purity === "ounce" ? "انس" : "هر گرم") :
        (it.kind === "crypto" ? it.symbol : (it.kind === "toman" ? "نقد" : "USDT"));
      return '<div class="port-item" data-id="' + it.id + '">' +
        '<div class="port-item__main"><div class="port-item__name">' + it.name + ' ' + pnl + '</div>' +
        '<div class="port-item__sub">' + CS.faNum(it.amount) + ' × ' + CS.faNum(it.unit_price_toman) + ' ت</div></div>' +
        '<div class="port-item__right"><div class="port-item__val">' + CS.faNum(it.value_toman) + ' ت</div>' +
        '<div class="port-item__usd">' + CS.faPriceUsd(it.value_usd) + '</div></div>' +
        '<button class="port-item__del" title="حذف" aria-label="حذف">×</button></div>';
    }).join("");
    el.querySelectorAll(".port-item__del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.target.closest(".port-item").dataset.id;
        await fetch("/api/portfolio/assets/" + id, { method: "DELETE" });
        await loadPortfolio();
      });
    });
  }

  async function loadPortfolio() {
    try {
      const d = await CS.fetchJSON("/api/portfolio/assets");
      const items = d.items || [];
      $("totalToman").textContent = items.length ? CS.faNum(d.total_toman) + " ت" : "—";
      $("totalUsd").textContent = items.length ? CS.faPriceUsd(d.total_usd) : "";
      donutSegments(items);
      renderLegend(items);
      renderList(items);
    } catch (e) { console.warn("portfolio:", e); }
  }

  // ───── راه‌اندازی ─────
  buildInput();
  loadPortfolio();
  setInterval(loadPortfolio, 15_000);
})(window);
