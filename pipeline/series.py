"""Small helpers for time series stored as sorted lists of (YYYY-MM-DD, value).

Shared by every dashboard's compute.py. Standard library only.
"""
import csv
from pathlib import Path


def _shift_month(d, n):
    """'YYYY-MM-01' moved n months."""
    y, m = divmod(int(d[:4]) * 12 + int(d[5:7]) - 1 + n, 12)
    return f"{y:04d}-{m + 1:02d}-01"


class Series:
    """A sorted run of (date, value) observations with a few convenience methods."""

    def __init__(self, sid, obs, est=()):
        self.id = sid
        self.obs = sorted(obs)
        self.map = dict(self.obs)
        self.est = set(est)  # dates whose value rests on an estimate (see yoy_pct)

    @classmethod
    def load(cls, data_dir, sid):
        path = Path(data_dir) / "fred" / f"{sid}.csv"
        with path.open() as f:
            rows = list(csv.reader(f))[1:]
        return cls(sid, [(d, float(v)) for d, v in rows])

    # --- basic access -------------------------------------------------------
    @property
    def last(self):
        return self.obs[-1]

    def since(self, start):
        return Series(self.id, [(d, v) for d, v in self.obs if d >= start], self.est)

    def get(self, d):
        return self.map.get(d)

    def value_on_or_before(self, d):
        best = None
        for od, v in self.obs:
            if od <= d:
                best = (od, v)
            else:
                break
        return best

    # --- transforms ---------------------------------------------------------
    def yoy_pct(self):
        """Percent change vs the same month one year earlier (monthly data).

        If that base month was never published (e.g. BLS skipped October 2025 during the
        government shutdown) but the months either side exist, the base is estimated as their
        geometric mean and the result's date is recorded in .est so pages can label it.
        """
        out, est = [], set()
        for d, v in self.obs:
            base = f"{int(d[:4]) - 1}{d[4:]}"
            prev = self.map.get(base)
            if prev is None:
                before, after = self.map.get(_shift_month(base, -1)), self.map.get(_shift_month(base, 1))
                if before and after:
                    prev = (before * after) ** 0.5
                    est.add(d)
            if prev:
                out.append((d, (v / prev - 1) * 100))
        return Series(self.id + "_yoy", out, est)

    def monthly_mean(self):
        """Average weekly/daily observations into calendar months (dated the 1st)."""
        buckets = {}
        for d, v in self.obs:
            buckets.setdefault(d[:7] + "-01", []).append(v)
        return Series(self.id, [(m, sum(vs) / len(vs)) for m, vs in buckets.items()])

    def year_ago(self, d=None, tolerance_days=10):
        """Observation closest to one year before d (default: latest), within tolerance."""
        d = d or self.last[0]
        target = _shift_year(d, -1)
        best = None
        for od, v in self.obs:
            gap = abs(_days(od) - _days(target))
            if gap <= tolerance_days and (best is None or gap < best[0]):
                best = (gap, (od, v))
        return best[1] if best else None

    # --- facts --------------------------------------------------------------
    def max(self):
        return max(self.obs, key=lambda x: x[1])

    def min(self):
        return min(self.obs, key=lambda x: x[1])

    def lowest_since(self):
        """For the latest value: the most recent earlier date with a value <= it (None = record)."""
        d0, v0 = self.last
        for d, v in reversed(self.obs[:-1]):
            if v <= v0:
                return d
        return None

    def highest_since(self):
        d0, v0 = self.last
        for d, v in reversed(self.obs[:-1]):
            if v >= v0:
                return d
        return None

    def decline_streak(self):
        """Number of consecutive period-over-period declines ending at the latest value."""
        n = 0
        for i in range(len(self.obs) - 1, 0, -1):
            if self.obs[i][1] < self.obs[i - 1][1]:
                n += 1
            else:
                break
        return n

    def mean_between(self, start, end):
        vals = [v for d, v in self.obs if start <= d <= end]
        return sum(vals) / len(vals) if vals else None

    def rows(self, digits=6):  # keep precision: the page rounds once, exactly like the headlines
        return [[d, round(v, digits)] for d, v in self.obs]


def spans(series, flag=1):
    """Contiguous date spans where the series equals `flag` (e.g. NBER recessions)."""
    out, start, prev = [], None, None
    for d, v in series.obs:
        if v == flag and start is None:
            start = d
        if v != flag and start is not None:
            out.append([start, prev])
            start = None
        prev = d
    if start is not None:
        out.append([start, prev])
    return out


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(d):
    """'2026-05-01' -> 'May 2026'."""
    return f"{MONTHS[int(d[5:7]) - 1]} {d[:4]}"


