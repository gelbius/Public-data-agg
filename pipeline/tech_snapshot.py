"""Build data/tech/prices_snapshot.json from raw price data, with sanity checks.

Usage:
  python3 pipeline/tech_snapshot.py dates [YYYY-MM-DD]   print the three target dates (now, 6m, 12m)
  python3 pipeline/tech_snapshot.py build RAW.json       validate RAW.json and write the snapshot

RAW.json (written by whoever pulled the prices, e.g. a scheduled Claude session):
  {"as_of": "YYYY-MM-DD",                  # last trading day with a close
   "companies": {"AAPL": {"market_cap": 4.97e12, "shares": 1.45e10,
                          "close_now": 342.37, "close_6m": 287.51, "close_12m": 269.77}, ...}}
Closes must be split-adjusted, taken on the target date or the nearest trading day before it.

The build refuses to write (exit 1) when tickers are missing or a market cap disagrees with
shares x price by more than 5%, so a bad pull never reaches the site.
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tech" / "prices_snapshot.json"
SOURCES = ROOT / "dashboards" / "tech" / "sources.json"
DOC = ("Price snapshot (market cap, shares outstanding, split-adjusted daily closes) pulled through the "
       "owner's brokerage data connector. Refreshed twice a week by a scheduled job.")


def _months_back(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue


def target_dates(asof):
    d = date.fromisoformat(asof)
    return {"12m": _months_back(d, 12).isoformat(), "6m": _months_back(d, 6).isoformat(), "now": asof}


def build(raw_path):
    raw = json.loads(Path(raw_path).read_text())
    src = json.loads(SOURCES.read_text())
    want = sorted(set(src["sec"]["tickers"]) - set(src.get("deal_targets", [])))
    comps = raw["companies"]
    problems = [f"{t}: missing" for t in want if t not in comps]
    out = {}
    for t in want:
        c = comps.get(t)
        if not c:
            continue
        keys = ("market_cap", "shares", "close_now", "close_6m", "close_12m")
        if any(not isinstance(c.get(k), (int, float)) or c[k] <= 0 for k in keys):
            problems.append(f"{t}: missing or non-positive field")
            continue
        implied = c["shares"] * c["close_now"]
        if abs(implied / c["market_cap"] - 1) > 0.05:
            problems.append(f"{t}: market cap {c['market_cap']:.3g} vs shares x price {implied:.3g}")
            continue
        out[t] = {k: c[k] for k in keys}
    if problems:
        print("Snapshot NOT written:\n  " + "\n  ".join(problems))
        sys.exit(1)
    snap = {"_doc": DOC, "as_of": raw["as_of"], "dates": target_dates(raw["as_of"]), "companies": out}
    OUT.write_text(json.dumps(snap, indent=1) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out)} companies as of {raw['as_of']}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "dates":
        print(json.dumps(target_dates(sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat())))
    elif len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
    else:
        sys.exit(__doc__)
