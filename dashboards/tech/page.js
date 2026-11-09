/* Tech valuations & deals: binds the computed data (embedded as JSON) to the page. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const S = D.sections;
  const { dayLabel, monthLabel } = viz;
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  // ---- formatting
  const money = (v) => v == null ? "—" : Math.abs(v) >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : Math.abs(v) >= 1e9 ? `$${(v / 1e9).toFixed(v >= 1e11 ? 0 : 1)}B` : `$${(v / 1e6).toFixed(0)}M`;
  const mult = (v) => v == null ? "n/m" : v >= 100 ? `${v.toFixed(0)}×` : `${v.toFixed(1)}×`;
  const pct = (v) => v == null ? "—" : `${v.toFixed(0)}%`;
  const VALUE_FULL = 50; // a ±50% move earns the strongest color

  viz.initThemeToggle($("#theme-btn"));
  $("#m-asof").textContent = dayLabel(D.as_of);
  document.querySelectorAll("[data-k]").forEach((n) => { const [s, k] = n.dataset.k.split("."); n.textContent = S[s][k] || ""; });
  viz.deltaKey($("#key-summary"), "Value change:", ["Up", "Down"]);

  // ---- time key: a mini version of the trail, labelled with real months
  (function timeKey(host) {
    const stops = [["12", monthLabel(D.dates["12m"])], ["6", monthLabel(D.dates["6m"])], ["now", "Now"]];
    stops.forEach(([cls, label], i) => {
      if (i) host.append(el("i", `tk-seg ${i === 1 ? "first" : "last"}`));
      const stop = el("span", "tk-stop");
      const dotBox = el("span", "tk-dot"); dotBox.append(el("i", `dd dd-${cls}`));
      stop.append(dotBox, el("span", "", label));
      host.append(stop);
    });
  })($("#time-key"));

  const valueBadge = (v, label) => v == null ? el("span", "", "—")
    : viz.deltaBadge(v, { goodUp: true, full: VALUE_FULL, text: `${Math.abs(v).toFixed(0)}%`, title: `${label}: ${v >= 0 ? "+" : ""}${v.toFixed(1)}%` });

  // ---- summary dumbbells: 12m ago, 6m ago, now per category
  function dumbbells(host, key, fmt) {
    const cats = S.summary.categories;
    const max = Math.max(...cats.flatMap((c) => ["now", "6m", "12m"].map((k) => c[key][k] || 0))) * 1.08;
    cats.forEach((c) => {
      const row = el("div", "db-row");
      const head = el("div", "db-head");
      head.append(el("span", "db-name", c.name), valueBadge(c.value_chg["6m"], "6-month value change"));
      const track = el("div", "db-track");
      // fading trail: each leg brightens toward the newer point; an arrowhead points into "now"
      const pts = ["12m", "6m", "now"].map((k) => [k, c[key][k]]).filter(([, v]) => v != null);
      pts.slice(1).forEach(([k, v], i) => {
        const a = (pts[i][1] / max) * 100, b = (v / max) * 100;
        const seg = el("span", `db-seg ${b >= a ? "r" : "l"} ${k === "now" ? "last" : "first"}`);
        seg.style.left = `${Math.min(a, b)}%`; seg.style.width = `${Math.abs(b - a)}%`;
        if (k === "now" && Math.abs(b - a) > 4) seg.classList.add("arrow");
        track.append(seg);
      });
      ["12m", "6m", "now"].forEach((k) => {
        const v = c[key][k];
        if (v == null) return;
        const dot = el("span", `dd dd-${k === "now" ? "now" : k === "6m" ? "6" : "12"}`);
        dot.style.left = `${(v / max) * 100}%`;
        dot.title = `${k === "now" ? "Now" : k === "6m" ? "6 months ago" : "12 months ago"}: ${fmt(v)}`;
        track.append(dot);
      });
      const val = el("div", "db-val");
      val.append(el("b", "", fmt(c[key].now)), el("span", "", ` (12m ago ${fmt(c[key]["12m"])})`));
      row.append(head, track, val);
      host.append(row);
    });
  }
  dumbbells($("#db-rev"), "ev_rev", mult);
  dumbbells($("#db-ebitda"), "ev_ebitda", mult);

  // ---- generic sortable table
  function table(host, cols, rows, initialSort) {
    let sortKey = initialSort.key, dir = initialSort.dir;
    const thead = host.createTHead(), tbody = host.createTBody();
    function render() {
      thead.textContent = ""; tbody.textContent = "";
      const tr = thead.insertRow();
      cols.forEach((c) => {
        const th = el("th", c.cls || "");
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
      const sorted = rows.filter((r) => !host._filter || host._filter(r)).sort((a, b) => {
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
    }
    host._render = render;
    render();
  }
  function filters(host, options, tableEl, test) {
    let current = "All";
    ["All", ...options].forEach((o) => {
      const b = el("button", "chip-btn", o); b.type = "button";
      b.setAttribute("aria-pressed", String(o === current));
      b.addEventListener("click", () => {
        current = o;
        host.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x.textContent === o)));
        tableEl._filter = o === "All" ? null : (r) => test(r, o);
        tableEl._render();
      });
      host.append(b);
    });
  }

  // ---- companies
  const C = S.companies.rows;
  const withMark = (text, on) => { const s = el("span", "", text); if (on) s.append(el("sup", "fn", "*")); return s; };
  const multDelta = (v) => v == null ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}×`;
  const nameCell = (r) => { const s = el("span", "co"); s.append(el("b", "", r.name), el("small", "", ` ${r.ticker}`)); return s; };
  table($("#comp-table"), [
    { key: "name", label: "Company", cls: "sticky", sort: (r) => r.name.toLowerCase(), cell: nameCell },
    { key: "cat", label: "Category", cls: "left", sort: (r) => r.category, cell: (r) => r.category },
    { key: "mcap", label: "Market cap", sort: (r) => r.market_cap, cell: (r) => money(r.market_cap) },
    { key: "ev", label: "EV", sort: (r) => r.ev, cell: (r) => money(r.ev) },
    { key: "evrev", label: "EV/Rev", sort: (r) => r.ev_rev, cell: (r) => mult(r.ev_rev) },
    { key: "evebitda", label: "EV/EBITDA", sort: (r) => r.ev_ebitda, cell: (r) => withMark(mult(r.ev_ebitda), r.da_partial && r.ev_ebitda) },
    { key: "pe", label: "P/E", sort: (r) => r.pe, cell: (r) => mult(r.pe) },
    { key: "growth", label: "Rev growth", sort: (r) => r.growth, cell: (r) => r.growth == null ? "—" : `${r.growth >= 0 ? "+" : ""}${r.growth.toFixed(0)}%` },
    { key: "margin", label: "EBITDA margin", sort: (r) => r.margin, cell: (r) => pct(r.margin) },
    { key: "c6", label: "Value 6m", sort: (r) => r.chg["6m"], cell: (r) => valueBadge(r.chg["6m"], "6-month change") },
    { key: "c12", label: "Value 12m", sort: (r) => r.chg["12m"], cell: (r) => valueBadge(r.chg["12m"], "12-month change") },
    { key: "m6", label: "EV/Rev Δ 6m", sort: (r) => r.mult_chg["6m"].ev_rev, cell: (r) => multDelta(r.mult_chg["6m"].ev_rev) },
    { key: "m12", label: "EV/Rev Δ 12m", sort: (r) => r.mult_chg["12m"].ev_rev, cell: (r) => multDelta(r.mult_chg["12m"].ev_rev) },
  ], C, { key: "mcap", dir: -1 });
  filters($("#cat-filters"), S.summary.categories.map((c) => c.name), $("#comp-table"), (r, o) => r.category === o);

  // ---- deals
  const R = S.deals.rows;
  const dealCell = (r) => {
    const s = el("span", "co");
    s.append(el("b", "", r.target), el("small", "", ` ← ${r.acquirer}`));
    if (r.segment === "Consumer subscription") s.append(el("span", "tag", "Consumer subscription"));
    return s;
  };
  const dealValue = (r) => {
    if (r.type === "Venture round") return `${money(r.raised)} at ${money(r.value)}`;
    if (r.value == null) return "Undisclosed";
    const v = r.ev != null ? money(r.ev) + (r.ev_is_derived ? "†" : "") : money(r.value);
    return r.value_note ? `${v}+` : v;
  };
  const link = (r) => { const a = el("a", "src-link", "Source ↗"); a.href = r.source; a.target = "_blank"; a.rel = "noopener"; return a; };
  table($("#deal-table"), [
    { key: "date", label: "Announced", sort: (r) => r.date, cell: (r) => r.date_precision === "month" ? monthLabel(r.date) : dayLabel(r.date) },
    { key: "deal", label: "Target ← buyer", cls: "sticky", sort: (r) => r.target.toLowerCase(), cell: dealCell },
    { key: "type", label: "Type", cls: "left", sort: (r) => r.type, cell: (r) => r.type },
    { key: "seg", label: "Segment", cls: "left", sort: (r) => r.segment, cell: (r) => r.segment },
    { key: "value", label: "Value", sort: (r) => r.ev ?? r.value, cell: dealValue },
    { key: "evrev", label: "EV/Rev", sort: (r) => r.ev_rev, cell: (r) => r.ev_rev ? mult(r.ev_rev) : (r.target_revenue ? "n/m" : "—") },
    { key: "evebitda", label: "EV/EBITDA", sort: (r) => r.ev_ebitda, cell: (r) => r.ev_ebitda ? withMark(mult(r.ev_ebitda), r.da_partial) : (r.target_revenue ? "n/m" : "—") },
    { key: "rev", label: "Target revenue", sort: (r) => r.target_revenue, cell: (r) => money(r.target_revenue) },
    { key: "ebitda", label: "Target EBITDA", sort: (r) => r.target_ebitda, cell: (r) => r.target_revenue ? money(r.target_ebitda) : "—" },
    { key: "margin", label: "EBITDA margin", sort: (r) => r.target_margin, cell: (r) => r.target_revenue ? pct(r.target_margin) : "—" },
    { key: "note", label: "Notes", cls: "left note", sort: null, cell: (r) => r.note || "" },
    { key: "src", label: "Source", sort: null, cell: link },
  ], R, { key: "date", dir: -1 });
  filters($("#deal-filters"), [...new Set(R.map((r) => r.type))], $("#deal-table"), (r, o) => r.type === o);

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
    `Prices and market caps are a snapshot from the close on ${dayLabel(D.as_of)}, refreshed every Monday and Friday after the market close. "6 months" and "12 months" compare with the closes on ${dayLabel(D.dates["6m"])} and ${dayLabel(D.dates["12m"])} (split-adjusted).`,
    "All multiples use the trailing 12 months (TTM): the latest four reported quarters, from each company's SEC filings. Forward estimates aren't used (they come from paid analyst data).",
    "EBITDA = reported operating income + depreciation and amortization (GAAP; not the adjusted figures companies promote, so stock-based compensation and one-off charges are included).",
    "EV = market cap + total debt − cash and short-term investments, from the latest balance sheet. Past multiples use the financials that had been reported by then (results assumed public about 35 days after a quarter ends) and today's share count.",
    "Universe: 36 US-listed companies chosen to represent each category. Foreign filers (e.g. TSMC, Arm, Spotify) are excluded because their reports use different accounting formats.",
    "Deals: a curated list of notable transactions announced in the six months to the snapshot date, from SEC filings, company announcements and press coverage (each row links its source). Private valuations are as reported for each funding round.",
    "Not investment advice.",
  ].forEach((t) => $("#method").append(el("li", "", t)));
})();
