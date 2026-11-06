#!/usr/bin/env python3
"""Build the static site into dist/.

Usage:  python3 pipeline/build.py

For every folder in dashboards/ that has compute.py + template.html:
  1. run compute(data/<name>) to get every number, series and headline,
  2. embed that JSON into template.html,
  3. write dist/<slug>/index.html (+ the dashboard's page.js).
Then copy shared assets to dist/assets/ and write the home page dist/index.html.

Standard library only, so Cloudflare Pages can run it with its built-in Python.
"""
import html
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT / "pipeline"))


def load_compute(dash_dir):
    spec = importlib.util.spec_from_file_location(f"compute_{dash_dir.name}", dash_dir / "compute.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def embed_json(obj):
    """JSON safe to place inside <script type="application/json">."""
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")


def build_dashboard(dash_dir):
    mod = load_compute(dash_dir)
    data = mod.compute(ROOT / "data" / dash_dir.name)
    data["order"] = getattr(mod, "ORDER", 99)
    out_dir = DIST / data["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    page = (dash_dir / "template.html").read_text()
    page = page.replace("__DESCRIPTION__", html.escape(data["description"]))
    page = page.replace("__DATA__", embed_json(data))
    (out_dir / "index.html").write_text(page)
    for extra in ("page.js",):
        if (dash_dir / extra).exists():
            shutil.copy(dash_dir / extra, out_dir / extra)
    print(f"  built /{data['slug']}/  ({len(page) // 1024} KB)")
    return data


def build_hub(dashboards):
    cards = []
    for i, d in enumerate(dashboards, 1):
        cards.append(f"""
      <a class="card hub-card" href="{d['slug']}/">
        <span class="num">DASHBOARD {i:02d} · DATA {html.escape(d['fetched'] or '')}</span>
        <h2>{html.escape(d['title'])}</h2>
        <p>{html.escape(d['hub_headline'])}</p>
        <p>{html.escape(d['description'])}</p>
        <span class="go">Open dashboard →</span>
      </a>""")
    cards.append("""
      <div class="card hub-card soon" aria-label="More dashboards coming">
        <span class="num">DASHBOARD __NEXT__</span>
        <h2>Next up</h2>
        <p>More public-data dashboards will land here, built on the same pipeline and design system.</p>
      </div>""")
    cards[-1] = cards[-1].replace("__NEXT__", f"{len(dashboards) + 1:02d}")
    tpl = (ROOT / "site" / "hub.html").read_text()
    (DIST / "index.html").write_text(tpl.replace("__CARDS__", "".join(cards)))
    print("  built / (home)")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ROOT / "site" / "assets", DIST / "assets")
    for f in ("_headers",):
        if (ROOT / "site" / f).exists():
            shutil.copy(ROOT / "site" / f, DIST / f)
    print("Building site")
    built = []
    for dash_dir in (p for p in (ROOT / "dashboards").iterdir() if (p / "compute.py").exists()):
        built.append(build_dashboard(dash_dir))
    built.sort(key=lambda d: d.get("order", 99))  # dashboard number on the home page
    build_hub(built)
    print(f"Done: {DIST}")


if __name__ == "__main__":
    main()
