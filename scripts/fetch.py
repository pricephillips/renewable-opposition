"""
fetch.py
--------
Fetcher layer for the renewable-opposition pipeline.

Responsibilities:
  1. Load config/sources.yaml (the source registry).
  2. For each selected source, make its request(s) over HTTP.
  3. Store an immutable raw copy under data/raw/, keyed by content hash.
  4. Append a record to data/raw/manifest.csv (url, hash, fetch_date,
     content_type, local_path, source_id).

Design constraints:
  - Raw files are never overwritten; each fetch produces a new file only if
    the content changed (hash differs from the last fetch of the same
    source_id and URL).
  - Only 'static' and 'api' fetch_method sources run. 'js_render' sources are
    skipped with a logged warning.
  - No parsing or extraction happens here; that is the parser layer's job.
  - A failed request is recorded in the manifest with its error and never
    stops the run: one throttled source must not cost the others their run.

Live intake (`--intake`) fetches every active source that something reads:
a source with an extractor in scripts/extractors/<source_id>.py, or one marked
`watch: true` (change detection only: the manifest records when the upstream
copy last changed). Sources with neither are not fetched on a schedule, since
nothing would read what they store.

Optional fields in a sources.yaml entry (all fetch_method static or api):
  requests       a list of {label, url} or {label, params}: one stored copy
                 per request. `params` are added to the entry's `url`.
  params         query parameters for the entry's single request.
  expand_from    a JSON file (repository-relative) whose "clients" list gives
                 one request per entry: `url` is formatted with each entry's
                 fields (config/legistar_clients.json fills {client}).
  min_interval_s seconds between this source's requests (GDELT asks for one
                 request every 5 seconds); the default is --delay.
  expect         json | xml | html | csv: a response that does not parse as
                 this is refused and recorded as an error (GDELT answers a
                 malformed query with HTTP 200 and a line of text).
  expect_contains  a string the body must contain (a page that changed shape).
  retry          {statuses: [...], backoff_s: [...]}: retry these HTTP
                 statuses after each pause in turn, honouring Retry-After.
  auth_env       an environment variable holding an API token; when it is
                 set, the token is sent in `auth_header` (default
                 Authorization) after `auth_prefix`. Unset, the request goes
                 out without it.
  compress       store the response gzipped, as <sha256><ext>.gz; the hash is
                 of the uncompressed bytes. common.read_raw reads either form.
  watch          fetch on intake runs without an extractor.
  on_change      what to do when a watched source's content changed; printed
                 in the run summary when a new copy replaces an earlier one
                 (a first copy is only the baseline).

--budget-s stops starting new requests once the run has taken that long: each
request not made is recorded as a manifest error, so the workflow commits
what it has well inside its job timeout and the next run starts afresh.

Usage:
    python scripts/fetch.py                    # fetch all active sources
    python scripts/fetch.py --source <id>      # fetch one source (repeatable)
    python scripts/fetch.py --intake           # the sources live intake reads
    python scripts/fetch.py --intake --budget-s 600
    python scripts/fetch.py --dry-run          # print plan, no network calls
"""

import argparse
import csv
import gzip
import hashlib
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.csv"
EXTRACTORS_DIR = Path(__file__).resolve().parent / "extractors"

MANIFEST_FIELDS = [
    "source_id", "url", "fetch_date", "content_type",
    "status_code", "content_hash", "local_path", "error",
]

RUNNABLE_METHODS = ("static", "api")
DEFAULT_RETRY = {"statuses": [429, 502, 503, 504], "backoff_s": [15, 45]}
MAX_RETRY_AFTER_S = 120
TIMEOUT_S = 60

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


def has_extractor(source_id: str) -> bool:
    return (EXTRACTORS_DIR / f"{source_id}.py").exists()


def active_sources(sources: list[dict], source_id=None, intake: bool = False) -> list[dict]:
    """Active sources, narrowed to the given source_id(s) and, for intake, to
    the ones something reads (an extractor, or watch: true)."""
    active = [s for s in sources if s.get("active", False)]
    if source_id:
        wanted = {source_id} if isinstance(source_id, str) else set(source_id)
        active = [s for s in active if s["source_id"] in wanted]
    if intake:
        active = [s for s in active
                  if s.get("fetch_method", "static") in RUNNABLE_METHODS
                  and (has_extractor(s["source_id"]) or s.get("watch"))]
    return active


