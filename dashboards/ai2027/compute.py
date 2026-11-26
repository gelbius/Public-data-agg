"""Dashboard 04 - AI 2027 vs reality: the AI 2027 scenario's predictions scored against what happened.

Inputs (data/ai2027/, curated by hand from linked sources, see each file's _doc):
  predictions.json  36 predictions: wording, verdict, dates, source link, gap checkpoints
  events.json       dated real-world events with primary links
  scenario.json     the scenario's own research-speed figures and milestone names
  story.json        the scroll story's beats
  watch.json        what to watch next

Every number on the page is computed here: the verdict counts, the schedule-gap trend, both curves
and every reading quoted in the story.

How the two curves work (a train against its timetable):
  * Scenario curve: cumulative AI research progress the scenario expects, in "months of progress at the
    April 2025 pace". Each month adds the scenario's AI R&D multiplier for that month (1x at publication,
    1.5x early 2026, 2x Dec 2026, 3x Jan 2027, 4x Mar 2027), so the curve bends upward.
  * Schedule gap: for each resolved prediction, how many months early (+) or late (-) reality met it.
    A Gaussian-weighted average of those dots (bandwidth 2 months) gives a smooth trend.
  * Reality curve: at date t, reality stands where the scenario expected to be at t + gap(t). Reality never
    moves backward: if the gap widens faster than time passes, the line holds flat.
"""
import json
import math
from datetime import date, timedelta
from pathlib import Path

TITLE = "AI 2027 vs Reality: The Script and the Record"
SLUG = "ai-2027"
ORDER = 4
DESCRIPTION = ("The AI 2027 scenario's 36 dated predictions scored against what actually happened, with a "
               "scroll-driven record of whether AI progress is running behind or ahead of the script.")

