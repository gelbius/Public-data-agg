/* AI 2027 vs reality: binds the computed data (embedded as JSON) to the page.
   - The record: a seismograph sheet. The red dotted line is the scenario's expected progress (printed in
     advance); the black trace is reality's position on that path, revealed as you scroll.
   - The departures board: every prediction as a flight. A mini board in the sticky stage flips in step
     with the scroll; the full board below lists all of them with filters.
   All numbers come from compute.py; this file only draws them. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const S = D.sections, R = S.record, B = S.board;
  const { dayLabel, monthLabel, esc } = viz;
  const $ = (sel) => document.querySelector(sel);
  const NS = "http://www.w3.org/2000/svg";
  const MS = 86400000, MONTH = 30.4375;
  const T0 = Date.parse(D.published);
  const tm = (iso) => (Date.parse(iso) - T0) / MS / MONTH;
  const T_TODAY = tm(D.as_of);
  const TMAX = tm(D.chart_end);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dateAt = (t) => new Date(T0 + t * MONTH * MS);
  const monthOf = (t) => { const x = dateAt(t); return `${MONTHS[x.getUTCMonth()]} ${x.getUTCFullYear()}`; };
  const shortMonth = (t) => { const x = dateAt(t); return `${MONTHS[x.getUTCMonth()]} ${String(x.getUTCFullYear()).slice(2)}`; };
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const narrow = () => window.innerWidth < 900;
  const gapWords = (g) => Math.abs(g) < 0.25 ? "on the script" : `${g > 0 ? "+" : "−"}${Math.abs(g).toFixed(1)} mo ${g > 0 ? "ahead of" : "behind"} the script`;
  const svgEl = (tag, attrs, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(el);
    return el;
  };

  viz.initThemeToggle($("#theme-btn"));
  $("#m-asof").textContent = dayLabel(D.as_of);
  document.querySelectorAll("[data-k]").forEach((el) => {
    const [sec, key] = el.dataset.k.split(".");
    el.textContent = S[sec][key] || "";
  });
  document.querySelectorAll("[data-src]").forEach((el) => {
    const src = S[el.dataset.src].source;
    const a = document.createElement("span"); a.className = "src"; a.innerHTML = "<b>SOURCE</b> "; a.append(src.label);
    const b = document.createElement("span"); b.textContent = `Verdicts as of ${dayLabel(src.as_of)} · curated by hand`;
    el.append(a, b);
  });

  /* ---------- scorecard */
  const K = S.kpis;
  $("#kpi-head").textContent = `${K.n} dated predictions, scored as of ${dayLabel(D.as_of)}.`;
  K.tiles.forEach((t) => {
    const el = document.createElement("div"); el.className = "tile";
    el.innerHTML = `<div class="label">${esc(t.label)}</div><div class="value">${esc(t.value)}</div><div class="when">${esc(t.when)}</div>`;
    $("#kpis").append(el);
  });

  /* ---------- series helpers */
  const toT = (rows) => rows.map(([d, v]) => [tm(d), v]);
  const scen = toT(R.scenario), real = toT(R.reality), gaps = toT(R.gap);
  function interp(arr, t) {
    if (t <= arr[0][0]) return arr[0][1];
    if (t >= arr[arr.length - 1][0]) return arr[arr.length - 1][1];
    let lo = 0, hi = arr.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (arr[m][0] <= t) lo = m; else hi = m; }
    const [t0, v0] = arr[lo], [t1, v1] = arr[hi];
    return v0 + (v1 - v0) * (t - t0) / (t1 - t0);
  }
  const VMAX = Math.max(scen[scen.length - 1][1], real[real.length - 1][1]) * 1.08;
  const T_CROSS = R.cross ? tm(R.cross) : null;
  const events = R.events.map((e) => ({ ...e, t: tm(e.date) }));
  const VERDICT_VAR = { "Ahead of schedule": "--v-ahead", "On track": "--v-ontrack", "Behind": "--v-behind", "Didn't happen": "--v-no", "Too early to tell": "--v-tbd", "Context": "--ink-dim" };

  /* ---------- the seismograph */
  const seisHost = $("#seis");
  let G = null; // geometry + live nodes

  function buildSeis() {
    if (G && G.svg) G.svg.remove();
    const W = Math.max(300, seisHost.clientWidth), H = Math.max(240, seisHost.clientHeight);
    const sm = W < 560;
    const L = sm ? 30 : 42, Rm = sm ? 10 : 18, T = sm ? 114 : 92, Bm = 26;
    const X = (t) => L + (t / TMAX) * (W - L - Rm);
    const Y = (v) => H - Bm - (v / VMAX) * (H - Bm - T);
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, "aria-hidden": "true" });
    seisHost.prepend(svg);
    const defs = svgEl("defs", {}, svg);
    const clip = svgEl("clipPath", { id: "rec-clip" }, defs);
    const clipRect = svgEl("rect", { x: 0, y: 0, width: L, height: H }, clip);

    for (let y = T - 10; y < H - Bm; y += 18) svgEl("line", { class: "paper-rule", x1: 0, x2: W, y1: y, y2: y }, svg);
    const step = VMAX > 60 ? 20 : 10;
    for (let v = 0; v <= VMAX; v += step) {
      const t = svgEl("text", { class: "axis-y", x: L - 6, y: Y(v) + 3, "text-anchor": "end" }, svg); t.textContent = v;
    }
    if (!sm) {
      const cap = svgEl("text", { class: "axis-y", x: W - Rm, y: T - 22, "text-anchor": "end" }, svg);
      cap.textContent = "AI research progress, in months at the April 2025 pace";
    }
    const every = sm ? 6 : 3;
    for (let m = 0; m <= Math.floor(TMAX); m += every) {
      const x = X(m);
      svgEl("line", { class: "paper-rule", x1: x, x2: x, y1: H - Bm, y2: H - Bm + 5 }, svg);
      const t = svgEl("text", { class: "axis-t", x, y: H - 8, "text-anchor": "middle" }, svg); t.textContent = shortMonth(m);
    }
    // ahead / behind washes between the curves, revealed with the trace
    const washG = svgEl("g", { "clip-path": "url(#rec-clip)" }, svg);
    let seg = [], sign = null;
    const flush = () => {
      if (seg.length < 2) { seg = []; return; }
      const top = seg.map(([t, a, b]) => `${X(t).toFixed(1)},${Y(Math.max(a, b)).toFixed(1)}`);
      const bot = seg.slice().reverse().map(([t, a, b]) => `${X(t).toFixed(1)},${Y(Math.min(a, b)).toFixed(1)}`);
      svgEl("polygon", { class: sign > 0 ? "wash-ahead" : "wash-behind", points: top.concat(bot).join(" ") }, washG);
      seg = [];
    };
    real.forEach(([t, v]) => {
      const s = interp(scen, t), sg = v >= s ? 1 : -1;
      if (sign !== null && sg !== sign) { const last = seg[seg.length - 1]; flush(); if (last) seg.push(last); }
      sign = sg; seg.push([t, v, s]);
    });
    flush();
    // the script
    const sp = scen.map(([t, v], i) => `${i ? "L" : "M"}${X(t).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
    svgEl("path", { class: "script", d: sp }, svg);
    const lblT = Math.min(TMAX - 0.5, 21.5);
    if (!sm) {
      const sl = svgEl("text", { class: "script-lbl", x: X(lblT) + 6, y: Y(interp(scen, lblT)) + 18 }, svg);
      sl.textContent = "the script, printed in advance";
    }
    R.milestones.forEach((m, i) => {
      const t = tm(m.date), x = X(t), y = Y(m.progress);
      svgEl("circle", { class: "ms-dot", cx: x, cy: y, r: 3.5 }, svg);
      if (sm && i % 2) return;
      const lb = svgEl("text", { class: "ms-lbl", x: x - 6, y: y - 7, "text-anchor": "end" }, svg); lb.textContent = m.label;
    });
    // today
    const xt = X(T_TODAY);
    svgEl("line", { class: "today", x1: xt, x2: xt, y1: T - 14, y2: H - Bm }, svg);
    const tl = svgEl("text", { class: "today-lbl", x: xt + 4, y: H - Bm - 6 }, svg); tl.textContent = "today";
    // the record
    const rp = real.map(([t, v], i) => `${i ? "L" : "M"}${X(t).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
    svgEl("path", { class: "trace", d: rp, "clip-path": "url(#rec-clip)" }, svg);
    // dated events as ticks on the trace
    const evNodes = events.filter((e) => e.t <= T_TODAY).map((e) => {
      const x = X(e.t), y = Y(interp(real, e.t));
      const g = svgEl("g", { class: "ev off" }, svg);
      svgEl("line", { x1: x, x2: x, y1: y - 8, y2: y + 8, style: `stroke:var(${VERDICT_VAR[e.verdict] || "--ink-dim"})` }, g);
      const tt = svgEl("title", {}, g); tt.textContent = `${e.title} · ${e.verdict}`;
      return { e, g, on: false };
    });
    // crossing
    let crossG = null;
    if (T_CROSS !== null) {
      crossG = svgEl("g", { opacity: 0 }, svg);
      const cx = X(T_CROSS), cy = Y(interp(real, T_CROSS));
      svgEl("circle", { class: "cross-ring", cx, cy, r: 9 }, crossG);
      const ct = svgEl("text", { class: "cross-lbl", x: cx + 13, y: cy + 20 }, crossG);
      ct.textContent = `crosses the script · ${monthOf(T_CROSS)}`;
    }
    // pen
    const arm = svgEl("line", { class: "arm", x1: L, x2: L, y1: T - 16, y2: T - 16 }, svg);
    const nib = svgEl("path", { class: "nib", d: "" }, svg);
    G = { svg, X, Y, L, clipRect, arm, nib, evNodes, crossG, H };
    if (lastT !== null) updateSeis(lastT, true);
  }

  function updateSeis(t, silent) {
    if (!G) return;
    const tt = Math.max(0, Math.min(t, T_TODAY));
    const x = G.X(tt), y = G.Y(interp(real, tt));
    G.clipRect.setAttribute("width", Math.max(0, x + 1));
    G.arm.setAttribute("x1", x); G.arm.setAttribute("x2", x); G.arm.setAttribute("y2", y - 10);
    G.nib.setAttribute("d", `M${x - 5} ${y - 11}L${x + 5} ${y - 11}L${x} ${y}Z`);
    G.evNodes.forEach((n) => {
      const on = n.e.t <= tt + 1e-6;
      if (on !== n.on) {
        n.on = on;
        n.g.classList.toggle("off", !on);
        if (on && !silent && !reduce) { n.g.classList.remove("hit"); void n.g.getBBox(); n.g.classList.add("hit"); }
      }
    });
    if (G.crossG) G.crossG.setAttribute("opacity", tt >= T_CROSS ? 1 : 0);
    $("#r-note").textContent = tt >= T_TODAY - 0.05 ? (narrow() ? `= script's ${monthOf(T_TODAY + R.today_gap)} spot; no superhuman coder yet` : `= the script's ${monthOf(T_TODAY + R.today_gap)} position (its superhuman coder hasn't arrived)`) : "";
    const g = interp(gaps, tt);
    $("#r-date").textContent = monthOf(tt);
    const rg = $("#r-gap");
    rg.textContent = gapWords(g);
    rg.className = "r-gap " + (g >= 0.25 ? "ahead" : g <= -0.25 ? "behind" : "");
  }

  /* ---------- telegraph: the latest dated event */
  let lastEv = null;
  function updateTelegraph(t) {
    const tt = Math.min(t, T_TODAY);
    let e = null;
    for (const x of events) if (x.t <= tt + 1e-6) e = x;
    if (e === lastEv) return;
    lastEv = e;
    const el = $("#telegraph");
    if (!e) { el.innerHTML = `<span class="tg-cap">TELEGRAPH</span><span class="tg-title">Awaiting the first dispatch</span>`; return; }
    const when = e.precision === "month" ? monthLabel(e.date) : dayLabel(e.date);
    el.innerHTML = `<span class="tg-cap">TELEGRAPH · </span><span class="tg-date">${esc(when.toUpperCase())}</span>` +
      `<span class="tg-title">${esc(e.title)}</span><span class="tg-detail">${esc(e.detail)} ` +
      `<a href="${esc(e.source.url)}" rel="noopener">${esc(e.source.title)} ↗</a></span>`;
  }

  /* ---------- split-flap helpers */
  function flap(text, len, extraCls) {
    const s = String(text || "").toUpperCase().padEnd(len, " ").slice(0, len);
    let h = `<span class="flap ${extraCls || ""}"><span class="sr">${esc(String(text || "").trim() || "none")}</span>`;
    for (const c of s) h += `<span class="ch" aria-hidden="true">${c === " " ? "&nbsp;" : esc(c)}</span>`;
    return h + "</span>";
  }
  function flipAll(root, baseDelay) {
    if (reduce) return;
    root.querySelectorAll(".ch").forEach((c, i) => {
      c.classList.remove("flip"); void c.offsetWidth;
      c.style.animationDelay = `${baseDelay + i * 22}ms`;
      c.classList.add("flip");
    });
  }
  const stCls = (st) => "st-" + st.replace(" ", "-");

  /* ---------- mini board: the flights whose status changed most recently */
  function statusAt(r, t) {
    const tv = r.verdict_on ? tm(r.verdict_on) : Infinity, ts = tm(r.scheduled);
    if (t >= tv) return r.status;
    if (r.status === "SCHEDULED") return "SCHEDULED";
    if (ts < 0) return "BOARDING";
    return t > ts ? "DELAYED" : "SCHEDULED";
  }
  function changedAt(r, t) {
    const tv = r.verdict_on ? tm(r.verdict_on) : Infinity, ts = tm(r.scheduled);
    let c = -Infinity;
    if (ts >= 0 && t > ts) c = ts;
    if (t >= tv) c = Math.max(c, tv);
    return c;
  }
  const miniPrev = new Map();
  let miniSig = "";
  function updateMini(t) {
    const n = narrow() ? 3 : 5, tt = Math.min(t, T_TODAY);
    const changed = B.rows.filter((r) => changedAt(r, tt) > -Infinity).sort((a, b) => changedAt(b, tt) - changedAt(a, tt));
    let pick = changed.slice(0, n);
    if (pick.length < n) {
      const upcoming = B.rows.filter((r) => !pick.includes(r) && tm(r.scheduled) >= tt).sort((a, b) => tm(a.scheduled) - tm(b.scheduled));
      pick = pick.concat(upcoming.slice(0, n - pick.length));
    }
    const rows = pick.map((r) => ({ r, st: statusAt(r, tt) }));
    const sig = rows.map((x) => x.r.id + x.st).join("|") + n;
    if (sig === miniSig) return;
    miniSig = sig;
    const el = $("#miniboard");
    el.innerHTML = `<div class="fl-head" aria-hidden="true"><span>SCHED</span><span>PREDICTION</span><span>STATUS</span></div>` +
      rows.map(({ r, st }) => `<div class="fl-row ${stCls(st)}" data-id="${r.id}"><span class="sched">${flap(r.sched_short, 7)}</span>` +
        `<span class="flight">${flap(r.label, 22)}</span><span class="status">${flap(st, 9)}</span></div>`).join("");
    el.querySelectorAll(".fl-row").forEach((row, i) => {
      const id = row.dataset.id, st = rows[i].st;
      if (miniPrev.get(id) !== st) flipAll(row.querySelector(".status"), i * 60);
      if (!miniPrev.has(id)) flipAll(row.querySelector(".flight"), i * 60);
    });
    miniPrev.clear();
    rows.forEach(({ r, st }) => miniPrev.set(r.id, st));
  }

  /* ---------- story steps and the scroll -> time mapping */
  const stepsEl = $("#steps");
  R.beats.forEach((b) => {
    const s = document.createElement("div"); s.className = "step"; s.dataset.t = tm(b.date);
    const refs = b.refs.length ? `<ul class="refs">${b.refs.map((r) => `<li><a href="${esc(r.url)}" rel="noopener">${esc(r.title)} ↗</a></li>`).join("")}</ul>` : "";
    s.innerHTML = `<div class="step-card"><span class="kick">${esc(b.kicker)}</span><h3>${esc(b.title)}</h3><p>${esc(b.body)}</p>${refs}</div>`;
    stepsEl.append(s);
  });
  const steps = [...stepsEl.querySelectorAll(".step")];
  let lastT = null, ticking = false;
  function scrollT() {
    const stage = $("#stage").getBoundingClientRect();
    const ref = narrow() ? stage.bottom + (window.innerHeight - stage.bottom) * 0.35 : window.innerHeight * 0.55;
    const pts = steps.map((s) => { const c = s.firstChild.getBoundingClientRect(); return { y: c.top + c.height / 2, t: +s.dataset.t }; });
    let active = 0;
    pts.forEach((p, i) => { if (p.y <= ref + 40) active = i; });
    steps.forEach((s, i) => s.classList.toggle("on", i === active));
    if (ref <= pts[0].y) return pts[0].t;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      if (ref >= a.y && ref < b.y) return a.t + (b.t - a.t) * (ref - a.y) / (b.y - a.y);
    }
    return pts[pts.length - 1].t;
  }
  function frame() {
    ticking = false;
    const t = scrollT();
    if (lastT !== null && Math.abs(t - lastT) < 1e-4) return;
    const first = lastT === null;
    lastT = t;
    updateSeis(t, first);
    updateTelegraph(t);
    updateMini(t);
  }
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(frame); } };
  window.addEventListener("scroll", onScroll, { passive: true });

  /* ---------- full board */
  const dimCount = {}, stCount = {};
  B.rows.forEach((r) => { dimCount[r.dimension] = (dimCount[r.dimension] || 0) + 1; stCount[r.status] = (stCount[r.status] || 0) + 1; });
  const filt = { dim: "all", st: "all" };
  const VERB = { "EARLY": "Ahead of schedule", "ON TIME": "On track", "DELAYED": "Behind", "CANCELLED": "Didn't happen", "SCHEDULED": "Too early to tell" };
  function chips(host, key, items) {
    host.innerHTML = items.map(([v, label, n, cls]) => `<button type="button" class="fchip ${cls || ""}" data-v="${esc(v)}" ${cls ? `data-st="${esc(v)}"` : ""} aria-pressed="${filt[key] === v}">${esc(label)}<span class="n">${n}</span></button>`).join("");
    host.addEventListener("click", (ev) => {
      const b = ev.target.closest(".fchip"); if (!b) return;
      filt[key] = b.dataset.v;
      host.querySelectorAll(".fchip").forEach((x) => x.setAttribute("aria-pressed", x === b));
      renderBoard(true);
    });
  }
  chips($("#f-dim"), "dim", [["all", "All", B.rows.length]].concat(B.dimensions.map((d) => [d, d, dimCount[d]])));
  chips($("#f-st"), "st", [["all", "Any status", B.rows.length, ""]].concat(Object.keys(VERB).filter((s) => stCount[s]).map((s) => [s, s, stCount[s], "st"])));
  $("#board-key").textContent = Object.entries(VERB).map(([s, v]) => `${s} = ${v.toLowerCase()}`).join(" · ") + `. Verdicts as of ${dayLabel(D.as_of)}.`;
  $("#board-clock").outerHTML = flap(monthOf(T_TODAY), 8, "b-clock");

  function arrived(r) {
    if (!r.actual) return "Not yet";
    return r.actual_precision === "month" ? `${monthLabel(r.actual)} (month only)` : dayLabel(r.actual);
  }
  function renderBoard(animate) {
    const rows = B.rows.filter((r) => (filt.dim === "all" || r.dimension === filt.dim) && (filt.st === "all" || r.status === filt.st));
    const host = $("#board-rows");
    if (!rows.length) { host.innerHTML = `<p class="board-empty">No predictions match these filters.</p>`; return; }
    host.innerHTML = rows.map((r) => `<details class="flight-d"><summary class="fl-row ${stCls(r.status)}">` +
      `<span class="sched">${flap(r.sched_short, 7)}</span><span class="flight">${flap(r.label, 22)}</span>` +
      `<span class="act">${flap(r.actual_short || "--", 6)}</span><span class="status">${flap(r.status, 9)}</span></summary>` +
      `<div class="manifest"><div><h4>The scenario said</h4><p class="m-quote">${esc(r.prediction)}</p></div>` +
      `<div><h4>What happened</h4><p>${esc(r.reality)}</p></div>` +
      `<div class="m-meta"><span>Scenario date: ${esc(r.sched_text)}</span><span>Arrived: ${esc(arrived(r))}</span>` +
      `<span>Area: ${esc(r.dimension)}${r.subtag ? " · " + esc(r.subtag) : ""}</span><span>Verdict: ${esc(r.verdict)}</span>` +
      `<span>Source: <a href="${esc(r.source.url)}" rel="noopener">${esc(r.source.title)} ↗</a></span></div></div></details>`).join("");
    if (animate) host.querySelectorAll(".status").forEach((s, i) => flipAll(s, i * 45));
  }
  renderBoard(false);
  const io = new IntersectionObserver((items) => {
    if (items.some((i) => i.isIntersecting)) { io.disconnect(); $("#board-rows").querySelectorAll(".status").forEach((s, i) => flipAll(s, i * 45)); }
  }, { threshold: 0.15 });
  io.observe($("#board"));

  /* ---------- schedule-gap dots */
  const DT = S.dots;
  const DIM_VAR = { "AI Capabilities": "--s-ff", "Alignment & safety": "--s-ur" };
  $("#gap-sub").textContent = `${DT.resolved.length} predictions in ${DT.dimensions.join(" and ").toLowerCase()} have a known arrival date. ` +
    `Each dot sits on the day reality met the prediction, at how many months early (+) or late (−) that was. The black line is ` +
    `their weighted average (Gaussian, ${DT.bandwidth}-month bandwidth), eased in from zero over the first ${DT.ramp} months. ` +
    `This line sets the record's position in the chart above.`;
  $("#gap-legend").innerHTML = DT.dimensions.map((d) => `<li><i class="dot-key" style="background:var(${DIM_VAR[d]})"></i>${esc(d)}</li>`).join("") +
    `<li><i class="dot-key" style="border:2px solid var(--ink-soft)"></i>Not met yet (lag as of today)</li>` +
    `<li><i class="key" style="color:var(--ink);height:2px"></i>Smoothed trend</li>`;
  function buildGap() {
    const host = $("#gapchart");
    host.innerHTML = "";
    const W = Math.max(300, host.clientWidth), sm = W < 560, H = sm ? 300 : 360;
    const L = 36, Rm = sm ? 12 : Math.min(250, Math.round(W * 0.26)), T = 16, Bm = 28;
    const tEnd = T_TODAY + 0.6;
    const all = DT.resolved.map((x) => x.gap).concat(DT.unmet.map((x) => x.lag));
    const ymin = Math.floor(Math.min(...all) - 1), ymax = Math.ceil(Math.max(...all) + 1);
    const X = (t) => L + (t / tEnd) * (W - L - Rm), Y = (g) => T + (ymax - g) / (ymax - ymin) * (H - T - Bm);
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true" }, host);
    for (let g = Math.ceil(ymin / 3) * 3; g <= ymax; g += 3) {
      svgEl("line", { class: "g-grid", x1: L, x2: W - Rm, y1: Y(g), y2: Y(g) }, svg);
      const t = svgEl("text", { class: "g-ax", x: L - 6, y: Y(g) + 4, "text-anchor": "end" }, svg); t.textContent = g > 0 ? `+${g}` : g;
    }
    for (let m = 0; m <= T_TODAY; m += sm ? 6 : 3) {
      const t = svgEl("text", { class: "g-ax", x: X(m), y: H - 8, "text-anchor": "middle" }, svg); t.textContent = shortMonth(m);
    }
    svgEl("line", { class: "g-zero", x1: L, x2: W - Rm, y1: Y(0), y2: Y(0) }, svg);
    const zl = svgEl("text", { class: "g-zero-lbl", x: W - Rm, y: Y(0) - 6, "text-anchor": "end" }, svg); zl.textContent = "on the script";
    const up = svgEl("text", { class: "g-ax", x: L + 4, y: T + 10 }, svg); up.textContent = "months early ↑";
    const dn = svgEl("text", { class: "g-ax", x: L + 4, y: H - Bm - 6 }, svg); dn.textContent = "months late ↓";
    svgEl("path", { class: "g-trend", d: gaps.map(([t, g], i) => `${i ? "L" : "M"}${X(t).toFixed(1)} ${Y(g).toFixed(1)}`).join("") }, svg);
    const placed = [];
    const label = (x, y, text) => {
      if (sm) return;
      let yy = y + 4;
      while (placed.some((p) => Math.abs(p - yy) < 13)) yy += 13;
      placed.push(yy);
      const t = svgEl("text", { class: "g-lbl", x: Math.min(x + 9, W - Rm + 6), y: yy }, svg); t.textContent = text;
    };
    DT.resolved.forEach((d) => {
      const x = X(tm(d.met)), y = Y(d.gap);
      const c = svgEl("circle", { class: "g-dot", cx: x, cy: y, r: 6, style: `fill:var(${DIM_VAR[d.dimension]})` }, svg);
      const tt = svgEl("title", {}, c); tt.textContent = `${d.label}: ${d.gap > 0 ? "+" : ""}${d.gap} months (${dayLabel(d.met)})`;
    });
    DT.unmet.forEach((d) => {
      const x = X(T_TODAY), y = Y(d.lag);
      const c = svgEl("circle", { class: "g-dot unmet", cx: x, cy: y, r: 6, style: `stroke:var(${DIM_VAR[d.dimension]})` }, svg);
      const tt = svgEl("title", {}, c); tt.textContent = `${d.label}: not met, ${d.lag} months as of today`;
    });
    // label the dots at the right edge of the plot, in date order, so labels never cover the trend
    if (!sm) {
      DT.resolved.concat(DT.unmet.map((u) => ({ ...u, met: D.as_of, gap: u.lag, unmetFlag: true })))
        .filter((d) => Math.abs(d.gap) >= 4)
        .sort((a, b) => b.gap - a.gap)
        .forEach((d) => {
          const x = d.unmetFlag ? X(T_TODAY) : X(tm(d.met));
          label(Math.max(x, W - Rm - 2), Y(d.gap), `${d.label}${d.unmetFlag ? " (not yet)" : ""}`);
          if (x < W - Rm - 12) svgEl("line", { x1: x + 7, x2: W - Rm + 4, y1: Y(d.gap), y2: placed[placed.length - 1] - 4, stroke: "var(--line-2)" }, svg);
        });
    }
  }

  /* ---------- tables */
  const scenAt = Object.fromEntries(R.scenario), realAt = Object.fromEntries(R.reality), gapAt = Object.fromEntries(R.gap);
  const monthly = R.scenario.filter((_, i) => i % 4 === 0 || R.scenario[i][0] === D.as_of);
  viz.table($("#t-record"), ["Week of", "Script: expected progress", "Record: reality's position", "Gap (months, + = ahead)"],
    monthly.map(([d]) => [dayLabel(d), scenAt[d].toFixed(1), realAt[d] != null ? realAt[d].toFixed(1) : "", gapAt[d] != null ? gapAt[d].toFixed(1) : ""]));
  viz.table($("#t-gap"), ["Prediction", "Area", "Scenario date", "Met", "Months early (+) / late (−)"],
    DT.resolved.map((d) => [d.label, d.dimension, d.scenario_date, dayLabel(d.met), `${d.gap > 0 ? "+" : ""}${d.gap}${d.note ? " (" + d.note + ")" : ""}`])
      .concat(DT.unmet.map((d) => [d.label, d.dimension, monthLabel(d.scheduled), "Not yet", `${d.lag} as of ${dayLabel(D.as_of)}`])));

  /* ---------- what to watch */
  $("#watch").innerHTML = S.watch.items.map((w) => {
    const when = w.date ? (w.scenario ? monthLabel(w.date) : dayLabel(w.date)) : "Undated";
    const ev = w.url ? `<a href="${esc(w.url)}" rel="noopener">${esc(w.event)}</a>` : esc(w.event);
    return `<li><span class="w-date">${esc(when)}${w.scenario ? "<small>scenario date</small>" : ""}</span>` +
      `<span><span class="w-ev">${ev}</span><br><span class="w-test">Tests: ${esc(w.tests)}</span></span></li>`;
  }).join("");

  /* ---------- method (numbers come from the data) */
  const mult = R.multipliers.filter((m) => m.quote).map((m) => `${m.value}x by ${monthLabel(m.date)}`).join(", ");
  const lastM = R.multipliers[R.multipliers.length - 1];
  const override = DT.resolved.find((d) => d.note);
  const aimMonth = monthOf(T_TODAY + R.today_gap);
  const coder = B.rows.find((r) => r.id === "superhuman-coder");
  const method = [
    `<b>Predictions, wording and verdicts.</b> ${K.n} dated predictions from AI 2027 and its supplements, as compiled and graded on <a href="${esc(D.compiled_from.url)}">${esc(D.compiled_from.title)}</a> (data as of ${dayLabel(D.as_of)}). Every row links to its primary source; most grades follow the AI 2027 authors' own reviews (AI Futures Project).`,
    `<b>The script (red).</b> Cumulative AI research progress the scenario expects, counted in months of progress at the April 2025 pace. Each month adds the scenario's own AI R&amp;D multiplier (${esc(mult)}), starting from 1x at publication, interpolated on a log scale and held at ${lastM.value}x after ${monthLabel(lastM.date)}. That is why the line bends upward.`,
    `<b>The record (black).</b> Reality's position on that same path. On each date it sits where the script expected to be the smoothed schedule gap's worth of months earlier or later (see "How the reading is made"). It never moves backward: if the gap widens faster than time passes, the line holds flat. Think of a train against its timetable.`,
    `<b>What today's reading means, and what it doesn't.</b> At ${esc(gapWords(R.today_gap))}, the record sits where the script expected to be in ${esc(aimMonth)}. That describes the overall schedule, not any one milestone: the scenario's ${esc(coder ? coder.sched_text : "Mar 2027")} superhuman coder has not happened (verdict: ${esc(coder ? coder.verdict.toLowerCase() : "too early to tell")}).`,
    `<b>What feeds the trend.</b> Only ${DT.dimensions.join(" and ").toLowerCase()} predictions with a known arrival date, matching the source page. Economic and political predictions are on the board but not in the line.` + (override ? ` One dot (${esc(override.label)}) uses the ${esc(override.note)} of ${override.gap > 0 ? "+" : ""}${override.gap} months instead of a date difference, because the scenario's milestone and METR's measurement are not the same quantity.` : ""),
    `<b>Dates.</b> The scenario's seasons become single days (Mid = Jul 1, Late = Nov 1, Early = Feb 1, a bare year = Dec 31), as on the source page. A few arrival dates are known only to the month and are marked on the board. A prediction met late can only plot late and one met early only early, so read the trend as a direction, not a measurement.`,
    `<b>Ticks on the trace</b> mark dated real-world events from the source page's timeline, colored by verdict. They are labels, not data points of the line.`,
    `<b>Updates.</b> This dashboard is curated by hand: add new evidence with its source link to <code>data/ai2027/*.json</code> and the build recomputes every number on the page.`,
  ];
  $("#method").innerHTML = method.map((m) => `<li>${m}</li>`).join("");

  /* ---------- lifecycle */
  function layout() { buildSeis(); buildGap(); miniSig = ""; lastT = null; frame(); }
  let w = window.innerWidth, timer;
  window.addEventListener("resize", () => {
    if (window.innerWidth === w) return;
    w = window.innerWidth; clearTimeout(timer); timer = setTimeout(layout, 180);
  });
  layout();
})();
