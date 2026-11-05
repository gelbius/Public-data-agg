/* Macro dashboard page: binds the computed data (embedded as JSON) to the DOM and charts. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const S = D.sections;
  const { FMT, monthLabel, dayLabel, quarterLabel } = viz;
  const $ = (sel) => document.querySelector(sel);

  viz.initThemeToggle($("#theme-btn"));
  $("#m-fetched").textContent = dayLabel(D.fetched);

  // ---- text: every headline / sub / footnote comes from compute.py
  document.querySelectorAll("[data-k]").forEach((el) => {
    const [sec, key] = el.dataset.k.split(".");
    el.textContent = S[sec][key] || "";
  });

  // ---- SOURCE footers
  document.querySelectorAll("[data-src]").forEach((el) => {
    const src = S[el.dataset.src].source;
    const ids = src.ids.join(" · ");
    const latest = Object.values(src.latest).sort().pop();
    const via = src.via === "fred" ? " (via FRED mirror)" : src.via === "bls" ? " (BLS API)" : "";
    const a = document.createElement("span");
    a.className = "src";
    a.innerHTML = "<b>SOURCE</b> ";
    a.append(`${ids}${via}`);
    const b = document.createElement("span");
    b.textContent = `Latest observation ${latest.includes("annual") ? latest : latest.endsWith("-01") ? monthLabel(latest) : dayLabel(latest)} · fetched ${dayLabel(src.fetched)}`;
    el.append(a, b);
  });

  const months = (rows) => rows.map((r) => r[0]);

  // ---- HERO
  const H = S.hero;
  viz.lineChart($("#c-hero"), {
    fmt: "pct1", bands: H.phases, bandLabels: true, alternate: true, notes: H.notes,
    xMin: H.series.cpi[0][0], top: 44,
    legendEl: $("#lg-hero"), bandKeyEl: $("#key-hero"),
    series: [
      { key: "cpi", name: "Inflation (CPI)", legend: "Inflation (CPI, year over year)", short: "Inflation", color: "cpi", rows: H.series.cpi },
      { key: "core", name: "Core inflation", legend: "Core inflation (ex food & energy)", short: "Core", color: "cpi", rows: H.series.core, dashed: true, hidden: true },
      { key: "fedfunds", name: "Fed funds rate", legend: "Fed funds rate", short: "Fed funds", color: "ff", rows: H.series.fedfunds },
      { key: "unrate", name: "Unemployment", legend: "Unemployment rate", short: "Unemployment", color: "ur", rows: H.series.unrate },
    ],
  });
  {
    const idx = (rows) => Object.fromEntries(rows);
    const c = idx(H.series.cpi), k = idx(H.series.core), f = idx(H.series.fedfunds), u = idx(H.series.unrate);
    const all = [...new Set([...months(H.series.unrate), ...months(H.series.cpi)])].sort();
    const fmtv = (v) => (v == null ? "n/a" : FMT.pct2(v));
    viz.table($("#t-hero"), ["Month", "CPI y/y", "Core CPI y/y", "Fed funds", "Unemployment"],
      all.map((d) => [monthLabel(d), fmtv(c[d]), fmtv(k[d]), fmtv(f[d]), fmtv(u[d])]));
  }

  // ---- KPI tiles
  const KPI_COLOR = { CPIAUCSL: "cpi", FEDFUNDS: "ff", UNRATE: "ur" };
  const grid = $("#kpis");
  viz.deltaKey($("#key-kpis"), "Change vs a year ago:");
  S.kpis.tiles.forEach((t) => {
    const el = document.createElement("div");
    el.className = "tile";
    const label = document.createElement("div"); label.className = "label"; label.textContent = t.label;
    const value = document.createElement("div"); value.className = "value"; value.textContent = t.value;
    el.append(label, value);
    if (t.delta) el.append(viz.deltaBadge(t.delta.value, { goodUp: t.good_up, full: t.delta.full, text: t.delta.text, when: "vs a year ago" }));
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("aria-hidden", "true");
    viz.sparkline(svg, t.spark, KPI_COLOR[t.id] || "accent");
    const when = document.createElement("div"); when.className = "when"; when.textContent = `${t.when} · ${t.id}`;
    el.append(svg, when);
    grid.append(el);
  });

  // ---- WAGES: two lines plus a shaded gap (stacked helper areas, hidden from the tooltip)
  const W = S.wages;
  {
    const cmap = Object.fromEntries(W.series.cpi);
    const rows = W.series.wages.filter((r) => r[0] in cmap);
    const base = rows.map(([d, w]) => [d, Math.min(w, cmap[d])]);
    const pos = rows.map(([d, w]) => [d, Math.max(0, w - cmap[d])]);
    const neg = rows.map(([d, w]) => [d, Math.max(0, cmap[d] - w)]);
    const helper = (name, data, color) => ({
      name, type: "line", stack: "gap", data, showSymbol: false, silent: true,
      lineStyle: { width: 0 }, areaStyle: color ? { color, opacity: 1 } : { opacity: 0 }, tooltip: { show: false },
      emphasis: { disabled: true }, z: 1,
    });
    viz.lineChart($("#c-wages"), {
      fmt: "pct1", xMin: rows[0][0],
      series: [
        { key: "wages", name: "Hourly pay", short: "Pay", color: "wage", rows: W.series.wages },
        { key: "cpi", name: "Prices (CPI)", short: "Prices", color: "cpi", rows: W.series.cpi },
      ],
      extraSeries: (t) => [helper("_base", base), helper("_pos", pos, t.goodWash), helper("_neg", neg, t.badWash)],
      tipExtra: (d) => {
        const w = Object.fromEntries(W.series.wages)[d], c = cmap[d];
        if (w == null || c == null) return null;
        const g = w - c;
        return `Real pay ${g >= 0 ? "rising" : "falling"}: ${g >= 0 ? "+" : "−"}${Math.abs(g).toFixed(2)} pt`;
      },
    });
    viz.table($("#t-wages"), ["Month", "Hourly pay y/y", "CPI y/y", "Gap (pt)"],
      rows.map(([d, w]) => [monthLabel(d), FMT.pct2(w), FMT.pct2(cmap[d]), (w - cmap[d]).toFixed(2)]));
  }

  // ---- SQUEEZE: three small multiples, each with its own single axis
  const Q = S.squeeze;
  Q.panels.forEach((p) => {
    const box = document.createElement("div");
    box.className = "panel";
    const h = document.createElement("h3"); h.textContent = p.title;
    const last = p.rows[p.rows.length - 1];
    const now = document.createElement("div"); now.className = "now";
    now.textContent = `${FMT[p.fmt](last[1])} · ${p.key === "apr" ? quarterLabel(last[0]) : monthLabel(last[0])}`;
    const c = document.createElement("div"); c.className = "chart short";
    c.setAttribute("role", "img"); c.setAttribute("aria-label", `${p.title} over time`);
    box.append(h, now, c);
    $("#squeeze").append(box);
    viz.lineChart(c, {
      fmt: p.fmt, scale: p.key !== "sav", rightPad: 16, endLabels: false, top: 34,
      dateLabel: p.key === "apr" ? quarterLabel : monthLabel,
      notes: p.note ? [{ ...p.note, series: "x", position: p.key === "sav" ? "right" : "left" }] : [],
      series: [{ key: "x", name: p.title, color: "accent", rows: p.rows, area: true }],
    });
  });
  {
    const [apr, rev, sav] = Q.panels.map((p) => Object.fromEntries(p.rows));
    const all = [...new Set(Q.panels.flatMap((p) => months(p.rows)))].sort();
    viz.table($("#t-squeeze"), ["Month", "Card APR", "Revolving credit ($T)", "Saving rate"],
      all.map((d) => [monthLabel(d), apr[d] != null ? FMT.pct2(apr[d]) : "", rev[d] != null ? rev[d].toFixed(3) : "", sav[d] != null ? FMT.pct1(sav[d]) : ""]));
  }

  // ---- DELINQUENCY
  const Dq = S.delinq;
  viz.lineChart($("#c-delinq"), {
    fmt: "pct2", bands: Dq.recessions.map(([start, end]) => ({ start, end })), yMin: 0, rightPad: 70,
    dateLabel: quarterLabel, notes: [{ ...Dq.note, series: "dq", position: "right" }],
    series: [{ key: "dq", name: "Delinquency rate", short: "", color: "accent", rows: Dq.rows, area: true,
      ref: { value: Dq.avg2019, label: `2019 avg ${FMT.pct2(Dq.avg2019)}` } }],
  });
  Dq.stats.forEach((s) => {
    const el = document.createElement("div"); el.className = "stat";
    const v = document.createElement("div"); v.className = "v"; v.textContent = s.value;
    const l = document.createElement("div"); l.className = "l"; l.textContent = s.label;
    const w = document.createElement("div"); w.className = "w"; w.textContent = s.when;
    el.append(v, l, w);
    $("#delinq-stats").append(el);
  });
  viz.table($("#t-delinq"), ["Quarter", "Delinquency rate"], Dq.rows.map(([d, v]) => [quarterLabel(d), FMT.pct2(v)]));

  // ---- SENTIMENT
  const Se = S.sentiment;
  viz.lineChart($("#c-sentiment"), {
    fmt: "num1", bands: Se.recessions.map(([start, end]) => ({ start, end })), rightPad: 60, yMin: 40,
    notes: [{ ...Se.note, series: "um", position: "left" }],
    series: [{ key: "um", name: "Consumer sentiment", short: "", color: "accent", rows: Se.rows }],
  });
  viz.table($("#t-sentiment"), ["Month", "Index"], Se.rows.map(([d, v]) => [monthLabel(d), v.toFixed(1)]));

  // ---- SANKEY
  const K = S.sankey;
  // color every spending node by how its change compares with inflation
  const VS = {};
  K.rows.forEach((r) => { VS[r.name] = r.vs; r.children.forEach((c) => { VS[c.name] = c.vs; }); });
  const hasInfl = !!K.inflation;
  const vsColor = (v) => (v == null ? viz.theme().muted : viz.deltaColor(v, false, K.vs_full));
  const keyCaption = hasInfl ? `vs ${K.inflation.value}% inflation:` : `Change vs ${K.prev}:`;
  const keyLabels = hasInfl ? ["Slower", "Faster"] : ["Better", "Worse"];
  const spendBadge = (r) => hasInfl && r.vs != null
    ? viz.deltaBadge(r.vs, { goodUp: false, full: K.vs_full, arrowValue: r.change, text: `${Math.abs(r.change).toFixed(1)}%`,
        title: `${r.change >= 0 ? "Up" : "Down"} ${Math.abs(r.change).toFixed(1)}% vs ${K.prev}: ${Math.abs(r.vs).toFixed(1)} points ${r.vs > 0 ? "faster" : "slower"} than prices` })
    : viz.deltaBadge(r.change, { goodUp: K.good_up, full: K.full, text: `${Math.abs(r.change).toFixed(1)}%`, when: `vs ${K.prev}` });
  viz.deltaKey($("#key-sankey"), keyCaption, keyLabels);
  viz.sankey($("#c-sankey"), { ...K, colorOf: hasInfl ? (name) => (name in VS ? vsColor(VS[name]) : null) : null });

  // desktop: where the year-over-year increase went
  if (K.delta_flow) {
    viz.sankey($("#c-delta"), { ...K.delta_flow, valuePrefix: "+", shareLabel: "of the increase",
      colorOf: (name) => (name in VS ? vsColor(VS[name]) : null) });
  }

  // phones: scroll-driven vertical flow (overview, then one cluster per step)
  if (K.flow) {
    viz.deltaKey($("#key-flow"), keyCaption, keyLabels);
    const story = viz.flowStory($("#flow-svg"), {
      total: K.total, prevTotal: K.prev_total, year: K.year, prevYear: K.prev,
      groups: K.flow.groups, steps: K.flow.steps,
      colorOf: (n) => vsColor(n.vs), fmt: (v) => `$${(v / 1000).toFixed(1)}K`,
      fmtDelta: (v) => `${v >= 0 ? "+" : "−"}$${Math.abs(Math.round(v)).toLocaleString("en-US")}`,
      label: `Average household spending of ${FMT.usd0(K.total)} flowing into categories`,
    });
    const stepsEl = $("#flow-steps");
    K.flow.steps.forEach((st, i) => {
      const wrap = document.createElement("div"); wrap.className = "fs-step"; wrap.dataset.i = i;
      const card = document.createElement("div"); card.className = "fs-card";
      const prog = document.createElement("div"); prog.className = "fs-progress";
      prog.textContent = `${i + 1} / ${K.flow.steps.length}${i === 0 ? " · KEEP SCROLLING" : ""}`;
      const h = document.createElement("h4"); h.textContent = st.title;
      const p = document.createElement("p"); p.textContent = st.text;
      card.append(prog, h, p);
      if (st.group != null) {
        const ul = document.createElement("ul"); ul.className = "fs-kids";
        K.flow.groups[st.group].children.forEach((c) => {
          const li = document.createElement("li");
          const b = document.createElement("b"); b.textContent = FMT.usd0(c.value);
          const nm = document.createElement("span"); nm.textContent = c.name;
          li.append(nm, b, c.change == null ? document.createElement("span") : spendBadge(c));
          ul.append(li);
        });
        card.append(ul);
      }
      wrap.append(card);
      stepsEl.append(wrap);
    });
    const io = new IntersectionObserver((items) => {
      items.forEach((it) => {
        const i = +it.target.dataset.i;
        if (it.isIntersecting) story.setStep(i);
        // scrolled back up past the first card: rewind to last year's total
        else if (i === 0 && it.boundingClientRect.top > window.innerHeight * 0.6) story.setStep(-1);
      });
    }, { rootMargin: "-62% 0px -30% 0px" });
    stepsEl.querySelectorAll(".fs-step").forEach((w) => io.observe(w));
    document.addEventListener("themechange", () => story.rebuild());
  }
  // budget bars: ranked list, tap a group to see what's inside it
  viz.deltaKey($("#key-budget"), keyCaption, keyLabels);
  const maxShare = Math.max(...K.rows.map((r) => r.share));
  const budgetRow = (r, tag, scale) => {
    const row = document.createElement(tag);
    row.className = "b-row";
    if (tag === "button") row.type = "button";
    const name = document.createElement("span"); name.className = "b-name";
    if (tag === "button") { const c = document.createElement("span"); c.className = "chev"; c.textContent = "›"; name.append(c); }
    name.append(r.name);
    const amt = document.createElement("span"); amt.className = "b-amt"; amt.textContent = FMT.usd0(r.value);
    const badge = r.change == null ? document.createElement("span") : spendBadge(r);
    const track = document.createElement("span"); track.className = "b-track";
    const bar = document.createElement("span"); bar.className = "b-bar"; bar.style.width = `${(r.share / scale) * 82}%`;
    const share = document.createElement("span"); share.className = "b-share"; share.textContent = `${r.share.toFixed(1)}%`;
    track.append(bar, share);
    row.append(name, amt, badge, track);
    return row;
  };
  K.rows.forEach((r, i) => {
    const li = document.createElement("li");
    const hasKids = r.children.length > 0;
    const row = budgetRow(r, hasKids ? "button" : "div", maxShare);
    li.append(row);
    if (hasKids) {
      const kids = document.createElement("ul");
      kids.className = "b-kids"; kids.hidden = true; kids.id = `b-kids-${i}`;
      r.children.forEach((c) => { const kl = document.createElement("li"); kl.append(budgetRow(c, "div", maxShare)); kids.append(kl); });
      row.setAttribute("aria-expanded", "false");
      row.setAttribute("aria-controls", kids.id);
      row.addEventListener("click", () => {
        const open = row.getAttribute("aria-expanded") !== "true";
        row.setAttribute("aria-expanded", String(open));
        kids.hidden = !open;
      });
      li.append(kids);
    }
    $("#budget").append(li);
  });
  K.notes.forEach((n) => { const li = document.createElement("li"); li.textContent = n; $("#sankey-notes").append(li); });
  viz.table($("#t-sankey"), ["From", "To", `${K.year} ($)`, "Share of total"],
    K.links.slice().reverse().map((l) => [l.source, l.target, FMT.usd0(l.value), `${((l.value / K.total) * 100).toFixed(1)}%`]));

  // ---- METHOD: series index
  D.series_index.forEach((s) => {
    const row = document.createElement("div");
    const code = document.createElement("code"); code.textContent = s.id;
    const name = document.createElement("span"); name.textContent = s.name;
    row.append(code, name);
    $("#series-index").append(row);
  });
})();
