/* گیج گرافیکی شاخص ترس و طمع به‌سبک CoinMarketCap:
   نیم‌دایرهٔ رنگی ۰ تا ۱۰۰، یک نشانگر دایره‌ای روی کمان، عدد بزرگ در مرکز و
   برچسب (مبلاً «ترس») زیر آن.

   رنگ عدد و برچسب دقیقاً از همان طیف کمان خوانده می‌شود؛ پس هر جا که نشانگر
   باشد، رنگ متن همان رنگ است — نه سه حالت دستی قبلی. */
(function (w) {
  "use strict";
  const CS = w.CS;

  // طیف مشترک کمان و متن: ترس شدید → طمع شدید.
  const STOPS = [
    { at: 0,   color: [234, 57, 67],  fa: "ترس شدید" },   // #EA3943
    { at: 25,  color: [234, 140, 0],  fa: "ترس" },        // #EA8C00
    { at: 50,  color: [243, 212, 47], fa: "خنطرال" },     // #F3D42F
    { at: 75,  color: [147, 217, 0],  fa: "طمع" },        // #93D900
    { at: 100, color: [22, 199, 132], fa: "طمع شدید" },   // #16C784
  ];

  function rgb(c) {
    return "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")";
  }

  function rgba(c, a) {
    return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")";
  }

  /** رنگ طیف در مقدار v (۰–۱۰۰) — میان‌یابی خطی در RGB. */
  function colorAt(v) {
    if (v <= STOPS[0].at) return STOPS[0].color;
    for (let i = 1; i < STOPS.length; i++) {
      const a = STOPS[i - 1];
      const b = STOPS[i];
      if (v <= b.at) {
        const t = (v - a.at) / (b.at - a.at);
        return [
          Math.round(a.color[0] + (b.color[0] - a.color[0]) * t),
          Math.round(a.color[1] + (b.color[1] - a.color[1]) * t),
          Math.round(a.color[2] + (b.color[2] - a.color[2]) * t),
        ];
      }
    }
    return STOPS[STOPS.length - 1].color;
  }

  /** نام ناحیه — فقط وقتی API برچسبی نفرستاده باشد. */
  function zoneFa(v) {
    if (v < 25) return STOPS[0].fa;
    if (v < 45) return STOPS[1].fa;
    if (v < 55) return STOPS[2].fa;
    if (v < 75) return STOPS[3].fa;
    return STOPS[4].fa;
  }

  function arc(cx, cy, r, a) {
    const rad = (a * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  }

  function render(el, fng) {
    if (!el || !fng) return;
    const value = Math.max(0, Math.min(100, fng.value || 0));
    const label = fng.label_fa || zoneFa(value);
    const c = colorAt(value);
    const color = rgb(c);
    const R = 80, cx = 100, cy = 100;
    const [sx, sy] = arc(cx, cy, R, 180);
    const [ex, ey] = arc(cx, cy, R, 360);
    // نشانگر دایره‌ای روی خود کمان (نه عقربه) — مطابق طرح CoinMarketCap
    const markA = 180 + (value / 100) * 180;
    const [mx, my] = arc(cx, cy, R, markA);
    const gradStops = STOPS.map(function (s) {
      return '<stop offset="' + s.at / 100 + '" stop-color="' + rgb(s.color) + '"/>';
    }).join("");

    el.innerHTML =
      '<svg class="gauge__svg" viewBox="0 0 200 116" aria-label="شاخص ترس و طمع">' +
        '<defs><linearGradient id="gaugeg" x1="0" x2="1">' + gradStops + '</linearGradient></defs>' +
        '<path d="M ' + sx + ' ' + sy + ' A ' + R + ' ' + R + ' 0 0 1 ' + ex + ' ' + ey + '" fill="none" stroke="url(#gaugeg)" stroke-width="13" stroke-linecap="butt" stroke-dasharray="11 5"/>' +
        // حلقهٔ نشانگر هم همین رنگ را می‌گیرد تا به قطعهٔ زیرش بچسبد
        '<circle cx="' + mx + '" cy="' + my + '" r="9" fill="#fff" stroke="' + color + '" stroke-width="3"/>' +
      '</svg>' +
      '<div class="gauge__value" style="color:' + color + ';text-shadow:0 0 18px ' + rgba(c, 0.45) + '">' +
        CS.toFa(value) +
      '</div>' +
      '<div class="gauge__label" style="color:' + color + '">' + label + '</div>';
  }

  w.CSGauge = { render, colorAt, zoneFa };
})(window);
