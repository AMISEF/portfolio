/* آزمون ریسک‌پذیری پورتفولیو — واکشی پرسش‌ها، مرحله‌به‌مرحله، ثبت و نمایش نتیجه. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  const introCard = $("introCard"), quizCard = $("quizCard"), resultCard = $("resultCard");
  let questions = [], answers = [], idx = 0;

  function show(el) { [introCard, quizCard, resultCard].forEach(c => c.hidden = (c !== el)); }

  function init() {
    // اگر کاربر وارد نشده، گیت سرور‌سایدی نمایش داده شده — API نیازی نیست
    if (!window.IS_AUTHED) return;
    // هدایتِ «قبلاً آزمون داده → مدیریت سرمایه» سمتِ سرور انجام می‌شود (بدون فلش)؛
    // پس اگر به این صفحه رسیدیم یعنی یا آزمون نداده‌ایم یا ?retake=1 است.
    const retake = new URLSearchParams(window.location.search).has("retake");
    if (retake) { startTest(); return; }
    show(introCard);
  }

  // توضیح طبقه بر اساس درصد (هماهنگ با بک‌اند، برای نمایش پروفایل ذخیره‌شده)
  function descFor(pct) {
    if (pct < 20) return "حفظ سرمایه برایتان از همه‌چیز مهم‌تر است. پیشنهاد: تمرکز بر استیبل‌کوین و بیت‌کوین، با کمترین قرارگیری در آلت‌کوین.";
    if (pct < 40) return "ثبات را به رشد سریع ترجیح می‌دهید. پیشنهاد: وزن اصلی روی BTC/ETH و سهم محدود از آلت‌کوین‌های بزرگ.";
    if (pct < 60) return "تعادلی میان رشد و امنیت می‌خواهید و نوسان معقول را تحمل می‌کنید. پیشنهاد: ترکیب BTC/ETH با آلت‌کوین‌های بزرگ و میان‌رده.";
    if (pct < 80) return "برای بازدهی بالاتر، نوسان قابل‌توجه را می‌پذیرید. پیشنهاد: سهم بیشتر آلت‌کوین‌های میان‌رده و کمی پروژه‌های نوظهور.";
    return "به دنبال بیشترین رشد هستید و با ریسک و نوسان شدید کاملاً راحتید. پیشنهاد: آلت‌کوین‌های کوچک، پروژه‌های نوظهور و ابزارهای اهرمی — همراه با مدیریت ریسک جدی.";
  }

  async function startTest() {
    try {
      const r = await CS.fetchJSON("/api/portfolio/risk/questions");
      questions = r.questions || [];
      answers = new Array(questions.length).fill(null);
      idx = 0;
      show(quizCard);
      renderQ();
    } catch (e) { alert("خطا در بارگذاری آزمون."); }
  }

  function renderQ() {
    const q = questions[idx];
    $("quizCount").textContent = "پرسش " + CS.toFa(idx + 1) + " از " + CS.toFa(questions.length);
    $("quizBar").style.width = ((idx + 1) / questions.length * 100) + "%";
    $("quizQ").textContent = q.q;
    const opts = $("quizOpts");
    opts.innerHTML = "";
    q.options.forEach((text, i) => {
      const b = document.createElement("button");
      b.className = "quiz__opt" + (answers[idx] === i ? " is-sel" : "");
      b.type = "button";
      b.innerHTML = '<span class="quiz__opt-dot"></span><span>' + text + '</span>';
      b.addEventListener("click", () => {
        answers[idx] = i;
        renderQ();
      });
      opts.appendChild(b);
    });
    $("quizPrev").disabled = idx === 0;
    $("quizNext").disabled = answers[idx] === null;
    $("quizNext").textContent = idx === questions.length - 1 ? "مشاهدهٔ نتیجه" : "بعدی";
  }

  async function next() {
    if (answers[idx] === null) return;
    if (idx < questions.length - 1) { idx++; renderQ(); return; }
    // پایان: ثبت
    $("quizNext").disabled = true;
    $("quizNext").textContent = "در حال محاسبه…";
    try {
      const res = await fetch("/api/portfolio/risk", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      renderResult(data);
    } catch (e) {
      alert("خطا در ثبت آزمون: " + e.message);
      renderQ();
    }
  }

  function setText(id, val) { const el = $(id); if (el) el.textContent = val || "—"; }

  function renderResult(d) {
    show(resultCard);
    const priv = $("pfPrivacy");
    if (priv) priv.hidden = false;
    const pct = d.percent || 0;
    $("riskLabel").textContent = d.label || "—";
    $("riskDesc").textContent = d.desc || descFor(pct);

    // تیپ شخصیتی
    if (d.personality) {
      const p = $("pfPersona"); if (p) p.hidden = false;
      setText("personaLabel", d.personality.label);
      setText("personaDesc", d.personality.desc);
    }

    // نظم در مدیریت ریسک
    if (d.discipline) {
      const dc = $("pfDiscipline"); if (dc) dc.hidden = false;
      setText("disciplineLabel", d.discipline.label);
      setText("disciplineDesc", d.discipline.desc);
    }

    // ابعاد IPS
    const dims = $("pfDims");
    if (dims) dims.hidden = false;
    const asPct = (v) => (v != null ? CS.toFa(Math.round(v)) + "٪" : "—");
    setText("dimTolerance", asPct(d.tolerance_pct));
    setText("dimCapacity", asPct(d.capacity_pct));
    setText("dimDiscipline", asPct(d.discipline_pct));
    setText("dimReturn", d.target_return);
    setText("dimLoss", d.max_loss);
    setText("dimMoney", d.money_mgmt);
    setText("dimRiskPerTrade", d.risk_per_trade);
    setText("dimStopLoss", d.stop_loss);
    setText("dimHorizon", d.horizon);
    setText("dimArea", d.area);
    // حلقهٔ درصد
    const ring = $("riskRingFg");
    const C = 2 * Math.PI * 52;
    ring.style.strokeDasharray = C;
    const color = colorFor(pct);
    ring.style.stroke = color;
    // انیمیشن شمارش
    let cur = 0;
    const target = pct;
    const step = () => {
      cur += Math.max(0.5, (target - cur) * 0.12);
      if (cur >= target) cur = target;
      $("riskPct").textContent = CS.toFa(cur.toFixed(1));
      ring.style.strokeDashoffset = C * (1 - cur / 100);
      if (cur < target) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function colorFor(pct) {
    if (pct < 20) return "#16C784";
    if (pct < 40) return "#4ED9CC";
    if (pct < 60) return "#2D63B0";
    if (pct < 80) return "#F59E0B";
    return "#EA3943";
  }

  $("startTestBtn").addEventListener("click", startTest);
  $("quizNext").addEventListener("click", next);
  $("quizPrev").addEventListener("click", () => { if (idx > 0) { idx--; renderQ(); } });
  $("retakeBtn").addEventListener("click", startTest);

  init();
})(window);
