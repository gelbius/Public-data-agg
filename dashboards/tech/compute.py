"""Dashboard 03 - Tech valuations & deals.

Public companies: prices/market caps from a manual snapshot (data/tech/prices_snapshot.json),
financials from SEC filings. Multiples use the trailing 12 months (TTM) of reported results.
Deals and private valuations: curated, sourced lists (data/tech/deals.json, private.json).
Every number and headline on the page is computed here.
"""
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fin  # noqa: E402

from series import day_label, month_label  # noqa: E402

TITLE = "Tech Valuations & Deals"
SLUG = "tech"
ORDER = 3
DESCRIPTION = ("What public tech companies are worth relative to their revenue and earnings, how sector multiples are "
               "trending, today's moves, notable deals and what investors are saying.")

NAMES = {"GOOGL": "Alphabet", "META": "Meta", "MSFT": "Microsoft", "AMZN": "Amazon", "AAPL": "Apple", "ORCL": "Oracle",
         "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "MU": "Micron", "MRVL": "Marvell", "ANET": "Arista",
         "VRT": "Vertiv", "CRWV": "CoreWeave", "SMCI": "Super Micro", "DELL": "Dell", "HPQ": "HP Inc", "HPE": "HPE",
         "CSCO": "Cisco", "WDC": "Western Digital", "STX": "Seagate", "CRM": "Salesforce", "NOW": "ServiceNow",
         "ADBE": "Adobe", "PLTR": "Palantir", "SNOW": "Snowflake", "DDOG": "Datadog", "INTU": "Intuit",
         "NFLX": "Netflix", "MTCH": "Match Group", "BMBL": "Bumble", "DUOL": "Duolingo", "GRND": "Grindr",
         "LIF": "Life360", "COUR": "Coursera", "CHGG": "Chegg", "PTON": "Peloton", "HIMS": "Hims & Hers",
         "ETSY": "Etsy", "TRIP": "Tripadvisor", "YELP": "Yelp", "ANGI": "Angi", "CMPR": "Cimpress", "NXDR": "Nextdoor",
         "INTC": "Intel", "QCOM": "Qualcomm", "TXN": "Texas Instruments", "ADI": "Analog Devices", "AMAT": "Applied Materials",
         "LRCX": "Lam Research", "KLAC": "KLA", "PANW": "Palo Alto Networks", "CRWD": "CrowdStrike", "FTNT": "Fortinet",
         "WDAY": "Workday", "ADSK": "Autodesk", "APP": "AppLovin", "NET": "Cloudflare", "IBM": "IBM", "UBER": "Uber",
         "ABNB": "Airbnb", "BKNG": "Booking Holdings", "DASH": "DoorDash"}
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
REPORT_LAG = 35  # days after a quarter ends before its results are assumed public


def _div(a, b):
    return a / b if (a is not None and b not in (None, 0)) else None


def _pos_multiple(ev, x):
    """EV / x, only when x is positive (a negative denominator makes the multiple meaningless)."""
    return ev / x if (ev is not None and x is not None and x > 0) else None


