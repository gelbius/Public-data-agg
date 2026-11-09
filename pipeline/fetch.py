#!/usr/bin/env python3
"""Download the public data a dashboard needs and save it under data/<dashboard>/.

Usage:  python3 pipeline/fetch.py macro

Reads dashboards/<dashboard>/sources.json and writes:
  data/<dashboard>/fred/<SERIES>.csv     one file per FRED series (date,value)
  data/<dashboard>/bls_ce.json           annual household spending, {series: {year: value}}
  data/<dashboard>/fetch_meta.json       when each source was fetched and its latest observation

Everything here is public and needs no API key. If the optional BLS_API_KEY
environment variable is set, the BLS v2 API is used (higher daily limit).

A failed download never deletes data: the previous file is kept, the failure is
printed, and the script exits non-zero only if a series has no data at all.
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "public-data-agg/1.0 (+https://github.com/gelbius/public-data-agg)"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd={start}"
BLS_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def http_get(url, data=None, headers=None, tries=4, binary=False):
    """GET (or POST when data is given) with simple exponential backoff."""
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
                return body if binary else body.decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == tries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"    retry in {wait}s ({exc})")
            time.sleep(wait)


def parse_fred_csv(text, series_id):
    """FRED CSV -> list of (YYYY-MM-DD, float). Missing values ('.') are skipped."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) < 2 or rows[0][1] != series_id:
        raise ValueError(f"unexpected FRED response for {series_id}: {text[:120]!r}")
    out = []
    for d, v in rows[1:]:
        if v not in ("", "."):
            out.append((d, float(v)))
    return out


def fetch_fred(dash_dir, series, meta):
    fred_dir = dash_dir / "fred"
    fred_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for sid, spec in series.items():
        if sid.startswith("_"):
            continue
        print(f"  FRED {sid}")
        path = fred_dir / f"{sid}.csv"
        try:
            text = http_get(FRED_CSV.format(id=sid, start=spec["start"]))
            obs = parse_fred_csv(text, sid)
            if not obs:
                raise ValueError("no observations")
            with path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "value"])
                w.writerows(obs)
            meta["fred"][sid] = {"fetched": today(), "latest": obs[-1][0], "count": len(obs)}
        except Exception as exc:  # keep the old file, report, move on
            print(f"    FAILED: {exc}")
            failures.append(sid)
            if not path.exists():
                meta["fred"].pop(sid, None)
    return failures


def fetch_bls_ce(dash_dir, series, meta):
    """Annual spending per household. Try BLS directly, then fill gaps from FRED's mirror."""
    ids = [s for s in series if not s.startswith("_")]
    path = dash_dir / "bls_ce.json"
    store = json.loads(path.read_text()) if path.exists() else {}
    this_year = date.today().year

    # 1) BLS API: has the newest year first (FRED's mirror lags by months).
    key = os.environ.get("BLS_API_KEY")
    body = {"seriesid": ids, "startyear": str(this_year - 4), "endyear": str(this_year)}
    if key:
        body["registrationkey"] = key
    source = "none"
    try:
        print(f"  BLS CE via API {'v2' if key else 'v1'} ({len(ids)} series)")
        text = http_get(BLS_V2 if key else BLS_V1, data=json.dumps(body).encode(),
                        headers={"Content-Type": "application/json"}, tries=2)
        res = json.loads(text)
        if res.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError("; ".join(res.get("message", [])) or res.get("status"))
        for s in res["Results"]["series"]:
            for obs in s["data"]:
                if obs.get("period") == "A01":
                    store.setdefault(s["seriesID"], {})[obs["year"]] = float(obs["value"])
        source = "bls"
    except Exception as exc:
        print(f"    BLS unavailable, using FRED mirror instead ({str(exc)[:160]})")

    # 2) FRED mirror: fills any series/years BLS did not return.
    for sid in ids:
        try:
            obs = parse_fred_csv(http_get(FRED_CSV.format(id=sid, start=f"{this_year - 6}-01-01")), sid)
            for d, v in obs:
                store.setdefault(sid, {}).setdefault(d[:4], v)
            if source == "none":
                source = "fred"
        except Exception as exc:
            print(f"    FRED mirror failed for {sid}: {exc}")

    if not store:
        return ids
    path.write_text(json.dumps(store, indent=1, sort_keys=True) + "\n")
    latest = max(max(v) for v in store.values() if v)
    meta["bls_ce"] = {"fetched": today(), "latest_year": latest, "source": source}
    return []


