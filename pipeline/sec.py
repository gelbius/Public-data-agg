"""SEC EDGAR company financials (XBRL "company facts"), public domain.

SEC asks automated clients to identify themselves with a contact address in the
User-Agent header. That address is read from the SEC_USER_AGENT environment
variable (a GitHub Actions secret / local setting) and is never stored in this repo.

fetch(tickers, out_dir) saves data/<dash>/sec/<TICKER>.json with only the concepts
the dashboard uses, to keep the repo small.
"""
import gzip
import json
import os
import time
import urllib.request
from pathlib import Path

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# us-gaap concepts we keep (several alternatives per line item; compute.py picks the best one)
CONCEPTS = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
    "OperatingIncomeLoss", "NetIncomeLoss",
    "DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet", "DepreciationAmortizationAndOther", "Depreciation",
    "AmortizationOfIntangibleAssets", "DepreciationNonproduction",
    "CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments",
    "MarketableSecuritiesCurrent", "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent",
    "ShortTermBorrowings", "CommercialPaper", "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligationsCurrent", "ConvertibleNotesPayable", "ConvertibleDebtNoncurrent",
    "SeniorNotes", "LongTermNotesPayable",
    "OtherDepreciationAndAmortization", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic",
    "DebtLongtermAndShorttermCombinedAmount", "NotesPayableCurrent", "ConvertibleLongTermNotesPayable",
    "ConvertibleNotesPayableCurrent", "UnsecuredLongTermDebt", "OtherLongTermDebt", "OtherLongTermDebtNoncurrent",
]
KEEP_FIELDS = ("start", "end", "val", "fy", "fp", "form", "filed")


def _get(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


def fetch(tickers, out_dir, cik_overrides=None):
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua or "@" not in ua:
        print("    SEC_USER_AGENT not set (needs a contact email); keeping previous SEC files")
        return ["sec"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in _get(TICKERS_URL, ua).values()}
    ciks.update({t.upper(): int(c) for t, c in (cik_overrides or {}).items()})  # delisted companies keep their filings
    failed = []
    for t in tickers:
        cik = ciks.get(t.upper())
        if cik is None:
            print(f"    SEC: no CIK for {t}")
            failed.append(t)
            continue
        try:
            facts = _get(FACTS_URL.format(cik=cik), ua)
        except Exception as exc:
            print(f"    SEC {t} failed: {exc}")
            failed.append(t)
            continue
        gaap = facts.get("facts", {}).get("us-gaap", {})
        slim = {c: [{k: f.get(k) for k in KEEP_FIELDS} for f in gaap[c]["units"].get("USD", [])]
                for c in CONCEPTS if c in gaap}
        (out_dir / f"{t}.json").write_text(json.dumps({"ticker": t, "cik": cik, "name": facts.get("entityName"),
                                                       "facts": slim}, separators=(",", ":")) + "\n")
        time.sleep(0.15)  # stay well under SEC's 10 requests/second
    return failed
