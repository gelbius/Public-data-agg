"""Macro dashboard: turn the raw public data in data/macro/ into the numbers, chart
series and headline sentences the page shows.

Rule: every number on the page comes out of this file. The HTML template never
contains a hand-typed statistic, so a data refresh can never leave stale prose.
"""
import json
from pathlib import Path

from series import Series, spans, month_label, quarter_label, day_label

TITLE = "The Consumer: An Economic State of the Union"
SLUG = "macro"
DESCRIPTION = ("Inflation, rates, jobs, wages, credit and sentiment for the US household, "
               "from public Federal Reserve, BLS, BEA and EIA data.")

# Hero chart phase bands. These labels are an INTERPRETATION of the data (dated from
# Fed rate moves and inflation turning points), not official designations. The page
# says so. "latest" means "through the most recent observation".
PHASES = [
    ("2020-03-01", "2020-04-01", "Pandemic shock"),
    ("2020-05-01", "2021-03-01", "Zero rates & stimulus"),
    ("2021-04-01", "2022-02-01", "Inflation takes off"),
    ("2022-03-01", "2023-07-01", "Rate hikes"),
    ("2023-08-01", "2024-08-01", "Holding high"),
    ("2024-09-01", "2025-12-01", "Rate cuts"),
    ("2026-03-01", "latest", "Energy shock"),
]
HERO_START = "2019-01-01"
WINDOW_START = "2014-01-01"


def pct(v, digits=1):
    return f"{v:.{digits}f}%"


