"""Download the Sabin Center's September 2026 edition into data/raw/.

"Opposition to Renewable Energy Facilities in the United States: September
2026 Edition" (6th edition, published 2026-09-02, data through 2025-12-31).
Each file is stored by fetch.py's rules: data/raw/<source_id>/<sha256><ext>,
never overwritten, with one row per attempt in data/raw/manifest.csv (URL,
date, HTTP status, SHA-256, local path, or the error).

Files
  sabin_2026_09_report_pdf          the report PDF on Columbia's Scholarship
                                    Archive. Behind a Cloudflare challenge for
                                    scripts and headless browsers on
                                    2026-10-09, and the Internet Archive copy
                                    was blocked too; the failed attempt is
                                    recorded and the PDF must be added by hand.
  sabin_2026_09_restrictions_csv    the Sabin Center's own export of the
                                    edition's restriction entries, linked from
                                    oppositionreport.org ("Restriction data")
  sabin_2026_09_projects_csv        the same for contested projects
  sabin_2026_09_report_html         oppositionreport.org/reports/current/, the
                                    Sabin Center's web edition of the report:
                                    full entry text and its per-state totals
  sabin_2026_09_landing_html        the edition's landing page on the Sabin
                                    Center site, which states the report's
                                    totals (at least 888 restrictions and 567
                                    contested projects, 48 states)

scripts/extract_sabin_edition.py reads the newest stored copy of each.

A file whose first bytes are not what its kind should be (a Cloudflare page
instead of a CSV) is refused and recorded as an error, not stored.

Usage
  python scripts/fetch_sabin_edition.py            fetch every file
  python scripts/fetch_sabin_edition.py --dry-run  print the plan
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

LANDING_URL = ("https://climate.law.columbia.edu/content/"
               "opposition-renewable-energy-facilities-united-states-september-2026-edition")
REPORT_PAGE_URL = "https://scholarship.law.columbia.edu/sabin_climate_change/280/"
PDF_URL = ("https://scholarship.law.columbia.edu/cgi/viewcontent.cgi?"
           "article=1281&context=sabin_climate_change")
HTML_URL = "https://oppositionreport.org/reports/current/"
RESTRICTIONS_URL = ("https://oppositionreport.org/wp-load.php?security_key=04611eaf3d6d15e6"
                    "&export_id=7&action=get_data")
PROJECTS_URL = ("https://oppositionreport.org/wp-load.php?security_key=bec1e2337cf73fbe"
                "&export_id=8&action=get_data")

# source_id -> (url, extension, what the first bytes must look like)
FILES = {
    "sabin_2026_09_report_pdf": (PDF_URL, ".pdf", (b"%PDF",)),
    "sabin_2026_09_restrictions_csv": (RESTRICTIONS_URL, ".csv", (b"ID,Title,",)),
    "sabin_2026_09_projects_csv": (PROJECTS_URL, ".csv", (b"Post iD,Title,",)),
    "sabin_2026_09_report_html": (HTML_URL, ".html", (b"<!DOCTYPE", b"<!doctype", b"<html")),
    "sabin_2026_09_landing_html": (LANDING_URL, ".html", (b"<!DOCTYPE", b"<!doctype", b"<html")),
}
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def looks_right(data: bytes, starts: tuple[bytes, ...]) -> bool:
    head = data[:64].lstrip().removeprefix(b"\xef\xbb\xbf").replace(b'"', b"")
    return any(head.startswith(s) for s in starts)


def fetch_one(source_id: str, manifest: list[dict], session: requests.Session) -> dict:
    url, ext, starts = FILES[source_id]
    record = {"source_id": source_id, "url": url, "fetch_date": datetime.now(timezone.utc).isoformat(),
              "content_type": "", "status_code": "", "content_hash": "", "local_path": "", "error": ""}
    try:
        resp = session.get(url, timeout=120)
        record["status_code"] = str(resp.status_code)
        record["content_type"] = resp.headers.get("Content-Type", "")
        resp.raise_for_status()
    except requests.RequestException as exc:
        record["error"] = str(exc)[:300]
        return record
    data = resp.content
    if not looks_right(data, starts):
        record["error"] = f"refused: content does not look like {ext} (first bytes {data[:40]!r})"
        return record
    sha = fetch.content_hash(data)
    record["content_hash"] = sha
    if sha == fetch.last_hash_for_source(manifest, source_id):
        record["local_path"] = "unchanged"
    else:
        record["local_path"] = str(fetch.store_raw(data, source_id, ext).relative_to(fetch.REPO_ROOT))
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        for sid, (url, ext, _) in FILES.items():
            print(f"[dry-run] {sid}: {url} -> data/raw/{sid}/<sha256>{ext}")
        return 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    manifest = fetch.load_manifest(fetch.MANIFEST_PATH)
    failed = 0
    for sid in FILES:
        rec = fetch_one(sid, manifest, session)
        fetch.append_manifest(fetch.MANIFEST_PATH, rec)
        manifest.append(rec)
        if rec["error"]:
            failed += 1
            print(f"{sid}: FAILED {rec['status_code']} {rec['error']}")
        else:
            print(f"{sid}: {rec['content_hash'][:12]} {rec['local_path']}")
    if failed:
        print(f"{failed} file(s) not fetched; add them to data/raw/ by hand (see the manifest rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
