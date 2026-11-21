# Public Data Dashboards

Dashboards built from **public data**. Every headline is computed from the source numbers, so nothing on the pages is typed by hand. Dashboards 01–02 use government data and refresh themselves every day; dashboard 03 is refreshed every weekday after the market close. Dashboard 04 is curated by hand from linked sources (see below).

| # | Dashboard | What it shows |
|---|---|---|
| 01 | [The Consumer: an economic state of the union](dashboards/macro/) | Inflation, rates, jobs, wages, business price pressure, housing affordability, credit, sentiment and household spending in the US |
| 02 | [AI at work](dashboards/ai/) | How many US businesses use AI, which industries lead, and its effect on jobs so far (Census BTOS) |
| 03 | [Tech valuations & deals](dashboards/tech/) | Valuation multiples (TTM) by tech category, how they moved over 6 and 12 months, notable deals of the last six months, and the biggest private AI valuations |
| 04 | [AI 2027 vs reality](dashboards/ai2027/) | The AI 2027 scenario's 36 dated predictions scored against what happened, a scroll-driven seismograph of whether AI progress runs behind or ahead of the script, and a split-flap board of every prediction |

Design follows the [Foundry Solutions](https://foundrysolutions.ai) brand. Charts use [Apache ECharts](https://echarts.apache.org).

---

## How it works

Think of it as a small kitchen that cooks fresh every morning:

```
 1. SHOP     pipeline/fetch.py   downloads raw data (FRED, BLS)    → data/<dashboard>/
 2. COOK     dashboards/*/compute.py  turns raw data into every number,
                                      chart series and headline sentence
 3. PLATE    pipeline/build.py   pours those numbers into the page → dist/
 4. SERVE    Cloudflare Pages    publishes dist/ to the web
```

A GitHub Action (`.github/workflows/refresh-data.yml`) runs steps 1–3 every day at 14:17 UTC. If the data changed, it commits it, and Cloudflare redeploys automatically.

**Ground rules**
- Only public data. No API keys are required (an optional free `BLS_API_KEY` raises the BLS rate limit).
- Sources so far: FRED (Federal Reserve Bank of St. Louis), BLS, BEA, EIA, Freddie Mac, University of Michigan, the Census Bureau's Business Trends and Outlook Survey, and Zillow Research (free with attribution). We avoid data whose terms restrict reprinting (e.g. NAR's tables).
- Every number on a page comes from `compute.py`. Templates never contain hand-typed statistics.
- Every chart cites its exact source series and latest observation date, and has a "Show the data" table.
- Chart colors are tested for color-blind safety in both light and dark mode.
- **Every change badge (vs a year ago, vs last year) is color-graded:** green = better for households, red = worse, gray = neutral. Bigger changes get stronger color on a continuous gradient, and an ▲/▼ arrow always shows direction too. Use `viz.deltaBadge(value, {goodUp, full, text})`, where `goodUp` says whether up is good and `full` is the change size that earns the strongest color. Add `viz.deltaKey()` near the badges as the legend.
- Where a fair benchmark exists, color against it instead of zero. For example, household spending is colored by whether it grew **faster or slower than inflation**, not just up or down.
- On phones, swap wide charts for phone-native forms. The spending flow becomes a scroll-driven vertical flow (`viz.flowStory`): an overview, then one cluster of sub-categories per scroll step.

## Repo layout

```
pipeline/            shared tools
  fetch.py           download a dashboard's data (FRED, BLS, Census BTOS, Zillow, SEC)
  sec.py             SEC EDGAR company financials (needs SEC_USER_AGENT, see below)
  tech_snapshot.py   validate and write dashboard 03's price snapshot
  btos.py            extract Census BTOS questions by wording
  xlsx.py            tiny Excel reader (standard library only)
  series.py          time-series helpers (year-over-year, streaks, "lowest since"…)
  build.py           build every dashboard + the home page into dist/
dashboards/
  macro/             dashboard 01
  ai/                dashboard 02 (same four files)
  tech/              dashboard 03 (plus fin.py: trailing-12-month math from SEC filings)
    sources.json     which series to download
    compute.py       all the math and headline sentences
    template.html    page layout
    page.js          wires the data to the charts
site/                shared look and home page
  assets/foundry.css design system (brand colors, type, cards, light/dark)
  assets/viz.js      chart helpers (crosshair tooltips, bands, tables)
  hub.html           home page listing all dashboards
data/                downloaded raw data, committed so every number is traceable
```

