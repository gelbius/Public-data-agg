"""Dashboard 02 - AI at work: how US businesses are adopting AI, from the Census Bureau's
Business Trends and Outlook Survey (BTOS). Every number and headline is computed here."""
import json
from pathlib import Path

from series import month_label, day_label

TITLE = "AI at Work: How US Businesses Are Adopting It"
SLUG = "ai"
ORDER = 2
DESCRIPTION = ("How many US businesses use AI, which industries lead, and what it is doing to jobs so far, "
               "from the Census Bureau's biweekly Business Trends and Outlook Survey.")


def _dated(by_code, waves):
    return sorted([waves[c]["end"], v] for c, v in by_code.items() if c in waves and waves[c].get("end"))


def _pct(v):
    return f"{v:.1f}%"


def compute(data_dir):
    data_dir = Path(data_dir)
    B = json.loads((data_dir / "btos.json").read_text())
    meta = json.loads((data_dir / "fetch_meta.json").read_text())
    W, N = B["waves"], B["national"]

    use = _dated(N["ai_use"]["answers"]["Yes"], W)
    nxt = _dated(N["ai_next6"]["answers"]["Yes"], W)
    first, last = use[0], use[-1]
    last_code = max(N["ai_use"]["answers"]["Yes"])
    published = W.get(last_code, {}).get("published")
    # closest wave to one year before the latest (52 weeks), if the series is long enough
    from datetime import date, timedelta
    target = date.fromisoformat(last[0]) - timedelta(days=364)
    year_ago = min(use, key=lambda r: abs((date.fromisoformat(r[0]) - target).days))
    has_year = abs((date.fromisoformat(year_ago[0]) - target).days) <= 10
    base = year_ago if has_year else first
    base_txt = "a year earlier" if has_year else f"in {month_label(first[0])}, when the current wording started"

    gaps = []
    for (a, _), (b, _) in zip(use, use[1:]):
        if (date.fromisoformat(b) - date.fromisoformat(a)).days > 21:
            gaps.append({"start": a, "end": b, "label": "No survey"})

    genai = N["ai_genai_staff"]["answers"]["Yes"]
    genai_last = genai[max(genai)] if genai else None
    expect = nxt[-1][1]

    # frozen history of the earlier, narrower question (Sep 2023 - Sep 2025), if present
    hist_path = data_dir / "btos_history_v1.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else None
    old_use, old_next = (hist["use"], hist["next6"]) if hist else ([], [])
    history_txt = ""
    if old_use:
        o0, o1 = old_use[0], old_use[-1]
        history_txt = (f" On the earlier, narrower question (AI \"in producing goods or services\"), use rose from "
                       f"{_pct(o0[1])} in {month_label(o0[0])} to {_pct(o1[1])} in {month_label(o1[0])}. The jump between "
                       f"the two lines mostly reflects the broader new wording, not a sudden surge.")
        gaps = [{"start": o1[0], "end": first[0], "label": "Question reworded"}]

    hero = {
        "headline": f"{last[1]:.0f}% of US businesses now use AI.",
        "sub": (f"In the two weeks ending {day_label(last[0])}, {_pct(last[1])} of employer businesses used AI in at least "
                f"one business function, up from {_pct(base[1])} {base_txt}. {_pct(expect)} expect to be using it within "
                f"six months." + history_txt),
        "series": {"use": use, "next6": nxt, "use_v1": old_use, "next6_v1": old_next}, "gaps": gaps,
        "break": first[0] if old_use else None,
    }

    def tile(label, value, sub, delta=None):
        return {"label": label, "value": value, "when": sub, "delta": delta}

    tiles = [
        tile("Businesses using AI", _pct(last[1]), f"two weeks ending {day_label(last[0])}",
             {"value": round(last[1] - base[1], 1), "text": f"{last[1] - base[1]:+.1f} pt vs {'a year ago' if has_year else month_label(first[0])}"}),
        tile("Expect to use AI within six months", _pct(expect), "next six months"),
        tile("Businesses whose employees use generative AI", _pct(genai_last) if genai_last is not None else "n/a",
             (f"two weeks ending {day_label(W[max(genai)]['end'])}" + (" · first time asked" if len(genai) == 1 else ""))
             if genai else ""),
    ]

    # by industry, latest wave with data for each sector
    names = B["sector_names"]
    by = B["sector"]["ai_use"]["by_sector"]
    rows = []
    for code, ans in by.items():
        yes = ans.get("Yes", {})
        if last_code in yes:
            firsts = sorted(yes)
            f0 = yes[firsts[0]]
            rows.append({"code": code, "name": names.get(code, code), "value": yes[last_code],
                         "change": round(yes[last_code] - f0, 1), "since": W[firsts[0]]["end"]})
    rows.sort(key=lambda r: -r["value"])
    top, bottom = rows[0], rows[-1]
    industries = {
        "headline": f"{top['name']} leads: {top['value']:.0f}% of firms use AI, vs {bottom['value']:.0f}% in {bottom['name'].lower()}.",
        "sub": (f"AI use by industry in the two weeks ending {day_label(last[0])}. The national rate is {_pct(last[1])}. "
                f"Industries whose estimates Census suppressed for that wave are not shown."),
        "rows": rows, "national": last[1],
    }

    def effect(key):
        a = N[key]["answers"]
        code = max(a["Increased"])
        return {"increased": a["Increased"][code], "decreased": a["Decreased"][code],
                "no_change": a.get("No change", {}).get(code), "dont_know": a.get("Do not know", {}).get(code),
                "when": W[code]["end"]}

    hc, hi = effect("ai_headcount"), effect("ai_hiring")
    net_hc = hc["increased"] - hc["decreased"]
    jobs = {
        "headline": ("So far, AI is barely moving headcount." if abs(net_hc) < 5 else
                     ("AI users are adding staff." if net_hc > 0 else "AI users are cutting staff.")),
        "sub": (f"Asked how AI affected their workforce over the last six months, {_pct(hc['no_change'])} of businesses reported "
                f"no change in headcount; {_pct(hc['increased'])} said it increased and {_pct(hc['decreased'])} said it decreased. "
                f"For new hiring: {_pct(hi['increased'])} more, {_pct(hi['decreased'])} fewer."),
        "rows": [{"label": "Total headcount", **hc}, {"label": "New hires", **hi}],
    }

    src = {"ids": ["BTOS"], "latest": {"BTOS": last[0]}, "fetched": meta.get("btos", {}).get("fetched"),
           "label": "Census Bureau, Business Trends and Outlook Survey (National.xlsx, Sector.xlsx)"
                    + (f" · published {day_label(published)}" if published else "")}
    for sct in (hero, industries, jobs):
        sct["source"] = src
    if old_use:  # credit the frozen pre-Nov-2025 history on the chart that uses it
        hero["source"] = {**src, "label": src["label"] + " · Sep 2023 – Sep 2025 from an archived copy of National.xlsx (Internet Archive)"}
    return {
        "title": TITLE, "slug": SLUG, "description": DESCRIPTION, "fetched": meta.get("fetched"),
        "hub_headline": hero["headline"] + " " + industries["headline"],
        "sections": {"hero": hero, "kpis": {"tiles": tiles, "source": src}, "industries": industries, "jobs": jobs},
        "question": N["ai_use"]["question"],
        "question_v1": hist["question_use"] if hist else None,
        "effect_question": N["ai_headcount"]["question"],
    }
