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
DESCRIPTION = ("What public tech companies are worth relative to their revenue and earnings, how that has moved over "
               "6 and 12 months, and the notable deals of the last six months.")

NAMES = {"GOOGL": "Alphabet", "META": "Meta", "MSFT": "Microsoft", "AMZN": "Amazon", "AAPL": "Apple", "ORCL": "Oracle",
         "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "MU": "Micron", "MRVL": "Marvell", "ANET": "Arista",
         "VRT": "Vertiv", "CRWV": "CoreWeave", "SMCI": "Super Micro", "DELL": "Dell", "HPQ": "HP Inc", "HPE": "HPE",
         "CSCO": "Cisco", "WDC": "Western Digital", "STX": "Seagate", "CRM": "Salesforce", "NOW": "ServiceNow",
         "ADBE": "Adobe", "PLTR": "Palantir", "SNOW": "Snowflake", "DDOG": "Datadog", "INTU": "Intuit",
         "NFLX": "Netflix", "MTCH": "Match Group", "BMBL": "Bumble", "DUOL": "Duolingo", "GRND": "Grindr",
         "LIF": "Life360", "COUR": "Coursera", "CHGG": "Chegg"}
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


def compute(data_dir):
    data_dir = Path(data_dir)
    src = json.loads((Path(__file__).parent / "sources.json").read_text())
    snap = json.loads((data_dir / "prices_snapshot.json").read_text())
    D = snap["dates"]
    cat_of = {t: c for c, ts in src["categories"].items() for t in ts}

    companies = []
    for t, p in snap["companies"].items():
        sec_path = data_dir / "sec" / f"{t}.json"
        if not sec_path.exists():
            continue
        facts = json.loads(sec_path.read_text())["facts"]
        now = _metrics(facts, p["market_cap"], D["now"])
        if not now:
            continue
        hist = {}
        for k in ("6m", "12m"):
            mcap_then = p["shares"] * p[f"close_{k}"]  # today's share count x the split-adjusted price then
            hist[k] = _metrics(facts, mcap_then, D[k])
        chg = {k: (p["close_now"] / p[f"close_{k}"] - 1) * 100 for k in ("6m", "12m")}
        mult_chg = {k: {"ev_rev": (now["ev_rev"] - hist[k]["ev_rev"]) if (hist[k] and now["ev_rev"] and hist[k]["ev_rev"]) else None,
                        "ev_ebitda": (now["ev_ebitda"] - hist[k]["ev_ebitda"]) if (hist[k] and now["ev_ebitda"] and hist[k]["ev_ebitda"]) else None}
                    for k in ("6m", "12m")}
        companies.append({"ticker": t, "name": NAMES.get(t, t), "category": cat_of.get(t), "market_cap": p["market_cap"],
                          **{k: v for k, v in now.items()}, "chg": chg, "mult_chg": mult_chg,
                          "hist": {k: ({"ev_rev": h["ev_rev"], "ev_ebitda": h["ev_ebitda"]} if h else None) for k, h in hist.items()}})
    companies = [c for c in companies if c["category"]]  # deal targets are not part of the public comp set

    # ---- category summary (medians, so one outlier can't swing a category)
    cats = []
    for cname in src["categories"]:
        cs = [c for c in companies if c["category"] == cname]
        mc_now = sum(c["market_cap"] for c in cs)
        mc_then = {k: sum(c["market_cap"] / (1 + c["chg"][k] / 100) for c in cs) for k in ("6m", "12m")}
        cats.append({"name": cname, "n": len(cs),
                     "ev_rev": {"now": _med(c["ev_rev"] for c in cs),
                                "6m": _med(c["hist"]["6m"] and c["hist"]["6m"]["ev_rev"] for c in cs),
                                "12m": _med(c["hist"]["12m"] and c["hist"]["12m"]["ev_rev"] for c in cs)},
                     "ev_ebitda": {"now": _med(c["ev_ebitda"] for c in cs),
                                   "6m": _med(c["hist"]["6m"] and c["hist"]["6m"]["ev_ebitda"] for c in cs),
                                   "12m": _med(c["hist"]["12m"] and c["hist"]["12m"]["ev_ebitda"] for c in cs)},
                     "growth": _med(c["growth"] for c in cs), "margin": _med(c["margin"] for c in cs),
                     "value_chg": {k: (mc_now / mc_then[k] - 1) * 100 for k in ("6m", "12m")}})

    # ---- overall summary
    all_now = sum(c["market_cap"] for c in companies)
    all_then = {k: sum(c["market_cap"] / (1 + c["chg"][k] / 100) for c in companies) for k in ("6m", "12m")}
    total_chg = {k: (all_now / all_then[k] - 1) * 100 for k in ("6m", "12m")}
    med_chg = {k: _med(c["chg"][k] for c in companies) for k in ("6m", "12m")}
    up6 = sum(1 for c in companies if c["chg"]["6m"] > 0)
    med_evrev = {k: _med((c["ev_rev"] if k == "now" else (c["hist"][k] and c["hist"][k]["ev_rev"])) for c in companies)
                 for k in ("now", "6m", "12m")}
    best = max(cats, key=lambda c: c["value_chg"]["6m"])
    worst = min(cats, key=lambda c: c["value_chg"]["6m"])
    direction = "fell" if med_chg["6m"] < 0 else "rose"
    headline = (f"Over six months, the typical tech stock here {direction} {abs(med_chg['6m']):.0f}%; "
                f"the group's combined value {'rose' if total_chg['6m'] >= 0 else 'fell'} {abs(total_chg['6m']):.0f}%.")
    sub = (f"{up6} of {len(companies)} companies are up. {best['name']} led ({best['value_chg']['6m']:+.0f}%), "
           f"{worst['name']} lagged ({worst['value_chg']['6m']:+.0f}%). Median EV/revenue: "
           f"{med_evrev['12m']:.1f}× a year ago, {med_evrev['6m']:.1f}× six months ago, {med_evrev['now']:.1f}× now.")

    # ---- deals: compute multiples for public targets from their pre-announcement filings
    deals_src = json.loads((data_dir / "deals.json").read_text())
    deals = []
    for dl in deals_src["deals"]:
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
        deals.append(row)
    deals.sort(key=lambda r: r["date"], reverse=True)
    mna = [r for r in deals if r["type"] != "Venture round"]
    public_multiples = [r["ev_rev"] for r in mna if r.get("ev_rev")]
    biggest = max((r for r in mna if r.get("ev")), key=lambda r: r["ev"])
    total_disclosed = sum(r["ev"] for r in mna if r.get("ev"))
    deal_head = (f"{len(mna)} notable tech acquisitions in six months, led by {biggest['acquirer']}–{biggest['target']} "
                 f"(${biggest['ev'] / 1e9:,.0f}B).")
    deal_sub = (f"Disclosed deal value about ${total_disclosed / 1e9:,.0f}B. Public targets sold at a median "
                f"{_med(public_multiples):.1f}× trailing revenue (range {min(public_multiples):.1f}–{max(public_multiples):.1f}×). "
                f"Plus {len(deals) - len(mna)} mega venture rounds.")

    priv = json.loads((data_dir / "private.json").read_text())["companies"]
    priv.sort(key=lambda r: -(r["valuation"] or 0))

    as_of = snap["as_of"]
    sec_meta = json.loads((data_dir / "fetch_meta.json").read_text()).get("sec", {}) if (data_dir / "fetch_meta.json").exists() else {}
    return {
        "title": TITLE, "slug": SLUG, "description": DESCRIPTION, "fetched": sec_meta.get("fetched") or as_of,
        "hub_headline": headline,
        "as_of": as_of, "dates": D,
        "sections": {
            "summary": {"headline": headline, "sub": sub, "total_chg": total_chg, "med_chg": med_chg,
                        "med_evrev": med_evrev, "categories": cats},
            "companies": {"headline": f"{len(companies)} public companies, five categories.",
                          "sub": f"Prices as of {day_label(as_of)} close; financials = latest 12 months reported.",
                          "rows": companies},
            "deals": {"headline": deal_head, "sub": deal_sub, "rows": deals, "window": deals_src["window"]},
            "private": {"headline": "The biggest private AI valuations.",
                        "sub": "Set by investors in each round; not directly comparable to public market caps.",
                        "rows": priv},
        },
        "notes": {"sec_fetched": sec_meta.get("fetched"), "report_lag": REPORT_LAG},
    }
