"""Census Bureau Business Trends and Outlook Survey (BTOS): extract the questions a
dashboard needs from the published National.xlsx / Sector.xlsx into compact JSON.

Questions are matched by their wording (a phrase in the question text), never by ID,
so if Census rewords or renumbers a question the extract fails loudly instead of
silently charting the wrong thing.

Spec (from a dashboard's sources.json, key "btos"):
  {"national": {"key": "phrase in question text", ...},
   "index": ["Input prices", ...],                # rows of the Index Estimates sheet
   "sector": {"key": "phrase", ...}}              # same matching, per NAICS sector
"""
import datetime
import re

from xlsx import read_sheet

NATIONAL_URL = "https://www.census.gov/hfp/btos/downloads/National.xlsx"
SECTOR_URL = "https://www.census.gov/hfp/btos/downloads/Sector.xlsx"

SECTORS = {
    "11": "Agriculture", "21": "Mining", "22": "Utilities", "23": "Construction", "31": "Manufacturing",
    "42": "Wholesale trade", "44": "Retail trade", "48": "Transportation & warehousing", "51": "Information",
    "52": "Finance & insurance", "53": "Real estate", "54": "Professional services",
    "55": "Management of companies", "56": "Admin & support services", "61": "Educational services",
    "62": "Health care", "71": "Arts & recreation", "72": "Accommodation & food", "81": "Other services",
}


class MatchError(RuntimeError):
    pass


def _norm(s):
    return re.sub(r"\s+", " ", str(s).replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def _num(v):
    if isinstance(v, float):
        return v
    v = str(v).strip().rstrip("%")
    try:
        return float(v)
    except ValueError:
        return None  # '.', 'S' (suppressed), ''


def _code(v):
    return str(int(float(v))) if v not in ("", None) else None


def _xl_date(v):
    try:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=float(v))).isoformat()
    except (TypeError, ValueError):
        return None


def _match(rows, qcol, phrase, extra=None):
    """Rows whose question text contains phrase (and optional filter)."""
    p = _norm(phrase)
    hits = [r for r in rows if len(r) > qcol and p in _norm(r[qcol]) and (extra is None or extra(r))]
    if not hits:
        raise MatchError(f"BTOS question match failed: {phrase!r}")
    texts = {_norm(r[qcol]) for r in hits}
    if len(texts) > 1:
        raise MatchError(f"BTOS phrase is ambiguous ({len(texts)} questions): {phrase!r}")
    return hits


def extract(national_path, sector_path, spec):
    out = {"waves": {}, "national": {}, "index": {}, "sector": {}, "sector_names": SECTORS}

    # wave code -> reference period and publication date
    for r in read_sheet(national_path, "Collection and Reference Dates")[1:]:
        if len(r) > 8 and r[3] not in ("", None):
            out["waves"][_code(r[3])] = {"start": _xl_date(r[6]), "end": _xl_date(r[7]), "published": _xl_date(r[8])}

    nat = read_sheet(national_path, "Response Estimates")
    hdr = nat[0]
    wave_cols = [(i, _code(h)) for i, h in enumerate(hdr) if re.fullmatch(r"\d{6}(\.0)?", str(h))]
    for key, phrase in spec.get("national", {}).items():
        hits = _match(nat[1:], 1, phrase)
        out["national"][key] = {
            "question": hits[0][1],
            "answers": {str(r[3]): {c: _num(r[i]) for i, c in wave_cols if i < len(r) and _num(r[i]) is not None}
                        for r in hits},
        }

    if spec.get("index"):
        idx = read_sheet(national_path, "Index Estimates")
        ihdr = idx[0]
        icols = [(i, _code(h)) for i, h in enumerate(ihdr) if re.fullmatch(r"\d{6}(\.0)?", str(h))]
        for name in spec["index"]:
            row = next((r for r in idx[1:] if r and _norm(r[0]) == _norm(name)), None)
            if row is None:
                raise MatchError(f"BTOS index row not found: {name!r}")
            out["index"][name] = {c: _num(row[i]) for i, c in icols if i < len(row) and _num(row[i]) is not None}

    if spec.get("sector"):
        sec = read_sheet(sector_path, "Response Estimates")
        shdr = sec[0]
        scols = [(i, _code(h)) for i, h in enumerate(shdr) if re.fullmatch(r"\d{6}(\.0)?", str(h))]
        rows = [r for r in sec[1:] if _code_safe(r[0]) in SECTORS]
        for key, phrase in spec["sector"].items():
            hits = _match(rows, 2, phrase)
            by = {}
            for r in hits:
                by.setdefault(_code(r[0]), {})[str(r[4])] = {
                    c: _num(r[i]) for i, c in scols if i < len(r) and _num(r[i]) is not None}
            out["sector"][key] = {"question": hits[0][2], "by_sector": by}
    return out


def _code_safe(v):
    try:
        return _code(v)
    except (TypeError, ValueError):
        return None
