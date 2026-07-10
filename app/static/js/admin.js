/* پنل مدیریت کاربران — فهرست، ویرایش، نقش، اشتراک، حذف و خروجی اکسل/PDF.
   با بک‌اند /api/admin/* صحبت می‌کند. */
(function () {
  "use strict";
  const root = document.querySelector(".admin");
  if (!root) return;
  const IS_ADMIN = root.dataset.isAdmin === "true";

  const ROLE_FA = { admin: "ادمین", support: "پشتیبان", member: "عضو ساده" };
  const TIER_FA = { bronze: "برنزی", silver: "نقره‌ای", gold: "طلایی", diamond: "الماسی",
                    free: "برنزی", pro: "نقره‌ای", vip: "طلایی" };

  let users = [];
  let filtered = [];
  const selected = new Set();

  // ---------- صفحه‌بندی ----------
  const PAGE_SIZE = 50;
  let page = 1;
  function pageCount() { return Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)); }
  function pageRows() {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }

  // ---------- ابزارها ----------
  const $ = (id) => document.getElementById(id);
  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function fmtDate(s) {
    if (!s) return "—";
    try { return new Date(s.replace(" ", "T") + "Z").toLocaleDateString("fa-IR"); }
    catch (e) { return s; }
  }
  async function api(path, opts) {
    const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    let json = {};
    try { json = await res.json(); } catch (e) {}
    return { ok: res.ok, status: res.status, data: json };
  }

  // ---------- بارگذاری ----------
  async function load() {
    const r = await api("/api/admin/users");
    if (!r.ok) { $("admBody").innerHTML = '<tr><td colspan="10" class="adm-empty">دسترسی غیرمجاز.</td></tr>'; return; }
    users = r.data.users || [];
    updateStats();
    applyFilter();
  }

  function updateStats() {
    const total = users.length;
    const verified = users.filter(function (u) { return u.verified; }).length;
    const paid = users.filter(function (u) { return u.subscription && u.subscription !== "free"; }).length;
    const fa = function (n) { return Number(n).toLocaleString("fa-IR"); };
    if ($("statTotal")) $("statTotal").textContent = fa(total);
    if ($("statVerified")) $("statVerified").textContent = fa(verified);
    if ($("statPaid")) $("statPaid").textContent = fa(paid);
  }

  function applyFilter() {
    const q = ($("admSearch").value || "").trim().toLowerCase();
    filtered = !q ? users.slice() : users.filter(function (u) {
      return [u.user_code, u.username, u.full_name, u.email, u.phone]
        .some(function (v) { return (v || "").toString().toLowerCase().indexOf(q) !== -1; });
    });
    page = 1;
    renderTable();
  }

  // ---------- جدول ----------
  function roleCell(u) {
    if (!IS_ADMIN) return esc(ROLE_FA[u.role] || u.role);
    let opts = "";
    ["admin", "support", "member"].forEach(function (r) {
      opts += '<option value="' + r + '"' + (u.role === r ? " selected" : "") + ">" + ROLE_FA[r] + "</option>";
    });
    return '<select class="adm-role" data-id="' + u.id + '">' + opts + "</select>";
  }

  function subCell(u) {
    const tier = TIER_FA[u.subscription] || u.subscription || "رایگان";
    const exp = u.sub_expires_at ? '<br><small class="adm-exp">تا ' + fmtDate(u.sub_expires_at) + "</small>" : "";
    return '<span class="adm-tier adm-tier--' + esc(u.subscription) + '">' + esc(tier) + "</span>" + exp;
  }

  var ICONS = {
    sub: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>',
    edit: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    del: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    pf: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="9" height="9" rx="1"/><rect x="13" y="2" width="9" height="9" rx="1"/><rect x="13" y="13" width="9" height="9" rx="1"/><rect x="2" y="13" width="9" height="9" rx="1"/></svg>',
  };
  function actionsCell(u) {
    let html = '<div class="adm-actions">';
    html += '<button class="adm-ibtn tip" data-act="pf" data-id="' + u.id + '" data-tip="مشاهدهٔ سبد" aria-label="مشاهدهٔ سبد">' + ICONS.pf + "</button>";
    html += '<button class="adm-ibtn tip" data-act="sub" data-id="' + u.id + '" data-tip="مدیریت اشتراک" aria-label="مدیریت اشتراک">' + ICONS.sub + "</button>";
    if (IS_ADMIN) {
      html += '<button class="adm-ibtn tip" data-act="edit" data-id="' + u.id + '" data-tip="ویرایش کاربر" aria-label="ویرایش کاربر">' + ICONS.edit + "</button>";
      html += '<button class="adm-ibtn adm-ibtn--danger tip" data-act="del" data-id="' + u.id + '" data-tip="حذف کاربر" aria-label="حذف کاربر">' + ICONS.del + "</button>";
    }
    html += "</div>";
    return html;
  }

  // آواتار با حرف اول نام و رنگِ پایدار بر اساس شناسه
  function avatarHue(u) { return (Number(u.id) * 47) % 360; }
  function initial(u) {
    const n = (u.full_name || u.username || u.email || "?").trim();
    return n ? n[0].toUpperCase() : "?";
  }
  function userCell(u) {
    const hue = avatarHue(u);
    const name = esc(u.full_name || "بدون نام");
    const uname = u.username ? "@" + esc(u.username) : "—";
    return '<div class="adm-user">' +
      '<span class="adm-avatar" style="--h:' + hue + '">' + esc(initial(u)) + "</span>" +
      '<span class="adm-user__txt"><span class="adm-user__name">' + name + "</span>" +
      '<span class="adm-user__uname">' + uname + "</span></span></div>";
  }

  function riskCell(u) {
    if (u.risk_percent == null) return '<span class="adm-badge">—</span>';
    const pct = Math.round(u.risk_percent);
    const cls = pct < 40 ? "adm-badge--ok" : pct < 70 ? "adm-badge--pending" : "adm-badge--danger";
    // قابل‌کلیک: نمایشِ نتیجهٔ کاملِ آزمون
    return '<button class="adm-badge adm-badge--btn ' + cls + '" data-act="risk" data-id="' + u.id +
      '" title="مشاهدهٔ نتیجهٔ کامل">' + pct + '٪ · ' + esc(u.risk_label || "") + "</button>";
  }

  function renderTable() {
    const body = $("admBody");
    if (!filtered.length) {
      body.innerHTML = '<tr><td colspan="11" class="adm-empty">کاربری یافت نشد.</td></tr>';
      renderPager();
      updateSelCount();
      return;
    }
    if (page > pageCount()) page = pageCount();
    body.innerHTML = pageRows().map(function (u) {
      const checked = selected.has(u.id) ? " checked" : "";
      const sel = selected.has(u.id) ? " is-selected" : "";
      return '<tr data-id="' + u.id + '" class="adm-row' + sel + '">' +
        '<td class="adm-col-check"><label class="adm-cb"><input type="checkbox" class="adm-row-check" data-id="' + u.id + '"' + checked + "><span></span></label></td>" +
        "<td>" + userCell(u) + "</td>" +
        '<td><code class="adm-code">' + esc(u.user_code || "—") + "</code></td>" +
        '<td class="adm-email">' + esc(u.email) + "</td>" +
        '<td class="adm-phone" dir="ltr">' + esc(u.phone || "—") + "</td>" +
        "<td>" + roleCell(u) + "</td>" +
        "<td>" + subCell(u) + "</td>" +
        '<td><button class="adm-link" data-act="assets" data-id="' + u.id + '">' + (u.asset_count || 0) + " دارایی</button></td>" +
        "<td>" + riskCell(u) + "</td>" +
        "<td>" + (u.verified ? '<span class="adm-badge adm-badge--ok"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>تأیید</span>' : '<span class="adm-badge adm-badge--pending">معلق</span>') + "</td>" +
        '<td class="adm-col-actions">' + actionsCell(u) + "</td>" +
        "</tr>";
    }).join("");
    renderPager();
    updateSelCount();
  }

  function renderPager() {
    const pager = $("admPager");
    if (!pager) return;
    const pc = pageCount();
    if (filtered.length <= PAGE_SIZE) { pager.hidden = true; pager.innerHTML = ""; return; }
    pager.hidden = false;
    const fa = function (n) { return Number(n).toLocaleString("fa-IR"); };
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = Math.min(page * PAGE_SIZE, filtered.length);
    pager.innerHTML =
      '<button class="adm-pager__btn" data-pg="prev"' + (page <= 1 ? " disabled" : "") + ">قبلی</button>" +
      '<span class="adm-pager__info">' + fa(start) + "–" + fa(end) + " از " + fa(filtered.length) +
        " (صفحهٔ " + fa(page) + " از " + fa(pc) + ")</span>" +
      '<button class="adm-pager__btn" data-pg="next"' + (page >= pc ? " disabled" : "") + ">بعدی</button>";
  }

  function updateSelCount() {
    $("admSelCount").textContent = selected.size + " کاربر انتخاب شده";
    const rows = pageRows();
    const all = rows.length && rows.every(function (u) { return selected.has(u.id); });
    $("admSelectAll").checked = !!all;
  }

  function findUser(id) { return users.find(function (u) { return u.id === id; }); }

  // ---------- رویدادهای جدول ----------
  $("admBody").addEventListener("click", function (e) {
    const t = e.target;
    if (t.classList.contains("adm-row-check")) {
      const id = +t.dataset.id;
      if (t.checked) selected.add(id); else selected.delete(id);
      const row = t.closest("tr");
      if (row) row.classList.toggle("is-selected", t.checked);
      updateSelCount();
      return;
    }
    const btn = t.closest("[data-act]");
    if (!btn) return;
    const id = +btn.dataset.id;
    const act = btn.dataset.act;
    if (act === "edit") openEdit(id);
    else if (act === "del") delUser(id);
    else if (act === "sub") openSub(id);
    else if (act === "assets") openAssets(id);
    else if (act === "risk") openRisk(id);
    else if (act === "pf") openPortfolio(id);
  });

  $("admBody").addEventListener("change", function (e) {
    if (e.target.classList.contains("adm-role")) {
      changeRole(+e.target.dataset.id, e.target.value, e.target);
    }
  });

  $("admSelectAll").addEventListener("change", function () {
    // انتخاب/لغوِ همهٔ کاربرانِ همین صفحه
    if (this.checked) pageRows().forEach(function (u) { selected.add(u.id); });
    else pageRows().forEach(function (u) { selected.delete(u.id); });
    renderTable();
  });

  $("admPager").addEventListener("click", function (e) {
    const btn = e.target.closest("[data-pg]");
    if (!btn || btn.disabled) return;
    if (btn.dataset.pg === "prev" && page > 1) page--;
    else if (btn.dataset.pg === "next" && page < pageCount()) page++;
    renderTable();
    // بازگشت به بالای جدول برای دیدِ بهتر
    const wrap = document.querySelector(".adm-table-wrap");
    if (wrap) wrap.scrollTop = 0;
  });

  $("admSearch").addEventListener("input", applyFilter);

  // ---------- تغییر نقش ----------
  async function changeRole(id, role, el) {
    const r = await api("/api/admin/users/" + id + "/role", {
      method: "POST", body: JSON.stringify({ role: role }),
    });
    if (r.ok) { const u = findUser(id); if (u) u.role = role; }
    else { alert(r.data.error || "خطا در تغییر نقش."); if (el) { const u = findUser(id); el.value = u ? u.role : role; } }
  }

  // ---------- حذف ----------
  async function delUser(id) {
    const u = findUser(id);
    if (!confirm("حذف کاربر «" + (u ? (u.full_name || u.email) : id) + "»؟ این عمل بازگشت‌ناپذیر است.")) return;
    const r = await api("/api/admin/users/" + id, { method: "DELETE" });
    if (r.ok) { users = users.filter(function (x) { return x.id !== id; }); selected.delete(id); applyFilter(); }
    else alert(r.data.error || "خطا در حذف.");
  }

  // ---------- ویرایش (ادمین) ----------
  function editField(label, id, type, value, extra) {
    return '<div class="field"><label for="' + id + '">' + label + '</label>' +
      '<input type="' + (type || "text") + '" id="' + id + '" value="' + esc(value || "") + '"' + (extra || "") + "></div>";
  }
  function openEdit(id) {
    const u = findUser(id);
    if (!u) return;
    const m = $("admEditModal");
    $("admEditMsg").hidden = true;
    $("admEditBody").innerHTML =
      '<div class="adm-edit-grid">' +
        editField("نام", "edFirst", "text", u.first_name) +
        editField("نام خانوادگی", "edLast", "text", u.last_name) +
        editField("نام کاربری", "edUsername", "text", u.username) +
        editField("شماره تماس", "edPhone", "tel", u.phone, ' dir="ltr" inputmode="numeric" maxlength="11"') +
        editField("ایمیل", "edEmail", "email", u.email) +
        editField("شناسهٔ کاربری", "edCode", "text", u.user_code, " disabled") +
      "</div>" +
      '<div class="field"><label class="adm-check"><input type="checkbox" id="edVerified"' + (u.verified ? " checked" : "") + "> ایمیل تأیید شده</label></div>" +
      '<div class="field"><label for="edPass">رمز عبور جدید (خالی = بدون تغییر)</label>' +
        '<input type="text" id="edPass" placeholder="' + (u.password ? esc(u.password) : "—") + '"></div>' +
      (u.password ? '<p class="adm-pw-note">رمز فعلی: <code dir="ltr">' + esc(u.password) + "</code></p>"
                  : '<p class="adm-pw-note">رمز این کاربر پیش از فعال‌سازیِ نمایش رمز ساخته شده و قابل نمایش نیست.</p>') +
      '<button class="btn-primary" id="edSave">ذخیرهٔ تغییرات</button>';
    m.hidden = false;
    $("edSave").onclick = function () { saveEdit(id); };
  }
  async function saveEdit(id) {
    const payload = {
      first_name: $("edFirst").value.trim(),
      last_name: $("edLast").value.trim(),
      username: $("edUsername").value.trim(),
      phone: $("edPhone").value.trim(),
      email: $("edEmail").value.trim(),
      verified: $("edVerified").checked,
    };
    const pw = $("edPass").value.trim();
    if (pw) payload.password = pw;
    const r = await api("/api/admin/users/" + id, { method: "POST", body: JSON.stringify(payload) });
    const msg = $("admEditMsg");
    if (r.ok) {
      msg.hidden = false; msg.className = "auth-msg auth-msg--ok"; msg.textContent = "ذخیره شد.";
      await load();
      setTimeout(function () { $("admEditModal").hidden = true; }, 600);
    } else {
      msg.hidden = false; msg.className = "auth-msg auth-msg--err"; msg.textContent = r.data.error || "خطا در ذخیره.";
    }
  }

  // ---------- اشتراک ----------
  let subUserId = null;
  function setTier(tier) {
    $("admSubTier").value = tier;
    document.querySelectorAll("#admSubTierPick .tier-opt").forEach(function (b) {
      const on = b.dataset.tier === tier;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-checked", on ? "true" : "false");
    });
  }
  function setDays(days) {
    $("admSubDays").value = days;
    document.querySelectorAll("#admSubDayPresets .day-chip").forEach(function (b) {
      b.classList.toggle("is-active", +b.dataset.days === +days);
    });
  }
  function openSub(id) {
    const u = findUser(id);
    if (!u) return;
    subUserId = id;
    $("admSubMsg").hidden = true;
    const sub = TIER_FA[u.subscription] || u.subscription;
    const exp = u.sub_expires_at ? " (تا " + fmtDate(u.sub_expires_at) + ")" : "";
    $("admSubUser").innerHTML = esc(u.full_name || u.email) +
      ' — اشتراک فعلی: <b>' + esc(sub) + "</b>" + esc(exp);
    setTier((function () {
      // نرمال‌سازی legacy: free/خالی → silver (پیش‌فرضِ انتخاب ادمین)، pro→silver، vip→gold.
      const s = (u.subscription || "").toLowerCase();
      if (s === "gold" || s === "silver" || s === "diamond" || s === "bronze") return s;
      if (s === "vip") return "gold";
      return "silver";
    })());
    setDays(30);
    $("admSubModal").hidden = false;
  }
  $("admSubTierPick").addEventListener("click", function (e) {
    const b = e.target.closest(".tier-opt");
    if (b) setTier(b.dataset.tier);
  });
  $("admSubDayPresets").addEventListener("click", function (e) {
    const b = e.target.closest(".day-chip");
    if (b) setDays(b.dataset.days);
  });
  $("admSubDays").addEventListener("input", function () {
    document.querySelectorAll("#admSubDayPresets .day-chip").forEach(function (b) {
      b.classList.toggle("is-active", +b.dataset.days === +$("admSubDays").value);
    });
  });
  async function subAction(action) {
    if (subUserId == null) return;
    const body = { action: action, tier: $("admSubTier").value, days: +$("admSubDays").value || 30 };
    const r = await api("/api/admin/users/" + subUserId + "/subscription", { method: "POST", body: JSON.stringify(body) });
    const msg = $("admSubMsg");
    if (r.ok) {
      msg.hidden = false; msg.className = "auth-msg auth-msg--ok"; msg.textContent = "انجام شد.";
      await load();
      const u = findUser(subUserId);
      if (u) $("admSubUser").textContent = (u.full_name || u.email) + " — اشتراک فعلی: " + (TIER_FA[u.subscription] || u.subscription);
    } else {
      msg.hidden = false; msg.className = "auth-msg auth-msg--err"; msg.textContent = r.data.error || "خطا.";
    }
  }
  $("admSubUpgrade").onclick = function () { subAction("upgrade"); };
  $("admSubRenew").onclick = function () { subAction("renew"); };
  $("admSubRemove").onclick = function () { subAction("remove"); };

  // ---------- نمایش سبد کامل کاربر ----------
  function openPortfolio(id) {
    $("admPfFrame").src = "/admin/user-portfolio/" + id;
    $("admPfOverlay").hidden = false;
  }
  $("admPfClose").addEventListener("click", function () {
    $("admPfOverlay").hidden = true;
    $("admPfFrame").src = "";
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !$("admPfOverlay").hidden) {
      $("admPfOverlay").hidden = true;
      $("admPfFrame").src = "";
    }
  });

  // ---------- دارایی‌ها ----------
  const KIND_FA = { crypto: "رمزارز", gold: "طلا", usdt: "تتر", toman: "تومان/ریال" };
  async function openAssets(id) {
    const u = findUser(id);
    const r = await api("/api/admin/users/" + id + "/assets");
    const box = $("admAssetsBody");
    if (!r.ok) { box.innerHTML = '<p class="adm-empty">خطا در دریافت.</p>'; }
    else if (!r.data.count) { box.innerHTML = '<p class="adm-empty">این کاربر دارایی ثبت‌شده‌ای ندارد.</p>'; }
    else {
      box.innerHTML = '<p class="modal__sub">' + esc(u ? (u.full_name || u.email) : "") + "</p>" +
        '<table class="adm-table adm-table--mini"><thead><tr>' +
        "<th>نوع</th><th>نماد</th><th>نام</th><th>مقدار</th><th>قیمت خرید (تومان)</th></tr></thead><tbody>" +
        r.data.assets.map(function (a) {
          return "<tr><td>" + esc(KIND_FA[a.kind] || a.kind) + "</td><td dir=\"ltr\">" + esc(a.symbol) +
            "</td><td>" + esc(a.name) + "</td><td>" + esc(a.amount) + "</td><td>" +
            (a.buy_price != null ? esc(Math.round(a.buy_price).toLocaleString("fa-IR")) : "—") + "</td></tr>";
        }).join("") + "</tbody></table>";
    }
    $("admAssetsModal").hidden = false;
  }

  // ---------- نتیجهٔ آزمون ریسک‌پذیری ----------
  function riskRow(k, v) {
    if (!v) return "";
    return '<div class="adm-risk__row"><span class="adm-risk__k">' + esc(k) +
      '</span><span class="adm-risk__v">' + esc(v) + "</span></div>";
  }
  async function openRisk(id) {
    const u = findUser(id);
    const box = $("admRiskBody");
    box.innerHTML = '<p class="adm-empty">در حال دریافت…</p>';
    $("admRiskModal").hidden = false;
    const r = await api("/api/admin/users/" + id + "/risk");
    const p = r.ok && r.data ? r.data.profile : null;
    const answersDetail = (r.ok && r.data ? r.data.answers_detail : null) || [];
    if (!p) { box.innerHTML = '<p class="adm-empty">این کاربر هنوز آزمون را نداده است.</p>'; return; }
    const res = p.result || {};
    const persona = res.personality || {};
    const disc = res.discipline || {};
    const pct = Math.round(p.percent != null ? p.percent : (res.percent || 0));
    const pctStr = function (v) { return v != null ? Math.round(v) + "٪" : ""; };
    box.innerHTML =
      '<p class="modal__sub">' + esc(u ? (u.full_name || u.email) : "") + "</p>" +
      '<div class="adm-risk__head">' +
        '<div class="adm-risk__pct">' + pct + '<i>٪</i></div>' +
        '<div><div class="adm-risk__label">' + esc(p.label || res.label || "—") + "</div>" +
        (persona.label ? '<div class="adm-risk__persona">' + esc(persona.label) +
          (disc.label ? " · نظم: " + esc(disc.label) : "") + "</div>" : "") +
        "</div></div>" +
      (res.desc ? '<p class="adm-risk__desc">' + esc(res.desc) + "</p>" : "") +
      (persona.desc ? '<p class="adm-risk__desc">' + esc(persona.desc) + "</p>" : "") +
      (disc.desc ? '<p class="adm-risk__desc">' + esc(disc.desc) + "</p>" : "") +
      '<div class="adm-risk__grid">' +
        riskRow("تحمل ریسک", pctStr(res.tolerance_pct)) +
        riskRow("ظرفیت ریسک", pctStr(res.capacity_pct)) +
        riskRow("نظم در مدیریت ریسک", pctStr(res.discipline_pct)) +
        riskRow("هدف بازدهی", res.target_return) +
        riskRow("حداکثر ضرر", res.max_loss) +
        riskRow("مدیریت سرمایه", res.money_mgmt) +
        riskRow("ریسکِ هر معامله", res.risk_per_trade) +
        riskRow("حدِ ضرر", res.stop_loss) +
        riskRow("افق سرمایه‌گذاری", res.horizon) +
        riskRow("حوزهٔ موردعلاقه", res.area) +
      "</div>" +
      (answersDetail.length ? '<h3 class="adm-risk__qtitle">تمامِ پاسخ‌های آزمون (' +
        answersDetail.length + ' پرسش)</h3><div class="adm-risk__qa">' +
        answersDetail.map(function (a, i) {
          return '<div class="adm-risk__qa-item"><div class="adm-risk__qa-q">' +
            (i + 1) + ". " + esc(a.q) + '</div><div class="adm-risk__qa-a">' +
            (a.answer ? esc(a.answer) : '<em>بدون پاسخ</em>') + "</div></div>";
        }).join("") + "</div>" : "");
  }

  // ---------- خروجی اکسل ----------
  async function exportXlsx() {
    const ids = Array.from(selected);
    const res = await fetch("/api/admin/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids }),
    });
    if (!res.ok) { alert("خطا در خروجی اکسل."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "cryptosmart-users.xlsx";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  // ---------- خروجی PDF (نمای چاپ مرورگر) ----------
  function exportPdf() {
    const rows = selected.size ? users.filter(function (u) { return selected.has(u.id); }) : filtered;
    if (!rows.length) { alert("کاربری برای خروجی انتخاب نشده است."); return; }
    const showPw = IS_ADMIN;
    const head = "<tr><th>شناسه</th><th>نام کاربری</th><th>نام و نام خانوادگی</th><th>ایمیل</th>" +
      "<th>شماره تماس</th><th>نقش</th><th>اشتراک</th><th>انقضا</th><th>تأیید</th><th>دارایی</th>" +
      (showPw ? "<th>گذرواژه</th>" : "") + "</tr>";
    const trs = rows.map(function (u) {
      return "<tr><td>" + esc(u.user_code) + "</td><td>" + esc(u.username || "—") + "</td><td>" +
        esc(u.full_name || "—") + "</td><td>" + esc(u.email) + "</td><td>'" + esc(u.phone || "") +
        "</td><td>" + esc(ROLE_FA[u.role] || u.role) + "</td><td>" + esc(TIER_FA[u.subscription] || u.subscription) +
        "</td><td>" + (u.sub_expires_at ? esc(fmtDate(u.sub_expires_at)) : "—") + "</td><td>" +
        (u.verified ? "بله" : "خیر") + "</td><td>" + (u.asset_count || 0) + "</td>" +
        (showPw ? "<td>" + esc(u.password || "—") + "</td>" : "") + "</tr>";
    }).join("");
    const w = window.open("", "_blank");
    w.document.write(
      '<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8"><title>کاربران — کریپتو اسمارت</title>' +
      "<style>body{font-family:Tahoma,Arial,sans-serif;direction:rtl;padding:20px;}" +
      "h1{font-size:18px;}table{width:100%;border-collapse:collapse;font-size:11px;}" +
      "th,td{border:1px solid #999;padding:5px 6px;text-align:right;}th{background:#eef;}" +
      "@media print{button{display:none;}}</style></head><body>" +
      "<h1>فهرست کاربران کریپتو اسمارت (" + rows.length + " کاربر)</h1>" +
      '<button onclick="window.print()">چاپ / ذخیره PDF</button>' +
      "<table>" + head + trs + "</table></body></html>"
    );
    w.document.close();
    setTimeout(function () { try { w.print(); } catch (e) {} }, 400);
  }

  // ---------- بستن مودال‌ها ----------
  function closer(modalId, btnId) {
    $(btnId).addEventListener("click", function () { $(modalId).hidden = true; });
    $(modalId).addEventListener("click", function (e) { if (e.target === $(modalId)) $(modalId).hidden = true; });
  }
  closer("admEditModal", "admEditClose");
  closer("admSubModal", "admSubClose");
  closer("admAssetsModal", "admAssetsClose");
  closer("admRiskModal", "admRiskClose");

  $("admExportXlsx").addEventListener("click", exportXlsx);
  $("admExportPdf").addEventListener("click", exportPdf);

  load();
})();
