"""Trailing-twelve-month (TTM) financials from SEC XBRL facts.

Companies report income-statement items as 3-month figures and/or as year-to-date
running totals, and cash-flow items (like depreciation) usually only year-to-date.
We turn everything into individual quarters, then add the latest four.
"""
from datetime import date

REVENUE = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
           "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
DA = ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
      "DepreciationAmortizationAndAccretionNet", "DepreciationAmortizationAndOther"]
CASH = ["CashCashEquivalentsAndShortTermInvestments", "CashAndCashEquivalentsAtCarryingValue"]
SHORT_INV = ["MarketableSecuritiesCurrent", "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"]
DA_COMBOS = [("Depreciation", "AmortizationOfIntangibleAssets"),
             ("OtherDepreciationAndAmortization", "AmortizationOfIntangibleAssets")]
NET_INCOME = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
DEBT_TOTAL = ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount", "LongTermDebtAndCapitalLeaseObligations"]
DEBT_PARTS = [("LongTermDebtNoncurrent", "LongTermDebtCurrent"), ("LongTermDebtNoncurrent", "DebtCurrent"),
              ("LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent"),
              ("LongTermNotesPayable", "NotesPayableCurrent"), ("ConvertibleLongTermNotesPayable", "ConvertibleNotesPayableCurrent"),
              ("ConvertibleDebtNoncurrent", "ConvertibleNotesPayableCurrent"), ("UnsecuredLongTermDebt", "LongTermDebtCurrent")]
DEBT_ONLY_CURRENT = ["NotesPayableCurrent", "DebtCurrent", "LongTermDebtCurrent"]  # used only if nothing else exists
DEBT_LAG_DAYS = 200  # a debt total up to ~2 quarters older than the cash figure is accepted (and flagged)
DEBT_EXTRA = ["ShortTermBorrowings", "CommercialPaper"]


def d(s):
    return date.fromisoformat(s)


def days(a, b):
    return (d(b) - d(a)).days


def quarters(facts):
    """Duration facts -> {(qstart, qend): value}. Uses direct ~3-month facts, and differences
    between consecutive year-to-date totals that share a start date (latest filing wins)."""
    q = {}
    latest = {}
    for f in facts:
        if not f.get("start"):
            continue
        key = (f["start"], f["end"])
        if key not in latest or (f.get("filed") or "") > (latest[key].get("filed") or ""):
            latest[key] = f
    for (s, e), f in latest.items():
        if 80 <= days(s, e) <= 100:
            q[(s, e)] = f["val"]
    by_start = {}
    for (s, e), f in latest.items():
        by_start.setdefault(s, []).append((e, f["val"]))
    for s, items in by_start.items():
        items.sort()
        prev_end, prev_val = None, None
        for e, v in items:
            if prev_end is not None and 80 <= days(prev_end, e) <= 100:
                qs = prev_end  # quarter runs from previous cumulative end
                key = next((k for k in q if k[1] == e and abs(days(k[0], qs)) <= 3), None)
                if key is None:
                    q[(qs, e)] = v - prev_val
            elif prev_end is None and 80 <= days(s, e) <= 100 and (s, e) not in q:
                q[(s, e)] = v
            prev_end, prev_val = e, v
    # one value per quarter end (drop near-duplicate keys)
    out = {}
    for (s, e), v in sorted(q.items(), key=lambda kv: kv[0][1]):
        out[e] = v
    return out  # {quarter_end: value}


def ttm(qmap, asof_end=None, offset=0):
    """Sum of 4 consecutive quarters ending at the latest quarter end <= asof_end
    (offset=1 -> the 4 quarters before that). Returns (end_date, value) or (None, None)."""
    ends = sorted(e for e in qmap if asof_end is None or e <= asof_end)
    if len(ends) < 4 * (offset + 1):
        return None, None
    chain = [ends[-1]]
    for e in reversed(ends[:-1]):
        if 80 <= days(e, chain[-1]) <= 100:
            chain.append(e)
        elif days(e, chain[-1]) > 100:
            break
        if len(chain) == 4 * (offset + 1):
            break
    if len(chain) < 4 * (offset + 1):
        return None, None
    window = chain[4 * offset: 4 * offset + 4]
    return window[0], sum(qmap[e] for e in window)


