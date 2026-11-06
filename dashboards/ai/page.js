/* AI at work: binds the computed data (embedded as JSON) to the DOM and charts. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const S = D.sections;
  const { FMT, dayLabel } = viz;
  const $ = (sel) => document.querySelector(sel);
  const twoWeeks = (d) => `Two weeks ending ${dayLabel(d)}`;

  viz.initThemeToggle($("#theme-btn"));
  $("#m-fetched").textContent = dayLabel(D.fetched);
  document.querySelectorAll("[data-k]").forEach((el) => {
    const [sec, key] = el.dataset.k.split(".");
    el.textContent = S[sec][key] || "";
  });
  document.querySelectorAll("[data-src]").forEach((el) => {
    const src = S[el.dataset.src].source;
    const a = document.createElement("span"); a.className = "src"; a.innerHTML = "<b>SOURCE</b> "; a.append(src.label);
    const b = document.createElement("span");
    b.textContent = `Latest wave ends ${dayLabel(Object.values(src.latest)[0])} · fetched ${dayLabel(src.fetched)}`;
    el.append(a, b);
  });

  // adoption over time
  const H = S.hero;
  viz.lineChart($("#c-hero"), {
    fmt: "pct0", dateLabel: twoWeeks, legendEl: $("#lg-hero"), bands: H.gaps, bandLabels: true, yMin: 0, top: 30,
    series: [
      { key: "use", name: "Using AI", legend: "Using AI (last two weeks)", short: "Using", color: "accent", rows: H.series.use, area: true },
      { key: "next6", name: "Expect to use within 6 months", legend: "Expect to use within six months", short: "Expect", color: "accent", rows: H.series.next6, dashed: true },
    ],
  });
  const nx = Object.fromEntries(H.series.next6);
  viz.table($("#t-hero"), ["Two weeks ending", "Using AI", "Expect within 6 months"],
    H.series.use.map(([d, v]) => [dayLabel(d), FMT.pct0(v), nx[d] != null ? FMT.pct0(nx[d]) : ""]));

  // key numbers
  S.kpis.tiles.forEach((t) => {
    const el = document.createElement("div"); el.className = "tile";
    const l = document.createElement("div"); l.className = "label"; l.textContent = t.label;
    const v = document.createElement("div"); v.className = "value"; v.textContent = t.value;
    el.append(l, v);
    // AI adoption is neither good nor bad for households by itself: neutral badge
    if (t.delta) el.append(viz.deltaBadge(t.delta.value, { goodUp: null, text: t.delta.text }));
    const w = document.createElement("div"); w.className = "when"; w.textContent = t.when;
    el.append(w);
    $("#kpis").append(el);
  });

  // by industry: ranked bars with the national rate marked
  const I = S.industries;
  const max = Math.max(...I.rows.map((r) => r.value), I.national);
  I.rows.forEach((r) => {
    const li = document.createElement("li");
    const row = document.createElement("div"); row.className = "b-row";
    const name = document.createElement("span"); name.className = "b-name"; name.textContent = r.name;
    const amt = document.createElement("span"); amt.className = "b-amt"; amt.textContent = FMT.pct0(r.value);
    const chg = document.createElement("span"); chg.className = "b-share";
    chg.textContent = `${r.change >= 0 ? "+" : "−"}${Math.abs(r.change).toFixed(1)} pt since ${viz.monthLabel(r.since)}`;
    const track = document.createElement("span"); track.className = "b-track b-track-ref";
    const bar = document.createElement("span"); bar.className = "b-bar"; bar.style.width = `${(r.value / max) * 82}%`;
    const ref = document.createElement("span"); ref.className = "b-ref"; ref.style.left = `${(I.national / max) * 82}%`;
    ref.title = `National: ${FMT.pct0(I.national)}`;
    track.append(bar, ref);
    row.append(name, amt, chg, track);
    li.append(row);
    $("#industries").append(li);
  });
  const key = document.createElement("li"); key.className = "b-refkey";
  key.textContent = `▏ marks the national rate (${FMT.pct0(I.national)})`;
  $("#industries").append(key);
  viz.table($("#t-industries"), ["Industry", "Using AI", "Change since first wave"],
    I.rows.slice().reverse().map((r) => [r.name, FMT.pct0(r.value), `${r.change.toFixed(1)} pt`]));

  // effect on jobs: diverging bars (decreased to the left, increased to the right)
  const J = S.jobs;
  const scale = Math.max(...J.rows.flatMap((r) => [r.increased, r.decreased])) * 1.15;
  J.rows.forEach((r) => {
    const wrap = document.createElement("div"); wrap.className = "dv-row";
    const lab = document.createElement("div"); lab.className = "dv-label"; lab.textContent = r.label;
    const bars = document.createElement("div"); bars.className = "dv-bars";
    const left = document.createElement("div"); left.className = "dv-side dv-left";
    const right = document.createElement("div"); right.className = "dv-side dv-right";
    const dec = document.createElement("span"); dec.className = "dv-bar bad"; dec.style.width = `${(r.decreased / scale) * 100}%`;
    const inc = document.createElement("span"); inc.className = "dv-bar good"; inc.style.width = `${(r.increased / scale) * 100}%`;
    const decT = document.createElement("span"); decT.className = "dv-val"; decT.textContent = `▼ ${FMT.pct0(r.decreased)} fewer`;
    const incT = document.createElement("span"); incT.className = "dv-val"; incT.textContent = `▲ ${FMT.pct0(r.increased)} more`;
    left.append(decT, dec); right.append(inc, incT);
    bars.append(left, right);
    const rest = document.createElement("div"); rest.className = "dv-rest";
    rest.textContent = `No change ${FMT.pct0(r.no_change)} · Don't know ${FMT.pct0(r.dont_know)}`;
    wrap.append(lab, bars, rest);
    $("#jobs").append(wrap);
  });
  $("#jobs-note").textContent = `Share of all employer businesses, two weeks ending ${dayLabel(J.rows[0].when)}. Asked once so far, so this is a snapshot, not a trend.`;
  $("#q-text").textContent = `Survey question: "${D.question}"`;
})();
