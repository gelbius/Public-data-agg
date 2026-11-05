/* Shared chart helpers for every dashboard (built on Apache ECharts).
   Conventions (see README): one y-axis per chart, 2px lines, hairline grid,
   text in ink colors (never the series color), crosshair tooltip on line charts,
   and a data table under every chart. Colors come from CSS custom properties so
   light/dark mode is a single source of truth. */
(function () {
  "use strict";

  const charts = []; // {el, render} — re-rendered on theme change / resize

  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthLabel = (d) => `${MONTHS[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}`;
  const dayLabel = (d) => `${MONTHS[+d.slice(5, 7) - 1]} ${+d.slice(8, 10)}, ${d.slice(0, 4)}`;
  const quarterLabel = (d) => `Q${Math.floor((+d.slice(5, 7) - 1) / 3) + 1} ${d.slice(0, 4)}`;

  const FMT = {
    pct1: (v) => `${v.toFixed(1)}%`,
    pct2: (v) => `${v.toFixed(2)}%`,
    num1: (v) => v.toFixed(1),
    usd: (v) => `$${v.toFixed(2)}`,
    usd0: (v) => `$${Math.round(v).toLocaleString("en-US")}`,
    tn: (v) => `$${v.toFixed(2)}T`,
  };
  const AXIS_FMT = {
    pct1: (v) => `${v}%`, pct2: (v) => `${v}%`, num1: (v) => `${v}`, usd: (v) => `$${v}`, tn: (v) => `$${v.toFixed(1)}T`,
  };

  function theme() {
    return {
      ink: cssVar("--ink"), soft: cssVar("--ink-soft"), dim: cssVar("--ink-dim"),
      panel: cssVar("--panel"), panel2: cssVar("--panel-2"), line: cssVar("--line"), line2: cssVar("--line-2"),
      grid: cssVar("--chart-grid"), axis: cssVar("--chart-axis"), muted: cssVar("--chart-muted"),
      band: cssVar("--band"), band2: cssVar("--band-2"), good: cssVar("--good"), bad: cssVar("--bad"),
      goodWash: cssVar("--good-wash"), badWash: cssVar("--bad-wash"), accent: cssVar("--accent"),
      mono: cssVar("--mono"), sans: cssVar("--sans"),
      series: (key) => cssVar(`--s-${key}`) || cssVar("--s-accent"),
    };
  }

  /* ---------- shared axis + tooltip scaffolding */
  function baseOption(t, yFmt, opts = {}) {
    const narrow = window.innerWidth < 640;
    return {
      animationDuration: 700,
      animationEasing: "cubicOut",
      textStyle: { fontFamily: t.sans },
      grid: { left: 8, right: opts.rightPad ?? (narrow ? 64 : 150), top: opts.top ?? 28, bottom: 8, containLabel: true },
      xAxis: {
        type: "time",
        min: opts.xMin, max: opts.xMax,
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 11, hideOverlap: true },
      },
      yAxis: {
        type: "value", scale: opts.scale ?? false, min: opts.yMin, max: opts.yMax,
        splitNumber: narrow ? 4 : 5,
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: t.grid, width: 1 } },
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 11, formatter: AXIS_FMT[yFmt] || ((v) => v) },
      },
      tooltip: {
        trigger: "axis",
        className: "viz-tip",
        backgroundColor: t.panel, borderColor: t.line2, borderWidth: 1, padding: [10, 12],
        textStyle: { color: t.ink },
        extraCssText: "box-shadow:0 12px 30px -18px rgba(0,0,0,.45);border-radius:4px;",
        axisPointer: { type: "line", lineStyle: { color: t.line2, width: 1, type: "solid" }, label: { show: false } },
        confine: true,
      },
    };
  }

  function tipHtml(dateText, rows, note) {
    let h = `<div class="t-date">${esc(dateText)}</div>`;
    for (const r of rows) {
      h += `<div class="t-row"><i class="t-key" style="background:${r.color}"></i><b>${esc(r.value)}</b><span>${esc(r.name)}</span></div>`;
    }
    if (note) h += `<div class="t-note">${esc(note)}</div>`;
    return h;
  }

  /* Bands (phases or recessions) as a markArea on an invisible helper series.
     labels: false | "full" (text inside each band; narrow bands get it above the plot)
           | "numbers" (1, 2, 3… for small screens, paired with an HTML key). */
  function bandSeries(t, bands, { labels = false, alternate = false } = {}) {
    const monthsBetween = (a, b) => (+b.slice(0, 4) - +a.slice(0, 4)) * 12 + (+b.slice(5, 7) - +a.slice(5, 7));
    const base = { color: t.dim, fontFamily: t.mono, fontSize: 10, lineHeight: 13 };
    const labelFor = (b, i) => {
      if (!labels || !b.label) return { show: false };
      if (labels === "numbers") return { ...base, show: true, position: "top", distance: 6, fontSize: 11, color: t.soft };
      if (monthsBetween(b.start, b.end) >= 4) {
        return { ...base, show: true, position: "insideTop", overflow: "break", width: 70, distance: 4 };
      }
      return { ...base, show: true, position: "top", distance: 4 }; // too thin to hold text: sit above the plot
    };
    return {
      type: "line", data: [], silent: true, tooltip: { show: false },
      markArea: {
        silent: true,
        data: bands.map((b, i) => [
          {
            xAxis: b.start,
            name: labels === "numbers" ? String(i + 1) : labels ? b.label || "" : "",
            itemStyle: { color: alternate && i % 2 ? t.band2 : t.band },
            label: labelFor(b, i),
          },
          { xAxis: b.end },
        ]),
      },
    };
  }

  function notePoint(t, note, color, position = "top") {
    return {
      coord: [note.date, note.value], value: note.text, symbol: "circle", symbolSize: 9,
      itemStyle: { color, borderColor: t.panel, borderWidth: 2 },
      label: {
        show: true, formatter: note.text, position, distance: 8, offset: note.offset || [0, 0],
        color: t.ink, fontSize: 11, fontFamily: t.sans, fontWeight: 500,
        backgroundColor: t.panel, borderColor: t.line2, borderWidth: 1, borderRadius: 2, padding: [3, 6],
      },
    };
  }

  /* ---------- line chart: one y-axis, any number of same-unit series */
  function lineChart(el, cfg) {
    // series the viewer has switched off (tappable legend); seeded from `hidden: true`
    const off = new Set(cfg.series.filter((s) => s.hidden).map((s) => s.name));
    const entry = register(el, () => {
      const t = theme();
      const fmt = FMT[cfg.fmt] || FMT.pct1;
      const opt = baseOption(t, cfg.fmt, cfg);
      const narrow = window.innerWidth < 640;
      const series = [];
      if (cfg.bands) {
        const mode = cfg.bandLabels ? (narrow ? "numbers" : "full") : false;
        series.push(bandSeries(t, cfg.bands, { labels: mode, alternate: cfg.alternate }));
      }
      for (const s of cfg.series) {
        const color = t.series(s.color);
        const notes = (cfg.notes || []).filter((n) => n.series === s.key);
        series.push({
          name: s.name, type: "line", data: s.rows, showSymbol: false, connectNulls: true,
          lineStyle: { width: 2, color, type: s.dashed ? [5, 3] : "solid", cap: "round", join: "round" },
          itemStyle: { color }, emphasis: { disabled: true },
          areaStyle: s.area ? { color, opacity: 0.1 } : undefined,
          endLabel: cfg.endLabels === false ? { show: false } : {
            show: true, color: t.ink, fontSize: 11, fontFamily: t.sans, distance: 8,
            formatter: (p) => { const nm = s.short ?? s.name; return narrow || !nm ? fmt(p.value[1]) : `${fmt(p.value[1])}  ${nm}`; },
          },
          labelLayout: { moveOverlap: "shiftY" },
          markPoint: notes.length ? { data: notes.map((n) => notePoint(t, n, color, n.position)), animation: false } : undefined,
          markLine: s.ref ? {
            silent: true, symbol: "none",
            lineStyle: { color: t.muted, type: [4, 4], width: 1 },
            label: { formatter: s.ref.label, color: t.dim, fontSize: 10, fontFamily: t.mono, position: "insideStartTop" },
            data: [{ yAxis: s.ref.value }],
          } : undefined,
        });
      }
      if (cfg.extraSeries) series.push(...cfg.extraSeries(t));
      opt.series = series;
      // a hidden legend component lets us switch series on/off and rescale the axis
      opt.legend = { show: false, data: cfg.series.map((s) => s.name),
        selected: Object.fromEntries(cfg.series.map((s) => [s.name, !off.has(s.name)])) };
      opt.tooltip.formatter = (ps) => {
        const shown = ps.filter((p) => p.seriesName && !p.seriesName.startsWith("_"));
        if (!shown.length) return "";
        const d = shown[0].value[0];
        const rows = shown.map((p) => ({ color: p.color, value: fmt(p.value[1]), name: p.seriesName }));
        const extra = cfg.tipExtra ? cfg.tipExtra(d, shown) : null;
        const band = (cfg.bands || []).find((b) => b.label && d >= b.start && d <= b.end);
        return tipHtml((cfg.dateLabel || monthLabel)(d), rows, extra || (band && cfg.bandLabels ? band.label : null));
      };
      return opt;
    });
    if (cfg.legendEl) toggleLegend(cfg.legendEl, cfg.series, off, entry);
    if (cfg.bandKeyEl && cfg.bands) {
      cfg.bands.forEach((b) => {
        const li = document.createElement("li");
        li.textContent = b.label;
        cfg.bandKeyEl.appendChild(li);
      });
    }
  }

  /* Legend whose entries are buttons: tap to show/hide a series (at least one stays on). */
  function toggleLegend(ul, seriesCfg, off, entry) {
    const t = theme();
    const anchor = ul.firstChild;
    seriesCfg.forEach((s) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lg-btn";
      const key = document.createElement("i");
      key.className = "key" + (s.dashed ? " dashed" : "");
      key.style.color = `var(--s-${s.color})`;
      btn.append(key, s.legend || s.name);
      const sync = () => btn.setAttribute("aria-pressed", String(!off.has(s.name)));
      btn.addEventListener("click", () => {
        const turningOff = !off.has(s.name);
        if (turningOff && off.size >= seriesCfg.length - 1) return; // keep one line visible
        turningOff ? off.add(s.name) : off.delete(s.name);
        sync();
        if (entry.chart) entry.chart.dispatchAction({ type: turningOff ? "legendUnSelect" : "legendSelect", name: s.name });
      });
      sync();
      li.appendChild(btn);
      ul.insertBefore(li, anchor);
    });
    ul.classList.add("toggles");
  }

  /* ---------- Sankey */
  function sankey(el, cfg) {
    register(el, () => {
      const t = theme();
      const narrow = window.innerWidth < 640;
      const level = {};
      level[cfg.nodes[0].name] = 0;
      cfg.links.forEach((l) => { level[l.target] = (level[l.source] ?? 0) + 1; });
      const total = cfg.total;
      return {
        animationDuration: 700,
        textStyle: { fontFamily: t.sans },
        tooltip: {
          trigger: "item", className: "viz-tip", backgroundColor: t.panel, borderColor: t.line2, padding: [10, 12],
          textStyle: { color: t.ink },
          formatter: (p) => {
            const v = p.data.value ?? p.value;
            const name = p.dataType === "edge" ? `${p.data.source} → ${p.data.target}` : p.name;
            return tipHtml(name, [{ color: t.series("accent"), value: FMT.usd0(v), name: `${((v / total) * 100).toFixed(1)}% of spending` }]);
          },
        },
        series: [{
          type: "sankey", left: 4, right: narrow ? 130 : 290, top: 8, bottom: 8,
          nodeWidth: 10, nodeGap: narrow ? 8 : 11, nodeAlign: "left", draggable: false,
          layoutIterations: 0,
          emphasis: { focus: "adjacency" },
          data: cfg.nodes.map((n) => ({
            name: n.name,
            itemStyle: { color: level[n.name] === 0 ? t.ink : level[n.name] === 1 ? t.series("accent") : t.muted, borderWidth: 0 },
          })),
          links: cfg.links.map((l) => ({ ...l, lineStyle: { color: level[l.source] === 0 ? t.series("accent") : t.muted } })),
          lineStyle: { opacity: 0.2, curveness: 0.5 },
          label: {
            color: t.ink, fontSize: narrow ? 10 : 12, fontFamily: t.sans,
            formatter: (p) => `${p.name}  {v|${FMT.usd0(p.value)}}`,
            rich: { v: { color: t.dim, fontFamily: t.mono, fontSize: narrow ? 9 : 11 } },
          },
        }],
      };
    });
  }

  /* ---------- sparkline (plain SVG; tiles stay light) */
  function sparkline(svg, rows, colorVar) {
    const vals = rows.map((r) => r[1]);
    const min = Math.min(...vals), max = Math.max(...vals);
    const w = 200, h = 34, pad = 4;
    const x = (i) => pad + (i / (vals.length - 1)) * (w - pad * 2);
    const y = (v) => (max === min ? h / 2 : h - pad - ((v - min) / (max - min)) * (h - pad * 2));
    const d = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.innerHTML =
      `<path d="${d}" fill="none" stroke="var(--chart-muted)" stroke-width="1.5" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>` +
      `<circle cx="${x(vals.length - 1)}" cy="${y(vals[vals.length - 1])}" r="3.5" fill="var(--s-${colorVar})" stroke="var(--panel)" stroke-width="2"/>`;
  }

  /* ---------- data table twin */
  function table(details, columns, rows) {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const tbl = document.createElement("table");
    const thead = tbl.createTHead().insertRow();
    columns.forEach((c) => { const th = document.createElement("th"); th.textContent = c; thead.appendChild(th); });
    const body = tbl.createTBody();
    let filled = false;
    details.appendChild(wrap);
    wrap.appendChild(tbl);
    // fill lazily the first time it is opened (some tables have hundreds of rows)
    details.addEventListener("toggle", () => {
      if (!details.open || filled) return;
      filled = true;
      rows.slice().reverse().forEach((r) => {
        const tr = body.insertRow();
        r.forEach((cell) => { tr.insertCell().textContent = cell; });
      });
    });
  }

  /* ---------- lifecycle: theme toggle, resize, lazy init */
  function register(el, buildOption) {
    const entry = { el, buildOption, chart: null };
    charts.push(entry);
    const io = new IntersectionObserver((items) => {
      if (items.some((i) => i.isIntersecting)) { io.disconnect(); draw(entry); }
    }, { rootMargin: "200px" });
    io.observe(el);
    return entry;
  }
  function draw(entry) {
    if (entry.chart) entry.chart.dispose();
    entry.chart = echarts.init(entry.el, null, { renderer: "svg" });
    entry.chart.setOption(entry.buildOption());
  }
  function redrawAll() { charts.forEach((c) => c.chart && draw(c)); }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(redrawAll, 180);
  });

  function initThemeToggle(btn) {
    const root = document.documentElement;
    let saved = null;
    try { saved = localStorage.getItem("theme"); } catch (e) { /* storage blocked: fine */ }
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
    const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    const sync = () => {
      btn.setAttribute("aria-label", isDark() ? "Switch to light mode" : "Switch to dark mode");
      btn.textContent = isDark() ? "☀" : "☾";
    };
    btn.addEventListener("click", () => {
      root.dataset.theme = isDark() ? "light" : "dark";
      try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* ignore */ }
      sync();
      redrawAll();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { sync(); redrawAll(); });
    sync();
  }

  window.viz = { lineChart, sankey, sparkline, table, initThemeToggle, FMT, esc, monthLabel, dayLabel, quarterLabel, theme, cssVar };
})();
