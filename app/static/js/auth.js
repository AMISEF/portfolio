/* احراز هویت ایمیلی — ورود/ثبت‌نام/تأیید کد/بازیابی رمز.
   با بک‌اند /api/auth/* صحبت می‌کند. بدنهٔ مودال بر اساس مرحله رندر می‌شود. */
(function () {
  "use strict";
  const modal = document.getElementById("authModal");
  const openBtn = document.getElementById("accountBtn");
  const closeBtn = document.getElementById("authClose");
  if (!modal || !openBtn) return;

  const title = document.getElementById("authTitle");
  const sub = document.getElementById("authSub");
  const msg = document.getElementById("authMsg");
  const body = document.getElementById("authBody");
  const switchEl = document.getElementById("authSwitch");

  let step = "login";          // login | signup | verify | forgot | reset | account
  let ctxEmail = "";           // ایمیل در جریان تأیید/بازیابی
  let currentUser = null;

  // ---------- ابزارها ----------
  function showMsg(text, kind) {
    msg.hidden = false;
    msg.textContent = text;
    msg.className = "auth-msg auth-msg--" + (kind || "info");
  }
  function clearMsg() { msg.hidden = true; msg.textContent = ""; }

  function field(label, id, type, ph, autocomplete, extra) {
    return '<div class="field"><label for="' + id + '">' + label + '</label>' +
      '<input type="' + type + '" id="' + id + '" placeholder="' + (ph || "") + '"' +
      (autocomplete ? ' autocomplete="' + autocomplete + '"' : "") +
      (extra || "") + "></div>";
  }
  function codeField() {
    return '<div class="field"><label for="authCode">کد ۶ رقمی ارسال‌شده به ایمیل</label>' +
      '<input type="text" id="authCode" inputmode="numeric" maxlength="6" ' +
      'placeholder="------" class="auth-code-input" autocomplete="one-time-code"></div>';
  }
  async function api(path, data) {
    const res = await fetch("/api/auth/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
    let json = {};
    try { json = await res.json(); } catch (e) {}
    return { ok: res.ok, status: res.status, data: json };
  }

  // ---------- سنجش قدرت رمز ----------
  function pwScore(p) {
    let s = 0;
    if (p.length >= 8) s++;
    if (/[a-z]/.test(p)) s++;
    if (/[A-Z]/.test(p)) s++;
    if (/[0-9]/.test(p)) s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;          // نماد (اختیاری، امتیاز اضافه)
    if (p.length >= 12) s++;
    return s;                                  // 0..6
  }
  function pwLabel(score) {
    if (score <= 2) return { t: "ضعیف", c: "weak" };
    if (score <= 4) return { t: "متوسط", c: "fair" };
    return { t: "قوی", c: "strong" };
  }
  function bindStrength() {
    const inp = document.getElementById("authPass");
    const bar = document.getElementById("pwBar");
    const lbl = document.getElementById("pwLabel");
    if (!inp || !bar) return;
    inp.addEventListener("input", function () {
      const sc = pwScore(inp.value);
      const pct = Math.min(100, Math.round((sc / 6) * 100));
      const info = pwLabel(sc);
      bar.style.width = pct + "%";
      bar.className = "pw-bar__fill pw-bar__fill--" + info.c;
      if (lbl) { lbl.textContent = inp.value ? ("قدرت رمز: " + info.t) : ""; lbl.className = "pw-label pw-label--" + info.c; }
    });
  }

  // ---------- رندر مراحل ----------
  function render() {
    clearMsg();
    if (step === "login") {
      title.textContent = "ورود به حساب";
      sub.textContent = "با ایمیل، شماره تماس یا شناسهٔ کاربری وارد شوید.";
      body.innerHTML =
        field("ایمیل / شماره تماس / شناسهٔ کاربری", "authIdent", "text", "example@mail.com یا 09123456789", "username") +
        field("گذرواژه", "authPass", "password", "••••••••", "current-password") +
        '<button class="btn-primary" id="btnLogin">ورود</button>' +
        '<button type="button" class="auth-link auth-link--block" id="toForgot">رمز را فراموش کرده‌اید؟</button>';
      switchEl.innerHTML = 'حساب ندارید؟ <button type="button" id="toSignup">ثبت‌نام</button>';
      bind("btnLogin", doLogin);
      bindClick("toForgot", () => go("forgot"));
      bindClick("toSignup", () => go("signup"));
    } else if (step === "signup") {
      title.textContent = "ساخت حساب جدید";
      sub.textContent = "برای استفادهٔ کامل از امکانات، ثبت‌نام کنید.";
      body.innerHTML =
        '<div class="field-row">' +
          field("نام", "authFirst", "text", "نام", "given-name") +
          field("نام خانوادگی", "authLast", "text", "نام خانوادگی", "family-name") +
        '</div>' +
        field("ایمیل", "authEmail", "email", "example@mail.com", "email") +
        field("شماره تماس", "authPhone", "tel", "0912", "tel", ' inputmode="numeric" maxlength="11"') +
        field("نام کاربری", "authUsername", "text", "username", "username") +
        field("گذرواژه", "authPass", "password", "حداقل ۸ کاراکتر", "new-password") +
        '<div class="pw-bar"><div class="pw-bar__fill" id="pwBar"></div></div>' +
        '<div class="pw-label" id="pwLabel"></div>' +
        '<p class="pw-hint">رمز باید شامل حروف بزرگ و کوچک انگلیسی و عدد باشد. ' +
        'استفاده از نماد (مثل ! یا @) اختیاری است ولی برای امنیت بیشتر توصیه می‌شود.</p>' +
        field("تکرار گذرواژه", "authPass2", "password", "تکرار رمز عبور", "new-password") +
        '<button class="btn-primary" id="btnSignup">ثبت‌نام و دریافت کد</button>';
      switchEl.innerHTML = 'قبلاً ثبت‌نام کرده‌اید؟ <button type="button" id="toLogin">ورود</button>';
      bind("btnSignup", doSignup);
      bindClick("toLogin", () => go("login"));
      bindStrength();
    } else if (step === "verify") {
      title.textContent = "تأیید ایمیل";
      sub.innerHTML = "کد ۶ رقمی به <b>" + ctxEmail + "</b> ارسال شد.";
      body.innerHTML = codeField() +
        '<button class="btn-primary" id="btnVerify">تأیید و ورود</button>' +
        '<button type="button" class="auth-link auth-link--block" id="btnResend">ارسال مجدد کد</button>';
      switchEl.innerHTML = '<button type="button" id="toLogin">بازگشت به ورود</button>';
      bind("btnVerify", doVerify);
      bindClick("btnResend", () => doResend("verify"));
      bindClick("toLogin", () => go("login"));
    } else if (step === "forgot") {
      title.textContent = "بازیابی رمز عبور";
      sub.textContent = "ایمیل حساب خود را وارد کنید تا کد بازیابی ارسال شود.";
      body.innerHTML =
        field("ایمیل", "authEmail", "email", "example@mail.com", "email") +
        '<button class="btn-primary" id="btnForgot">ارسال کد بازیابی</button>';
      switchEl.innerHTML = '<button type="button" id="toLogin">بازگشت به ورود</button>';
      bind("btnForgot", doForgot);
      bindClick("toLogin", () => go("login"));
    } else if (step === "reset") {
      title.textContent = "تنظیم رمز جدید";
      sub.innerHTML = "کد ارسال‌شده به <b>" + ctxEmail + "</b> و رمز جدید را وارد کنید.";
      body.innerHTML = codeField() +
        field("رمز عبور جدید", "authPass", "password", "حداقل ۸ کاراکتر", "new-password") +
        '<div class="pw-bar"><div class="pw-bar__fill" id="pwBar"></div></div>' +
        '<div class="pw-label" id="pwLabel"></div>' +
        '<button class="btn-primary" id="btnReset">تغییر رمز و ورود</button>' +
        '<button type="button" class="auth-link auth-link--block" id="btnResend">ارسال مجدد کد</button>';
      switchEl.innerHTML = '<button type="button" id="toLogin">بازگشت به ورود</button>';
      bind("btnReset", doReset);
      bindClick("btnResend", () => doResend("reset"));
      bindClick("toLogin", () => go("login"));
      bindStrength();
    } else if (step === "account") {
      title.textContent = "حساب کاربری";
      sub.textContent = "";
      const u = currentUser || {};
      const roleFa = { admin: "ادمین", support: "پشتیبان", member: "عضو" }[u.role] || "عضو";
      body.innerHTML =
        '<div class="auth-account">' +
        '<div class="auth-account__avatar">' + ((u.name && u.name[0]) || "👤") + '</div>' +
        '<div class="auth-account__name">' + (u.name || "کاربر") + '</div>' +
        '<div class="auth-account__email">' + (u.email || "") + '</div>' +
        '<div class="auth-account__meta">شناسه: ' + (u.user_code || "—") +
          ' • نقش: ' + roleFa + '</div>' +
        '</div>' +
        (u.is_staff ? '<a class="btn-primary btn-admin" href="/admin">ورود به پنل مدیریت</a>' : '') +
        '<button class="btn-primary btn-danger" id="btnLogout">خروج از حساب</button>';
      switchEl.innerHTML = "";
      bind("btnLogout", doLogout);
    }
  }

  function go(s) { step = s; render(); }
  function bind(id, fn) { const el = document.getElementById(id); if (el) el.onclick = fn; }
  function bindClick(id, fn) { const el = document.getElementById(id); if (el) el.onclick = fn; }
  function val(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }
  function busy(id, on) {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = on;
    if (on) { el.dataset.t = el.textContent; el.textContent = "لطفاً صبر کنید…"; }
    else if (el.dataset.t) { el.textContent = el.dataset.t; }
  }

  // ---------- اکشن‌ها ----------
  async function doSignup() {
    clearMsg();
    const pass = val("authPass");
    const pass2 = val("authPass2");
    if (pass !== pass2) { showMsg("رمز عبور و تکرار آن یکسان نیستند.", "err"); return; }
    busy("btnSignup", true);
    const r = await api("register", {
      first_name: val("authFirst"),
      last_name: val("authLast"),
      email: val("authEmail"),
      phone: val("authPhone"),
      username: val("authUsername"),
      password: pass,
      confirm_password: pass2,
    });
    busy("btnSignup", false);
    if (r.ok && r.data.stage === "verify") { ctxEmail = r.data.email; go("verify"); showMsg("کد تأیید به ایمیل شما ارسال شد.", "ok"); }
    else showMsg(r.data.error || "خطا در ثبت‌نام.", "err");
  }

  async function doVerify() {
    clearMsg();
    busy("btnVerify", true);
    const r = await api("verify", { email: ctxEmail, code: val("authCode") });
    busy("btnVerify", false);
    if (r.ok && r.data.ok) onLoggedIn(r.data.user);
    else showMsg(r.data.error || "کد نادرست است.", "err");
  }

  async function doLogin() {
    clearMsg();
    busy("btnLogin", true);
    const r = await api("login", { identifier: val("authIdent"), password: val("authPass") });
    busy("btnLogin", false);
    if (r.ok && r.data.ok) { onLoggedIn(r.data.user); return; }
    if (r.data.stage === "verify") { ctxEmail = r.data.email; go("verify"); showMsg(r.data.error, "info"); return; }
    showMsg(r.data.error || "ورود ناموفق بود.", "err");
  }

  async function doForgot() {
    clearMsg();
    busy("btnForgot", true);
    const email = val("authEmail");
    const r = await api("forgot", { email: email });
    busy("btnForgot", false);
    if (r.ok && r.data.stage === "reset") { ctxEmail = email; go("reset"); showMsg("اگر این ایمیل ثبت شده باشد، کد بازیابی ارسال شد.", "ok"); }
    else showMsg(r.data.error || "خطا در ارسال کد.", "err");
  }

  async function doReset() {
    clearMsg();
    busy("btnReset", true);
    const r = await api("reset", { email: ctxEmail, code: val("authCode"), password: val("authPass") });
    busy("btnReset", false);
    if (r.ok && r.data.ok) onLoggedIn(r.data.user);
    else showMsg(r.data.error || "تغییر رمز ناموفق بود.", "err");
  }

  async function doResend(purpose) {
    clearMsg();
    const r = await api("resend", { email: ctxEmail, purpose: purpose });
    if (r.ok) showMsg("کد جدید ارسال شد (در صورت وجود حساب).", "ok");
    else showMsg(r.data.error || "خطا در ارسال مجدد.", "err");
  }

  async function doLogout() {
    await api("logout", {});
    currentUser = null;
    setAccountButton(null);
    close();
    location.reload();
  }

  function onLoggedIn(user) {
    currentUser = user;
    setAccountButton(user);
    showMsg("خوش آمدید! ورود موفق بود.", "ok");
    setTimeout(function () { close(); location.reload(); }, 700);
  }

  // ---------- وضعیت دکمهٔ حساب ----------
  function setAccountButton(user) {
    const span = openBtn.querySelector("span");
    if (user) {
      if (span) span.textContent = user.name || user.email;
      openBtn.classList.add("account-btn--in");
    } else {
      if (span) span.textContent = "ورود / ثبت‌نام";
      openBtn.classList.remove("account-btn--in");
    }
  }

  // ---------- باز/بسته ----------
  function open() {
    modal.hidden = false;
    step = currentUser ? "account" : "login";
    render();
  }
  function close() { modal.hidden = true; }

  openBtn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  modal.addEventListener("click", function (e) { if (e.target === modal) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });

  // ---------- بررسی نشست فعلی هنگام بارگذاری ----------
  fetch("/api/auth/me").then(function (r) { return r.json(); }).then(function (d) {
    if (d && d.user) { currentUser = d.user; setAccountButton(d.user); }
  }).catch(function () {});
})();
