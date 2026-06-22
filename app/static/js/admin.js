/* پنل مدیریت کاربران — فهرست، ویرایش، نقش، اشتراک، حذف و خروجی اکسل/PDF.
   با بک‌اند /api/admin/* صحبت می‌کند. */
(function () {
  "use strict";
  const root = document.querySelector(".admin");
  if (!root) return;
  const IS_ADMIN = root.dataset.isAdmin === "true";

  const ROLE_FA = { admin: "ادمین", support: "پشتیبان", member: "عضو ساده" };
  const TIER_FA = { free: "رایگان", pro: "حرفه‌ای", vip: "ویژه" };

  let users = [];
  let filtered = [];
  const selected = new Set();

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
    if (!r.ok) { $("admBody").innerHTML = '<tr><td colspan="11" class="adm-empty">دسترسی غیرمجاز.</td></tr>'; return; }
    users = r.data.users || [];
    applyFilter();
  }

  function applyFilter() {
    const q = ($("admSearch").value || "").trim().toLowerCase();
    filtered = !q ? users.slice() : users.filter(function (u) {
      return [u.user_code, u.username, u.full_name, u.email, u.phone]
        .some(function (v) { return (v || "").toString().toLowerCase().indexOf(q) !== -1; });
    });
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

  function actionsCell(u) {
    let html = '<div class="adm-actions">';
    html += '<button class="adm-btn" data-act="sub" data-id="' + u.id + '">اشتراک</button>';
    if (IS_ADMIN) {
      html += '<button class="adm-btn" data-act="edit" data-id="' + u.id + '">ویرایش</button>';
      html += '<button class="adm-btn adm-btn--danger" data-act="del" data-id="' + u.id + '">حذف</button>';
    }
    html += "</div>";
    return html;
  }

  function renderTable() {
    const body = $("admBody");
    if (!filtered.length) {
      body.innerHTML = '<tr><td colspan="11" class="adm-empty">کاربری یافت نشد.</td></tr>';
      updateSelCount();
      return;
    }
    body.innerHTML = filtered.map(function (u) {
      const checked = selected.has(u.id) ? " checked" : "";
      return '<tr data-id="' + u.id + '">' +
        '<td class="adm-col-check"><input type="checkbox" class="adm-row-check" data-id="' + u.id + '"' + checked + "></td>" +
        "<td>" + esc(u.user_code) + "</td>" +
        "<td>" + esc(u.username || "—") + "</td>" +
        "<td>" + esc(u.full_name || "—") + "</td>" +
        "<td>" + esc(u.email) + "</td>" +
        '<td class="adm-phone" dir="ltr">' + esc(u.phone || "—") + "</td>" +
        "<td>" + roleCell(u) + "</td>" +
        "<td>" + subCell(u) + "</td>" +
        '<td><button class="adm-link" data-act="assets" data-id="' + u.id + '">' + (u.asset_count || 0) + " دارایی</button></td>" +
        "<td>" + (u.verified ? '<span class="adm-badge adm-badge--ok">تأیید</span>' : '<span class="adm-badge">معلق</span>') + "</td>" +
        "<td>" + actionsCell(u) + "</td>" +
        "</tr>";
    }).join("");
    updateSelCount();
  }

  function updateSelCount() {
    $("admSelCount").textContent = selected.size + " کاربر انتخاب شده";
    const all = filtered.length && filtered.every(function (u) { return selected.has(u.id); });
    $("admSelectAll").checked = !!all;
  }

  function findUser(id) { return users.find(function (u) { return u.id === id; }); }

  // ---------- رویدادهای جدول ----------
  $("admBody").addEventListener("click", function (e) {
    const t = e.target;
    if (t.classList.contains("adm-row-check")) {
      const id = +t.dataset.id;
      if (t.checked) selected.add(id); else selected.delete(id);
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
  });

  $("admBody").addEventListener("change", function (e) {
    if (e.target.classList.contains("adm-role")) {
      changeRole(+e.target.dataset.id, e.target.value, e.target);
    }
  });

  $("admSelectAll").addEventListener("change", function () {
    if (this.checked) filtered.forEach(function (u) { selected.add(u.id); });
    else filtered.forEach(function (u) { selected.delete(u.id); });
    renderTable();
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
  function openSub(id) {
    const u = findUser(id);
    if (!u) return;
    subUserId = id;
    $("admSubMsg").hidden = true;
    $("admSubUser").textContent = (u.full_name || u.email) + " — اشتراک فعلی: " + (TIER_FA[u.subscription] || u.subscription);
    $("admSubTier").value = u.subscription === "free" ? "pro" : u.subscription;
    $("admSubModal").hidden = false;
  }
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

  $("admExportXlsx").addEventListener("click", exportXlsx);
  $("admExportPdf").addEventListener("click", exportPdf);

  load();
})();
