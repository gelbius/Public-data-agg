"""Upcoming official release dates for FRED series, from FRED's public release calendar.

fetch(series_ids, out_path) writes {"fetched": "YYYY-MM-DD", "series": {SID: {"rid", "release", "dates": [...]}}}
where "dates" are the release's scheduled dates from today onward (about 14 months ahead). A series whose lookup
fails keeps its previous entry, so a FRED hiccup never blanks the "Next update" line.
Standard library only.
"""
import html
import json
import re
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

MONTHS = "January February March April May June July August September October November December".split()
DATE_RE = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) (" + "|".join(MONTHS) + r") (\d{1,2}), (20\d\d)")


def _get(url, tries=4):
    """GET with a short pause between requests and backoff on dropped connections (FRED throttles bursts)."""
    for attempt in range(tries):
        time.sleep(0.5 + 3 * attempt)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:  # default client name: FRED drops some custom ones
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if attempt == tries - 1:
                raise


def _text(page):
    page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", page)))


def _release_of(sid):
    page = _get(f"https://fred.stlouisfed.org/series/{sid}")
    m = re.search(r"release\?rid=(\d+)", page)
    return m.group(1) if m else None


def _upcoming(rid, start, end, max_pages=3):
    dates, name = set(), None
    for page_id in range(1, max_pages + 1):
        txt = _text(_get(f"https://fred.stlouisfed.org/releases/calendar?rid={rid}&vs={start}&ve={end}&pageID={page_id}"))
        if name is None:
            m = re.search(r"Release Calendar - ([^|]+?) \| FRED", txt)
            name = m.group(1).strip() if m else None
        found = {f"{y}-{MONTHS.index(mo) + 1:02d}-{int(d):02d}" for mo, d, y in DATE_RE.findall(txt)}
        if not found - dates:
            break
        dates |= found
    return sorted(d for d in dates if start <= d <= end), name


def fetch(series_ids, out_path):
    out_path = Path(out_path)
    old = json.loads(out_path.read_text()).get("series", {}) if out_path.exists() else {}
    today = date.today()
    start, end = today.isoformat(), (today + timedelta(days=430)).isoformat()
    series, failed, by_rid = {}, [], {}
    for sid in series_ids:
        try:
            rid = (old.get(sid) or {}).get("rid") or _release_of(sid)
            if not rid:
                raise ValueError("no release found")
            if rid not in by_rid:
                by_rid[rid] = _upcoming(rid, start, end)
            dates, name = by_rid[rid]
            series[sid] = {"rid": rid, "release": name, "dates": dates}
        except Exception as exc:  # keep yesterday's entry rather than blank it
            print(f"    release calendar {sid} failed: {exc}")
            failed.append(sid)
            if sid in old:
                series[sid] = old[sid]
    out_path.write_text(json.dumps({"fetched": start, "series": series}, indent=1) + "\n")
    return failed