def compute(data_dir):
    data_dir = Path(data_dir)
    S = {sid: Series.load(data_dir, sid) for sid in (
        "UNRATE CPIAUCSL CPILFESL FEDFUNDS MORTGAGE30US TERMCBCCALLNS REVOLSL PSAVERT "
        "TDSP DRCCLACBS UMCSENT USREC GASREGW CES0500000003 DSPIC96").split()}
    meta_raw = json.loads((data_dir / "fetch_meta.json").read_text())

    cpi = S["CPIAUCSL"].yoy_pct()
    core = S["CPILFESL"].yoy_pct()
    wages = S["CES0500000003"].yoy_pct()
    ff, ur = S["FEDFUNDS"], S["UNRATE"]

    out = {"title": TITLE, "slug": SLUG, "description": DESCRIPTION,
           "fetched": meta_raw.get("fetched"), "sections": {}}
    sec = out["sections"]

    # ------------------------------------------------------------------ hero
    cpi_h, core_h, ff_h, ur_h = (s.since(HERO_START) for s in (cpi, core, ff, ur))
    last_cpi = cpi_h.last
    jan = cpi.get(f"{last_cpi[0][:4]}-01-01")
    ff_now = ff.last
    ff_prev_change = _last_change(ff)
    cpi_peak = cpi_h.max()
    ur_peak = ur_h.max()
    phases = [{"start": a, "end": (cpi_h.last[0] if b == "latest" else b), "label": l}
              for a, b, l in PHASES]

    direction = "rising again" if jan is not None and last_cpi[1] > jan + 0.25 else (
        "cooling" if jan is not None and last_cpi[1] < jan - 0.25 else "holding steady")
    hero_head = f"Inflation is {direction}."
    hero_sub = (f"Consumer prices rose {pct(last_cpi[1])} in the year to {month_label(last_cpi[0])}"
                + (f", up from {pct(jan)} in January" if jan is not None and direction != "holding steady" else "")
                + f". Unemployment is {pct(ur.last[1])}, and the Fed's policy rate is {pct(ff_now[1], 2)}.")
    if ff_prev_change and ff_prev_change.get("previous_same_dir"):
        verb = "rising" if ff_prev_change["direction"] == "up" else "falling"
        noun = "increase" if ff_prev_change["direction"] == "up" else "decrease"
        hero_sub += (f" The rate started {verb} in {month_label(ff_prev_change['run_start'])}, its first "
                     f"{noun} since {month_label(ff_prev_change['previous_same_dir'])}.")
    sec["hero"] = {
        "headline": hero_head, "sub": hero_sub,
        "series": {"cpi": cpi_h.rows(), "core": core_h.rows(), "fedfunds": ff_h.rows(), "unrate": ur_h.rows()},
        "phases": phases,
        "notes": [
            {"date": cpi_peak[0], "value": round(cpi_peak[1], 1), "series": "cpi",
             "text": f"Inflation peaks at {pct(cpi_peak[1])}"},
            {"date": ur_peak[0], "value": ur_peak[1], "series": "unrate",
             "text": f"Unemployment hits {pct(ur_peak[1])}", "position": "right", "offset": [0, 34]},
            {"date": ff_h.max()[0], "value": round(ff_h.max()[1], 2), "series": "fedfunds",
             "text": f"Policy rate tops out at {pct(ff_h.max()[1], 2)}"},
        ],
        "source": _src(S, ["CPIAUCSL", "CPILFESL", "FEDFUNDS", "UNRATE"], meta_raw),
    }

    # ------------------------------------------------------------------ KPIs
    gas = S["GASREGW"]
    tiles = [
        # full = the year-over-year change that earns the strongest color (see viz.deltaBadge)
        _tile("Unemployment rate", ur, "pct1", good_up=False, unit="pp", full=0.6),
        _tile_from_derived("Inflation (CPI, year over year)", cpi, "CPIAUCSL", good_up=False, full=1.5),
        _tile("Fed funds rate", ff, "pct2", good_up=None, unit="pp", full=1.0),
        _tile("30-year mortgage rate", S["MORTGAGE30US"], "pct2", good_up=False, unit="pp", weekly=True, full=1.0),
        _tile("Credit card APR", S["TERMCBCCALLNS"], "pct2", good_up=False, unit="pp", full=1.0),
        _tile("Personal saving rate", S["PSAVERT"], "pct1", good_up=True, unit="pp", full=1.5),
        _tile("Regular gas, per gallon", gas, "usd", good_up=False, unit="pct", weekly=True, full=25),
        _tile("Consumer sentiment", S["UMCSENT"], "num1", good_up=True, unit="pct", full=15),
    ]
    sec["kpis"] = {"headline": "Eight numbers that define the consumer right now.",
                   "tiles": tiles,
                   "source": _src(S, ["UNRATE", "CPIAUCSL", "FEDFUNDS", "MORTGAGE30US", "TERMCBCCALLNS",
                                      "PSAVERT", "GASREGW", "UMCSENT"], meta_raw)}

    # ------------------------------------------------------------------ wages vs prices
    w_h, c_h = wages.since(HERO_START), cpi.since(HERO_START)
    gap = [(d, w - c_h.map[d]) for d, w in w_h.obs if d in c_h.map]
    streak, since = _negative_streak(gap)
    lw, lc = w_h.last, c_h.map.get(w_h.last[0])
    if streak >= 2:
        wage_head = f"Real wages have fallen for {streak} straight months."
    elif gap and gap[-1][1] < 0:
        wage_head = "Prices are outrunning paychecks again."
    else:
        wage_head = "Paychecks are outpacing prices."
    wage_sub = f"Hourly pay is up {pct(lw[1])} from a year earlier, against prices up {pct(lc)}."
    if streak >= 2 and since:
        wage_sub += f" The last run at least this long ended in {month_label(since)}."
    # Stimulus checks show up in disposable income, not in hourly wages.
    dpi = S["DSPIC96"]
    mom = [(d, (v / dpi.obs[i - 1][1] - 1) * 100) for i, (d, v) in enumerate(dpi.obs) if i]
    spikes = [(d, round(v, 1)) for d, v in mom if v >= 5]
    sec["wages"] = {
        "headline": wage_head, "sub": wage_sub,
        "series": {"wages": w_h.rows(), "cpi": c_h.rows()},
        "footnote": ("Stimulus checks are not in these lines: this chart is hourly pay only. The checks show up "
                     "in real disposable income instead, which jumped "
                     + ", ".join(f"{v:+.1f}% in {month_label(d)}" for d, v in spikes)
                     + " month over month." + (" There is no such jump in the latest data." if spikes and spikes[-1][0] < "2024-01-01" else "")),
        "source": _src(S, ["CES0500000003", "CPIAUCSL", "DSPIC96"], meta_raw),
    }

    # ------------------------------------------------------------------ the squeeze
    apr, rev, sav = S["TERMCBCCALLNS"], S["REVOLSL"], S["PSAVERT"]
    apr_max = apr.max()
    sav_w = sav.since(WINDOW_START)
    sav_low_since = sav.lowest_since()
    rev_w = rev.since(WINDOW_START)
    # Largest one-month fall since 2022 (the pandemic paydown in 2020 was real, not a data quirk).
    drops = [(d, (v - rev_w.obs[i - 1][1]) / 1000) for i, (d, v) in enumerate(rev_w.obs)
             if i and d >= "2022-01-01"]
    big_drop = min(drops, key=lambda x: x[1])
    squeeze_head = ("Borrowing costs near a record, savings thinning."
                    if apr.last[1] >= apr_max[1] - 1 and sav.last[1] < sav.mean_between("2014-01-01", "2019-12-01")
                    else "Borrowing costs and savings, side by side.")
    squeeze_sub = (f"Card APRs are {pct(apr.last[1], 2)}, {apr_max[1] - apr.last[1]:.2f} points below the record "
                   f"{pct(apr_max[1], 2)} set in {month_label(apr_max[0])}. Revolving balances are "
                   f"${rev.last[1] / 1e6:.2f} trillion. The saving rate is {pct(sav.last[1])}"
                   + (f", the lowest since {month_label(sav_low_since)}." if sav_low_since else ", a record low."))
    sec["squeeze"] = {
        "headline": squeeze_head, "sub": squeeze_sub,
        "panels": [
            {"key": "apr", "title": "Credit card APR", "fmt": "pct2", "rows": apr.since("1994-01-01").rows(),
             "note": {"date": apr_max[0], "value": apr_max[1], "text": f"Record {pct(apr_max[1], 2)}"}},
            {"key": "rev", "title": "Revolving credit outstanding", "fmt": "tn",
             "rows": [[d, round(v / 1e6, 3)] for d, v in rev_w.obs],
             "note": ({"date": big_drop[0], "value": round(rev.get(big_drop[0]) / 1e6, 3),
                       "text": f"-${-big_drop[1]:.0f}B in one month ({month_label(big_drop[0])})"}
                      if big_drop[1] < -30 else None)},
            {"key": "sav", "title": "Personal saving rate", "fmt": "pct1", "rows": sav_w.rows(1),
             "note": {"date": sav_w.max()[0], "value": sav_w.max()[1], "text": f"Pandemic high {pct(sav_w.max()[1])}"}},
        ],
        "source": _src(S, ["TERMCBCCALLNS", "REVOLSL", "PSAVERT"], meta_raw),
    }

    # ------------------------------------------------------------------ delinquency
    dq, tdsp = S["DRCCLACBS"], S["TDSP"]
    dq_streak = dq.decline_streak()
    avg19 = dq.mean_between("2019-01-01", "2019-12-31")
    dq_peak = dq.max()
    if dq_streak >= 2:
        dq_head = f"Card delinquencies have fallen {dq_streak} quarters in a row."
    else:
        dq_head = "Card delinquencies, three decades of context."
    dq_sub = (f"{pct(dq.last[1], 2)} of card balances were 30+ days past due in {quarter_label(dq.last[0])}"
              + (f", still above the 2019 average of {pct(avg19, 2)}." if dq.last[1] > avg19 else
                 f", below the 2019 average of {pct(avg19, 2)}."))
    tdsp19 = tdsp.mean_between("2019-01-01", "2019-12-31")
    sec["delinq"] = {
        "headline": dq_head, "sub": dq_sub,
        "rows": dq.rows(), "avg2019": round(avg19, 2),
        "note": {"date": dq_peak[0], "value": dq_peak[1], "text": f"Peak {pct(dq_peak[1], 2)}, {quarter_label(dq_peak[0])}"},
        "recessions": spans(S["USREC"].since("1991-01-01")),
        "stats": [
            {"label": "Delinquency rate", "value": pct(dq.last[1], 2), "when": quarter_label(dq.last[0])},
            {"label": "2019 average", "value": pct(avg19, 2), "when": "pre-pandemic baseline"},
            {"label": "Debt payments / disposable income", "value": pct(tdsp.last[1], 1),
             "when": f"{quarter_label(tdsp.last[0])} (2019: {pct(tdsp19, 1)})"},
        ],
        "source": _src(S, ["DRCCLACBS", "TDSP", "USREC"], meta_raw),
    }

    # ------------------------------------------------------------------ sentiment
    um = S["UMCSENT"]
    low = um.min()
    year = um.last[0][:4]
    bottom5 = sorted(um.obs, key=lambda x: x[1])[:5]
    n_this_year = sum(1 for d, _ in bottom5 if d[:4] == year)
    first = um.obs[0][0][:4]
    span_years = int(um.last[0][:4]) - int(first)
    if low[0][:4] >= str(int(year) - 1):
        sent_head = f"Consumer sentiment hit {low[1]:.1f}, the lowest in {span_years} years of records."
    else:
        sent_head = f"{span_years} years of consumer sentiment."
    sent_sub = (f"The University of Michigan index has run since {first}. Its record low of {low[1]:.1f} came in "
                f"{month_label(low[0])}." + (f" {_count_word(n_this_year)} of the five lowest readings ever came in {year}."
                                              if n_this_year >= 2 else "")
                + f" The latest reading is {um.last[1]:.1f} ({month_label(um.last[0])}).")
    sec["sentiment"] = {
        "headline": sent_head, "sub": sent_sub,
        "rows": um.rows(1), "recessions": spans(S["USREC"]),
        "note": {"date": low[0], "value": low[1], "text": f"Record low {low[1]:.1f}"},
        "source": _src(S, ["UMCSENT", "USREC"], meta_raw),
    }

    # ------------------------------------------------------------------ household spending (Sankey)
    sec["sankey"] = _sankey(json.loads((data_dir / "bls_ce.json").read_text()), meta_raw)

    # ------------------------------------------------------------------ methodology
    sources = json.loads((Path(__file__).parent / "sources.json").read_text())
    out["series_index"] = [
        {"id": sid, "name": spec["name"], "latest": meta_raw["fred"].get(sid, {}).get("latest")}
        for sid, spec in sources["fred"].items() if not sid.startswith("_")]
    out["hub_headline"] = hero_head + " " + wage_head
    return out


