"""
fetch.py
--------
Fetcher layer for the renewable-opposition pipeline.

Responsibilities:
  1. Load config/sources.yaml (the source registry).
  2. For each active source, fetch the page/document via HTTP.
  3. Store an immutable raw copy under data/raw/, keyed by content hash.
  4. Append a record to data/raw/manifest.csv (url, hash, fetch_date,
     content_type, local_path, source_id).

Design constraints:
  - Raw files are never overwritten; each fetch produces a new file if
    content changed (hash differs from last fetch of same source_id).
  - Only 'static' fetch_method sources are active in v1.
    'js_render' sources are skipped with a logged warning.
  - No parsing or extraction happens here; that is the parser layer's job.

Usage:
    python scripts/fetch.py                    # fetch all active sources
    python scripts/fetch.py --source <id>      # fetch one source by source_id
    python scripts/fetch.py --dry-run          # print plan, no network calls
"""

import argparse
import csv
import hashlib
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.csv"

MANIFEST_FIELDS = [
    "source_id", "url", "fetch_date", "content_type",
    "status_code", "content_hash", "local_path", "error",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "renewable-opposition-pipeline/0.1 "
        "(research; contact: github.com/pricephillips/renewable-opposition)"
    )
})


# ── Config ──────────────────────────────────────────────────────────────────────────────

def load_sources(config_path: Path) -> list[dict]:
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("sources", [])


def active_sources(sources: list[dict], source_id: Optional[str] = None) -> list[dict]:
    active = [s for s in sources if s.get("active", False)]
    if source_id:
        active = [s for s in active if s["source_id"] == source_id]
    return active


# ── Manifest ────────────────────────────────────────────────────────────────────────────

def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_manifest(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def last_hash_for_source(manifest: list[dict], source_id: str) -> Optional[str]:
    """Return the content_hash from the most recent successful fetch of source_id."""
    rows = [
        r for r in manifest
        if r["source_id"] == source_id and not r.get("error")
    ]
    return rows[-1]["content_hash"] if rows else None


# ── Fetch ───────────────────────────────────────────────────────────────────────────────

def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extension_for(content_type: str, url: str) -> str:
    ct = content_type.lower()
    if "pdf" in ct or url.lower().endswith(".pdf"):
        return ".pdf"
    if "html" in ct:
        return ".html"
    if "json" in ct:
        return ".json"
    return ".bin"


def fetch_url(url: str, timeout: int = 30) -> tuple[bytes, str, int]:
    """
    Fetch a URL. Returns (content_bytes, content_type, status_code).
    Raises requests.RequestException on network/HTTP errors.
    """
    resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    ct = resp.headers.get("Content-Type", "application/octet-stream")
    return resp.content, ct, resp.status_code


def store_raw(data: bytes, source_id: str, ext: str) -> Path:
    """Write data to data/raw/<source_id>/<sha256><ext>. Never overwrites."""
    sha = content_hash(data)
    dest_dir = RAW_DIR / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sha}{ext}"
    if not dest.exists():
        dest.write_bytes(data)
    return dest


# ── Main loop ───────────────────────────────────────────────────────────────────────────

def process_source(source: dict, manifest: list[dict], dry_run: bool = False) -> dict:
    sid = source["source_id"]
    url = source["url"]
    method = source.get("fetch_method", "static")

    record: dict = {
        "source_id": sid,
        "url": url,
        "fetch_date": datetime.now(timezone.utc).isoformat(),
        "content_type": "",
        "status_code": "",
        "content_hash": "",
        "local_path": "",
        "error": "",
    }

    if method != "static":
        msg = f"{sid}: fetch_method='{method}' not yet implemented — skipping."
        log.warning(msg)
        record["error"] = f"skipped: {method} not implemented"
        return record

    if dry_run:
        log.info(f"[dry-run] would fetch {sid}: {url}")
        return record

    try:
        log.info(f"Fetching {sid}: {url}")
        data, ct, status = fetch_url(url)
        sha = content_hash(data)
        record["content_type"] = ct
        record["status_code"] = str(status)
        record["content_hash"] = sha

        prev_hash = last_hash_for_source(manifest, sid)
        if sha == prev_hash:
            log.info(f"  {sid}: content unchanged (hash={sha[:12]}…), skipping store.")
            record["local_path"] = "unchanged"
        else:
            ext = extension_for(ct, url)
            dest = store_raw(data, sid, ext)
            record["local_path"] = str(dest.relative_to(REPO_ROOT))
            log.info(f"  {sid}: stored {dest.name}")

    except requests.RequestException as exc:
        log.error(f"  {sid}: fetch failed — {exc}")
        record["error"] = str(exc)

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch raw sources for renewable-opposition.")
    parser.add_argument("--source", help="Fetch only this source_id.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without fetching.")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds to wait between requests (default: 2).")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        sys.exit(f"Config not found: {CONFIG_PATH}")

    all_sources = load_sources(CONFIG_PATH)
    targets = active_sources(all_sources, source_id=args.source)

    if not targets:
        log.warning("No active sources matched. Check config/sources.yaml.")
        return

    log.info(f"Fetching {len(targets)} source(s). dry_run={args.dry_run}")
    manifest = load_manifest(MANIFEST_PATH)

    for i, source in enumerate(targets):
        record = process_source(source, manifest, dry_run=args.dry_run)
        if not args.dry_run:
            append_manifest(MANIFEST_PATH, record)
            manifest.append(record)
        if i < len(targets) - 1:
            time.sleep(args.delay)

    log.info("Done.")


if __name__ == "__main__":
    main()
