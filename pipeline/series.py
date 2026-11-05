"""Small helpers for time series stored as sorted lists of (YYYY-MM-DD, value).

Shared by every dashboard's compute.py. Standard library only.
"""
import csv
from pathlib import Path


class Series:
    """A sorted run of (date, value) observations with a few convenience methods."""

    def __init__(self, sid, obs):
        self.id = sid
        self.obs = sorted(obs)
        self.map = dict(self.obs)

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
        return Series(self.id, [(d, v) for d, v in self.obs if d >= start])

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
        """Percent change vs the same month one year earlier (monthly data)."""
        out = []
        for d, v in self.obs:
            prev = self.map.get(f"{int(d[:4]) - 1}{d[4:]}")
            if prev:
                out.append((d, (v / prev - 1) * 100))
        return Series(self.id + "_yoy", out)

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

    def rows(self, digits=2):
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