# ---------------------------------------------------------------------- helpers
def _src(S, ids, meta):
    return {"ids": ids, "latest": {i: S[i].last[0] for i in ids}, "fetched": meta.get("fetched")}


def _fmt(v, kind):
    return {"pct1": f"{v:.1f}%", "pct2": f"{v:.2f}%", "usd": f"${v:.2f}", "num1": f"{v:.1f}"}[kind]


def _when(d, weekly):
    return f"week of {day_label(d)}" if weekly else month_label(d)


def _tile(label, s, kind, good_up, unit, weekly=False, full=1.0):
    d, v = s.last
    ago = s.year_ago()
    delta = None
    if ago:
        if unit == "pp":
            delta = {"value": round(v - ago[1], 2), "text": f"{v - ago[1]:+.2f} pt"}
        else:
            delta = {"value": round((v / ago[1] - 1) * 100, 1), "text": f"{(v / ago[1] - 1) * 100:+.1f}%"}
    spark_src = s.monthly_mean() if weekly else s
    spark = [[dd, round(vv, 2)] for dd, vv in spark_src.obs[-25:]]
    if delta:
        delta["full"] = full
    return {"label": label, "value": _fmt(v, kind), "when": _when(d, weekly), "delta": delta,
            "good_up": good_up, "spark": spark, "id": s.id}


