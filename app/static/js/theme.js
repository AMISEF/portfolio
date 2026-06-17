/* تغییر تم روشن/تاریک با ذخیره در localStorage (نماد خورشید/ماه در هدر). */
(function () {
  "use strict";
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("cs-theme", next); } catch (e) {}
  });
})();
