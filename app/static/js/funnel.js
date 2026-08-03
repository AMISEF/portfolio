/* قیف محصول — داشبورد اندازه‌گیری در پنل مدیریت.
   همهٔ استایل‌ها درون‌خطی و متکی بر متغیرهای تم هستند، پس در هر تمی درست دیده می‌شود. */
(function () {
  "use strict";

  var root = document.getElementById("admFunnel");
  if (!root) return;

  var DAYS = 30;
  var FA = ["\u06f0", "\u06f1", "\u06f2", "\u06f3", "\u06f4", "\u06f5", "\u06f6", "\u06f7", "\u06f8", "\u06f9"];

  function fa(n) {
    if (n === null || n === undefined || n === "") return "\u2014";
    return String(n).replace(/[0-9]/g, function (d) { return FA[+d]; });
  }
  function pct(v) {
    if (v === null || v === undefined) return "\u2014";
    return fa(Number(v).toFixed(1)) + "\u066a";
  }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  var C = {
    card: "background:var(--surface,#131722);border:1px solid var(--border,#232a3a);" +
          "border-radius:14px;padding:14px 16px",
    label: "font-size:12px;color:var(--muted,#8aa0b8);margin:0 0 6px",
    big: "font-size:26px;font-weight:800;line-height:1.1;color:var(--text,#e6eef7)",
    th: "text-align:right;font-size:12px;color:var(--muted,#8aa0b8);" +
        "padding:8px 10px;border-bottom:1px solid var(--border,#232a3a);font-weight:600",
    td: "padding:8px 10px;border-bottom:1px solid var(--border,#232a3a);font-size:13px"
  };

  /* رنگ هر مرحلهٔ قیف */
  var STEP_COLORS = ["#38bdf8", "#22c55e", "#f59e0b", "#a855f7"];

  /* داوری کیفیت عدد — تا مدیر بداند عدد خوب است یا بد */
  function verdict(key, value) {
    var scale = {
      visit_to_signup: [1, 3],
      signup_to_activation: [25, 50],
      activation_to_paid: [3, 10],
      churn: [10, 5]
    }[key];
    if (!scale || value === null || value === undefined) return null;
    var good, ok;
    if (key === "churn") { good = value <= scale[1]; ok = value <= scale[0]; }
    else { good = value >= scale[1]; ok = value >= scale[0]; }
    if (good) return { t: "\u0639\u0627\u0644\u06cc", c: "#22c55e" };
    if (ok) return { t: "\u0642\u0627\u0628\u0644 \u0642\u0628\u0648\u0644", c: "#f59e0b" };
    return { t: "\u0646\u06cc\u0627\u0632 \u0628\u0647 \u0628\u0647\u0628\u0648\u062f", c: "#f87171" };
  }

  function headlineCard(title, value, key, note) {
    var v = verdict(key, value);
    var badge = v
      ? '<span style="font-size:11px;font-weight:700;color:' + v.c +
        ';background:' + v.c + '1f;border-radius:20px;padding:2px 9px">' + v.t + "</span>"
      : "";
    return '<div style="' + C.card + '">' +
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px">' +
      '<p style="' + C.label + '">' + title + "</p>" + badge + "</div>" +
      '<div style="' + C.big + '">' + pct(value) + "</div>" +
      (note ? '<p style="font-size:11px;color:var(--muted,#8aa0b8);margin:6px 0 0">' +
        note + "</p>" : "") +
      "</div>";
  }

  function kpi(label, value, sub) {
    return '<div style="' + C.card + ';padding:12px 14px">' +
      '<p style="' + C.label + ';margin-bottom:4px">' + label + "</p>" +
      '<div style="font-size:19px;font-weight:700;color:var(--text,#e6eef7)">' + value + "</div>" +
      (sub ? '<p style="font-size:11px;color:var(--muted,#8aa0b8);margin:4px 0 0">' +
        sub + "</p>" : "") + "</div>";
  }

  function funnelBars(steps) {
    var top = Math.max.apply(null, steps.map(function (s) { return s.value || 0; })) || 1;
    var html = "";
    steps.forEach(function (s, i) {
      var width = Math.max(4, Math.round(((s.value || 0) / top) * 100));
      var color = STEP_COLORS[i % STEP_COLORS.length];
      var rate = i === 0 ? "" :
        '<span style="font-size:12px;color:' + color + ';font-weight:700">' +
        pct(s.rate) + ' <span style="color:var(--muted,#8aa0b8);font-weight:400">\u0627\u0632 ' +
        esc(s.of) + "</span></span>";
      html +=
        '<div style="margin-bottom:12px">' +
        '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px">' +
        '<span style="font-size:13px;font-weight:600;color:var(--text,#e6eef7)">' +
        fa(i + 1) + ". " + esc(s.label) +
        ' <span style="font-size:11px;color:var(--muted,#8aa0b8);font-weight:400">' +
        esc(s.hint || "") + "</span></span>" + rate + "</div>" +
        '<div style="display:flex;align-items:center;gap:10px">' +
        '<div style="flex:1;height:26px;background:var(--surface-2,#1b2233);border-radius:8px;overflow:hidden">' +
        '<div style="height:100%;width:' + width + "%;background:linear-gradient(90deg," +
        color + "cc," + color + ');border-radius:8px"></div></div>' +
        '<span style="min-width:56px;text-align:left;font-size:15px;font-weight:800;color:var(--text,#e6eef7)">' +
        fa(s.value) + "</span></div></div>";
    });
    return html;
  }

  function table(title, head, rows, empty) {
    var body = rows.length
      ? rows.join("")
      : '<tr><td colspan="' + head.length + '" style="' + C.td +
        ';text-align:center;color:var(--muted,#8aa0b8)">' + (empty || "\u062f\u0627\u062f\u0647\u200c\u0627\u06cc \u0646\u06cc\u0633\u062a") + "</td></tr>";
    return '<div style="' + C.card + '">' +
      '<p style="' + C.label + ';font-size:13px;font-weight:700;color:var(--text,#e6eef7)">' +
      title + "</p>" +
      '<table style="width:100%;border-collapse:collapse"><thead><tr>' +
      head.map(function (h) { return '<th style="' + C.th + '">' + h + "</th>"; }).join("") +
      "</tr></thead><tbody>" + body + "</tbody></table></div>";
  }

  function sparkline(trend) {
    if (!trend.length) return "";
    var top = Math.max.apply(null, trend.map(function (d) {
      return Math.max(d.visitors || 0, d.signups || 0);
    })) || 1;
    var bars = trend.slice(-30).map(function (d) {
      var hv = Math.round(((d.visitors || 0) / top) * 100);
      var hs = Math.round(((d.signups || 0) / top) * 100);
      return '<div title="' + esc(d.day) + " \u2014 \u0628\u0627\u0632\u062f\u06cc\u062f " + fa(d.visitors) +
        " / \u062b\u0628\u062a\u200c\u0646\u0627\u0645 " + fa(d.signups) +
        '" style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;gap:2px;height:100%">' +
        '<div style="height:' + hv + '%;background:#38bdf8;border-radius:3px 3px 0 0;min-height:2px"></div>' +
        '<div style="height:' + hs + '%;background:#22c55e;border-radius:0 0 3px 3px;min-height:1px"></div>' +
        "</div>";
    }).join("");
    return '<div style="' + C.card + '">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
      '<p style="' + C.label + ';margin:0;font-size:13px;font-weight:700;color:var(--text,#e6eef7)">' +
      "\u0631\u0648\u0646\u062f \u0631\u0648\u0632\u0627\u0646\u0647" + "</p>" +
      '<span style="font-size:11px;color:var(--muted,#8aa0b8)">' +
      '<span style="color:#38bdf8">\u25a0</span> \u0628\u0627\u0632\u062f\u06cc\u062f  ' +
      '<span style="color:#22c55e">\u25a0</span> \u062b\u0628\u062a\u200c\u0646\u0627\u0645</span></div>' +
      '<div style="display:flex;gap:3px;height:90px;align-items:flex-end">' + bars + "</div></div>";
  }

  function render(d) {
    var h = d.headline || {};
    var c = d.counts || {};
    var l = d.lifetime || {};
    var r = d.retention || {};
    var g = d.growth || {};

    var grid = "display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))";

    var html = "";

    /* ۳ عدد طلایی + ریزش */
    html += '<div style="' + grid + ';margin-bottom:14px">' +
      headlineCard("\u0628\u0627\u0632\u062f\u06cc\u062f \u2190 \u062b\u0628\u062a\u200c\u0646\u0627\u0645", h.visit_to_signup, "visit_to_signup",
        "\u0647\u062f\u0641 \u0633\u0627\u0644\u0645: \u0628\u0627\u0644\u0627\u06cc \u06f3\u066a") +
      headlineCard("\u062b\u0628\u062a\u200c\u0646\u0627\u0645 \u2190 \u0641\u0639\u0627\u0644\u200c\u0633\u0627\u0632\u06cc", h.signup_to_activation, "signup_to_activation",
        "\u0645\u0647\u0645\u200c\u062a\u0631\u06cc\u0646 \u0639\u062f\u062f \u0645\u062d\u0635\u0648\u0644 \u2014 \u0647\u062f\u0641: \u0628\u0627\u0644\u0627\u06cc \u06f5\u06f0\u066a") +
      headlineCard("\u0641\u0639\u0627\u0644\u200c\u0633\u0627\u0632\u06cc \u2190 \u062e\u0631\u06cc\u062f", h.activation_to_paid, "activation_to_paid",
        "\u0647\u062f\u0641 \u0633\u0627\u0644\u0645: \u0628\u0627\u0644\u0627\u06cc \u06f1\u06f0\u066a") +
      headlineCard("\u0631\u06cc\u0632\u0634 \u0645\u0627\u0647\u0627\u0646\u0647", h.monthly_churn, "churn",
        "\u06a9\u0645\u062a\u0631 \u0627\u0632 \u06f5\u066a \u0639\u0627\u0644\u06cc \u0627\u0633\u062a") +
      "</div>";

    /* قیف */
    html += '<div style="' + C.card + ';margin-bottom:14px">' +
      '<p style="' + C.label + ';font-size:13px;font-weight:700;color:var(--text,#e6eef7);margin-bottom:14px">' +
      "\u0642\u06cc\u0641 \u06a9\u0627\u0645\u0644 \u062a\u0628\u062f\u06cc\u0644" + "</p>" +
      funnelBars(d.steps || []) +
      '<p style="font-size:12px;color:var(--muted,#8aa0b8);margin:4px 0 0">' +
      "\u0628\u0627\u0632\u062f\u06cc\u062f \u062a\u0627 \u062e\u0631\u06cc\u062f: " +
      '<b style="color:var(--text,#e6eef7)">' + pct(h.visit_to_paid) + "</b></p></div>";

    /* KPI ها */
    html += '<div style="' + grid + ';margin-bottom:14px">' +
      kpi("\u0628\u0627\u0632\u062f\u06cc\u062f\u06a9\u0646\u0646\u062f\u0647\u0654 \u06cc\u06a9\u062a\u0627", fa(c.visitors),
        g.visitors === null || g.visitors === undefined ? "" :
          "\u0646\u0633\u0628\u062a \u0628\u0647 \u062f\u0648\u0631\u0647\u0654 \u0642\u0628\u0644: " + pct(g.visitors)) +
      kpi("\u0628\u0627\u0632\u062f\u06cc\u062f \u0635\u0641\u062d\u0647", fa(c.pageviews),
        "\u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 \u0647\u0631 \u0646\u0641\u0631: " + fa(c.pages_per_visitor)) +
      kpi("\u062b\u0628\u062a\u200c\u0646\u0627\u0645 \u062c\u062f\u06cc\u062f", fa(c.signups),
        "\u062a\u0623\u06cc\u06cc\u062f\u200c\u0634\u062f\u0647: " + fa(c.verified)) +
      kpi("\u0641\u0639\u0627\u0644\u200c\u0634\u062f\u0647", fa(c.activated),
        "\u0622\u0632\u0645\u0648\u0646 \u0631\u06cc\u0633\u06a9: " + fa(c.risk_done)) +
      kpi("\u062e\u0631\u06cc\u062f \u0627\u0634\u062a\u0631\u0627\u06a9", fa(c.paid),
        "\u062f\u0631 \u0647\u0645\u06cc\u0646 \u0628\u0627\u0632\u0647") +
      kpi("\u0645\u062f\u062a \u062a\u0627 \u0641\u0639\u0627\u0644\u200c\u0633\u0627\u0632\u06cc",
        d.median_hours_to_activate === null || d.median_hours_to_activate === undefined
          ? "\u2014" : fa(d.median_hours_to_activate) + " \u0633\u0627\u0639\u062a",
        "\u0645\u06cc\u0627\u0646\u0647\u0654 \u0641\u0627\u0635\u0644\u0647\u0654 \u062b\u0628\u062a\u200c\u0646\u0627\u0645 \u062a\u0627 \u0627\u0648\u0644\u06cc\u0646 \u062f\u0627\u0631\u0627\u06cc\u06cc") +
      kpi("\u0645\u0634\u062a\u0631\u06a9 \u0641\u0639\u0627\u0644", fa(r.active_paid),
        "\u06f7 \u0631\u0648\u0632 \u062a\u0627 \u0627\u0646\u0642\u0636\u0627: " + fa(r.expiring_7d)) +
      kpi("\u0627\u0634\u062a\u0631\u0627\u06a9 \u0645\u0646\u0642\u0636\u06cc\u200c\u0634\u062f\u0647", fa(r.expired_30d),
        "\u062f\u0631 \u06f3\u06f0 \u0631\u0648\u0632 \u06af\u0630\u0634\u062a\u0647") +
      "</div>";

    /* روند */
    html += '<div style="margin-bottom:14px">' + sparkline(d.trend || []) + "</div>";

    /* جدول‌ها */
    var sources = (d.sources || []).map(function (s) {
      return "<tr><td style=\"" + C.td + '">' + esc(s.source) + "</td><td style=\"" + C.td +
        '">' + fa(s.visitors) + "</td><td style=\"" + C.td + '">' + fa(s.views) + "</td></tr>";
    });
    var pages = (d.pages || []).map(function (p) {
      return "<tr><td style=\"" + C.td + '">' + esc(p.path) + "</td><td style=\"" + C.td +
        '">' + fa(p.views) + "</td><td style=\"" + C.td + '">' + fa(p.visitors) + "</td></tr>";
    });
    var devices = (d.devices || []).map(function (x) {
      var name = { mobile: "\u0645\u0648\u0628\u0627\u06cc\u0644", desktop: "\u062f\u0633\u06a9\u062a\u0627\u067e",
                   tablet: "\u062a\u0628\u0644\u062a", app: "\u0627\u067e" }[x.device] || x.device;
      return "<tr><td style=\"" + C.td + '">' + esc(name) + "</td><td style=\"" + C.td +
        '">' + fa(x.visitors) + "</td></tr>";
    });
    var cohorts = (d.cohorts || []).map(function (x) {
      return "<tr><td style=\"" + C.td + '">' + esc(x.month) + "</td><td style=\"" + C.td +
        '">' + fa(x.signups) + "</td><td style=\"" + C.td + '">' + fa(x.activated) +
        " (" + pct(x.activation_rate) + ")</td><td style=\"" + C.td + '">' + fa(x.paid) +
        " (" + pct(x.paid_rate) + ")</td></tr>";
    });

    html += '<div style="' + grid + ';margin-bottom:14px">' +
      table("\u0645\u0646\u0627\u0628\u0639 \u0648\u0631\u0648\u062f\u06cc",
        ["\u0645\u0646\u0628\u0639", "\u0628\u0627\u0632\u062f\u06cc\u062f\u06a9\u0646\u0646\u062f\u0647", "\u0628\u0627\u0632\u062f\u06cc\u062f"], sources) +
      table("\u062f\u0633\u062a\u06af\u0627\u0647", ["\u0646\u0648\u0639", "\u0628\u0627\u0632\u062f\u06cc\u062f\u06a9\u0646\u0646\u062f\u0647"], devices) +
      "</div>";

    html += '<div style="' + grid + '">' +
      table("\u067e\u0631\u0628\u0627\u0632\u062f\u06cc\u062f\u062a\u0631\u06cc\u0646 \u0635\u0641\u062d\u0627\u062a",
        ["\u0645\u0633\u06cc\u0631", "\u0628\u0627\u0632\u062f\u06cc\u062f", "\u06a9\u0627\u0631\u0628\u0631"], pages) +
      table("\u06a9\u0648\u0647\u0648\u0631\u062a \u0645\u0627\u0647\u0627\u0646\u0647",
        ["\u0645\u0627\u0647", "\u062b\u0628\u062a\u200c\u0646\u0627\u0645", "\u0641\u0639\u0627\u0644\u200c\u0634\u062f\u0647", "\u062e\u0631\u06cc\u062f"], cohorts) +
      "</div>";

    /* اعداد مادام‌العمر */
    html += '<p style="font-size:12px;color:var(--muted,#8aa0b8);margin:14px 0 0">' +
      "\u0627\u0632 \u0627\u0628\u062a\u062f\u0627 \u062a\u0627 \u0627\u0645\u0631\u0648\u0632: " + fa(l.users) +
      " \u06a9\u0627\u0631\u0628\u0631 \u00b7 " + fa(l.activated) + " \u0641\u0639\u0627\u0644 (" +
      pct(l.activation_rate) + ") \u00b7 " + fa(l.paid) + " \u062e\u0631\u06cc\u062f (" +
      pct(l.paid_rate) + ")" +
      (d.tracking_since ? " \u00b7 \u0631\u0647\u06af\u06cc\u0631\u06cc \u0628\u0627\u0632\u062f\u06cc\u062f \u0627\u0632 " +
        esc(d.tracking_since) : "") +
      (c.bot_hits ? " \u00b7 " + fa(c.bot_hits) + " \u0628\u0627\u0632\u062f\u06cc\u062f \u0631\u0628\u0627\u062a (\u0634\u0645\u0631\u062f\u0647 \u0646\u0634\u062f)" : "") +
      "</p>";

    document.getElementById("admFunnelBody").innerHTML = html;
  }

  function load() {
    var body = document.getElementById("admFunnelBody");
    body.innerHTML = '<p style="padding:18px;text-align:center;color:var(--muted,#8aa0b8)">' +
      "\u062f\u0631 \u062d\u0627\u0644 \u0645\u062d\u0627\u0633\u0628\u0647\u2026</p>";
    fetch("/api/admin/funnel?days=" + DAYS, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.error) throw new Error(d.error);
        render(d);
      })
      .catch(function (e) {
        body.innerHTML = '<p style="padding:18px;text-align:center;color:#f87171">' +
          "\u062e\u0637\u0627 \u062f\u0631 \u062f\u0631\u06cc\u0627\u0641\u062a \u06af\u0632\u0627\u0631\u0634: " + esc(e.message) + "</p>";
      });
  }

  root.querySelectorAll("[data-days]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      DAYS = parseInt(btn.getAttribute("data-days"), 10) || 30;
      root.querySelectorAll("[data-days]").forEach(function (b) {
        var on = b === btn;
        b.style.background = on ? "var(--primary,#38bdf8)" : "transparent";
        b.style.color = on ? "#06121d" : "var(--muted,#8aa0b8)";
        b.style.fontWeight = on ? "700" : "500";
      });
      load();
    });
  });

  load();
})();
