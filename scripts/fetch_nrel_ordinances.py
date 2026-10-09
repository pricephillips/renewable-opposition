"""Download NREL's 2025 wind and solar siting ordinance spreadsheets into data/raw/.

  wind   https://data.openei.org/submissions/8519 (DOI 10.25984/3363758, CC BY 4.0)
  solar  https://data.openei.org/submissions/8602 (DOI 10.25984/3363739, CC BY 4.0)

Each file is stored by fetch.py's rules (data/raw/<source_id>/<sha256>.xlsx,
never overwritten) with one row per attempt in data/raw/manifest.csv (URL,
date, HTTP status, SHA-256, local path or the error).

Before anything is stored, the workbook goes through the schema guard
(nrel_ordinances.check_schema): the sheets, every sheet's header and the
feature vocabulary must be exactly what nrel_ordinances.py reads. If NREL
changes the structure, the file is refused, the manifest records why, and the
script exits 1, so a changed layout is never read with the old mapping.

Usage
  python scripts/fetch_nrel_ordinances.py             fetch both
  python scripts/fetch_nrel_ordinances.py --check     re-run the guard on the stored copies
  python scripts/fetch_nrel_ordinances.py --dry-run   print the plan
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from nrel_ordinances import DATASETS, check_schema, newest_raw  # noqa: E402

USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def fetch_one(tech: str, manifest: list[dict], session: requests.Session) -> dict:
    meta = DATASETS[tech]
    sid, url = meta["source_id"], meta["url"]
    record = {"source_id": sid, "url": url, "fetch_date": datetime.now(timezone.utc).isoformat(),
              "content_type": "", "status_code": "", "content_hash": "", "local_path": "", "error": ""}
    try:
        resp = session.get(url, timeout=180)
        record["status_code"] = str(resp.status_code)
        record["content_type"] = resp.headers.get("Content-Type", "")
        resp.raise_for_status()
    except requests.RequestException as exc:
        record["error"] = str(exc)[:300]
        return record
    data = resp.content
    problems = check_schema(data, tech)
    if problems:
        record["error"] = "refused by the schema guard: " + "; ".join(problems)[:600]
        return record
    sha = fetch.content_hash(data)
    record["content_hash"] = sha
    if sha == fetch.last_hash_for_source(manifest, sid):
        record["local_path"] = "unchanged"
    else:
        record["local_path"] = str(fetch.store_raw(data, sid, ".xlsx").relative_to(fetch.REPO_ROOT))
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="run the schema guard on the stored copies")
    args = ap.parse_args()
    if args.dry_run:
        for tech, meta in DATASETS.items():
            print(f"[dry-run] {meta['source_id']}: {meta['url']}")
        return 0
    if args.check:
        bad = 0
        for tech in DATASETS:
            problems = check_schema(newest_raw(tech).read_bytes(), tech)
            print(f"{tech}: " + ("; ".join(problems) if problems else "structure as expected"))
            bad += bool(problems)
        return 1 if bad else 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    manifest = fetch.load_manifest(fetch.MANIFEST_PATH)
    failed = 0
    for tech in DATASETS:
        rec = fetch_one(tech, manifest, session)
        fetch.append_manifest(fetch.MANIFEST_PATH, rec)
        manifest.append(rec)
        if rec["error"]:
            failed += 1
            print(f"{tech}: FAILED {rec['status_code']} {rec['error']}")
        else:
            print(f"{tech}: {rec['content_hash'][:12]} {rec['local_path']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