def quarter_label(d):
    return f"Q{(int(d[5:7]) - 1) // 3 + 1} {d[:4]}"


def day_label(d):
    return f"{MONTHS[int(d[5:7]) - 1]} {int(d[8:10])}, {d[:4]}"


def _days(d):
    from datetime import date
    return date.fromisoformat(d).toordinal()


def _shift_year(d, n):
    y = int(d[:4]) + n
    md = d[5:]
    if md == "02-29":
        md = "02-28"
    return f"{y}-{md}"


def btos_next_update(waves, last_code, today=None):
    """One line about the next Census BTOS release, from the schedule in Census's own workbook.

    waves: {code: {"start", "end", "published"}}; last_code: the latest wave we have data for.
    """
    from datetime import date
    today = today or date.today().isoformat()
    later = sorted(c for c in waves if c > last_code and waves[c].get("published") and waves[c].get("end"))
    if not later:
        return ""
    w = waves[later[0]]
    short = lambda d: f"{MONTHS[int(d[5:7]) - 1]} {int(d[8:10])}"
    covers = f"{short(w['start'])} – {short(w['end'])}"
    if w["published"] < today:
        return f"Census's next release ({covers}) was due {short(w['published'])} and isn't out yet."
    return f"Next update: {short(w['published'])}, covering {covers} (Census release schedule)."


# Plain-language "next update" notes for sources without a published calendar.
UNSCHEDULED = {
    "ZILLOW": "monthly, around mid-month (Zillow sets no fixed date)",
    "BLS_CE": "annual, usually in September",
    "TDSP": "quarterly; next date not yet announced",
    "DRCCLACBS": "quarterly; next date not yet announced",
    "MEHOINUSA646N": "annual, usually in September",
    "USREC": "only when a recession starts or ends",
}


FRIENDLY = {
    "Employment Situation": "jobs report",
    "Consumer Price Index": "CPI",
    "H.15 Selected Interest Rates": "Fed funds rate",
    "Primary Mortgage Market Survey": "Freddie Mac mortgage rates",
    "G.19 Consumer Credit": "Fed consumer credit",
    "Personal Income and Outlays": "personal income & saving",
    "Surveys of Consumers": "UMich consumer sentiment",
    "Gasoline and Diesel Fuel Update": "EIA gas prices",
    "S&P Cotality Case-Shiller Home Price Indices": "Case-Shiller home prices",
    "New Residential Sales": "new home sales",
    "Census Business Trends and Outlook Survey": "Census business survey",
}

# US stock-market holidays (NYSE), for the tech dashboard's next trading day
MARKET_HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
                   "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}


def next_trading_day(d):
    from datetime import date, timedelta
    x = date.fromisoformat(d)
    while True:
        x += timedelta(days=1)
        if x.weekday() < 5 and x.isoformat() not in MARKET_HOLIDAYS:
            return x.isoformat()


def _days_between(a, b):
    from datetime import date
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def next_update(ids, releases, latest=None, btos_waves=None, btos_last=None, today=None):
    """Soonest scheduled update among a chart's sources.

    Returns {"date", "release", "id"} for the earliest dated release after today, else {"text"} describing the
    cadence of the first source that has one, else None. Monthly figures that come from a daily release (e.g. the
    fed funds monthly average, H.15) use the first release once the next month's value is due, not tomorrow's print.
    """
    from datetime import date
    today = today or date.today().isoformat()
    cands, texts = [], []
    for sid in ids:
        if sid == "BTOS" and btos_waves and btos_last:
            later = sorted(c for c in btos_waves if c > btos_last and btos_waves[c].get("published"))
            if later:
                cands.append((btos_waves[later[0]]["published"], "Census Business Trends and Outlook Survey", sid))
            continue
        key = "BLS_CE" if sid.startswith("CXU") else sid
        info = (releases or {}).get(sid)
        if info and info.get("dates"):
            dates = [d for d in info["dates"] if d > today]
            last = (latest or {}).get(sid)
            daily = sum(1 for d in info["dates"] if _days_between(info["dates"][0], d) <= 31) >= 8
            if last and daily and last[8:10] == "01":  # monthly value from a daily release
                y, m = divmod(int(last[:4]) * 12 + int(last[5:7]) - 1 + 2, 12)
                due = f"{y:04d}-{m + 1:02d}-01"
                dates = [d for d in dates if d >= due]
            if dates and sid != "USREC":
                cands.append((dates[0], info.get("release") or sid, sid))
                continue
        if key in UNSCHEDULED:
            texts.append(UNSCHEDULED[key])
    if cands:
        d, rel, sid = min(cands)
        return {"date": d, "release": FRIENDLY.get(rel, rel), "id": sid}
    return {"text": texts[0]} if texts else None
