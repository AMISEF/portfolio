/* آزمون ریسک‌پذیری پورتفولیو — واکشی پرسش‌ها، مرحله‌به‌مرحله، ثبت و نمایش نتیجه. */
(function (w) {
  "use strict";
  const CS = w.CS;
  const $ = (id) => document.getElementById(id);

  const introCard = $("introCard"), quizCard = $("quizCard"), resultCard = $("resultCard");
  let questions = [], answers = [], idx = 0;

  function show(el) { [introCard, quizCard, resultCard].forEach(c => c.hidden = (c !== el)); }

  async function init() {
    // اگر کاربر قبلاً آزمون داده، مستقیم نتیجه را نشان بده
    try {
      const r = await CS.fetchJSON("/api/portfolio/risk");
      if (r && r.profile) {
        renderResult({ percent: r.profile.percent, label: r.profile.label,
                       key: r.profile.category, desc: descFor(r.profile.percent) });
        return;
      }
    } catch (e) { /* ادامه با معرفی */ }
    show(introCard);
  }

  // توضیح طبقه بر اساس درصد (هماهنگ با بک‌اند، برای نمایش پروفایل ذخیره‌شده)
  function descFor(pct) {
    if (pct < 20) return "حفظ اصل سرمایه برایتان از همه‌چیز مهم‌تر است و از نوسان شدید پرهیز می‌کنید.";
    if (pct < 40) return "ثبات را به رشد سریع ترجیح می‌دهید و ریسک محدود را می‌پذیرید.";
    if (pct < 60) return "تعادلی میان رشد و امنیت می‌خواهید و نوسان معقول را تحمل می‌کنید.";
    if (pct < 80) return "برای بازدهی بالاتر، نوسان قابل‌توجه را می‌پذیرید.";
    return "به دنبال بیشترین رشد هستید و با ریسک و نوسان بالا کاملاً راحتید.";
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

  function renderResult(d) {
    show(resultCard);
    const pct = d.percent || 0;
    $("riskLabel").textContent = d.label || "—";
    $("riskDesc").textContent = d.desc || descFor(pct);
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