def with_params(url: str, params: Optional[dict]) -> str:
    """The URL with params appended to its query, in the order given."""
    if not params:
        return url
    parts = urlsplit(url)
    extra = urlencode([(k, str(v)) for k, v in params.items()])
    query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def build_requests(source: dict, root: Path = REPO_ROOT) -> list[tuple[str, str]]:
    """(label, url) for each request a source makes."""
    sid = source["source_id"]
    if source.get("requests"):
        out = []
        for i, req in enumerate(source["requests"], start=1):
            label = req.get("label") or f"{sid}#{i}"
            out.append((label, req.get("url") or with_params(source["url"], req.get("params"))))
        return out
    if source.get("expand_from"):
        spec = json.loads((root / source["expand_from"]).read_text(encoding="utf-8"))
        return [(c.get("client") or c.get("label") or sid,
                 with_params(source["url"].format(**c), source.get("params")))
                for c in spec.get("clients", []) if c.get("active", True)]
    return [(sid, with_params(source["url"], source.get("params")))]


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
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def last_hash_for_source(manifest: list[dict], source_id: str, url: Optional[str] = None) -> Optional[str]:
    """The content_hash from the most recent successful fetch of source_id (and
    of this URL, when a source makes several requests)."""
    rows = [
        r for r in manifest
        if r["source_id"] == source_id and not r.get("error") and r.get("content_hash")
        and (url is None or r.get("url") == url)
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
    if "xml" in ct or "rss" in ct:
        return ".xml"
    if "csv" in ct:
        return ".csv"
    return ".bin"


def looks_like(data: bytes, expect: Optional[str], contains: Optional[str] = None) -> Optional[str]:
    """None when the body is what the source promises, else why not."""
    text_head = data[:120].decode("utf-8", "replace").strip()
    try:
        if expect == "json":
            json.loads(data.decode("utf-8-sig"))
        elif expect == "xml":
            ET.fromstring(data)
        elif expect == "html":
            if b"<html" not in data[:4096].lower() and b"<!doctype" not in data[:4096].lower():
                raise ValueError("no <html> or <!doctype> near the top")
        elif expect == "csv":
            if b"," not in data.split(b"\n", 1)[0]:
                raise ValueError("first line has no comma")
    except (ValueError, ET.ParseError) as exc:
        return f"refused: expected {expect} ({type(exc).__name__}); body starts {text_head!r}"
    if contains and contains.encode("utf-8") not in data:
        return f"refused: body does not contain {contains!r}; body starts {text_head!r}"
    return None


def auth_headers(source: dict) -> dict:
    var = source.get("auth_env")
    token = os.environ.get(var, "").strip() if var else ""
    if not token:
        return {}
    return {source.get("auth_header", "Authorization"): f"{source.get('auth_prefix', '')}{token}"}


def _retry_after(resp: requests.Response) -> Optional[float]:
    try:
        return min(float(resp.headers.get("Retry-After", "")), MAX_RETRY_AFTER_S)
    except ValueError:
        return None


def fetch_url(url: str, timeout: int = 30, headers: Optional[dict] = None,
              retry: Optional[dict] = None, sleep=time.sleep) -> tuple[bytes, str, int]:
    """
    Fetch a URL. Returns (content_bytes, content_type, status_code).
    Retries the statuses in `retry` after each pause in its backoff_s list
    (or the server's Retry-After, capped). Raises requests.RequestException on
    network/HTTP errors that remain.
    """
    retry = retry or {"statuses": [], "backoff_s": []}
    pauses = list(retry.get("backoff_s", []))
    while True:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True, headers=headers or {})
        if resp.status_code in retry.get("statuses", []) and pauses:
            wait = _retry_after(resp) or pauses[0]
            pauses.pop(0)
            log.info(f"    HTTP {resp.status_code}; retrying in {wait:.0f}s")
            sleep(wait)
            continue
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "application/octet-stream")
        return resp.content, ct, resp.status_code


def store_raw(data: bytes, source_id: str, ext: str, compress: bool = False) -> Path:
    """Write data to data/raw/<source_id>/<sha256><ext> (gzipped to
    <sha256><ext>.gz when compress). Never overwrites."""
    sha = content_hash(data)
    dest_dir = RAW_DIR / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (f"{sha}{ext}.gz" if compress else f"{sha}{ext}")
    if not dest.exists():
        # mtime=0 keeps the bytes a function of the content alone.
        dest.write_bytes(gzip.compress(data, compresslevel=9, mtime=0) if compress else data)
    return dest


# ── Main loop ───────────────────────────────────────────────────────────────────────────

def fetch_request(source: dict, url: str, manifest: list[dict], sleep=time.sleep) -> dict:
    """One request of a source: fetch, check, store. Returns its manifest row."""
    sid = source["source_id"]
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
    try:
        data, ct, status = fetch_url(url, timeout=TIMEOUT_S, headers=auth_headers(source),
                                     retry=source.get("retry", DEFAULT_RETRY), sleep=sleep)
    except requests.RequestException as exc:
        resp = getattr(exc, "response", None)
        record["status_code"] = str(resp.status_code) if resp is not None else ""
        record["error"] = str(exc)[:300]
        log.error(f"  {sid}: fetch failed: {record['error']}")
        return record
    record["content_type"] = ct
    record["status_code"] = str(status)
    why = looks_like(data, source.get("expect"), source.get("expect_contains"))
    if why:
        record["error"] = why[:300]
        log.error(f"  {sid}: {record['error']}")
        return record
    sha = content_hash(data)
    record["content_hash"] = sha
    if sha == last_hash_for_source(manifest, sid, url):
        log.info(f"  {sid}: content unchanged (hash={sha[:12]}), skipping store.")
        record["local_path"] = "unchanged"
    else:
        dest = store_raw(data, sid, extension_for(ct, url), compress=bool(source.get("compress")))
        record["local_path"] = dest.relative_to(REPO_ROOT).as_posix()
        log.info(f"  {sid}: stored {dest.name}")
    return record


