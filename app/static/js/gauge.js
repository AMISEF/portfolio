/* گیج نیم‌دایره‌ای شاخص ترس و طمع (۰ تا ۱۰۰) با عقربه و قوس رنگی */
(function (w) {
  "use strict";

  function color(v) {
    if (v <= 25) return "#ea3943";       // ترس شدید
    if (v <= 45) return "#f59e0b";        // ترس
    if (v <= 55) return "#eab308";        // خنثی
    if (v <= 75) return "#84cc16";        // طمع
    return "#16c784";                     // طمع شدید
  }

  // نقطه روی کمان نیم‌دایره (۱۸۰° از چپ به راست)
  function polar(cx, cy, r, deg) {
    const rad = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)];
  }
  function arc(cx, cy, r, a0, a1) {
    const [x0, y0] = polar(cx, cy, r, a0);
    const [x1, y1] = polar(cx, cy, r, a1);
    const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
    const sweep = a1 > a0 ? 0 : 1;
    return `M ${x0} ${y0} A ${r} ${r} 0 ${large} ${sweep} ${x1} ${y1}`;
  }

  function render(el, data) {
    const v = Math.max(0, Math.min(100, data.value || 0));
    const cx = 120, cy = 120, r = 92;
    // مقدار ۰..۱۰۰ → زاویه ۱۸۰..۰ درجه
    const ang = 180 - (v / 100) * 180;
    const segs = [
      [180, 135, "#ea3943"],
      [135, 99, "#f59e0b"],
      [99, 81, "#eab308"],
      [81, 45, "#84cc16"],
      [45, 0, "#16c784"],
    ];
    const segPaths = segs
      .map(([a, b, c]) => `<path d="${arc(cx, cy, r, a, b)}" stroke="${c}" stroke-width="18" fill="none" stroke-linecap="round" opacity=".92"/>`)
      .join("");
    const [nx, ny] = polar(cx, cy, r - 14, ang);
    const c = color(v);

    el.innerHTML = `
      <svg class="gauge__svg" viewBox="0 0 240 160">
        ${segPaths}
        <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="${c}" stroke-width="5" stroke-linecap="round"/>
        <circle cx="${cx}" cy="${cy}" r="9" fill="${c}"/>
        <circle cx="${cx}" cy="${cy}" r="4" fill="#fff"/>
      </svg>
      <div class="gauge__value" style="color:${c}">${w.CS.toFa(v)}</div>
      <div class="gauge__label" style="color:${c}">${data.label_fa || ""}</div>
    `;
  }

  w.CSGauge = { render };
})(window);
