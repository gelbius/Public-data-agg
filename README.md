# Public Data Dashboards

Dashboards built only from **public government data**. They refresh themselves every day and compute every headline from the source numbers, so nothing on the pages is typed by hand.

| # | Dashboard | What it shows |
|---|---|---|
| 01 | [The Consumer: an economic state of the union](dashboards/macro/) | Inflation, rates, jobs, wages, credit, sentiment and household spending in the US |

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
- Every number on a page comes from `compute.py`. Templates never contain hand-typed statistics.
- Every chart cites its exact source series and latest observation date, and has a "Show the data" table.
- Chart colors are tested for color-blind safety in both light and dark mode.
- **Every change badge (vs a year ago, vs last year) is color-graded:** green = better for households, red = worse, gray = neutral. Bigger changes get stronger color (3 steps), and an ▲/▼ arrow always shows direction too. Use `viz.deltaBadge(value, {goodUp, full, text})`, where `goodUp` says whether up is good and `full` is the change size that earns the strongest color. Add `viz.deltaKey()` near the badges as the legend.
- Where a fair benchmark exists, color against it instead of zero. For example, household spending is colored by whether it grew **faster or slower than inflation**, not just up or down.
- On phones, swap wide charts for phone-native forms. The spending flow becomes a scroll-driven vertical flow (`viz.flowStory`): an overview, then one cluster of sub-categories per scroll step.

## Repo layout

```
pipeline/            shared tools
  fetch.py           download a dashboard's data
  series.py          time-series helpers (year-over-year, streaks, "lowest since"…)
  build.py           build every dashboard + the home page into dist/
dashboards/
  macro/             dashboard 01
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

## Add a new dashboard

1. Create `dashboards/<name>/` with `sources.json`, `compute.py` (a `compute(data_dir)` function returning `title`, `slug`, `description`, `fetched`, `hub_headline` and your sections), `template.html` and `page.js`. Copying `macro/` is the easiest start.
2. Run `python3 pipeline/fetch.py <name>` and `python3 pipeline/build.py`.
3. It appears on the home page automatically, and the daily job refreshes it too.

## License

Code: MIT (see `LICENSE`). Data: public-domain US government sources; see each dashboard's Method section for series and caveats. ECharts is Apache-2.0 (`site/assets/vendor/`).
