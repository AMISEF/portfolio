/* تغییر تم روشن/تاریک با ذخیره در localStorage + پشتیبانی تلگرام */
(function () {
  "use strict";
  const btn = document.getElementById("themeToggle");
  const root = document.documentElement;

  function setTheme(t) {
    root.setAttribute("data-theme", t);
    try { localStorage.setItem("cs-theme", t); } catch (e) {}
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "dark" ? "#0a1525" : "#162F55");
  }

  if (btn) {
    btn.addEventListener("click", () => {
      const cur = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
      setTheme(cur === "dark" ? "light" : "dark");
    });
  }

  // اگر داخل مینی‌اپ تلگرام بود، تم تلگرام را به‌عنوان پیش‌فرض اعمال کن
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (!localStorage.getItem("cs-theme") && tg.colorScheme) setTheme(tg.colorScheme);
    }
  } catch (e) {}

  // دکمهٔ حساب کاربری (فاز بعدی: ثبت‌نام/ورود واقعی)
  const acc = document.getElementById("accountBtn");
  if (acc) acc.addEventListener("click", () => {
    alert("ورود و ثبت‌نام در فاز بعدی فعال می‌شود.");
  });
})();
