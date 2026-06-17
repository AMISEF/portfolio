/* گیج گرافیکی شاخص ترس و طمع (نیم‌دایره ۰ تا ۱۰۰ با عقربه). */
(function (w) {
  "use strict";
  const CS = w.CS;

  function arc(cx, cy, r, a) {
    const rad = (a * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  }

  function render(el, fng) {
    if (!el || !fng) return;
    const value = Math.max(0, Math.min(100, fng.value || 0));
    const label = fng.label_fa || "";
    const color = value < 45 ? "var(--down)" : value < 55 ? "var(--warn)" : "var(--up)";
    const R = 80, cx = 100, cy = 100;
    const [sx, sy] = arc(cx, cy, R, 180);
    const [ex, ey] = arc(cx, cy, R, 360);
    const needleA = 180 + (value / 100) * 180;
    const [nx, ny] = arc(cx, cy, R - 14, needleA);

    el.innerHTML =
      '<svg class="gauge__svg" viewBox="0 0 200 120" aria-label="شاخص ترس و طمع">' +
        '<defs><linearGradient id="gaugeg" x1="0" x2="1">' +
          '<stop offset="0" stop-color="#EA3943"/><stop offset="0.5" stop-color="#F59E0B"/><stop offset="1" stop-color="#16C784"/>' +
        '</linearGradient></defs>' +
        '<path d="M ' + sx + ' ' + sy + ' A ' + R + ' ' + R + ' 0 0 1 ' + ex + ' ' + ey + '" fill="none" stroke="url(#gaugeg)" stroke-width="16" stroke-linecap="round"/>' +
        '<line x1="' + cx + '" y1="' + cy + '" x2="' + nx + '" y2="' + ny + '" stroke="var(--heading)" stroke-width="4" stroke-linecap="round"/>' +
        '<circle cx="' + cx + '" cy="' + cy + '" r="6" fill="var(--heading)"/>' +
      '</svg>' +
      '<div class="gauge__value" style="color:' + color + '">' + CS.toFa(value) + '</div>' +
      '<div class="gauge__label" style="color:' + color + '">' + label + '</div>';
  }

  w.CSGauge = { render };
})(window);