def _med(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None


def _metrics(facts, mcap, asof):
    lag = (date.fromisoformat(asof) - timedelta(days=REPORT_LAG)).isoformat()
    f = fin.financials(facts, lag)
    if not f:
        return None
    ev = mcap + f["bs_debt"] - (f["bs_cash"] or 0)
    return {"ttm_end": f["ttm_end"], "revenue": f["revenue"], "ebitda": f["ebitda"], "net_income": f["net_income"],
            "ev": ev, "ev_rev": _pos_multiple(ev, f["revenue"]), "ev_ebitda": _pos_multiple(ev, f["ebitda"]),
            "pe": _pos_multiple(mcap, f["net_income"]),
            "growth": (_div(f["revenue"], f["revenue_prev"]) - 1) * 100 if f["revenue_prev"] else None,
            "margin": _div(f["ebitda"], f["revenue"]) * 100 if f["ebitda"] is not None else None,
            "cash": f["bs_cash"], "debt": f["bs_debt"], "debt_found": f["bs_debt_found"], "da_partial": f["da_partial"]}


def _deal_row(dl, data_dir):
    """A deal plus, for SEC-filing targets, the target's TTM financials and implied multiples before announcement."""
    row = dict(dl)
    t = dl.get("target_ticker")
    if t and (data_dir / "sec" / f"{t}.json").exists() and dl["value"]:
        facts = json.loads((data_dir / "sec" / f"{t}.json").read_text())["facts"]
        lag = (date.fromisoformat(dl["date"]) - timedelta(days=REPORT_LAG)).isoformat()
        f = fin.financials(facts, lag)
        if f:
            ev = dl["value"] if dl["value_kind"] == "ev" else dl["value"] + f["bs_debt"] - (f["bs_cash"] or 0)
            row.update({"ev": ev, "ev_is_derived": dl["value_kind"] != "ev",
                        "target_revenue": f["revenue"], "target_ebitda": f["ebitda"],
                        "target_margin": _div(f["ebitda"], f["revenue"]) * 100 if f["ebitda"] is not None else None,
                        "ev_rev": _pos_multiple(ev, f["revenue"]), "ev_ebitda": _pos_multiple(ev, f["ebitda"]),
                        "ttm_end": f["ttm_end"], "da_partial": f["da_partial"]})
    elif dl["value_kind"] == "ev":
        row["ev"] = dl["value"]
    return row


def _money(v):
    return f"${v / 1e9:,.1f}B" if v >= 1e9 else f"${v / 1e6:,.0f}M"


def _funding_note(f):
    """'Raised about $200M before the deal; key investors: A, B, C.' from the deal's funding record."""
    if not f:
        return ""
    if f.get("range"):
        amt = f"between {_money(f['range'][0])} and {_money(f['range'][1])} (trackers disagree)"
    else:
        amt = ("about " if f.get("approx") else "") + _money(f["total"])
    inv = f"; key investors: {', '.join(f['investors'])}" if f.get("investors") else ""
    return f"Raised {amt} before the deal{inv}."


def compute(data_dir):
    data_dir = Path(data_dir)
    src = json.loads((Path(__file__).parent / "sources.json").read_text())
    snap = json.loads((data_dir / "prices_snapshot.json").read_text())
    D = snap["dates"]
    as_of = snap["as_of"]
    cat_of = {t: c for c, ts in src["categories"].items() for t in ts}

    companies, history = [], {}  # history: ticker -> {date: (ev_rev, ev_ebitda)}
    for t, p in snap["companies"].items():
        sec_path = data_dir / "sec" / f"{t}.json"
        if t not in cat_of or not sec_path.exists():
            continue
        facts = json.loads(sec_path.read_text())["facts"]
        now = _metrics(facts, p["market_cap"], D["now"])
        if not now:
            continue
        hist = {}
        for k in ("6m", "12m"):
            mcap_then = p["shares"] * p[f"close_{k}"]  # today's share count x the split-adjusted price then
            hist[k] = _metrics(facts, mcap_then, D[k])
        h = {}
        for d, close in (p.get("monthly") or {}).items():
            m = _metrics(facts, p["shares"] * close, d)
            if m:
                h[d] = (m["ev_rev"], m["ev_ebitda"])
        h[D["now"]] = (now["ev_rev"], now["ev_ebitda"])
        history[t] = h
        chg = {k: (p["close_now"] / p[f"close_{k}"] - 1) * 100 for k in ("6m", "12m")}
        chg["1d"] = (p["close_now"] / p["close_prev"] - 1) * 100 if p.get("close_prev") else None
        mult_chg = {k: {"ev_rev": (now["ev_rev"] - hist[k]["ev_rev"]) if (hist[k] and now["ev_rev"] and hist[k]["ev_rev"]) else None,
                        "ev_ebitda": (now["ev_ebitda"] - hist[k]["ev_ebitda"]) if (hist[k] and now["ev_ebitda"] and hist[k]["ev_ebitda"]) else None}
                    for k in ("6m", "12m")}
        companies.append({"ticker": t, "name": NAMES.get(t, t), "category": cat_of[t], "market_cap": p["market_cap"],
                          **now, "chg": chg, "mult_chg": mult_chg,
                          "hist": {k: ({"ev_rev": x["ev_rev"], "ev_ebitda": x["ev_ebitda"]} if x else None) for k, x in hist.items()}})

    # ---- sector multiples over time: category medians at each month-end and today
    dates = sorted({d for h in history.values() for d in h})
    def med_series(members, i):
        rows = []
        for d in dates:
            v = _med(history[t][d][i] for t in members if d in history[t])
            if v is not None:
                rows.append([d, round(v, 3)])
        return rows
    cat_names = list(src["categories"])
    members = {c: [x["ticker"] for x in companies if x["category"] == c] for c in cat_names}
    trend = {"ev_rev": {c: med_series(members[c], 0) for c in cat_names},
             "ev_ebitda": {c: med_series(members[c], 1) for c in cat_names}}
    allm = [x["ticker"] for x in companies]
    trend["ev_rev"]["All companies"] = med_series(allm, 0)
    trend["ev_ebitda"]["All companies"] = med_series(allm, 1)

    # ---- category summary (medians, so one outlier can't swing a category)
    cats = []
    for cname in cat_names:
        cs = [c for c in companies if c["category"] == cname]
        mc_now = sum(c["market_cap"] for c in cs)
        mc_then = {k: sum(c["market_cap"] / (1 + c["chg"][k] / 100) for c in cs) for k in ("1d", "6m", "12m")}
        r12 = trend["ev_rev"][cname]
        cats.append({"name": cname, "n": len(cs),
                     "ev_rev": {"now": _med(c["ev_rev"] for c in cs), "12m_ago": r12[0][1] if r12 else None},
                     "ev_ebitda": {"now": _med(c["ev_ebitda"] for c in cs)},
                     "value_chg": {k: (mc_now / mc_then[k] - 1) * 100 for k in ("1d", "6m", "12m")}})

    # ---- top summary: how multiples have trended
    ev_all = trend["ev_rev"]["All companies"]
    first, last = ev_all[0], ev_all[-1]
    peak = max(ev_all, key=lambda r: r[1])
    moved = [(c["name"], c["ev_rev"]["now"] / c["ev_rev"]["12m_ago"] - 1) for c in cats if c["ev_rev"]["now"] and c["ev_rev"]["12m_ago"]]
    up_c, down_c = max(moved, key=lambda x: x[1]), min(moved, key=lambda x: x[1])
    cheaper = sum(1 for _, x in moved if x < 0)
    headline = (f"Tech multiples have {'compressed' if last[1] < first[1] else 'expanded'} over the past year: the median company "
                f"trades at {last[1]:.1f}× revenue, {'down' if last[1] < first[1] else 'up'} from {first[1]:.1f}×.")
    sub = (f"{cheaper} of {len(moved)} sectors got cheaper. Biggest {'drop' if down_c[1] < 0 else 'rise'}: {down_c[0]} "
           f"({down_c[1] * 100:+.0f}%). {up_c[0]} {'rose most' if up_c[1] > 0 else 'fell least'} ({up_c[1] * 100:+.0f}%). "
           f"Peak: {peak[1]:.1f}× in {month_label(peak[0])}.")

    # ---- public comps: summary of the day
    tot_now = sum(c["market_cap"] for c in companies)
    tot_prev = sum(c["market_cap"] / (1 + c["chg"]["1d"] / 100) for c in companies if c["chg"]["1d"] is not None)
    day_total = (tot_now / tot_prev - 1) * 100
    day_med = _med(c["chg"]["1d"] for c in companies)
    ups = sum(1 for c in companies if (c["chg"]["1d"] or 0) > 0)
    movers = [c for c in companies if c["chg"]["1d"] is not None]
    top, bot = max(movers, key=lambda c: c["chg"]["1d"]), min(movers, key=lambda c: c["chg"]["1d"])
    cbest = max(cats, key=lambda c: c["value_chg"]["1d"])
    cworst = min(cats, key=lambda c: c["value_chg"]["1d"])
    word = "rose" if day_total >= 0 else "fell"
    comp_head = (f"{day_label(as_of)}: tech stocks {word} {abs(day_total):.1f}%, with {ups} of {len(companies)} up. "
                 f"{bot['name'] if day_total < 0 else top['name']} {'fell' if day_total < 0 else 'rose'} most "
                 f"({(bot if day_total < 0 else top)['chg']['1d']:+.1f}%).")
    comp_sub = (f"Combined value of the {len(companies)} companies; median move {day_med:+.1f}%. "
                f"Best sector: {cbest['name']} ({cbest['value_chg']['1d']:+.1f}%). Weakest: {cworst['name']} ({cworst['value_chg']['1d']:+.1f}%). "
                f"Biggest {'gainer' if top['chg']['1d'] > 0 else 'riser'}: {top['name']} ({top['chg']['1d']:+.1f}%). "
                f"Financials = latest 12 months reported.")

    # ---- deals (all, newest first); headline covers the last six months
    deals = []
    for dl in json.loads((data_dir / "deals.json").read_text())["deals"]:
        row = _deal_row(dl, data_dir)
        row["funding_note"] = _funding_note(dl.get("funding"))
        deals.append(row)
    deals.sort(key=lambda r: r["date"], reverse=True)
    window_start = (date.fromisoformat(as_of) - timedelta(days=183)).isoformat()
    recent = [r for r in deals if r["date"] >= window_start]
    mna = [r for r in recent if r["type"] != "Venture round"]
    public_multiples = [r["ev_rev"] for r in mna if r.get("ev_rev")]
    biggest = max((r for r in mna if r.get("ev")), key=lambda r: r["ev"])
    total_disclosed = sum(r["ev"] for r in mna if r.get("ev"))
    deal_head = (f"{len(mna)} notable tech acquisitions in six months, led by {biggest['acquirer']}–{biggest['target']} "
                 f"(${biggest['ev'] / 1e9:,.0f}B).")
    deal_sub = (f"Disclosed deal value about ${total_disclosed / 1e9:,.0f}B. Public targets sold at a median "
                f"{_med(public_multiples):.1f}× trailing revenue (range {min(public_multiples):.1f}–{max(public_multiples):.1f}×). "
                f"Plus {len(recent) - len(mna)} mega venture rounds. Older consumer deals are included; filter by date.")

    quotes = json.loads((data_dir / "quotes.json").read_text())["quotes"]
    quotes.sort(key=lambda q: q["date"], reverse=True)
    priv = json.loads((data_dir / "private.json").read_text())["companies"]
    priv.sort(key=lambda r: -(r["valuation"] or 0))

    sec_meta = json.loads((data_dir / "fetch_meta.json").read_text()).get("sec", {}) if (data_dir / "fetch_meta.json").exists() else {}
    return {
        "title": TITLE, "slug": SLUG, "description": DESCRIPTION, "fetched": sec_meta.get("fetched") or as_of,
        "hub_headline": headline,
        "as_of": as_of, "dates": D,
        "sections": {
            "summary": {"headline": headline, "sub": sub, "trend": trend, "categories": cats},
            "companies": {"headline": comp_head, "sub": comp_sub, "rows": companies, "n_categories": len(cat_names)},
            "deals": {"headline": deal_head, "sub": deal_sub, "rows": deals, "window_start": window_start},
            "quotes": {"headline": "What investors are saying about tech valuations.",
                       "sub": "Recent remarks from investors, fund managers and CEOs, quoted word for word with a link to each source.",
                       "rows": quotes},
            "private": {"headline": "The biggest private AI valuations.",
                        "sub": "Set by investors in each round; not directly comparable to public market caps.",
                        "rows": priv},
        },
        "notes": {"sec_fetched": sec_meta.get("fetched"), "report_lag": REPORT_LAG},
    }
