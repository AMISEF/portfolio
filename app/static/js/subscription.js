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

  // ── حساب کاربرِ جاری (یک‌بار خوانده و کش می‌شود) ────────────────────────
  let ME = null;
  let meFetched = false;

  async function fetchMe() {
    if (meFetched) return ME;
    meFetched = true;
    try {
      const r = await fetch("/api/auth/me");
      if (r.ok) { const d = await r.json(); ME = d.user || null; }
    } catch (e) { ME = null; /* مهمان */ }
    return ME;
  }

  async function init() {
    const me = await fetchMe();
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

  // ── مودال راهنمای پرداخت ───────────────────────────────────────────────
  const SUPPORT_URL = "https://t.me/cryptosmart_sup";

  /** نامِ کاملِ کاربر از فیلدهای موجود. */
  function fullName(me) {
    return (me.name || [me.first_name, me.last_name].filter(Boolean).join(" ") || "").trim();
  }

  /**
   * بلوک «مشخصات من» برای انتهای پیامِ پشتیبانی.
   *
   * مقادیر داخل backtick قرار می‌گیرند؛ تلگرام هنگام ارسالِ پیام آن‌ها را به
   * قالبِ مونواسپیس (code) تبدیل می‌کند و پشتیبان با یک لمس کپی می‌کند.
   */
  function identityBlock(me) {
    if (!me) return "";
    const mono = (v) => "`" + String(v) + "`";
    const rows = [];
    if (me.email) rows.push("Email: " + mono(me.email));
    if (me.username) rows.push("Username: " + mono(me.username));
    const full = fullName(me);
    if (full) rows.push("Name & Last Name: " + mono(full));
    if (me.phone) rows.push("Phone: " + mono(me.phone));
    if (!rows.length) return "";
    return "\n\nمشخصات من:\n" + rows.join("\n");
  }

  /** پیام رسمیِ آمادهٔ ارسال به پشتیبانی برای پلن انتخاب‌شده. */
  function supportMessage(btn, me) {
    const name = btn.getAttribute("data-plan-name") || "";
    const price = btn.getAttribute("data-plan-price") || "";
    const period = btn.getAttribute("data-plan-period") || "";
    return (
      "سلام؛ وقت بخیر.\n" +
      "مایل به تهیهٔ اشتراک «" + name + "» الگو هاب کریپتو اسمارت (" +
      period + " — " + price + ") هستم.\n" +
      "لطفاً راهنمایی بفرمایید. سپاسگزارم." +
      identityBlock(me)
    );
  }

  /** کپی در حافظه با فالبک برای مرورگرهای بدون Clipboard API. */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:-9999px;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* بی‌اثر */ }
    document.body.removeChild(ta);
  }

  function initPayModal() {
    const overlay = document.getElementById("payModal");
    if (!overlay) return;
    const planLine = document.getElementById("payModalPlan");
    const support = document.getElementById("paySupport");
    const closeBtn = document.getElementById("payModalClose");
    const ctaDesc = overlay.querySelector(".pay-cta__desc");
    const ctaDescBase = ctaDesc ? ctaDesc.textContent : "";

    const open = (btn) => {
      const name = btn.getAttribute("data-plan-name") || "";
      const price = btn.getAttribute("data-plan-price") || "";
      const period = btn.getAttribute("data-plan-period") || "";
      planLine.innerHTML =
        "پلن انتخابی شما: <b>" + name + "</b> — " + period + " " + price;

      // پیام از پیش نوشته‌شده در لینک تلگرام قرار می‌گیرد؛ ضمناً هنگام کلیک در
      // حافظه هم کپی می‌شود تا اگر کلاینت تلگرام متن را پر نکرد، کاربر فقط
      // Paste کند. مشخصاتِ حساب به‌محض آماده‌شدن به پیام افزوده می‌شود.
      const setLink = (me) => {
        const msg = supportMessage(btn, me);
        support.href = SUPPORT_URL + "?text=" + encodeURIComponent(msg);
        support.onclick = () => { copyText(msg); };
        if (ctaDesc) {
          ctaDesc.textContent = me
            ? ctaDescBase + " مشخصات حساب شما (ایمیل، نام کاربری و نام و نام خانوادگی) به‌صورت خودکار انتهای پیام درج می‌شود."
            : ctaDescBase;
        }
      };

      setLink(ME);
      fetchMe().then(setLink);

      overlay.hidden = false;
      document.body.style.overflow = "hidden";
    };

    const close = () => {
      overlay.hidden = true;
      document.body.style.overflow = "";
    };

    document.querySelectorAll(".js-buy").forEach((btn) => {
      btn.addEventListener("click", () => open(btn));
    });
    if (closeBtn) closeBtn.addEventListener("click", close);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !overlay.hidden) close();
    });

    // کلیک روی آدرس‌ها → کپی + بازخورد کوتاه
    overlay.querySelectorAll(".js-copy").forEach((el) => {
      const act = el.querySelector(".pay-addr__act");
      el.addEventListener("click", () => {
        copyText(el.getAttribute("data-copy") || "");
        el.classList.add("is-copied");
        if (act) act.textContent = "کپی شد ✓";
        setTimeout(() => {
          el.classList.remove("is-copied");
          if (act) act.textContent = "کپی";
        }, 1600);
      });
    });
  }

  // ── بنر تمدید/ارتقا (اشتراک جاری) ──────────────────────────────────────
  // برای این دکمه هم همان پیامِ حاوی مشخصات ساخته می‌شود.
  function initRenewLink() {
    const banner = document.getElementById("subCurrent");
    if (!banner) return;
    const link = banner.querySelector("a[href^='https://t.me/']");
    if (!link) return;
    fetchMe().then((me) => {
      if (!me) return;
      const msg =
        "سلام؛ وقت بخیر.\n" +
        "مایل به تمدید/ارتقای اشتراک الگو هاب کریپتو اسمارت هستم.\n" +
        "لطفاً راهنمایی بفرمایید. سپاسگزارم." +
        identityBlock(me);
      link.href = SUPPORT_URL + "?text=" + encodeURIComponent(msg);
      link.addEventListener("click", () => { copyText(msg); });
    });
  }

  function boot() { init(); initPayModal(); initRenewLink(); }

  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