def _tile_from_derived(label, yoy, sid, good_up, full=1.0):
    d, v = yoy.last
    ago = yoy.get(f"{int(d[:4]) - 1}{d[4:]}")
    delta = ({"value": round(v - ago, 2), "text": f"{v - ago:+.2f} pt", "full": full}
             if ago is not None else None)
    return {"label": label, "value": f"{v:.1f}%", "when": month_label(d), "delta": delta,
            "good_up": good_up, "spark": [[dd, round(vv, 2)] for dd, vv in yoy.obs[-25:]], "id": sid}


def _last_change(s):
    """Latest month-over-month move of >= 0.1 pt, and the previous move in the same direction."""
    moves = [(s.obs[i][0], s.obs[i][1] - s.obs[i - 1][1]) for i in range(1, len(s.obs))]
    moves = [(d, m) for d, m in moves if abs(m) >= 0.1]
    if not moves:
        return None
    d, m = moves[-1]
    up = m > 0
    direction = "up" if up else "down"
    # walk back over the current run of same-direction moves
    i = len(moves) - 1
    while i > 0 and (moves[i - 1][1] > 0) == up:
        i -= 1
    run_start = moves[i][0]
    prev = next((pd for pd, pm in reversed(moves[:i]) if (pm > 0) == up), None)
    # only worth saying when the previous same-direction move was more than a year earlier
    months = lambda x: int(x[:4]) * 12 + int(x[5:7])
    gap_ok = prev is not None and months(run_start) - months(prev) > 12
    return {"date": d, "direction": direction, "run_start": run_start,
            "previous_same_dir": prev if gap_ok else None}