def fetch_btos(dash_dir, spec, meta):
    """Census BTOS workbooks -> data/<dash>/btos.json (only the questions the dashboard uses).
    The raw workbooks are downloaded to a temporary folder and not kept."""
    import tempfile
    import btos
    print("  Census BTOS (National.xlsx, Sector.xlsx)")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            nat, sec = Path(tmp) / "National.xlsx", Path(tmp) / "Sector.xlsx"
            nat.write_bytes(http_get(btos.NATIONAL_URL, binary=True))
            sec.write_bytes(http_get(btos.SECTOR_URL, binary=True) if spec.get("sector") else b"")
            data = btos.extract(nat, sec if spec.get("sector") else None, spec)
    except Exception as exc:  # keep the previous extract; a wording change must be fixed by hand
        print(f"    FAILED: {exc}")
        return ["btos"]
    (dash_dir / "btos.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    codes = sorted({c for q in data["national"].values() for a in q["answers"].values() for c in a})
    meta["btos"] = {"fetched": today(), "latest_wave": codes[-1] if codes else None}
    return []


def fetch_zillow(dash_dir, spec, meta):
    """Zillow Research public CSV -> data/<dash>/zillow_us.csv (the 'United States' row only)."""
    print("  Zillow Research (U.S. median sale price)")
    try:
        rows = list(csv.reader(io.StringIO(http_get(spec["url"]))))
        hdr = rows[0]
        us = next(r for r in rows[1:] if r[hdr.index("RegionName")] == spec.get("region", "United States"))
        obs = [(d, float(v)) for d, v in zip(hdr, us) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and v not in ("",)]
        if len(obs) < 100:
            raise ValueError(f"only {len(obs)} observations")
    except Exception as exc:
        print(f"    FAILED: {exc}")
        return ["zillow"]
    with (dash_dir / "zillow_us.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value"])
        w.writerows(obs)
    meta["zillow"] = {"fetched": today(), "latest": obs[-1][0], "count": len(obs)}
    return []


def fetch_sec(dash_dir, spec, meta):
    """SEC EDGAR financials for the dashboard's tickers -> data/<dash>/sec/<TICKER>.json."""
    import sec
    print(f"  SEC EDGAR company facts ({len(spec['tickers'])} companies)")
    failed = sec.fetch(spec["tickers"], dash_dir / "sec")
    if failed != ["sec"]:
        meta["sec"] = {"fetched": today(), "failed": failed}
    return [] if failed == ["sec"] else []  # missing SEC data keeps old files; compute flags gaps


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    name = args[0]
    sources = json.loads((ROOT / "dashboards" / name / "sources.json").read_text())
    if sources.get("manual_refresh") and "--force" not in sys.argv:
        print(f"'{name}' is refreshed on request (manual snapshot); skipping. Use --force to refresh.")
        return
    dash_dir = ROOT / "data" / name
    dash_dir.mkdir(parents=True, exist_ok=True)
    meta_path = dash_dir / "fetch_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta.setdefault("fred", {})

    print(f"Fetching data for '{name}'")
    failed = fetch_fred(dash_dir, sources.get("fred", {}), meta)
    if "bls_ce" in sources:
        failed += fetch_bls_ce(dash_dir, sources["bls_ce"], meta)
    if "btos" in sources:
        failed += fetch_btos(dash_dir, sources["btos"], meta)
    if "sec" in sources:
        failed += fetch_sec(dash_dir, sources["sec"], meta)
    if "zillow" in sources:
        failed += fetch_zillow(dash_dir, sources["zillow"], meta)
    meta["fetched"] = today()
    meta_path.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")

    files = {"btos": "btos.json", "zillow": "zillow_us.csv"}
    missing = [s for s in failed if not (dash_dir / files.get(s, f"fred/{s}.csv")).exists()]
    if failed:
        print(f"Some downloads failed (kept previous data): {', '.join(failed)}")
    if missing:
        sys.exit(f"No data at all for: {', '.join(missing)}")
    print("Done.")


if __name__ == "__main__":
    main()
