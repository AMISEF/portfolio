/* بخش «تحلیل اختصاصی» — کانالِ نمایشیِ تحلیل‌های تلگرام + نمایشگرِ زوم + مدیریتِ ادمین.
   پست‌ها را از /api/exclusive/signals می‌گیرد و مثل کانال تلگرام نشان می‌دهد:
   آواتار دایره‌ایِ کریپتو اسمارت سمت چپِ حباب + تصویر/تصاویر تحلیل + کپشن + ساعت
   تهران + تاریخ شمسی. بخش‌بندی، صفحه‌بندی ۱۰تایی، نمایشگرِ بزرگ با زوم، و پنجرهٔ
   «مدیریت تحلیل‌ها» برای ادمین (افزودن/ویرایش/حذف با آپلود تصویر). */
(function (w, d) {
  "use strict";
  const CS = w.CS || { toFa: (s) => String(s), fetchJSON: (u) => fetch(u).then((r) => r.json()) };

  const feedEl = d.getElementById("tgcFeed");
  if (!feedEl) return;
  const tabsEl = d.getElementById("tgcTabs");
  const pagerEl = d.getElementById("tgcPager");
  const prevBtn = d.getElementById("tgcPrev");
  const nextBtn = d.getElementById("tgcNext");
  const pageInfoEl = d.getElementById("tgcPageInfo");

  let state = { filter: "all", page: 1, totalPages: 0, loading: false };
  let channel = { avatar: "/static/img/channel-avatar.png", name: "کریپتو اسمارت | Crypto Smart" };

  // ── زمان تهران / تاریخ شمسی ──
  const fmtTime = new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Tehran" });
  const fmtDate = new Intl.DateTimeFormat("fa-IR", { weekday: "long", year: "numeric", month: "long", day: "numeric", timeZone: "Asia/Tehran" });
  const fmtDateShort = new Intl.DateTimeFormat("fa-IR", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "Asia/Tehran" });
  function tehranTime(ts) { try { return fmtTime.format(new Date(ts * 1000)); } catch (e) { return ""; } }
  function shamsiDate(ts) {
    try {
      const p = fmtDate.formatToParts(new Date(ts * 1000));
      const g = (t) => { const x = p.find((e) => e.type === t); return x ? x.value : ""; };
      return g("weekday") + "، " + g("day") + " " + g("month") + " " + g("year");
    } catch (e) { return ""; }
  }
  function shamsiShort(ts) { try { return fmtDateShort.format(new Date(ts * 1000)); } catch (e) { return ""; } }

  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function renderCaption(text) {
    if (!text) return "";
    return esc(text).replace(/#([\p{L}\p{N}_]+)/gu, '<span class="tgc__tag">#$1</span>');
  }
  // نام ارز از نخستین هشتگ (لاتین بزرگ‌نویسی می‌شود).
  function coinFromTags(tags) {
    if (!tags || !tags.length) return "—";
    const t = tags[0];
    return "#" + (/^[a-z0-9]+$/i.test(t) ? t.toUpperCase() : t);
  }

  function postHTML(p) {
    const imgs = p.images && p.images.length ? p.images : (p.image_url ? [p.image_url] : []);
    let media = "";
    if (imgs.length) {
      // گالریِ آلبوم: همهٔ تصاویر در یک پست، پشتِ سرِ هم (n تصویر). data-gallery =
      // فهرستِ کاملِ آلبوم تا نمایشگرِ بزرگ بتواند بینِ آن‌ها جابه‌جا شود.
      const gal = esc(JSON.stringify(imgs));
      const cls = imgs.length > 1 ? "tgc__media--gallery" : "";
      media = `<div class="tgc__media ${cls}" data-count="${imgs.length}">` +
        imgs.map((u, i) => `<img loading="lazy" class="tgc__mediaimg" data-gallery="${gal}" data-idx="${i}" src="${esc(u)}" alt="تحلیل">`).join("") +
        `</div>`;
    }
    const caption = p.text ? `<div class="tgc__caption">${renderCaption(p.text)}</div>` : "";
    return (
      `<article class="tgc__post">
        <div class="tgc__bubble">
          <div class="tgc__author">${esc(channel.name)}</div>
          ${media}
          ${caption}
          <div class="tgc__meta">
            <span class="tgc__date">${esc(shamsiDate(p.ts))}</span>
            <span class="tgc__dot">•</span>
            <span class="tgc__time">${CS.toFa(tehranTime(p.ts))}</span>
          </div>
        </div>
        <img class="tgc__avatar" src="${esc(channel.avatar)}" alt="کریپتو اسمارت">
      </article>`
    );
  }

  function showMessage(icon, title, desc) {
    feedEl.innerHTML =
      `<div class="tgc__empty"><div class="tgc__empty-icon">${icon}</div>
        <div class="tgc__empty-title">${esc(title)}</div>
        ${desc ? `<div class="tgc__empty-desc">${esc(desc)}</div>` : ""}</div>`;
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    feedEl.innerHTML = `<div class="tgc__loading"><span class="tgc__spinner"></span><span>در حال بارگذاری تحلیل‌ها…</span></div>`;
    pagerEl.hidden = true;
    try {
      const data = await CS.fetchJSON(`/api/exclusive/signals?filter=${encodeURIComponent(state.filter)}&page=${state.page}`);
      if (data.channel) channel = data.channel;
      state.totalPages = data.total_pages || 0;
      if (!data.posts || !data.posts.length) {
        showMessage('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
          "هنوز تحلیلی در این بخش منتشر نشده", "به‌محضِ انتشار تحلیل تازه، همین‌جا نمایش داده می‌شود.");
        renderPager();
        return;
      }
      feedEl.innerHTML = data.posts.map(postHTML).join("");
      renderPager();
    } catch (e) {
      showMessage('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>',
        "خطا در دریافت تحلیل‌ها", "لطفاً چند لحظه بعد دوباره تلاش کنید.");
    } finally {
      state.loading = false;
    }
  }

  function renderPager() {
    if (!state.totalPages || state.totalPages <= 1) { pagerEl.hidden = true; return; }
    pagerEl.hidden = false;
    pageInfoEl.textContent = "صفحهٔ " + CS.toFa(state.page) + " از " + CS.toFa(state.totalPages);
    prevBtn.disabled = state.page <= 1;
    nextBtn.disabled = state.page >= state.totalPages;
  }

  tabsEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".tgc__tab");
    if (!btn || btn.classList.contains("is-active")) return;
    tabsEl.querySelectorAll(".tgc__tab").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.filter = btn.getAttribute("data-filter") || "all";
    state.page = 1;
    load();
  });
  prevBtn.addEventListener("click", () => { if (state.page > 1) { state.page--; load(); window.scrollTo({ top: 0, behavior: "smooth" }); } });
  nextBtn.addEventListener("click", () => { if (state.page < state.totalPages) { state.page++; load(); window.scrollTo({ top: 0, behavior: "smooth" }); } });

  // کلیک روی تصویرِ تحلیل → نمایشگرِ بزرگ (با امکانِ مرورِ آلبوم)
  feedEl.addEventListener("click", (ev) => {
    const img = ev.target.closest(".tgc__mediaimg");
    if (!img) return;
    let gallery;
    try { gallery = JSON.parse(img.getAttribute("data-gallery") || "[]"); } catch (e) { gallery = []; }
    if (!gallery.length) gallery = [img.getAttribute("src")];
    Lightbox.open(gallery, parseInt(img.getAttribute("data-idx") || "0", 10));
  });

  // ─────────────────────────────────────────────────────────────
  // نمایشگرِ بزرگ با زوم/جابه‌جایی
  // ─────────────────────────────────────────────────────────────
  const Lightbox = (function () {
    const box = d.getElementById("tgcLightbox");
    if (!box) return { open: function () {} };
    const img = d.getElementById("lbxImg");
    const stage = d.getElementById("lbxStage");
    const counterEl = d.getElementById("lbxCounter");
    const prevNav = d.getElementById("lbxPrev");
    const nextNav = d.getElementById("lbxNext");
    let scale = 1, tx = 0, ty = 0;
    let drag = null; const pointers = new Map(); let pinch = null;
    let album = []; let cur = 0;

    function apply() { img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`; }
    function reset() { scale = 1; tx = 0; ty = 0; apply(); }
    function clampScale(s) { return Math.max(1, Math.min(6, s)); }
    function zoomAt(cx, cy, factor) {
      const rect = stage.getBoundingClientRect();
      const ox = cx - rect.left - rect.width / 2;
      const oy = cy - rect.top - rect.height / 2;
      const ns = clampScale(scale * factor);
      const k = ns / scale;
      tx = ox - (ox - tx) * k;
      ty = oy - (oy - ty) * k;
      scale = ns;
      if (scale === 1) { tx = 0; ty = 0; }
      apply();
    }
    function show(i) {
      if (!album.length) return;
      cur = (i + album.length) % album.length;
      img.src = album[cur]; reset();
      const multi = album.length > 1;
      counterEl.hidden = !multi;
      prevNav.hidden = !multi;
      nextNav.hidden = !multi;
      if (multi) counterEl.textContent = CS.toFa(cur + 1) + " / " + CS.toFa(album.length);
    }
    function open(list, idx) {
      album = Array.isArray(list) ? list.filter(Boolean) : [list];
      if (!album.length) return;
      show(idx || 0);
      box.hidden = false;
      d.body.style.overflow = "hidden";
    }
    function close() { box.hidden = true; img.src = ""; album = []; d.body.style.overflow = ""; }

    prevNav.addEventListener("click", (e) => { e.stopPropagation(); show(cur - 1); });
    nextNav.addEventListener("click", (e) => { e.stopPropagation(); show(cur + 1); });
    d.addEventListener("keydown", (ev) => {
      if (box.hidden) return;
      if (ev.key === "ArrowLeft") show(cur + (d.dir === "rtl" ? -1 : 1));
      else if (ev.key === "ArrowRight") show(cur + (d.dir === "rtl" ? 1 : -1));
    });
    d.getElementById("lbxClose").addEventListener("click", close);
    d.getElementById("lbxIn").addEventListener("click", () => { const r = stage.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1.4); });
    d.getElementById("lbxOut").addEventListener("click", () => { const r = stage.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1 / 1.4); });
    d.getElementById("lbxReset").addEventListener("click", reset);
    box.addEventListener("click", (ev) => { if (ev.target === box || ev.target === stage) close(); });
    d.addEventListener("keydown", (ev) => { if (!box.hidden && ev.key === "Escape") close(); });

    stage.addEventListener("wheel", (ev) => { ev.preventDefault(); zoomAt(ev.clientX, ev.clientY, ev.deltaY < 0 ? 1.12 : 1 / 1.12); }, { passive: false });
    img.addEventListener("dblclick", (ev) => { ev.preventDefault(); if (scale > 1) reset(); else zoomAt(ev.clientX, ev.clientY, 2.2); });

    stage.addEventListener("pointerdown", (ev) => {
      stage.setPointerCapture(ev.pointerId);
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      if (pointers.size === 2) {
        const pts = [...pointers.values()];
        pinch = { dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y), cx: (pts[0].x + pts[1].x) / 2, cy: (pts[0].y + pts[1].y) / 2 };
      } else if (scale > 1) {
        drag = { x: ev.clientX, y: ev.clientY, tx, ty };
      }
    });
    stage.addEventListener("pointermove", (ev) => {
      if (!pointers.has(ev.pointerId)) return;
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      if (pinch && pointers.size === 2) {
        const pts = [...pointers.values()];
        const nd = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
        if (pinch.dist > 0) zoomAt(pinch.cx, pinch.cy, nd / pinch.dist);
        pinch.dist = nd;
      } else if (drag) {
        tx = drag.tx + (ev.clientX - drag.x);
        ty = drag.ty + (ev.clientY - drag.y);
        apply();
      }
    });
    function endPtr(ev) { pointers.delete(ev.pointerId); if (pointers.size < 2) pinch = null; if (pointers.size === 0) drag = null; }
    stage.addEventListener("pointerup", endPtr);
    stage.addEventListener("pointercancel", endPtr);

    return { open };
  })();

  // ─────────────────────────────────────────────────────────────
  // مدیریتِ ادمین: جدول + افزودن/ویرایش/حذف
  // ─────────────────────────────────────────────────────────────
  (function initAdmin() {
    if (!w.CS_IS_ADMIN) return;
    const modal = d.getElementById("tgcManage");
    const openBtn = d.getElementById("tgcManageBtn");
    if (!modal || !openBtn) return;
    const listView = d.getElementById("mngListView");
    const form = d.getElementById("mngForm");
    const tableWrap = d.getElementById("mngTableWrap");
    const fId = d.getElementById("mngId");
    const fText = d.getElementById("mngText");
    const fImgs = d.getElementById("mngImgs");
    const galleryEl = d.getElementById("mngGallery");
    const msg = d.getElementById("mngMsg");
    // تصاویرِ فعلیِ تحلیلِ در حالِ ویرایش: {url, idx, keep}
    let existingImgs = [];

    function openModal() { modal.hidden = false; d.body.style.overflow = "hidden"; showList(); }
    function closeModal() { modal.hidden = true; d.body.style.overflow = ""; }
    openBtn.addEventListener("click", openModal);
    modal.querySelectorAll("[data-mng-close]").forEach((el) => el.addEventListener("click", closeModal));

    function showList() { form.hidden = true; listView.hidden = false; loadTable(); }
    function showForm() { listView.hidden = true; form.hidden = false; msg.hidden = true; }

    async function loadTable() {
      tableWrap.innerHTML = `<div class="tgc__loading"><span class="tgc__spinner"></span><span>در حال بارگذاری…</span></div>`;
      try {
        const data = await CS.fetchJSON("/api/admin/signals");
        const rows = data.signals || [];
        if (!rows.length) { tableWrap.innerHTML = `<div class="mng__empty">هنوز تحلیلی ثبت نشده است.</div>`; return; }
        tableWrap.innerHTML =
          `<table class="mng__table"><thead><tr>
            <th>ارز</th><th>تاریخ</th><th>ساعت</th><th>منبع</th><th>تصویر</th><th></th>
          </tr></thead><tbody>` +
          rows.map((r) => {
            const src = r.source === "admin" ? "ادمین" : "کانال";
            return `<tr>
              <td class="mng__coin">${esc(coinFromTags(r.hashtags))}</td>
              <td>${CS.toFa(shamsiShort(r.ts))}</td>
              <td class="mng__t">${CS.toFa(tehranTime(r.ts))}</td>
              <td><span class="mng__srcbadge mng__srcbadge--${r.source}">${src}</span></td>
              <td>${CS.toFa(r.images.length)}</td>
              <td class="mng__rowact">
                <button type="button" class="mng__iconbtn" data-edit="${r.id}" title="ویرایش">✎</button>
                <button type="button" class="mng__iconbtn mng__iconbtn--del" data-del="${r.id}" title="حذف">🗑</button>
              </td></tr>`;
          }).join("") + `</tbody></table>`;
      } catch (e) {
        tableWrap.innerHTML = `<div class="mng__empty">خطا در دریافت فهرست.</div>`;
      }
    }

    // نگه‌داریِ ردیف‌ها برای پرکردنِ فرمِ ویرایش
    let cache = [];
    async function loadTableCached() { const data = await CS.fetchJSON("/api/admin/signals"); cache = data.signals || []; return cache; }

    tableWrap.addEventListener("click", async (ev) => {
      const del = ev.target.closest("[data-del]");
      const edit = ev.target.closest("[data-edit]");
      if (del) {
        const id = del.getAttribute("data-del");
        if (!w.confirm("این تحلیل حذف شود؟")) return;
        await fetch("/api/admin/signals/" + id, { method: "DELETE" });
        loadTable(); load();
      } else if (edit) {
        const id = edit.getAttribute("data-edit");
        const rows = cache.length ? cache : await loadTableCached();
        const r = rows.find((x) => String(x.id) === String(id));
        openForm(r || { id: id, text: "", images: [] });
      }
    });

    d.getElementById("mngAddBtn").addEventListener("click", () => openForm(null));
    d.getElementById("mngCancel").addEventListener("click", showList);

    function renderGallery() {
      // تصاویرِ موجود (با دکمهٔ حذف) + تصاویرِ تازه‌انتخاب‌شده (پیش‌نمایش)
      let html = existingImgs.filter((x) => x.keep).map((x) =>
        `<div class="mng__gitem"><img src="${esc(x.url)}" alt="">
          <button type="button" class="mng__gremove" data-rm="${x.idx}" title="حذف">×</button></div>`).join("");
      const files = fImgs.files ? Array.from(fImgs.files) : [];
      html += files.map((f) => `<div class="mng__gitem mng__gitem--new"><span class="mng__gnew">${esc(f.name)}</span></div>`).join("");
      galleryEl.innerHTML = html || `<div class="mng__gempty">بدون تصویر</div>`;
    }

    function openForm(r) {
      fId.value = r ? r.id : "";
      fText.value = r ? (r.text || "") : "";
      fImgs.value = "";
      existingImgs = ((r && r.images) || []).map((u, i) => ({ url: u, idx: i, keep: true }));
      renderGallery();
      showForm();
    }

    galleryEl.addEventListener("click", (ev) => {
      const rm = ev.target.closest("[data-rm]");
      if (!rm) return;
      const idx = parseInt(rm.getAttribute("data-rm"), 10);
      const it = existingImgs.find((x) => x.idx === idx);
      if (it) it.keep = false;
      renderGallery();
    });
    fImgs.addEventListener("change", renderGallery);

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData();
      fd.append("text", fText.value || "");
      const id = fId.value;
      if (id) {
        const keep = existingImgs.filter((x) => x.keep).map((x) => x.idx);
        fd.append("keep_images", JSON.stringify(keep));
      }
      const files = fImgs.files ? Array.from(fImgs.files) : [];
      files.forEach((f) => fd.append("images", f));
      const url = id ? "/api/admin/signals/" + id : "/api/admin/signals";
      msg.hidden = true;
      try {
        const r = await fetch(url, { method: "POST", body: fd });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { msg.hidden = false; msg.textContent = j.error || "خطا در ذخیره."; return; }
        // پیش‌بارگذاریِ کش برای ویرایش‌های بعدی
        await loadTableCached();
        showList(); load();
      } catch (e) {
        msg.hidden = false; msg.textContent = "خطا در ارتباط با سرور.";
      }
    });
  })();

  load();
})(window, document);
