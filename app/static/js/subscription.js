/* صفحهٔ اشتراک — نمایش وضعیت اشتراک جاری و علامت‌گذاری کارت پلنِ فعلی. */
(function () {
  "use strict";

  function fmtDate(s) {
    if (!s) return "";
    try { return new Date(s.replace(" ", "T") + "Z").toLocaleDateString("fa-IR"); }
    catch (e) { return s; }
  }

  function quotaLabel(quota, used) {
    if (quota === null || quota === undefined) return "تحلیل نامحدود";
    const left = Math.max((quota || 0) - (used || 0), 0);
    return (window.CS ? CS.toFa(left) : left) + " تحلیل باقی‌مانده این ماه";
  }

  async function init() {
    let me = null;
    try {
      const r = await fetch("/api/auth/me");
      if (r.ok) { const d = await r.json(); me = d.user || null; }
    } catch (e) { /* مهمان */ }
    if (!me) return; // کاربر وارد نشده — کارت‌ها همان‌گونه می‌مانند

    const tier = me.tier || "bronze";
    const card = document.getElementById("card-" + tier);
    if (card) card.classList.add("pricecard--current");

    // بنر اشتراک جاری
    const banner = document.getElementById("subCurrent");
    if (!banner) return;
    document.getElementById("subCurrentTier").textContent = me.tier_name_fa || tier;
    document.getElementById("subCurrentQuota").textContent = quotaLabel(me.ai_quota, me.ai_used);
    const exp = me.sub_expires_at;
    if (exp) {
      document.getElementById("subCurrentExp").textContent = "انقضا: " + fmtDate(exp);
    }
    banner.hidden = false;

    // دکمهٔ کارت برنزی برای کاربر لاگین‌شده → «اشتراک فعلی»
    if (tier === "bronze") {
      const bronzeCta = document.querySelector('#card-bronze .pricecard__cta');
      if (bronzeCta) { bronzeCta.textContent = "اشتراک فعلی شما"; bronzeCta.removeAttribute("target"); }
    }
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