MONTH = 30.4375          # days per month
BANDWIDTH = 2.0          # months, Gaussian smoothing of the schedule-gap dots
RAMP = 3.0               # months over which the trend is eased in from zero at publication
TREND_DIMENSIONS = ("AI Capabilities", "Alignment & safety")   # same set as the source page's gap chart
VERDICTS = ["Ahead of schedule", "On track", "Behind", "Didn't happen", "Too early to tell"]
STATUS = {"Ahead of schedule": "EARLY", "On track": "ON TIME", "Behind": "DELAYED",
          "Didn't happen": "CANCELLED", "Too early to tell": "SCHEDULED"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def d(s):
    return date.fromisoformat(s)


def month_label(x):
    return f"{MONTHS[x.month - 1]} {x.year}"


def day_label(x):
    return f"{MONTHS[x.month - 1]} {x.day}, {x.year}"


def gap_text(g):
    if abs(g) < 0.25:
        return "on the script"
    return f"{abs(g):.1f} months {'ahead of' if g > 0 else 'behind'} the script"


def gap_short(g):
    return f"{'+' if g >= 0 else '−'}{abs(g):.1f} mo"


def compute(data_dir):
    data_dir = Path(data_dir)
    P = json.loads((data_dir / "predictions.json").read_text())
    E = json.loads((data_dir / "events.json").read_text())["events"]
    S = json.loads((data_dir / "scenario.json").read_text())
    ST = json.loads((data_dir / "story.json").read_text())["beats"]
    W = json.loads((data_dir / "watch.json").read_text())["items"]
    preds = P["predictions"]
    as_of = d(P["as_of"])
    t0 = d(S["published"])
    end = d(S["chart_end"])

    def tm(x):              # date -> months since publication
        return (x - t0).days / MONTH

    def from_tm(t):
        return t0 + timedelta(days=round(t * MONTH))

    # ---- scenario curve: cumulative progress = integral of the R&D multiplier (log-linear between figures)
    knots = [(tm(d(k["date"])), k["value"]) for k in S["rd_multiplier"]]

    def mult(t):
        if t <= knots[0][0]:
            return knots[0][1]
        for (a, va), (b, vb) in zip(knots, knots[1:]):
            if t <= b:
                u = (t - a) / (b - a)
                return math.exp(math.log(va) + u * (math.log(vb) - math.log(va)))
        return knots[-1][1]

    STEP = 0.05
    t_max = tm(end) + 12      # room for reality running ahead of the chart's end date
    cum, acc = [0.0], 0.0
    n_steps = int(t_max / STEP) + 2
    for i in range(1, n_steps):
        acc += STEP * (mult((i - 0.5) * STEP))
        cum.append(acc)

    def progress(t):
        if t <= 0:
            return 0.0
        i = min(int(t / STEP), len(cum) - 2)
        f = t / STEP - i
        return cum[i] + f * (cum[i + 1] - cum[i])

    # ---- schedule-gap dots (resolved checkpoints) and unmet checkpoints
    dots, unmet = [], []
    for p in preds:
        if p["dimension"] not in TREND_DIMENSIONS:
            continue
        for c in p["checkpoints"]:
            sched = d(c["scheduled"])
            if c["met"]:
                met = d(c["met"])
                g = c["gap_override"] if c["gap_override"] is not None else (sched - met).days / MONTH
                dots.append({"label": c["label"], "prediction": p["id"], "dimension": p["dimension"],
                             "scheduled": c["scheduled"], "scenario_date": p["scenario_date"], "met": c["met"],
                             "gap": round(g, 1), "note": c.get("gap_note"), "source": p["source"]})
            else:
                unmet.append({"label": c["label"], "prediction": p["id"], "dimension": p["dimension"],
                              "scheduled": c["scheduled"], "lag": round(-(as_of - sched).days / MONTH, 1),
                              "source": p["source"]})
    dots.sort(key=lambda x: x["met"])
    anchor = [(0.0, 0.0)]  # at publication the scenario describes the present
    pts = anchor + [(tm(d(x["met"])), x["gap"]) for x in dots]

    def raw_gap(t):
        w = [math.exp(-0.5 * ((t - ti) / BANDWIDTH) ** 2) for ti, _ in pts]
        return sum(wi * gi for wi, (_, gi) in zip(w, pts)) / sum(w)

    def gap(t):
        r = max(0.0, min(1.0, t / RAMP))
        return raw_gap(t) * r * r * (3 - 2 * r)

    # ---- sample both curves weekly
    t_today = tm(as_of)
    weeks, x = [], t0
    while x <= end:
        weeks.append(x)
        x += timedelta(days=7)
    if as_of not in weeks:
        weeks.append(as_of)
        weeks.sort()
    scen, real, gaps = [], [], []
    pos_max = 0.0
    for x in weeks:
        t = tm(x)
        scen.append([x.isoformat(), round(progress(t), 3)])
        if x <= as_of:
            g = gap(t)
            pos_max = max(pos_max, t + g)
            real.append([x.isoformat(), round(progress(pos_max), 3)])
            gaps.append([x.isoformat(), round(g, 2)])

    # readings: today, lowest point, crossings
    g_today = gap(t_today)
    low = min(gaps, key=lambda r: r[1])
    high_early = max((r for r in gaps if d(r[0]) < d(low[0])), key=lambda r: r[1])
    crossings = []
    for (a, ga), (b, gb) in zip(gaps, gaps[1:]):
        if (ga < 0) != (gb < 0) and abs(ga - gb) > 1e-9:
            crossings.append({"date": b, "dir": "up" if gb > ga else "down"})
    slip = next((c for c in crossings if c["dir"] == "down"), None)
    cross = next((c for c in crossings if c["dir"] == "up" and (not slip or c["date"] > slip["date"])), None)
    cross_label = month_label(d(cross["date"])) if cross else "n/a"

    # ---- verdict counts
    counts = {v: sum(1 for p in preds if p["verdict"] == v) for v in VERDICTS}
    n = len(preds)
    ahead_or_on = counts["Ahead of schedule"] + counts["On track"]
    behind_or_no = counts["Behind"] + counts["Didn't happen"]
    dims = []
    for p in preds:
        if p["dimension"] not in dims:
            dims.append(p["dimension"])
    by_dim = [{"dimension": dm, **{v: sum(1 for p in preds if p["dimension"] == dm and p["verdict"] == v) for v in VERDICTS}}
              for dm in dims]

    # ---- board rows (all 36), ordered by scheduled date
    def short_date(iso, prec):
        if not iso:
            return None
        x = d(iso)
        return f"{MONTHS[x.month - 1].upper()} {str(x.year)[2:]}"

    board = []
    for p in sorted(preds, key=lambda p: (p["scheduled"], p["label"])):
        board.append({
            "id": p["id"], "label": p["label"], "dimension": p["dimension"], "subtag": p["subtag"],
            "sched_text": p["scenario_date"], "scheduled": p["scheduled"],
            "sched_short": _sched_short(p["scenario_date"]),
            "actual": p["actual"], "actual_short": short_date(p["actual"], p["actual_precision"]),
            "actual_precision": p["actual_precision"], "verdict_on": p["verdict_on"],
            "verdict": p["verdict"], "status": STATUS[p["verdict"]],
            "prediction": p["prediction"], "reality": p["reality"], "source": p["source"],
        })

    # ---- story beats with computed readings filled in
    def fill(text, at):
        t = min(tm(at), t_today)
        return (text.replace("{gap}", gap_text(gap(t)))
                    .replace("{cross}", cross_label)
                    .replace("{low}", f"{abs(low[1]):.1f} months behind, in {month_label(d(low[0]))}"))
    pid = {p["id"]: p for p in preds}
    beats = []
    for b in ST:
        at = d(b["date"])
        refs = []
        for r in b["refs"]:
            if r in pid:
                refs.append({"title": pid[r]["source"]["title"], "url": pid[r]["source"]["url"]})
        beats.append({"date": b["date"], "kicker": b["kicker"], "title": b["title"],
                      "body": fill(b["body"], at), "refs": refs,
                      "gap": round(gap(min(tm(at), t_today)), 1)})

    milestones = [{"date": m["date"], "label": m["label"], "progress": round(progress(tm(d(m["date"]))), 3)}
                  for m in S["milestones"]]

    headline = (f"Reality is running {gap_text(g_today)}." if abs(g_today) >= 0.25 else
                "Reality is running right on the script.")
    sub = (f"The record slipped behind in {month_label(d(slip['date'])) if slip else 'n/a'}, bottomed out "
           f"{abs(low[1]):.1f} months behind in {month_label(d(low[0]))}, then crossed the script in {cross_label}. "
           f"Built from {len(dots)} predictions with a known arrival date.")
    hub = (f"AI progress is running about {abs(g_today):.0f} months {'ahead of' if g_today > 0 else 'behind'} the AI 2027 "
           f"scenario, after falling {abs(low[1]):.0f} months behind in {month_label(d(low[0]))}. "
           f"{ahead_or_on} of {n} predictions are ahead or on track.")

    didnt = counts["Didn't happen"]
    tiles = [
        {"label": "Reality vs the script today", "value": gap_short(g_today),
         "when": f"smoothed schedule gap, {day_label(as_of)}"},
        {"label": "Ahead of schedule or on track", "value": f"{ahead_or_on} of {n}",
         "when": f"{counts['Ahead of schedule']} ahead · {counts['On track']} on track"},
        {"label": "Behind or didn't happen", "value": f"{behind_or_no} of {n}",
         "when": f"{counts['Behind']} behind · {didnt} didn't happen"},
        {"label": "Too early to tell", "value": f"{counts['Too early to tell']} of {n}",
         "when": "scenario dates still ahead"},
    ]

    src = {"label": "Verdicts and wording: compiled page 'AI 2027: Predictions vs. Reality' (Grok Bot), "
                    "each row linked to its primary source · Scenario figures: ai-2027.com",
           "as_of": P["as_of"]}

    return {
        "title": TITLE, "slug": SLUG, "description": DESCRIPTION, "fetched": P["as_of"],
        "hub_headline": hub,
        "as_of": P["as_of"], "published": S["published"], "chart_end": S["chart_end"],
        "scenario_url": S["url"], "compiled_from": P["compiled_from"],
        "sections": {
            "kpis": {"tiles": tiles, "counts": counts, "n": n, "by_dim": by_dim, "source": src},
            "record": {
                "headline": headline, "sub": sub,
                "scenario": scen, "reality": real, "gap": gaps,
                "today_gap": g_today, "low": {"date": low[0], "gap": low[1]},
                "early_high": {"date": high_early[0], "gap": high_early[1]},
                "slip": slip["date"] if slip else None, "cross": cross["date"] if cross else None,
                "cross_label": cross_label,
                "milestones": milestones, "multipliers": S["rd_multiplier"],
                "beats": beats, "events": E, "source": src,
            },
            "board": {"rows": board, "verdicts": VERDICTS, "status": STATUS, "dimensions": dims, "source": src},
            "dots": {"resolved": dots, "unmet": unmet, "bandwidth": BANDWIDTH, "ramp": RAMP,
                     "dimensions": list(TREND_DIMENSIONS), "source": src},
            "watch": {"items": sorted(W, key=lambda w: w["date"] or "9999"), "source": src},
        },
    }


def _sched_short(text):
    """Fit the scenario's date wording into the board's 7-character column:
    'Mid 2025' -> 'MID 25', 'Late 2025' -> 'LATE 25', 'Early 2026' -> 'EARLY26', 'Jan 2027' -> 'JAN 27',
    '2025' -> '2025', '2024 onward' -> '2024+', '2025–2026' or '2025 → End 2026' -> '25–26'."""
    toks = text.replace("→", " ").replace("–", " ").split()
    years = [t for t in toks if t[:4].isdigit()]
    if toks[0][:4].isdigit():
        if len(years) >= 2:
            return f"{years[0][2:4]}–{years[-1][2:4]}"
        return f"{toks[0][:4]}+" if len(toks) > 1 else toks[0][:4]
    word, yr = toks[0].upper(), years[0][2:4]
    return f"{word} {yr}" if len(word) <= 4 else f"{word}{yr}"
