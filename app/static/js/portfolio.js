/* داشبورد پورتفولیو: بارگذاری خلاصه، نمودار دونات، جدول دارایی‌ها، CRUD. */
(function () {
  "use strict";
  const CS = window.CS;
  const $ = (id) => document.getElementById(id);
  const PALETTE = ["#19C3B3", "#214E8A", "#4ED9CC", "#2D63B0", "#f59e0b", "#a78bfa", "#ef6f6f", "#6F95C8", "#84cc16", "#14b8a6"];

  let editing = null;

  async function load() {
    let d;
    try { d = await CS.fetchJSON("/api/portfolio/summary"); }
    catch (e) { console.warn(e); return; }

    const t = d.totals;
    $("pfValue").textContent = CS.faBig(t.value_usd);
    $("pfValueToman").textContent = t.value_toman ? CS.faNum(Math.round(t.value_toman)) + " تومان" : "";
    const pnlEl = $("pfPnl");
    pnlEl.textContent = (t.pnl_usd >= 0 ? "+" : "−") + CS.faBig(Math.abs(t.pnl_usd)).replace("$", "$");
    pnlEl.className = "stat-card__value " + (t.pnl_usd >= 0 ? "up" : "down");
    $("pfPnlPct").textContent = CS.faPct(t.pnl_pct);
    $("pfPnlPct").className = "stat-card__sub " + (t.pnl_usd >= 0 ? "up" : "down");
    $("pfCost").textContent = CS.faBig(t.cost_usd);
    $("pfCount").textContent = CS.toFa(t.count) + " دارایی";

    renderDonut(d.holdings);
    renderTable(d.holdings);
    if (d.risk) renderRisk(d.risk);
  }

  function renderRisk(r) {
    const card = $("riskCard");
    if (!card) return;
    card.hidden = false;
    const colors = { "بالا": "var(--down)", "متوسط": "#f59e0b", "پایین": "var(--up)" };
    const col = colors[r.risk_level] || "var(--text-dim)";
    $("riskBadge").textContent = "ریسک: " + r.risk_level;
    $("riskBadge").style.color = col;
    $("riskFill").style.width = r.score + "%";
    $("riskFill").style.background = col;
    const m = r.metrics || {};
    $("riskMetrics").innerHTML = [
      m.assets !== undefined ? `<span>دارایی‌ها: <b>${CS.toFa(m.assets)}</b></span>` : "",
      m.top_pct !== undefined ? `<span>تمرکز: <b>${CS.toFa(m.top_pct)}٪ ${m.top_symbol || ""}</b></span>` : "",
      m.stable_pct !== undefined ? `<span>استیبل‌کوین: <b>${CS.toFa(m.stable_pct)}٪</b></span>` : "",
      m.change_24h !== undefined ? `<span>تغییر ۲۴ساعته: <b class="${CS.chgClass(m.change_24h)}">${CS.faPct(m.change_24h)}</b></span>` : "",
    ].join("");
    $("riskInsights").innerHTML = (r.insights || []).map((i) =>
      `<li class="ri ri--${i.type}">${i.text}</li>`).join("");
  }

  function renderDonut(holdings) {
    const el = $("donut");
    const legend = $("donutLegend");
    if (!holdings.length) {
      el.innerHTML = '<div class="donut-empty">دارایی‌ای ثبت نشده</div>';
      legend.innerHTML = "";
      return;
    }
    const R = 70, C = 2 * Math.PI * R;
    let offset = 0;
    const segs = holdings.map((h, i) => {
      const frac = (h.allocation || 0) / 100;
      const len = frac * C;
      const seg = `<circle cx="90" cy="90" r="${R}" fill="none" stroke="${PALETTE[i % PALETTE.length]}"
        stroke-width="26" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}"
        transform="rotate(-90 90 90)"><title>${h.symbol} ${CS.toFa((h.allocation||0).toFixed(1))}%</title></circle>`;
      offset += len;
      return seg;
    }).join("");
    el.innerHTML = `<svg viewBox="0 0 180 180" width="180" height="180">${segs}
      <text x="90" y="84" text-anchor="middle" class="donut-center">${CS.toFa(holdings.length)}</text>
      <text x="90" y="104" text-anchor="middle" class="donut-center-sm">دارایی</text></svg>`;
    legend.innerHTML = holdings.slice(0, 8).map((h, i) =>
      `<span class="donut-leg"><i style="background:${PALETTE[i % PALETTE.length]}"></i>${h.symbol}
       <b>${CS.toFa((h.allocation||0).toFixed(1))}٪</b></span>`).join("");
  }

  function renderTable(holdings) {
    const body = $("holdingsBody");
    if (!holdings.length) {
      body.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:24px">هنوز دارایی‌ای اضافه نکرده‌اید.</td></tr>';
      return;
    }
    body.innerHTML = holdings.map((h) => `
      <tr>
        <td><div class="td-coin">
          <img src="${h.icon}" onerror="this.style.visibility='hidden'" width="26" height="26" style="border-radius:50%">
          <div><b>${h.symbol}</b><small>${h.name || ""}</small></div>
        </div></td>
        <td>${CS.faNum(h.amount, h.amount < 1 ? 4 : 2)}</td>
        <td>${CS.faPrice(h.price)}<br><small class="${CS.chgClass(h.change_24h)}">${CS.faPct(h.change_24h)}</small></td>
        <td><b>${CS.faPrice(h.value)}</b></td>
        <td class="${h.pnl >= 0 ? 'up' : 'down'}">${(h.pnl>=0?'+':'−')}${CS.faPrice(Math.abs(h.pnl))}<br><small>${CS.faPct(h.pnl_pct)}</small></td>
        <td class="td-actions">
          <button class="iconlink" data-edit='${JSON.stringify(h).replace(/'/g, "&#39;")}' title="ویرایش">✎</button>
          <button class="iconlink" data-del="${h.id}" title="حذف">🗑</button>
        </td>
      </tr>`).join("");

    body.querySelectorAll("[data-edit]").forEach((b) =>
      b.addEventListener("click", () => openModal(JSON.parse(b.dataset.edit))));
    body.querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => del(b.dataset.del)));
  }

  // ---- مودال افزودن/ویرایش ----
  const modal = $("holdingModal");
  function openModal(h) {
    editing = h && h.id ? h.id : null;
    const f = $("holdingForm");
    f.symbol.value = h ? h.symbol : "";
    f.amount.value = h ? h.amount : "";
    f.avg_buy_price.value = h ? h.avg_buy_price : 0;
    f.note.value = h && h.note ? h.note : "";
    $("holdingTitle").textContent = editing ? "ویرایش دارایی" : "افزودن دارایی";
    $("holdingError").hidden = true;
    modal.hidden = false;
  }
  function closeModal() { modal.hidden = true; }

  if ($("addHoldingBtn")) $("addHoldingBtn").addEventListener("click", () => openModal(null));
  modal.querySelectorAll("[data-hclose]").forEach((el) => el.addEventListener("click", closeModal));

  $("holdingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const body = {
      symbol: f.symbol.value.trim().toUpperCase(),
      amount: parseFloat(f.amount.value),
      avg_buy_price: parseFloat(f.avg_buy_price.value) || 0,
      note: f.note.value || "",
    };
    const url = editing ? `/api/portfolio/holdings/${editing}` : "/api/portfolio/holdings";
    const method = editing ? "PUT" : "POST";
    try {
      const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "خطا");
      closeModal();
      load();
    } catch (err) {
      $("holdingError").textContent = err.message;
      $("holdingError").hidden = false;
    }
  });

  async function del(id) {
    if (!confirm("این دارایی حذف شود؟")) return;
    await fetch(`/api/portfolio/holdings/${id}`, { method: "DELETE" });
    load();
  }

  load();
  setInterval(load, 30 * 1000);
})();
