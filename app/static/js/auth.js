/* احراز هویت سمت کلاینت: مودال ورود/ثبت‌نام، ورود تلگرام، منوی کاربر، خروج. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const modal = $("authModal");

  function openModal() { if (modal) { modal.hidden = false; document.body.style.overflow = "hidden"; } }
  function closeModal() { if (modal) { modal.hidden = true; document.body.style.overflow = ""; } }

  // باز/بسته‌کردن مودال
  const accountBtn = $("accountBtn");
  if (accountBtn) accountBtn.addEventListener("click", openModal);
  if (modal) modal.querySelectorAll("[data-close]").forEach((el) => el.addEventListener("click", closeModal));

  // تب‌ها (ورود / ثبت‌نام)
  let mode = "login";
  const tabs = modal ? modal.querySelectorAll(".auth__tab") : [];
  const nameField = $("nameField");
  const submitBtn = $("authSubmit");
  const errorEl = $("authError");
  tabs.forEach((t) => t.addEventListener("click", () => {
    mode = t.dataset.tab;
    tabs.forEach((x) => x.classList.toggle("is-active", x === t));
    if (nameField) nameField.hidden = mode !== "register";
    if (submitBtn) submitBtn.textContent = mode === "register" ? "ثبت‌نام" : "ورود";
    $("authTitle").textContent = mode === "register" ? "ساخت حساب جدید" : "ورود به حساب";
    if (errorEl) errorEl.hidden = true;
  }));

  // ارسال فرم
  const form = $("authForm");
  if (form) form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (errorEl) errorEl.hidden = true;
    const fd = new FormData(form);
    const body = { login: fd.get("login"), password: fd.get("password") };
    if (mode === "register") body.display_name = fd.get("display_name") || "";
    submitBtn.disabled = true;
    submitBtn.textContent = "لطفاً صبر کنید…";
    try {
      const r = await fetch("/api/auth/" + mode, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "خطا در ورود");
      location.reload();
    } catch (err) {
      if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
      submitBtn.disabled = false;
      submitBtn.textContent = mode === "register" ? "ثبت‌نام" : "ورود";
    }
  });

  // منوی کاربر و خروج
  const userBtn = $("userMenuBtn");
  const pop = $("userMenuPop");
  if (userBtn && pop) {
    userBtn.addEventListener("click", () => { pop.hidden = !pop.hidden; });
    document.addEventListener("click", (e) => {
      if (!userBtn.contains(e.target) && !pop.contains(e.target)) pop.hidden = true;
    });
  }
  const logoutBtn = $("logoutBtn");
  if (logoutBtn) logoutBtn.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    location.href = "/";
  });

  // ورود خودکار از طریق مینی‌اپ تلگرام
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    const initData = tg && tg.initData;
    const isLoggedIn = !!document.getElementById("userMenuBtn");
    if (initData && !isLoggedIn) {
      fetch("/api/auth/telegram", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ init_data: initData }),
      }).then((r) => { if (r.ok) location.reload(); });
    }
  } catch (e) {}
})();