def skipped_row(sid: str, url: str, why: str) -> dict:
    return {"source_id": sid, "url": url, "fetch_date": datetime.now(timezone.utc).isoformat(),
            "content_type": "", "status_code": "", "content_hash": "", "local_path": "", "error": why}


def process_source(source: dict, manifest: list[dict], dry_run: bool = False,
                   delay: float = 2.0, sleep=time.sleep, deadline: Optional[float] = None,
                   clock=time.monotonic) -> list[dict]:
    """Every request of one source, paced, until the deadline (a clock()
    value) passes. Returns their manifest rows."""
    sid = source["source_id"]
    method = source.get("fetch_method", "static")
    if method not in RUNNABLE_METHODS:
        log.warning(f"{sid}: fetch_method='{method}' not yet implemented, skipping.")
        return [skipped_row(sid, source.get("url", ""), f"skipped: {method} not implemented")]
    reqs = build_requests(source)
    interval = float(source.get("min_interval_s", delay))
    rows = []
    for i, (label, url) in enumerate(reqs):
        if dry_run:
            log.info(f"[dry-run] would fetch {sid} ({label}): {url}")
            continue
        if deadline is not None and clock() >= deadline:
            log.warning(f"{sid} ({label}): run time budget reached; not fetched this run")
            rows.append(skipped_row(sid, url, "skipped: run time budget reached"))
            continue
        if i:
            sleep(interval)
        log.info(f"Fetching {sid} ({label})")
        rec = fetch_request(source, url, manifest, sleep=sleep)
        manifest.append(rec)
        rows.append(rec)
    return rows


def summarize(rows: list[dict], sources: Optional[dict] = None, prior: Optional[set] = None) -> list[str]:
    """One line per source: requests, stored, unchanged, failed; and, for a
    watched source whose upstream changed, what to do about it (on_change).
    `prior` holds the (source_id, url) pairs that had a stored copy before
    this run: a first copy is a baseline, not a change."""
    by: dict[str, dict] = {}
    changed: set = set()
    for r in rows:
        s = by.setdefault(r["source_id"], {"requests": 0, "stored": 0, "unchanged": 0, "failed": 0})
        s["requests"] += 1
        if r.get("error"):
            s["failed"] += 1
        elif r.get("local_path") == "unchanged":
            s["unchanged"] += 1
        else:
            s["stored"] += 1
            if prior is None or (r["source_id"], r.get("url")) in prior:
                changed.add(r["source_id"])
    lines = []
    for sid, s in by.items():
        lines.append(f"{sid}: {s['requests']} request(s), {s['stored']} stored, {s['unchanged']} unchanged, "
                     f"{s['failed']} failed")
        note = ((sources or {}).get(sid) or {}).get("on_change")
        if note and sid in changed:
            lines.append(f"  {note}")
        elif note and s["stored"]:
            lines.append("  first copy stored: the baseline for change detection")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch raw sources for renewable-opposition.")
    parser.add_argument("--source", action="append", help="Fetch only this source_id (repeatable).")
    parser.add_argument("--intake", action="store_true",
                        help="Only the sources live intake reads: an extractor exists, or watch: true.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without fetching.")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds to wait between requests (default: 2).")
    parser.add_argument("--budget-s", type=float,
                        help="Stop starting new requests after this many seconds (each one skipped is recorded).")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        sys.exit(f"Config not found: {CONFIG_PATH}")

    all_sources = load_sources(CONFIG_PATH)
    targets = active_sources(all_sources, source_id=args.source, intake=args.intake)

    if not targets:
        log.warning("No active sources matched. Check config/sources.yaml.")
        return

    log.info(f"Fetching {len(targets)} source(s). dry_run={args.dry_run}")
    manifest = load_manifest(MANIFEST_PATH)
    prior = {(r["source_id"], r.get("url")) for r in manifest if r.get("content_hash") and not r.get("error")}
    deadline = time.monotonic() + args.budget_s if args.budget_s else None

    written = []
    for i, source in enumerate(targets):
        if i and not args.dry_run and not (deadline and time.monotonic() >= deadline):
            time.sleep(args.delay)
        rows = process_source(source, manifest, dry_run=args.dry_run, delay=args.delay, deadline=deadline)
        for rec in rows:
            append_manifest(MANIFEST_PATH, rec)
        written += rows

    for line in summarize(written, {s["source_id"]: s for s in targets}, prior):
        print(line)
    log.info("Done.")


if __name__ == "__main__":
    main()
