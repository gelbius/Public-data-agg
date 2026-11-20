/* Tech valuations & deals: binds the computed data (embedded as JSON) to the page. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const S = D.sections;
  const { dayLabel, monthLabel } = viz;
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  // ---- formatting
  const money = (v) => v == null ? "—" : v < 0 ? `−${money(-v)}` : Math.abs(v) >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : Math.abs(v) >= 1e9 ? `$${(v / 1e9).toFixed(v >= 1e11 ? 0 : 1)}B` : `$${(v / 1e6).toFixed(0)}M`;
  const mult = (v) => v == null ? "n/m" : v >= 100 ? `${v.toFixed(0)}×` : `${v.toFixed(1)}×`;
  const pct = (v) => v == null ? "—" : `${v.toFixed(0)}%`;
  const signed = (v, d = 0) => v == null ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d)}%`;
  const VALUE_FULL = 50; // a ±50% move earns the strongest color
  const DAY_FULL = 5;    // a ±5% day earns the strongest color
  const mean = (a) => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
  const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

  viz.initThemeToggle($("#theme-btn"));
  $("#m-asof").textContent = dayLabel(D.as_of);
  document.querySelectorAll("[data-k]").forEach((n) => { const [s, k] = n.dataset.k.split("."); n.textContent = S[s][k] || ""; });

  // ---- source footers: latest observation + next update
  document.querySelectorAll("[data-src]").forEach((node) => {
    const src = S[node.dataset.src].source;
    const a = el("span", "src"); a.innerHTML = "<b>SOURCE</b> "; a.append(src.label);
    const b = el("span", "", `Latest observation ${src.latest_text} · Next update ${src.next_text}`);
    node.append(a, b);
  });

  const badge = (v, full, label, digits = 0) => v == null ? el("span", "", "—")
    : viz.deltaBadge(v, { goodUp: true, full, text: `${Math.abs(v).toFixed(digits)}%`, title: `${label}: ${v >= 0 ? "+" : ""}${v.toFixed(1)}%` });

  // ---- sector multiples over time (line charts; one per metric, switched by tabs)
  const T = S.summary.trend;
  const COLORS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"];
  const SHORT = { "AI platforms": "AI platforms", "AI infrastructure & chips": "AI infra", "Semiconductors & equipment": "Semis",
    "Hardware": "Hardware", "Software & security": "Software", "Consumer subscription": "Cons. sub", "Consumer marketplaces & services": "Marketplaces" };
  function trendChart(metric) {
    const names = Object.keys(T[metric]);
    const narrow = window.innerWidth < 640;
    viz.lineChart($(`#c-${metric}`), {
      fmt: "mult1", legendEl: $(`#lg-${metric}`), top: 24, rightPad: 120,
      series: names.map((n, i) => n === "All companies"
        ? { key: "all", name: n, short: "All", legend: narrow ? "All" : n, color: "all", rows: T[metric][n], dashed: true }
        : { key: `s${i}`, name: n, short: SHORT[n] || n, legend: narrow ? (SHORT[n] || n) : n, color: COLORS[i % COLORS.length], rows: T[metric][n] }),
    });
  }
  trendChart("ev_rev");
  trendChart("ev_ebitda");
  document.querySelectorAll("#metric-tabs button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#metric-tabs button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.querySelectorAll(".trend-pane").forEach((p) => { p.hidden = p.id !== `pane-${b.dataset.metric}`; });
  }));

  // ---- generic sortable table, with optional Average / Median rows for the rows currently shown
  function table(host, cols, rows, initialSort) {
    let sortKey = initialSort.key, dir = initialSort.dir;
    const thead = host.createTHead(), tbody = host.createTBody(), tfoot = host.createTFoot();
    function render() {
      thead.textContent = ""; tbody.textContent = ""; tfoot.textContent = "";
      const tr = thead.insertRow();
      cols.forEach((c) => {
        const th = el("th", c.cls || "");
        if (c.title) th.title = c.title;
        if (c.sort) {
          const b = el("button", "th-sort", c.label);
          b.type = "button";
          b.setAttribute("aria-sort", sortKey === c.key ? (dir < 0 ? "descending" : "ascending") : "none");
          if (sortKey === c.key) b.append(el("span", "th-dir", dir < 0 ? " ▼" : " ▲"));
          b.addEventListener("click", () => { dir = sortKey === c.key ? -dir : -1; sortKey = c.key; render(); });
          th.append(b);
        } else th.textContent = c.label;
        tr.append(th);
      });
      const col = cols.find((c) => c.key === sortKey);
      const shown = rows.filter((r) => !host._filter || host._filter(r));
      const sorted = shown.sort((a, b) => {
        const va = col.sort(a), vb = col.sort(b);
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
      });
      sorted.forEach((r) => {
        const row = tbody.insertRow();
        cols.forEach((c) => { const td = row.insertCell(); if (c.cls) td.className = c.cls; const v = c.cell(r); td.append(v instanceof Node ? v : document.createTextNode(v)); });
      });
      if (!sorted.length) {
        const row = tbody.insertRow(); const td = row.insertCell(); td.colSpan = cols.length; td.className = "left empty"; td.textContent = "No rows match these filters.";
      }
      if (cols.some((c) => c.agg) && sorted.length > 1) {
        [["Average", mean], ["Median", median]].forEach(([label, fn]) => {
          const row = tfoot.insertRow();
          cols.forEach((c, i) => {
            const td = row.insertCell(); if (c.cls) td.className = c.cls;
            if (i === 0) { td.textContent = label; td.classList.add("agg-label"); return; }
            if (!c.agg) return;
            const vals = sorted.map(c.agg).filter((v) => v != null && isFinite(v));
            const v = vals.length ? fn(vals) : null;
            td.textContent = v == null ? "—" : (c.aggFmt || ((x) => x))(v);
            if (vals.length && vals.length < sorted.length) td.title = `Based on ${vals.length} of ${sorted.length} rows with a value`;
          });
        });
      }
      if (host._after) host._after(sorted);
    }
    host._render = render;
    render();
  }
  function chips(host, options, targets, test) {
    ["All", ...options].forEach((o) => {
      const b = el("button", "chip-btn", o); b.type = "button";
      b.setAttribute("aria-pressed", String(o === "All"));
      b.addEventListener("click", () => {
        host.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x.textContent === o)));
        targets.forEach((t) => { t._filter = o === "All" ? null : (r) => test(r, o); t._render(); });
      });
      host.append(b);
    });
  }

  // ---- sector table under the trend charts
  const withMark = (text, on) => { const s = el("span", "", text); if (on) s.append(el("sup", "fn", "*")); return s; };
  table($("#sector-table"), [
    { key: "name", label: "Sector", cls: "sticky left", sort: (r) => r.name, cell: (r) => { const s = el("span", "co"); s.append(el("b", "", r.name), el("small", "", ` ${r.n}`)); return s; } },
    { key: "evrev", label: "EV/Rev", sort: (r) => r.ev_rev.now, cell: (r) => mult(r.ev_rev.now) },
    { key: "evrev12", label: "A year ago", sort: (r) => r.ev_rev["12m_ago"], cell: (r) => mult(r.ev_rev["12m_ago"]) },
    { key: "evebitda", label: "EV/EBITDA", sort: (r) => r.ev_ebitda.now, cell: (r) => mult(r.ev_ebitda.now) },
    { key: "d1", label: "Value 1d", sort: (r) => r.value_chg["1d"], cell: (r) => badge(r.value_chg["1d"], DAY_FULL, "1-day value change", 1) },
    { key: "d6", label: "Value 6m", sort: (r) => r.value_chg["6m"], cell: (r) => badge(r.value_chg["6m"], VALUE_FULL, "6-month value change") },
    { key: "d12", label: "Value 12m", sort: (r) => r.value_chg["12m"], cell: (r) => badge(r.value_chg["12m"], VALUE_FULL, "12-month value change") },
  ], S.summary.categories, { key: "evrev", dir: -1 });

  // ---- companies
  const C = S.companies.rows;
  const MULT_FULL = 50; // a ±50% change in the multiple earns the deepest tint
  const multDelta = (r, k) => {
    const v = r.mult_chg[k].ev_rev, then = r.hist[k] && r.hist[k].ev_rev;
    if (v == null) return "—";
    const pctChg = then ? (v / then) * 100 : 0, depth = Math.min(1, Math.abs(pctChg) / MULT_FULL);
    const p = el("span", `pill ${v >= 0 ? "mx-up" : "mx-down"}`, `${v >= 0 ? "▲" : "▼"} ${Math.abs(v).toFixed(1)}×`);
    p.style.background = `color-mix(in srgb, var(${v >= 0 ? "--mx-up" : "--mx-down"}) ${Math.round(8 + 34 * depth)}%, transparent)`;
    p.title = `EV/revenue ${v >= 0 ? "expanded" : "compressed"} ${Math.abs(pctChg).toFixed(0)}% (from ${mult(then)} to ${mult(r.ev_rev)})`;
    return p;
  };
  const nameCell = (r) => { const s = el("span", "co"); s.append(el("b", "", r.name), el("small", "", ` ${r.ticker}`)); return s; };
  const x1 = (v) => `${v.toFixed(1)}×`;
  table($("#comp-table"), [
    { key: "name", label: "Company", cls: "sticky", sort: (r) => r.name.toLowerCase(), cell: nameCell },
    { key: "d1", label: "Today", title: "Change in share price on the latest trading day", sort: (r) => r.chg["1d"], cell: (r) => badge(r.chg["1d"], DAY_FULL, "1-day change", 1), agg: (r) => r.chg["1d"], aggFmt: (v) => signed(v, 1) },
    { key: "cat", label: "Category", cls: "left", sort: (r) => r.category, cell: (r) => r.category },
    { key: "mcap", label: "Market cap", sort: (r) => r.market_cap, cell: (r) => money(r.market_cap), agg: (r) => r.market_cap, aggFmt: money },
    { key: "ev", label: "EV", sort: (r) => r.ev, cell: (r) => money(r.ev), agg: (r) => r.ev, aggFmt: money },
    { key: "evrev", label: "EV/Rev", sort: (r) => r.ev_rev, cell: (r) => mult(r.ev_rev), agg: (r) => r.ev_rev, aggFmt: x1 },
    { key: "evebitda", label: "EV/EBITDA", sort: (r) => r.ev_ebitda, cell: (r) => withMark(mult(r.ev_ebitda), r.da_partial && r.ev_ebitda), agg: (r) => r.ev_ebitda, aggFmt: x1 },
    { key: "pe", label: "P/E", sort: (r) => r.pe, cell: (r) => mult(r.pe), agg: (r) => r.pe, aggFmt: x1 },
    { key: "growth", label: "Rev growth", sort: (r) => r.growth, cell: (r) => r.growth == null ? "—" : `${r.growth >= 0 ? "+" : ""}${r.growth.toFixed(0)}%`, agg: (r) => r.growth, aggFmt: (v) => signed(v) },
    { key: "margin", label: "EBITDA margin", sort: (r) => r.margin, cell: (r) => pct(r.margin), agg: (r) => r.margin, aggFmt: pct },
    { key: "c6", label: "Value 6m", sort: (r) => r.chg["6m"], cell: (r) => badge(r.chg["6m"], VALUE_FULL, "6-month change"), agg: (r) => r.chg["6m"], aggFmt: (v) => signed(v) },
    { key: "c12", label: "Value 12m", sort: (r) => r.chg["12m"], cell: (r) => badge(r.chg["12m"], VALUE_FULL, "12-month change"), agg: (r) => r.chg["12m"], aggFmt: (v) => signed(v) },
    { key: "m6", label: "EV/Rev Δ 6m", sort: (r) => r.mult_chg["6m"].ev_rev, cell: (r) => multDelta(r, "6m") },
    { key: "m12", label: "EV/Rev Δ 12m", sort: (r) => r.mult_chg["12m"].ev_rev, cell: (r) => multDelta(r, "12m") },
  ], C, { key: "mcap", dir: -1 });
  chips($("#cat-filters"), S.summary.categories.map((c) => c.name), [$("#comp-table")], (r, o) => r.category === o);

  // ---- deals: one list, filtered by date range, sector and type
  const R = S.deals.rows;
  const CONSUMER = new Set(S.summary.categories.map((c) => c.name).filter((n) => n.startsWith("Consumer")));
  const dealCell = (r) => {
    const s = el("span", "co");
    s.append(el("b", "", r.target), el("small", "", ` ← ${r.acquirer}`));
    if (CONSUMER.has(r.segment)) s.append(el("span", "tag", r.segment));
    return s;
  };
  const isRound = (r) => r.type === "Venture round";
  const dealValue = (r) => {
    if (r.value == null) return "Undisclosed";
    const v = isRound(r) ? money(r.value) : r.ev != null ? money(r.ev) + (r.ev_is_derived ? "†" : "") : money(r.value);
    return r.value_note ? `${v}+` : r.approx ? `~${v}` : v;
  };
  const link = (r) => { const a = el("a", "src-link", "Source ↗"); a.href = r.source; a.target = "_blank"; a.rel = "noopener"; return a; };
  const fundLink = (r) => { const a = el("a", "src-link", "funding ↗"); a.href = r.funding.source; a.target = "_blank"; a.rel = "noopener"; return a; };
  const announced = (r) => r.date_precision === "month" ? monthLabel(r.date) : dayLabel(r.date);
  const dEvRev = (r) => r.ev_rev ? mult(r.ev_rev) : (r.target_revenue ? "n/m" : "—");
  const dEvEbitda = (r) => r.ev_ebitda ? withMark(mult(r.ev_ebitda), r.da_partial) : (r.target_revenue ? "n/m" : "—");
  const dMargin = (r) => r.target_revenue ? pct(r.target_margin) : "—";
  const notes = (r) => {
    const s = el("span", "");
    s.append(r.note || "");
    if (r.funding_note) { s.append(" ", el("b", "", r.funding_note), " "); if (r.funding && r.funding.source) s.append(fundLink(r)); }
    return s;
  };
  const dealCols = [
    { key: "date", label: "Announced", sort: (r) => r.date, cell: announced },
    { key: "deal", label: "Target ← buyer", cls: "sticky", sort: (r) => r.target.toLowerCase(), cell: dealCell },
    { key: "value", label: "Value", title: "Enterprise value for acquisitions; post-money valuation for venture rounds", sort: (r) => r.ev ?? r.value, cell: dealValue },
    { key: "raised", label: "Raised", title: "Amount raised in the round (venture rounds only)", sort: (r) => r.raised, cell: (r) => r.raised ? money(r.raised) : "—" },
    { key: "evrev", label: "EV/Rev", sort: (r) => r.ev_rev, cell: dEvRev, agg: (r) => r.ev_rev, aggFmt: x1 },
    { key: "evebitda", label: "EV/EBITDA", sort: (r) => r.ev_ebitda, cell: dEvEbitda, agg: (r) => r.ev_ebitda, aggFmt: x1 },
    { key: "rev", label: "Target revenue", sort: (r) => r.target_revenue, cell: (r) => money(r.target_revenue) },
    { key: "ebitda", label: "Target EBITDA", sort: (r) => r.target_ebitda, cell: (r) => r.target_revenue ? money(r.target_ebitda) : "—" },
    { key: "margin", label: "EBITDA margin", sort: (r) => r.target_margin, cell: dMargin, agg: (r) => r.target_revenue ? r.target_margin : null, aggFmt: pct },
    { key: "type", label: "Type", cls: "left", sort: (r) => r.type, cell: (r) => r.type },
    { key: "seg", label: "Sector", cls: "left", sort: (r) => r.segment, cell: (r) => r.segment },
    { key: "note", label: "Notes", cls: "left note", sort: null, cell: notes },
    { key: "src", label: "Source", sort: null, cell: link },
  ];
  // phone view: one card per deal, key numbers in a grid (no sideways scrolling)
  function dealCards(host, rows) {
    function render() {
      host.textContent = "";
      const shown = rows.filter((r) => !host._filter || host._filter(r));
      const m = shown.map((r) => r.ev_rev).filter((v) => v);
      if (m.length > 1) host.append(el("p", "dc-summary", `${shown.length} deals · EV/revenue average ${x1(mean(m))}, median ${x1(median(m))} (${m.length} with financials)`));
      if (!shown.length) host.append(el("p", "dc-summary", "No deals match these filters."));
      shown.forEach((r) => {
        const card = el("article", "dcard");
        const top = el("div", "dc-top"); top.append(el("span", "", announced(r)), el("span", "dc-type", r.type));
        const name = el("div", "dc-name"); name.append(dealCell(r));
        const stats = el("dl", "dc-stats");
        const stat = (label, v) => { const d = el("div"); d.append(el("dt", "", label)); const dd = el("dd"); dd.append(v instanceof Node ? v : document.createTextNode(v)); d.append(dd); stats.append(d); };
        stat(isRound(r) ? "Valuation" : "Value", dealValue(r));
        if (isRound(r) && r.raised) stat("Raised", money(r.raised));
        if (r.target_revenue) {
          stat("EV / revenue", dEvRev(r)); stat("EV / EBITDA", dEvEbitda(r));
          stat("Revenue (TTM)", money(r.target_revenue)); stat("EBITDA", money(r.target_ebitda)); stat("EBITDA margin", dMargin(r));
        }
        card.append(top, name, stats);
        if (!r.target_revenue && !isRound(r)) card.append(el("p", "dc-nofin", "Target financials not published (private company)."));
        if (r.note || r.funding_note) { const p = el("p", "dc-note"); p.append(notes(r)); card.append(p); }
        card.append(link(r));
        host.append(card);
      });
    }
    host._render = render;
    render();
  }
  const dealTable = $("#deal-table"), cards = $("#deal-cards");
  table(dealTable, dealCols, R, { key: "date", dir: -1 });
  dealCards(cards, R);
  (function dealFilters() {
    const today = D.as_of;
    const back = (days) => { const d = new Date(today + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() - days); return d.toISOString().slice(0, 10); };
    const ranges = [["Last 6 months", S.deals.window_start], ["Last 12 months", back(365)], ["Last 3 years", back(3 * 365)], ["All dates", "0000"]];
    const sectors = [...new Set(R.map((r) => r.segment))].sort();
    const types = [...new Set(R.map((r) => r.type))].sort();
    const host = $("#deal-filters");
    const mk = (label, opts) => {
      const wrap = el("label", "sel"); wrap.append(el("span", "", label));
      const s = el("select"); opts.forEach(([t, v]) => { const o = el("option", "", t); o.value = v; s.append(o); });
      wrap.append(s); host.append(wrap); return s;
    };
    const sDate = mk("Announced", ranges.map(([t, v]) => [t, v]));
    const sSector = mk("Sector", [["All sectors", ""], ...sectors.map((x) => [x, x])]);
    const sType = mk("Type", [["All types", ""], ...types.map((x) => [x, x])]);
    const apply = () => {
      const f = (r) => r.date >= sDate.value && (!sSector.value || r.segment === sSector.value) && (!sType.value || r.type === sType.value);
      [dealTable, cards].forEach((t) => { t._filter = f; t._render(); });
    };
    [sDate, sSector, sType].forEach((s) => s.addEventListener("change", apply));
    apply();
  })();

  // ---- what investors are saying
  S.quotes.rows.forEach((q) => {
    const fig = el("figure", "quote");
    const bq = el("blockquote", "", `“${q.quote}”`);
    const cap = el("figcaption");
    cap.append(el("b", "", q.who), el("span", "", ` · ${q.role}`));
    const meta = el("div", "q-meta");
    meta.append(el("span", "", `${dayLabel(q.date)} · ${q.outlet} `));
    const a = el("a", "src-link", "Source ↗"); a.href = q.source; a.target = "_blank"; a.rel = "noopener"; meta.append(a);
    fig.append(bq, cap);
    if (q.context) fig.append(el("p", "q-context", q.context));
    fig.append(meta);
    $("#quotes").append(fig);
  });

  // ---- private valuations
  table($("#priv-table"), [
    { key: "name", label: "Company", cls: "sticky", sort: (r) => r.name.toLowerCase(), cell: (r) => { const s = el("span", "co"); s.append(el("b", "", r.name)); return s; } },
    { key: "val", label: "Valuation", sort: (r) => r.valuation, cell: (r) => money(r.valuation) },
    { key: "raised", label: "Raised", sort: (r) => r.raised, cell: (r) => r.raised ? money(r.raised) : "—" },
    { key: "round", label: "Event", cls: "left", sort: (r) => r.round, cell: (r) => r.round },
    { key: "date", label: "Date", sort: (r) => r.date, cell: (r) => dayLabel(r.date) },
    { key: "note", label: "Notes", cls: "left note", sort: null, cell: (r) => r.note || "" },
    { key: "src", label: "Source", sort: null, cell: link },
  ], S.private.rows, { key: "val", dir: -1 });

  // ---- method
  [
    `Prices and market caps are from the close on ${dayLabel(D.as_of)} and refresh every weekday after the market close. "Today" compares with the close on ${dayLabel(D.dates.prev)}; "6 months" and "12 months" with ${dayLabel(D.dates["6m"])} and ${dayLabel(D.dates["12m"])} (or the trading day before; split-adjusted).`,
    "All multiples use the trailing 12 months (TTM): the latest four reported quarters, from each company's SEC filings. Forward estimates aren't used (they come from paid analyst data).",
    "Sector lines are the median company in each sector at each month-end, using that month's closing price and the results reported by then. Medians, so one outlier can't swing a sector.",
    "EBITDA = reported operating income + depreciation and amortization (GAAP; not the adjusted figures companies promote, so stock-based compensation and one-off charges are included).",
    "EV = market cap + total debt − cash and short-term investments, from the latest balance sheet. Past multiples use the financials that had been reported by then (results assumed public about 35 days after a quarter ends) and today's share count.",
    `Universe: ${C.length} US-listed companies in ${S.companies.n_categories} sectors. Foreign filers (e.g. TSMC, Arm, Spotify) are excluded because their reports use different accounting formats. Average and Median rows cover the rows currently shown and skip blanks and n/m.`,
    "Deals: a curated list of notable transactions from SEC filings, company announcements and press coverage (each row links its source); older consumer deals are kept as precedents. For acquired private companies, notes show the funding raised before the deal and key investors, from company announcements and funding trackers (which sometimes disagree).",
    "Investor quotes are copied word for word from the linked article, which may itself quote a Substack, LinkedIn or X post.",
    "Not investment advice.",
  ].forEach((t) => $("#method").append(el("li", "", t)));
})();