def best_flow(facts, names, asof_end=None):
    """Pick the concept whose 4-quarter TTM ends latest; returns (concept, qmap, end, value)."""
    best = (None, None, None, None)
    for n in names:
        if n not in facts:
            continue
        qm = quarters(facts[n])
        e, v = ttm(qm, asof_end)
        if e and (best[2] is None or e > best[2]):
            best = (n, qm, e, v)
    return best


def instant(facts, name, asof_end=None):
    vals = [f for f in facts.get(name, []) if not f.get("start") and (asof_end is None or f["end"] <= asof_end)]
    if not vals:
        return None, None
    f = max(vals, key=lambda x: (x["end"], x.get("filed") or ""))
    return f["end"], f["val"]


def balance(facts, asof_end=None):
    """Cash (incl. short-term investments) and total debt at the latest balance sheet <= asof_end."""
    cash_end, cash = None, None
    for n in CASH:
        e, v = instant(facts, n, asof_end)
        if e and (cash_end is None or e > cash_end):
            cash_end, cash, cash_name = e, v, n
    if cash_end and cash_name == "CashAndCashEquivalentsAtCarryingValue":
        for n in SHORT_INV:
            e, v = instant(facts, n, asof_end)
            if e == cash_end:
                cash += v
                break
    ref = cash_end
    debt, debt_end = None, None

    def near(e):
        return e and ref and e <= ref and days(e, ref) <= DEBT_LAG_DAYS

    for n in DEBT_TOTAL:
        e, v = instant(facts, n, asof_end)
        if near(e) and (debt_end is None or e > debt_end):
            debt, debt_end = v, e
    if debt is None or debt_end != ref:
        for a, b in DEBT_PARTS:
            ea, va = instant(facts, a, asof_end)
            if not near(ea) or (debt_end is not None and ea <= debt_end):
                continue
            total = va
            if b:
                eb, vb = instant(facts, b, asof_end)
                if eb == ea:
                    total += vb
            debt, debt_end = total, ea
            break
    if debt is None:
        for n in DEBT_ONLY_CURRENT:
            e, v = instant(facts, n, asof_end)
            if near(e):
                debt, debt_end = v, e
                break
    if debt is not None:
        for n in DEBT_EXTRA:
            e, v = instant(facts, n, asof_end)
            if e == debt_end:
                debt += v
    return {"end": ref, "cash": cash, "debt": debt if debt is not None else 0.0, "debt_found": debt is not None,
            "debt_end": debt_end}


def financials(facts, asof_end=None):
    rn, rq, re_, rev = best_flow(facts, REVENUE, asof_end)
    if not re_:
        return None
    _, rev_prev = ttm(rq, asof_end, offset=1)
    oi_q = quarters(facts.get("OperatingIncomeLoss", []))
    oe, oi = ttm(oi_q, re_)
    ne, ni = None, None
    for n in NET_INCOME:
        e, v = ttm(quarters(facts.get(n, [])), re_)
        if e == re_:
            ne, ni = e, v
            break
    # D&A: companies switch between equivalent labels across filings, so merge them into one series
    merged = [f for n in DA for f in facts.get(n, [])]
    da_name, da_partial = "D&A", False
    dae, da = ttm(quarters(merged), re_)
    if dae != re_:  # a fiscal-year-end TTM can use the annual figure directly
        annual = [f for f in merged if f.get("start") and f["end"] == re_ and 350 <= days(f["start"], f["end"]) <= 380]
        if annual:
            dae, da = re_, max(annual, key=lambda f: f.get("filed") or "")["val"]
    if dae != re_:
        for a, b in DA_COMBOS + [("OtherDepreciationAndAmortization", None), ("Depreciation", None)]:
            ea, va = ttm(quarters(facts.get(a, [])), re_)
            eb, vb = ttm(quarters(facts.get(b, [])), re_) if b else (re_, 0)
            if ea == re_ and eb == re_:
                da_name, dae, da, da_partial = (f"{a}+{b}" if b else a), re_, va + vb, b is None
                break
    ebitda = oi + da if (oi is not None and da is not None and oe == re_ and dae == re_) else None
    return {"ttm_end": re_, "revenue": rev, "revenue_prev": rev_prev,
            "op_income": oi if oe == re_ else None, "net_income": ni if ne == re_ else None,
            "da": da if dae == re_ else None, "ebitda": ebitda,
            "concepts": {"revenue": rn, "da": da_name}, "da_partial": da_partial, **{"bs_" + k: v for k, v in balance(facts, asof_end).items()}}
