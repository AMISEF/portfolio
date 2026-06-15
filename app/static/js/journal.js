/* ژورنال معاملاتی: آمار، منحنی سرمایه (SVG)، جدول معاملات، ثبت/حذف. */
(function () {
  "use strict";
  const CS = window.CS;
  const $ = (id) => document.getElementById(id);

  async function load() {
    let d;
    try { d = await CS.fetchJSON("/api/journal/summary"); }
    catch (e) { console.warn(e); return; }
    renderStats(d.stats);
    renderEquity(d.stats.equity_curve);
    renderTrades(d.entries);
  }

  function statCard(label, value, cls) {
    return `<div class="card stat-card rise"><div class="stat-card__label">${label}</div>
      <div class="stat-card__value ${cls || ''}">${value}</div></div>`;
  }

  function renderStats(s) {
    $("jrStats").innerHTML = [
      statCard("نرخ برد", CS.toFa(s.win_rate.toFixed(1)) + "٪", s.win_rate >= 50 ? "up" : "down"),
      statCard("سود/زیان کل", (s.total_pnl >= 0 ? "+" : "−") + CS.faPrice(Math.abs(s.total_pnl)), s.total_pnl >= 0 ? "up" : "down"),
      statCard("فاکتور سود", CS.toFa(s.profit_factor.toFixed(2)), s.profit_factor >= 1 ? "up" : "down"),
      statCard("تعداد معاملات", CS.toFa(s.total_trades) + (s.open_trades ? ` (${CS.toFa(s.open_trades)} باز)` : ""), ""),
      statCard("میانگین R:R", CS.toFa(s.avg_rr.toFixed(2)), s.avg_rr >= 1 ? "up" : "down"),
      statCard("بیشترین افت", CS.faPrice(s.max_drawdown), "down"),
      statCard("بهترین معامله", CS.faPrice(s.best), "up"),
      statCard("بدترین معامله", CS.faPrice(s.worst), "down"),
    ].join("");
  }

  function renderEquity(curve) {
    const el = $("equityChart");
    if (!curve || curve.length < 2) { el.innerHTML = '<div class="donut-empty">برای منحنی سرمایه حداقل ۲ معاملهٔ بسته‌شده لازم است.</div>'; return; }
    const W = 520, H = 180, pad = 8;
    const min = Math.min(0, ...curve), max = Math.max(0, ...curve);
    const range = (max - min) || 1;
    const x = (i) => pad + (i / (curve.length - 1)) * (W - 2 * pad);
    const y = (v) => H - pad - ((v - min) / range) * (H - 2 * pad);
    const pts = curve.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    const last = curve[curve.length - 1];
    const color = last >= 0 ? "#16c784" : "#ea3943";
    const zeroY = y(0);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none" style="max-height:200px">
      <line x1="${pad}" y1="${zeroY}" x2="${W - pad}" y2="${zeroY}" stroke="var(--border-strong)" stroke-dasharray="4 4"/>
      <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round"/>
      <polyline points="${x(0)},${zeroY} ${pts} ${x(curve.length-1)},${zeroY}" fill="${color}" opacity=".1"/>
    </svg>`;
  }

  function renderTrades(entries) {
    const body = $("tradesBody");
    if (!entries.length) { body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-dim);padding:24px">هنوز معامله‌ای ثبت نشده.</td></tr>'; return; }
    body.innerHTML = entries.map((e) => {
      const pnl = e.pnl;
      const pnlHtml = e.is_open ? '<span class="src-tag">باز</span>'
        : `<span class="${pnl >= 0 ? 'up' : 'down'}">${(pnl>=0?'+':'−')}${CS.faPrice(Math.abs(pnl))}</span>`;
      return `<tr>
        <td><b>${e.pair}</b>${e.strategy ? `<br><small>${e.strategy}</small>` : ""}</td>
        <td><span class="chg ${e.side === 'long' ? 'up' : 'down'}">${e.side === 'long' ? 'خرید' : 'فروش'}</span></td>
        <td>${CS.faPrice(e.entry_price)}${e.exit_price ? " → " + CS.faPrice(e.exit_price) : ""}</td>
        <td>${pnlHtml}</td>
        <td class="td-actions"><button class="iconlink" data-del="${e.id}" title="حذف">🗑</button></td>
      </tr>`;
    }).join("");
    body.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => del(b.dataset.del)));
  }

  // مودال
  const modal = $("tradeModal");
  if ($("addTradeBtn")) $("addTradeBtn").addEventListener("click", () => { modal.hidden = false; });
  modal.querySelectorAll("[data-tclose]").forEach((el) => el.addEventListener("click", () => { modal.hidden = true; }));

  $("tradeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const body = {
      pair: f.pair.value.trim().toUpperCase(), side: f.side.value,
      entry_price: parseFloat(f.entry_price.value), size: parseFloat(f.size.value),
      exit_price: f.exit_price.value ? parseFloat(f.exit_price.value) : null,
      strategy: f.strategy.value || "", emotion: f.emotion.value || "", note: f.note.value || "",
    };
    try {
      const r = await fetch("/api/journal/entries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "خطا");
      modal.hidden = true; f.reset(); load();
    } catch (err) { $("tradeError").textContent = err.message; $("tradeError").hidden = false; }
  });

  async function del(id) {
    if (!confirm("این معامله حذف شود؟")) return;
    await fetch(`/api/journal/entries/${id}`, { method: "DELETE" });
    load();
  }

  load();
})();
