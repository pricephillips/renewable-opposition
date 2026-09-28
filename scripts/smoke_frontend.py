"""Load every published page in a headless browser and fail on any page error.

Why this exists: on 2026-09-25 the map and map-audit pages both threw during
initialization (a control removed from the markup, a constant read before its
declaration) and rendered nothing, and nothing in CI looked. A syntax check
would not have caught either -- both were valid JavaScript that failed at run
time -- so this loads each page the way a reader would and checks that it
reached a usable state.

For each page in PAGES:
  - serve the repository over http (pages fetch their data with relative URLs);
  - fail on any uncaught page error;
  - fail if the page's own "records loaded" signal (a selector whose text must
    contain a nonzero number) does not appear within the timeout.

Map tiles and web fonts are blocked on purpose: they are decoration, and a
tile outage is not a page defect. Leaflet itself is required. Where the CDN is
unreachable (sandboxed sessions), pass --leaflet-dir pointing at a local copy
(the directory holding leaflet/ and leaflet.markercluster/ from npm) and the
CDN requests are served from it.

Usage
  python scripts/smoke_frontend.py
  python scripts/smoke_frontend.py --leaflet-dir /path/to/node_modules
  python scripts/smoke_frontend.py --screenshots out/

Requires: pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import argparse
import functools
import http.server
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# page -> (selector whose text proves records loaded, what it should say)
PAGES = {
    "index.html": ("#resultBadge, .result-badge, [id$='Badge']", "records"),
    "renewable-opposition-map.html": ("#resultBadge", "instances"),
    "map-audit.html": ("body", "Visible records"),
    "dashboard.html": ("body", "records"),
}
BLOCKED = re.compile(r"(tile\.openstreetmap|basemaps\.cartocdn|arcgisonline|fontshare|fonts\.g)")
CDN = re.compile(r"https://unpkg\.com/(leaflet(?:\.markercluster)?)@[^/]+/(.*)")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def check_page(page, url: str, selector: str, expect: str, timeout_ms: int) -> list[str]:
    problems: list[str] = []
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            """([sel, word]) => [...document.querySelectorAll(sel)].some(el => {
                   const t = el.innerText || '';
                   return t.includes(word) && /[1-9]/.test(t);
               })""",
            arg=[selector, expect], timeout=timeout_ms)
    except Exception:
        problems.append(f"no nonzero '{expect}' count appeared in {selector!r} within {timeout_ms} ms")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--leaflet-dir", type=Path, help="local node_modules with leaflet packages")
    ap.add_argument("--screenshots", type=Path, help="write one screenshot per page here")
    ap.add_argument("--timeout", type=int, default=15000, help="ms to wait for records per page")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    httpd, port = serve(ROOT)
    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, (selector, expect) in PAGES.items():
            if not (ROOT / name).exists():
                continue
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.route(BLOCKED, lambda route: route.abort())
            if args.leaflet_dir:
                # Playwright passes (route, request) to a handler that accepts
                # two arguments, so the directory must not be a parameter.
                base = args.leaflet_dir

                def local_cdn(route):
                    m = CDN.match(route.request.url)
                    path = base / m.group(1) / m.group(2)
                    if path.exists():
                        route.fulfill(path=str(path))
                    else:
                        route.abort()
                page.route(CDN, local_cdn)
            problems = check_page(page, f"http://127.0.0.1:{port}/{name}", selector, expect, args.timeout)
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.screenshots / f"{Path(name).stem}.png"))
            status = "ok  " if not problems else "FAIL"
            print(f"{status} {name}")
            for p in problems:
                print(f"     {p}")
            failures += bool(problems)
            page.close()
        browser.close()
    httpd.shutdown()
    print(f"{len(PAGES) - failures}/{len(PAGES)} pages loaded cleanly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