def _negative_streak(gap):
    n = 0
    for _, g in reversed(gap):
        if g < 0:
            n += 1
        else:
            break
    if n == 0:
        return 0, None
    rest = gap[:-n]
    # longest earlier run that is at least as long, most recent first
    run = 0
    for i in range(len(rest) - 1, -1, -1):
        if rest[i][1] < 0:
            run += 1
            if run >= n:
                # find the end of this run
                j = i
                while j + 1 < len(rest) and rest[j + 1][1] < 0:
                    j += 1
                return n, rest[j][0]
        else:
            run = 0
    return n, None


def _count_word(n):
    return ["None", "One", "Two", "Three", "Four", "Five"][n]


SANKEY_GROUPS = [
    ("Housing", "CXUHOUSINGLB0101M", [("Shelter", "CXUSHELTERLB0101M"),
                                      ("Utilities & fuels", "CXUUTILSLB0101M")]),
    ("Transportation", "CXUTRANSLB0101M", [("Vehicle purchases", "CXUVEHPURCHLB0101M"),
                                           ("Public & other transport", "CXUPUBTRANSLB0101M")]),
    ("Food", "CXUFOODTOTLLB0101M", [("Groceries", "CXUFOODHOMELB0101M"),
                                    ("Eating out", "CXUFOODAWAYLB0101M")]),
    ("Insurance & pensions", "CXUINSPENSNLB0101M", []),
    ("Healthcare", "CXUHEALTHLB0101M", []),
    ("Entertainment", "CXUENTRTAINLB0101M", []),
    ("Cash gifts & donations", "CXUCASHCONTLB0101M", []),
    ("Clothing", "CXUAPPARELLB0101M", []),
]
REMAINDER_LABEL = {"Housing": "Furnishings, supplies & services",
                   "Transportation": "Gas, upkeep & insurance (derived)"}


