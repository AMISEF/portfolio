/* صفحهٔ تنظیمات — تغییر رمز عبور (با کد ایمیل) و اتصال به API اسپاتِ توبیت. */
(function () {
  "use strict";

  if (!window.IS_AUTHED) return;

  const $ = (id) => document.getElementById(id);

  function msg(el, text, ok) {
    if (!el) return;
    if (!text) { el.hidden = true; return; }
    el.textContent = text;
    el.className = "auth-msg " + (ok ? "auth-msg--ok" : "auth-msg--err");
    el.hidden = false;
  }

  function busy(btn, on, label) {
    if (!btn) return;
    btn.disabled = on;
    if (on) { btn.dataset.t = btn.textContent; btn.textContent = label || "لطفاً صبر کنید…"; }
    else if (btn.dataset.t) { btn.textContent = btn.dataset.t; }
  }

  async function post(url, body, method) {
    const opt = { method: method || "POST", headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opt.body = JSON.stringify(body);
    const r = await fetch(url, opt);
    const d = await r.json().catch(() => ({}));
    return { ok: r.ok, data: d };
  }

  // ───────────── تغییر رمز عبور ─────────────
  (function password() {
    const codeBtn = $("pwCodeBtn"), saveBtn = $("pwSaveBtn");
    if (!codeBtn || !saveBtn) return;
    const box = $("pwMsg");

    codeBtn.addEventListener("click", async () => {
      msg(box, "");
      busy(codeBtn, true, "در حال ارسال…");
      const r = await post("/api/settings/password/code");
      busy(codeBtn, false);
      if (!r.ok) { msg(box, r.data.error || "ارسال کد ناموفق بود.", false); return; }
      msg(box, "کد تأیید به ایمیل شما ارسال شد. لطفاً صندوق ورودی (و پوشهٔ اسپم) را بررسی کنید.", true);
      const hint = $("pwCodeHint");
      if (hint) hint.textContent = "کد ارسال شد ✓";
      const f = $("pwCode"); if (f) f.focus();
    });

    saveBtn.addEventListener("click", async () => {
      msg(box, "");
      const code = ($("pwCode").value || "").trim();
      const p1 = $("pwNew").value || "";
      const p2 = $("pwNew2").value || "";
      if (!code) { msg(box, "کد تأیید را وارد کنید.", false); return; }
      if (p1 !== p2) { msg(box, "رمز عبور جدید و تکرار آن یکسان نیستند.", false); return; }
      busy(saveBtn, true, "در حال ثبت…");
      const r = await post("/api/settings/password", { code: code, password: p1 });
      busy(saveBtn, false);
      if (!r.ok) { msg(box, r.data.error || "تغییر رمز ناموفق بود.", false); return; }
      $("pwCode").value = ""; $("pwNew").value = ""; $("pwNew2").value = "";
      msg(box, "✅ رمز عبور شما با موفقیت تغییر کرد.", true);
    });
  })();

  // ───────────── اتصال به توبیت ─────────────
  (function toobit() {
    const saveBtn = $("tbSaveBtn"), syncBtn = $("tbSyncBtn"), delBtn = $("tbDelBtn");
    if (!saveBtn) return;
    const box = $("tbMsg"), info = $("tbInfo"), badge = $("tbBadge");

    function paint(d) {
      const on = !!d.connected;
      if (badge) {
        badge.textContent = on ? "متصل" : "متصل نیست";
        badge.className = "settings-badge" + (on ? " settings-badge--on" : "");
      }
      if (syncBtn) syncBtn.hidden = !on;
      if (delBtn) delBtn.hidden = !on;
      if (info) {
        if (on) {
          let t = "کلید ثبت‌شده: " + (d.api_key_masked || "••••");
          if (d.synced_at) t += " • آخرین به‌روزرسانی: " + d.synced_at;
          if (d.sync_error) t += " • آخرین خطا: " + d.sync_error;
          info.textContent = t;
          info.hidden = false;
        } else { info.hidden = true; }
      }
    }

    async function load() {
      try {
        const r = await fetch("/api/settings/toobit");
        if (r.ok) paint(await r.json());
      } catch (e) { /* بی‌صدا */ }
    }

    saveBtn.addEventListener("click", async () => {
      msg(box, "");
      const key = ($("tbKey").value || "").trim();
      const sec = ($("tbSecret").value || "").trim();
      if (!key || !sec) { msg(box, "هر دو مقدار Access Key و Secret Key لازم است.", false); return; }
      busy(saveBtn, true, "در حال بررسی اتصال…");
      const r = await post("/api/settings/toobit", { api_key: key, secret_key: sec });
      busy(saveBtn, false);
      if (!r.ok) { msg(box, r.data.error || "ذخیره ناموفق بود.", false); return; }
      $("tbKey").value = ""; $("tbSecret").value = "";
      paint(r.data);
      msg(box, "✅ اتصال برقرار شد. برای واردکردن دارایی‌ها، «به‌روزرسانی دارایی‌ها» را بزنید.", true);
    });

    if (syncBtn) syncBtn.addEventListener("click", async () => {
      msg(box, "");
      busy(syncBtn, true, "در حال دریافت…");
      const r = await post("/api/settings/toobit/sync");
      busy(syncBtn, false);
      if (!r.ok) { msg(box, r.data.error || "همگام‌سازی ناموفق بود.", false); return; }
      const d = r.data;
      msg(box, "✅ دارایی‌ها به‌روزرسانی شد — " + (d.imported || 0) + " مورد جدید و "
        + (d.updated || 0) + " مورد به‌روزشده. برای مشاهده به صفحهٔ مدیریت سرمایه بروید.", true);
      load();
    });

    if (delBtn) delBtn.addEventListener("click", async () => {
      if (!confirm("اتصال به توبیت قطع شود؟ کلیدهای ذخیره‌شده حذف می‌شوند.")) return;
      msg(box, "");
      busy(delBtn, true, "در حال حذف…");
      const r = await post("/api/settings/toobit", undefined, "DELETE");
      busy(delBtn, false);
      if (!r.ok) { msg(box, r.data.error || "حذف ناموفق بود.", false); return; }
      paint({ connected: false });
      msg(box, "اتصال به توبیت قطع شد.", true);
    });

    load();
  })();
})();
