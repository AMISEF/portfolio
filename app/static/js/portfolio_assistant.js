/* دستیار مدیریت سرمایه — چت‌بات اسکریپتی (فاز اول) + ارزش‌گذاری زندهٔ سبد.
   اتصال به مدل هوش مصنوعی از پلتفرم Dify در فاز بعد جایگزین این جریان می‌شود. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);
  const chat = $("chat"), inputArea = $("chatInput");

  const HORIZONS = [
    { label: "کوتاه‌مدت (زیر ۶ ماه)", value: "کوتاه‌مدت" },
    { label: "میان‌مدت (۶ تا ۱۸ ماه)", value: "میان‌مدت" },
    { label: "بلندمدت (بیش از ۱۸ ماه)", value: "بلندمدت" },
  ];
  const PALETTE = ["#2D63B0", "#19C3B3", "#F59E0B", "#EA3943", "#6F95C8",
                   "#4ED9CC", "#128F84", "#A6F0E8", "#214E8A", "#16C784"];

  // ---------- ابزار چت ----------
  function bubble(text, who) {
    const d = document.createElement("div");
    d.className = "chat__msg chat__msg--" + who;
    d.innerHTML = '<div class="chat__bubble">' + text + "</div>";
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
  }
  const bot = (t) => bubble(t, "bot");
  const me = (t) => bubble(t, "me");

  function clearInput() { inputArea.innerHTML = ""; }

  function choices(options, onPick) {
    clearInput();
    options.forEach(o => {
      const b = document.createElement("button");
      b.className = "chip-btn";
      b.textContent = o.label;
      b.addEventListener("click", () => { me(o.label); onPick(o.value); });
      inputArea.appendChild(b);
    });
  }

  function prompt(placeholder, onSubmit, opts) {
    opts = opts || {};
    clearInput();
    const wrap = document.createElement("form");
    wrap.className = "chat__form";
    const inp = document.createElement("input");
    inp.className = "chat__field";
    inp.placeholder = placeholder;
    inp.type = opts.numeric ? "text" : "text";
    inp.inputMode = opts.numeric ? "decimal" : "text";
    const send = document.createElement("button");
    send.className = "btn btn--brand";
    send.type = "submit";
    send.textContent = "ثبت";
    wrap.appendChild(inp); wrap.appendChild(send);
    inputArea.appendChild(wrap);
    inp.focus();
    wrap.addEventListener("submit", (e) => {
      e.preventDefault();
      let v = inp.value.trim();
      if (!v) return;
      if (opts.numeric) {
        v = v.replace(/[٬,،\s]/g, "");
        const n = parseFloat(v);
        if (isNaN(n) || n <= 0) { inp.classList.add("is-err"); return; }
        me(CS.faNum(n) + (opts.unit ? " " + opts.unit : ""));
        onSubmit(n);
      } else {
        me(v); onSubmit(v);
      }
    });
  }

  // ---------- جریان گفتگو ----------
  let draft = {};

  function intro() {
    bot("سلام! من چت‌بات مدیریت سرمایهٔ <b>کریپتو اسمارت</b> هستم. 👋");
    setTimeout(() => {
      bot("اینجا قراره بهت پیشنهاد بدم چه سبدی برای رشد سرمایه‌ت ببندی.<br>" +
          "فقط کافیه بهم بگی چه دارایی‌هایی داری، روی چه قیمتی خریدی و چه مدت می‌خوای سرمایه‌گذاری کنی.");
      setTimeout(askKind, 500);
    }, 500);
  }

  function askKind() {
    draft = {};
    bot("چه نوع دارایی‌ای می‌خوای اضافه کنی؟");
    choices([
      { label: "ارز دیجیتال", value: "crypto" },
      { label: "طلا", value: "gold" },
      { label: "تتر (USDT)", value: "usdt" },
      { label: "تومان نقد", value: "toman" },
    ], onKind);
  }

  function onKind(kind) {
    draft.kind = kind;
    if (kind === "crypto") {
      bot("اسم یا نماد ارز رو بنویس (مثلاً BTC یا ETH):");
      prompt("BTC", (sym) => {
        draft.symbol = sym.toUpperCase(); draft.name = draft.symbol;
        askAmount("چه مقدار " + draft.symbol + " داری؟", "واحد");
      });
    } else if (kind === "gold") {
      bot("طلا رو به چه صورت داری؟");
      choices([
        { label: "۱۸ عیار", value: "18" },
        { label: "۲۴ عیار", value: "24" },
        { label: "انس", value: "ounce" },
      ], (purity) => {
        draft.purity = purity;
        draft.symbol = "GOLD";
        draft.name = purity === "ounce" ? "انس طلا" : (purity === "24" ? "طلای ۲۴ عیار" : "طلای ۱۸ عیار");
        askAmount("چه مقدار داری؟", purity === "ounce" ? "انس" : "گرم");
      });
    } else if (kind === "usdt") {
      draft.symbol = "USDT"; draft.name = "تتر";
      askAmount("چه مقدار تتر داری؟", "USDT");
    } else { // toman
      draft.symbol = "TOMAN"; draft.name = "تومان نقد";
      bot("چه مبلغی تومان نقد داری؟");
      prompt("مبلغ به تومان", (amt) => {
        draft.amount = amt;
        saveAsset(); // تومان: بدون قیمت خرید و افق
      }, { numeric: true, unit: "تومان" });
    }
  }

  function askAmount(q, unit) {
    bot(q);
    prompt("مقدار", (amt) => {
      draft.amount = amt;
      draft.unit = unit;
      bot("روی چه قیمتی خریدی؟ (تومان به ازای هر " + unit + ")");
      prompt("قیمت خرید (تومان)", (bp) => {
        draft.buy_price = bp;
        askHorizon();
      }, { numeric: true, unit: "تومان" });
    }, { numeric: true, unit: unit });
  }

  function askHorizon() {
    bot("چه مدت می‌خوای روی این دارایی سرمایه‌گذاری کنی؟");
    choices(HORIZONS, (h) => { draft.horizon = h; saveAsset(); });
  }

  async function saveAsset() {
    clearInput();
    try {
      const res = await fetch("/api/portfolio/assets", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft)
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      bot("✅ <b>" + draft.name + "</b> به سبدت اضافه شد.");
      await loadPortfolio();
    } catch (e) {
      bot("⚠️ خطا در ثبت دارایی: " + e.message);
    }
    setTimeout(() => {
      bot("دارایی دیگه‌ای اضافه کنم؟");
      choices([
        { label: "بله، یکی دیگه", value: "more" },
        { label: "نه، همین کافیه", value: "done" },
      ], (v) => v === "more" ? askKind() : finish());
    }, 400);
  }

  function finish() {
    bot("عالی! سبدت در سمت ☚ نمایش داده شده و ارزش هر دارایی به‌صورت زنده به‌روز می‌شه.<br>" +
        "به‌زودی دستیار هوشمند، سبد بهینهٔ متناسب با ریسک‌پذیری‌ت رو پیشنهاد می‌ده.");
    clearInput();
    const b = document.createElement("button");
    b.className = "chip-btn";
    b.textContent = "افزودن دارایی جدید";
    b.addEventListener("click", askKind);
    inputArea.appendChild(b);
  }

  // ---------- نمایش سبد + ارزش‌گذاری زنده ----------
  function donutSegments(items) {
    const svg = $("donut");
    svg.innerHTML = "";
    const r = 46, cx = 60, cy = 60, C = 2 * Math.PI * r;
    if (!items.length) {
      svg.innerHTML = '<circle cx="60" cy="60" r="46" fill="none" stroke="var(--border-strong)" stroke-width="16"/>';
      return;
    }
    let off = 0;
    items.forEach((it, i) => {
      const seg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      seg.setAttribute("cx", cx); seg.setAttribute("cy", cy); seg.setAttribute("r", r);
      seg.setAttribute("fill", "none");
      seg.setAttribute("stroke", PALETTE[i % PALETTE.length]);
      seg.setAttribute("stroke-width", "16");
      const len = (it.weight || 0) / 100 * C;
      seg.setAttribute("stroke-dasharray", len + " " + (C - len));
      seg.setAttribute("stroke-dashoffset", -off);
      seg.setAttribute("transform", "rotate(-90 60 60)");
      svg.appendChild(seg);
      off += len;
    });
  }

  function renderLegend(items) {
    const el = $("portLegend");
    el.innerHTML = items.map((it, i) =>
      '<div class="port-legend__row"><span class="port-legend__dot" style="background:' +
      PALETTE[i % PALETTE.length] + '"></span>' +
      '<span class="port-legend__name">' + it.name + '</span>' +
      '<span class="port-legend__pct">' + CS.toFa((it.weight || 0).toFixed(1)) + '٪</span></div>'
    ).join("");
  }

  function renderList(items) {
    const el = $("portList");
    if (!items.length) { el.innerHTML = '<p class="port-empty">هنوز دارایی‌ای اضافه نشده است.</p>'; return; }
    el.innerHTML = items.map(it => {
      const pnl = (it.pnl_pct === null || it.pnl_pct === undefined) ? "" :
        '<span class="chg ' + CS.chgClass(it.pnl_pct) + '">' + CS.faPct(it.pnl_pct) + '</span>';
      const sub = it.kind === "gold" && it.purity ?
        (it.purity === "ounce" ? "انس" : "هر گرم") :
        (it.kind === "crypto" ? it.symbol : (it.kind === "toman" ? "نقد" : "USDT"));
      return '<div class="port-item" data-id="' + it.id + '">' +
        '<div class="port-item__main"><div class="port-item__name">' + it.name + ' ' + pnl + '</div>' +
        '<div class="port-item__sub">' + CS.faNum(it.amount) + ' × ' + CS.faNum(it.unit_price_toman) + ' ت</div></div>' +
        '<div class="port-item__right"><div class="port-item__val">' + CS.faNum(it.value_toman) + ' ت</div>' +
        '<div class="port-item__usd">' + CS.faPriceUsd(it.value_usd) + '</div></div>' +
        '<button class="port-item__del" title="حذف" aria-label="حذف">×</button></div>';
    }).join("");
    el.querySelectorAll(".port-item__del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.target.closest(".port-item").dataset.id;
        await fetch("/api/portfolio/assets/" + id, { method: "DELETE" });
        await loadPortfolio();
      });
    });
  }

  async function loadPortfolio() {
    try {
      const d = await CS.fetchJSON("/api/portfolio/assets");
      const items = d.items || [];
      $("totalToman").textContent = items.length ? CS.faNum(d.total_toman) + " ت" : "—";
      $("totalUsd").textContent = items.length ? CS.faPriceUsd(d.total_usd) : "";
      donutSegments(items);
      renderLegend(items);
      renderList(items);
    } catch (e) { console.warn("portfolio:", e); }
  }

  // ---------- راه‌اندازی ----------
  intro();
  loadPortfolio();
  setInterval(loadPortfolio, 15 * 1000);   // ارزش‌گذاری زنده هر ۱۵ ثانیه
})(window);