def _sankey(ce, meta):
    total_id = "CXUTOTALEXPLB0101M"
    years = sorted(y for y in ce[total_id] if all(y in ce.get(g[1], {}) for g in SANKEY_GROUPS))
    yr, prev = years[-1], (years[-2] if len(years) > 1 else None)

    def val(sid, y):
        return ce.get(sid, {}).get(y)

    total = val(total_id, yr)

    def chg(v, pv):
        return round((v / pv - 1) * 100, 1) if v is not None and pv else None

    nodes, links, rows = [{"name": "Average household"}], [], []
    named = 0
    for name, sid, kids in SANKEY_GROUPS:
        v = val(sid, yr)
        pv = val(sid, prev) if prev else None
        named += v
        nodes.append({"name": name})
        links.append({"source": "Average household", "target": name, "value": v})
        row = {"name": name, "value": v, "share": round(v / total * 100, 1), "change": chg(v, pv), "children": []}
        if kids:
            kid_sum = kid_prev = 0
            for kname, kid in kids:
                kv = val(kid, yr)
                if kv is None:
                    continue
                kpv = val(kid, prev) if prev else None
                kid_sum += kv
                kid_prev += kpv or 0
                nodes.append({"name": kname})
                links.append({"source": name, "target": kname, "value": kv})
                row["children"].append({"name": kname, "value": kv, "share": round(kv / total * 100, 1),
                                        "change": chg(kv, kpv)})
            rem = v - kid_sum
            if name in REMAINDER_LABEL and rem > 0:
                rlabel = REMAINDER_LABEL[name]
                nodes.append({"name": rlabel})
                links.append({"source": name, "target": rlabel, "value": rem})
                rprev = (pv - kid_prev) if pv and kid_prev else None
                row["children"].append({"name": rlabel, "value": rem, "share": round(rem / total * 100, 1),
                                        "change": chg(rem, rprev)})
            row["children"].sort(key=lambda c: -c["value"])
        rows.append(row)
    other = total - named
    nodes.append({"name": "Everything else"})
    links.append({"source": "Average household", "target": "Everything else", "value": other})
    ptotal = val(total_id, prev) if prev else None
    pother = (ptotal - sum(val(g[1], prev) for g in SANKEY_GROUPS)) if ptotal else None
    rows.sort(key=lambda r: -r["value"])
    rows.append({"name": "Everything else", "value": other, "share": round(other / total * 100, 1),
                 "change": chg(other, pother), "children": []})  # always last
    big3 = sum(val(g[1], yr) for g in SANKEY_GROUPS[:3]) / total * 100
    return {
        "year": yr, "prev": prev, "total": total,
        "headline": f"Where the average household's ${total:,.0f} went in {yr}.",
        "sub": (f"Housing, transportation and food took {big3:.0f}% of spending."
                + (f" Total spending was {((total / ptotal - 1) * 100):+.1f}% vs {prev}." if ptotal else "")),
        "listTitle": "Every category, ranked",
        "nodes": nodes, "links": links, "rows": rows,
        # spending more on a category = costlier for households, so up is "worse"
        "good_up": False, "full": 8,
        "notes": [f"{REMAINDER_LABEL['Transportation']} is transportation minus vehicle purchases and public & other "
                  "transport. BLS's separate gasoline line has no usable values after 2022.",
                  "\"Everything else\" is total spending minus the named groups (education, personal care, "
                  "reading, tobacco, alcohol and miscellaneous)."],
        "source": {"ids": [total_id] + [g[1] for g in SANKEY_GROUPS], "latest": {total_id: f"{yr} annual"},
                   "fetched": meta.get("bls_ce", {}).get("fetched"), "via": meta.get("bls_ce", {}).get("source")},
    }
