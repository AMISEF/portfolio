/* بخش «تحلیل اختصاصی» — کانالِ نمایشیِ تحلیل‌های تلگرام.
   پست‌ها را از /api/exclusive/signals می‌گیرد و مثل یک کانال تلگرامی نمایش می‌دهد:
   آواتار دایره‌ایِ کریپتو اسمارت + تصویر تحلیل + کپشن + ساعت تهران + تاریخ شمسی.
   بخش‌بندی (همه/خارجی/داخلی/بیت‌کوین‌واتریوم) و صفحه‌بندی ۱۰تایی. */
(function (w) {
  "use strict";
  const CS = w.CS || { toFa: (s) => String(s) };

  const feedEl = document.getElementById("tgcFeed");
  if (!feedEl) return;
  const tabsEl = document.getElementById("tgcTabs");
  const pagerEl = document.getElementById("tgcPager");
  const prevBtn = document.getElementById("tgcPrev");
  const nextBtn = document.getElementById("tgcNext");
  const pageInfoEl = document.getElementById("tgcPageInfo");

  let state = { filter: "all", page: 1, totalPages: 0, loading: false };
  let channel = { avatar: "/static/img/logo.png", name: "کریپتو اسمارت | Crypto Smart" };

  // ── قالب‌بندیِ زمان و تاریخ به وقت تهران / تقویم شمسی ──
  const fmtTime = new Intl.DateTimeFormat("fa-IR", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Tehran",
  });
  const fmtDate = new Intl.DateTimeFormat("fa-IR", {
    weekday: "long", year: "numeric", month: "long", day: "numeric", timeZone: "Asia/Tehran",
  });
  function tehranTime(ts) { try { return fmtTime.format(new Date(ts * 1000)); } catch (e) { return ""; } }
  function shamsiDate(ts) {
    try {
      const p = fmtDate.formatToParts(new Date(ts * 1000));
      const g = (t) => { const x = p.find((e) => e.type === t); return x ? x.value : ""; };
      return g("weekday") + "، " + g("day") + " " + g("month") + " " + g("year");
    } catch (e) { return ""; }
  }

  // متن کپشن → HTML امن، با هایلایتِ هشتگ‌ها و حفظِ خطوط.
  function renderCaption(text) {
    if (!text) return "";
    const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return esc.replace(/#([\p{L}\p{N}_]+)/gu, '<span class="tgc__tag">#$1</span>');
  }

  function postHTML(p) {
    const media = p.image_url
      ? `<div class="tgc__media"><img loading="lazy" src="${p.image_url}" alt="تحلیل"></div>`
      : "";
    const caption = p.text
      ? `<div class="tgc__caption">${renderCaption(p.text)}</div>`
      : "";
    return (
      `<article class="tgc__post">
        <img class="tgc__avatar" src="${channel.avatar}" alt="کریپتو اسمارت">
        <div class="tgc__bubble">
          <div class="tgc__author">${channel.name}</div>
          ${media}
          ${caption}
          <div class="tgc__meta">
            <span class="tgc__date">${shamsiDate(p.ts)}</span>
            <span class="tgc__dot">•</span>
            <span class="tgc__time">${CS.toFa(tehranTime(p.ts))}</span>
          </div>
        </div>
      </article>`
    );
  }

  function showMessage(icon, title, desc) {
    feedEl.innerHTML =
      `<div class="tgc__empty">
        <div class="tgc__empty-icon">${icon}</div>
        <div class="tgc__empty-title">${title}</div>
        ${desc ? `<div class="tgc__empty-desc">${desc}</div>` : ""}
      </div>`;
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    feedEl.innerHTML =
      `<div class="tgc__loading"><span class="tgc__spinner"></span><span>در حال بارگذاری تحلیل‌ها…</span></div>`;
    pagerEl.hidden = true;
    try {
      const data = await CS.fetchJSON(
        `/api/exclusive/signals?filter=${encodeURIComponent(state.filter)}&page=${state.page}`
      );
      if (data.channel) channel = data.channel;
      state.totalPages = data.total_pages || 0;

      if (!data.posts || !data.posts.length) {
        showMessage(
          '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
          "هنوز تحلیلی در این بخش منتشر نشده",
          "به‌محضِ انتشار تحلیل تازه در کانال، همین‌جا نمایش داده می‌شود."
        );
        renderPager(data.total || 0);
        return;
      }
      feedEl.innerHTML = data.posts.map(postHTML).join("");
      renderPager(data.total || 0);
      feedEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      showMessage(
        '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>',
        "خطا در دریافت تحلیل‌ها",
        "لطفاً چند لحظه بعد دوباره تلاش کنید."
      );
    } finally {
      state.loading = false;
    }
  }

  function renderPager(total) {
    if (!state.totalPages || state.totalPages <= 1) {
      pagerEl.hidden = state.totalPages <= 1 && state.page === 1;
      if (state.totalPages <= 1) { pagerEl.hidden = true; return; }
    }
    pagerEl.hidden = false;
    pageInfoEl.textContent = "صفحهٔ " + CS.toFa(state.page) + " از " + CS.toFa(state.totalPages);
    prevBtn.disabled = state.page <= 1;
    nextBtn.disabled = state.page >= state.totalPages;
  }

  // ── تعامل‌ها ──
  tabsEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".tgc__tab");
    if (!btn || btn.classList.contains("is-active")) return;
    tabsEl.querySelectorAll(".tgc__tab").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.filter = btn.getAttribute("data-filter") || "all";
    state.page = 1;
    load();
  });
  prevBtn.addEventListener("click", () => { if (state.page > 1) { state.page--; load(); } });
  nextBtn.addEventListener("click", () => { if (state.page < state.totalPages) { state.page++; load(); } });

  load();
})(window);
