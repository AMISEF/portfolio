/* مودال ورود/ثبت‌نام — فاز ۱: رابط کاربری و اعتبارسنجی پایه.
   اتصال واقعی به بک‌اند احراز هویت در فاز بعد انجام می‌شود. */
(function () {
  "use strict";
  const modal = document.getElementById("authModal");
  const openBtn = document.getElementById("accountBtn");
  const closeBtn = document.getElementById("authClose");
  const switchBtn = document.getElementById("authSwitch");
  if (!modal || !openBtn) return;

  const title = document.getElementById("authTitle");
  const sub = document.getElementById("authSub");
  const submit = document.getElementById("authSubmit");
  const switchText = document.getElementById("switchText");
  const nameField = document.getElementById("nameField");
  const form = document.getElementById("authForm");
  let mode = "login";

  function render() {
    const login = mode === "login";
    title.textContent = login ? "ورود به حساب" : "ساخت حساب جدید";
    sub.textContent = login ? "به پنل مدیریت سرمایهٔ کریپتو اسمارت خوش آمدید." : "برای استفادهٔ کامل از امکانات ثبت‌نام کنید.";
    submit.textContent = login ? "ورود" : "ثبت‌نام";
    switchText.textContent = login ? "حساب کاربری ندارید؟" : "قبلاً ثبت‌نام کرده‌اید؟";
    switchBtn.textContent = login ? "ثبت‌نام" : "ورود";
    nameField.hidden = login;
  }
  function open() { modal.hidden = false; render(); }
  function close() { modal.hidden = true; }

  openBtn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  switchBtn.addEventListener("click", function () { mode = mode === "login" ? "signup" : "login"; render(); });
  modal.addEventListener("click", function (e) { if (e.target === modal) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    submit.textContent = "به‌زودی…";
    submit.disabled = true;
    setTimeout(function () {
      submit.disabled = false;
      render();
      alert("احراز هویت در فاز بعدی فعال می‌شود.");
    }, 600);
  });
})();