## Run it on your own computer

You need Python 3.10 or newer. Nothing else to install.

```bash
python3 pipeline/fetch.py macro     # download fresh data (optional, data is committed)
python3 pipeline/build.py           # build the site into dist/
python3 -m http.server 8000 -d dist # open http://localhost:8000
```

## Refreshing dashboard 03 (tech)

The daily GitHub job skips dashboard 03. A scheduled Claude session refreshes it every weekday at 5:47 PM Eastern, after the market close:

1. Pulls market caps, share counts and split-adjusted closes through the owner's brokerage data connector: today, the previous trading day, 6 and 12 months ago, and month-end closes for the last 12 months (for the sector-multiples chart). Then runs `python3 pipeline/tech_snapshot.py build raw.json`. The script refuses to write if a ticker is missing or a market cap disagrees with shares × price.
2. Re-pulls SEC filings: `python3 pipeline/fetch.py tech --force`. The SEC requires a contact email in the request header. It comes from the `SEC_USER_AGENT` environment variable, set privately on the cloud environment. Never commit it.
3. Reviews the curated lists. `data/tech/deals.json` keeps every deal (the page filters by date, sector and type); new deals need a primary source link, and acquired private companies get their funding history and key investors. `data/tech/quotes.json` holds investor quotes, copied word for word with a link. `data/tech/private.json` holds private valuations. Delisted deal targets keep their SEC filings via `sec.cik` in `sources.json`.
4. Rebuilds, checks the page and pushes to `main`.

To run it yourself:

```bash
export SEC_USER_AGENT="public-data-agg dashboard you@example.com"
python3 pipeline/tech_snapshot.py dates          # the dates to pull closes for
python3 pipeline/tech_snapshot.py build raw.json # after writing raw.json (format in the script)
python3 pipeline/fetch.py tech --force
python3 pipeline/build.py
```

## Updating dashboard 04 (AI 2027 vs reality)

Dashboard 04 has no automatic download: its inputs are hand-curated JSON files in `data/ai2027/`, each with a `_doc` note explaining its fields.

- `predictions.json`: the 36 predictions, their verdicts, dates and source links. When new evidence lands, update `reality`, `verdict`, `actual` / `verdict_on`, and the `checkpoints` that feed the schedule-gap trend, then bump `as_of`.
- `events.json`: dated real-world events shown on the seismograph and in the telegraph slip. Every event needs a primary link.
- `scenario.json`: the AI 2027 scenario's own research-speed figures (quoted from ai-2027.com) that shape the red "script" curve.
- `story.json`: the scroll story. Readings in `{braces}` are filled in by `compute.py`, so the text never goes stale.
- `watch.json`: what to watch next.

Then run `python3 pipeline/build.py`. `compute.py` recomputes the counts, the trend, both curves and every reading quoted on the page.

## Publish with Cloudflare Pages

In the Cloudflare dashboard: **Workers & Pages → Create → Pages → Connect to Git**, pick this repo, then:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Framework preset | None |
| Build command | `python3 pipeline/build.py` |
| Build output directory | `dist` |
| Environment variable | `PYTHON_VERSION` = `3.12` |

Every push to `main` (including the daily data commit) redeploys the site.

**Troubleshooting:** if Cloudflare stops deploying new commits (its Deployments page shows a "disconnected from your Git account" warning), the repo was probably renamed or the Cloudflare GitHub app lost access. Fix it under **Settings → Builds → Git repository → Manage**, make sure this repo is selected, then push a new commit. Pushes made while it was disconnected are not redeployed automatically.

## Add a new dashboard

1. Create `dashboards/<name>/` with `sources.json`, `compute.py` (a `compute(data_dir)` function returning `title`, `slug`, `description`, `fetched`, `hub_headline` and your sections), `template.html` and `page.js`. Copying `macro/` is the easiest start.
2. Run `python3 pipeline/fetch.py <name>` and `python3 pipeline/build.py`.
3. It appears on the home page automatically, and the daily job refreshes it too.

## License

Code: MIT (see `LICENSE`). Data: public-domain US government sources; see each dashboard's Method section for series and caveats. ECharts is Apache-2.0 (`site/assets/vendor/`).
