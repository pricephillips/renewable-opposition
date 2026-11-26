#!/usr/bin/env python3
"""Find solar, wind and storage developments in open map and federal filing data (the development scout).

The project universe (docs/predictive_foundation_design.md, section 5) comes
from the federal plant inventories (scripts/fetch_facilities.py) and the
interconnection queues (scripts/fetch_queued_up.py). Both miss projects at
the start: a wind farm files with the FAA for its turbines before it is in
any inventory, and many projects are mapped by local people while being
built. This script reads two open geographic sources for those projects,
places each in its county by its coordinates, and sorts out the ones the
inventories and the queues already hold. What is left goes to the
development-reader agent (docs/development_scout.md).

Sources (config/development_scout.json, "sources")
  faa_oeaaa     FAA Obstruction Evaluation / Airport Airspace Analysis. Any
                structure over 200 feet, so every utility wind turbine, is
                filed on Form 7460-1 before it is built. The FAA publishes
                every case as one CSV per region and year; regions WTE and
                WTW hold the wind turbines. Each filing has coordinates, a
                county, dates, a status and often a sponsor. Public domain.
                Filings within cluster_km of each other are one candidate
                project (single linkage), so a 120-turbine array is one row.
                Crane filings mark construction; a group of cranes with no
                turbine or met tower is a port or vessel staging area
                (stage crane_only) and never reaches the worklist.
  osm_overpass  OpenStreetMap, through the Overpass API: power plants tagged
                under construction or proposed whose source is solar, wind
                or battery. ODbL 1.0; the OSM rows of the output are offered
                under the ODbL with attribution "(c) OpenStreetMap
                contributors".

A filing or a map tag is a lead about a place, never a record. It does not
say who opposed what, and the FAA's "No Hazard" is an airspace finding, not a
permit. Nothing here changes a published record.

Sorting (deterministic; "matching" in the config)
  known_facility  a plant of the same technology in data/reference/
                  facilities.csv (EIA-860M, USWTDB, USPVDB) lies within
                  facility_km of the candidate.
  queue_county    no such plant, but an active or suspended interconnection
                  request of the same technology is in the same county
                  (data/reference/queue_projects.csv); the queue has no
                  coordinates, so a reader decides whether it is the same
                  project.
  new             neither.

Outputs
  data/reference/development_signals.csv           every candidate, one row each
  data/reference/development_signals_manifest.csv  URL, SHA-256 and rows per file read
  data/review/development_worklist.csv             new and queue_county candidates
                                                   nobody has resolved, ranked
A source that cannot be fetched keeps its rows from the last run, and the
manifest says so: an outage never reads as a run that found nothing.

Resolutions. data/review/development_resolutions.csv holds what a
development-reader and a blind-reviewer agreed on (verdicts in the config),
written by the record-editor. A resolved candidate leaves the worklist and
carries its verdict in development_signals.csv.

Usage
  python scripts/development_scout.py                        fetch every source, sort, write
  python scripts/development_scout.py --only faa_oeaaa       one source (the others keep their rows)
  python scripts/development_scout.py --faa FILE [FILE ...] --osm FILE   local copies
  python scripts/development_scout.py --dry-run              print the plan
  python scripts/development_scout.py batch                  today's candidates for the daily routine
  python scripts/development_scout.py card <signal_id>       the reader's card (also the blind card)
  python scripts/development_scout.py check <packet>         check a draft or review packet
  python scripts/development_scout.py reconcile <draft> <review>
                                                             print the resolution row when both agree
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo  # noqa: E402
from common import ROOT, STATE_CODES, read_csv, write_csv  # noqa: E402

CONFIG_PATH = ROOT / "config" / "development_scout.json"
REFERENCE_DIR = ROOT / "data" / "reference"
SIGNALS_PATH = REFERENCE_DIR / "development_signals.csv"
MANIFEST_PATH = REFERENCE_DIR / "development_signals_manifest.csv"
FACILITIES_PATH = REFERENCE_DIR / "facilities.csv"
QUEUE_PATH = REFERENCE_DIR / "queue_projects.csv"
WORKLIST_PATH = ROOT / "data" / "review" / "development_worklist.csv"
RESOLUTIONS_PATH = ROOT / "data" / "review" / "development_resolutions.csv"
LOG_PATH = ROOT / "data" / "review" / "verification_log.csv"
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")

FIELDS = ["signal_id", "source", "technology", "stage", "name", "sponsor", "description", "state",
          "county_fips", "counties_fips", "latitude", "longitude", "structures", "cranes", "met_towers",
          "first_filed", "last_filed", "statuses", "height_ft_max", "source_url", "case_ids",
          "match_status", "facility_id", "facility_status", "facility_km", "queue_project_ids", "resolution"]
MANIFEST_FIELDS = ["source", "url", "sha256", "bytes", "fetched_at", "data_as_of", "rows_read",
                   "rows_kept", "result"]
WORKLIST_FIELDS = ["rank", "signal_id", "technology", "stage", "state", "county_fips", "county",
                   "structures", "first_filed", "last_filed", "name", "sponsor", "match_status",
                   "queue_project_ids", "source_url", "search_hint"]
RESOLUTION_FIELDS = ["signal_id", "verdict", "technology", "stage", "project_name", "developer",
                     "county_fips", "matched_id", "capacity_mw", "evidence_url", "evidence_date",
                     "evidence_note", "reviewer", "access", "archived_url", "opposition_url", "checked_on"]
FAA_REQUIRED = ["STUDY (ASN)", "STATUS", "RECEIVED DATE", "LATITUDE", "LONGITUDE", "STRUCTURE STATE",
                "STRUCTURE TYPE", "NOTICE OF", "PROPOSAL DESCRIPTION", "AGL HEIGHT PROPOSED"]
STAGE_ORDER = ["under_construction", "determined", "filed", "proposed", "prospecting",
               "determined_hazard", "terminated", "withdrawn"]
ENDED = {"terminated", "withdrawn", "crane_only"}
EMDASH = "—"


class SchemaError(ValueError):
    pass


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742.0 * math.asin(min(1.0, math.sqrt(a)))


def _num(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _place(lat: float, lon: float) -> str:
    if not (-180 <= lon <= -60 and 15 <= lat <= 72):
        return ""
    return geo.county_at(lat, lon)


def _clean(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", (text or "").replace(EMDASH, "-")).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


# ── FAA OE/AAA ──────────────────────────────────────────────────────────────

def read_faa(data: bytes, src: dict) -> tuple[list[dict], int, str]:
    """(filings kept, rows read, "data as of" line). The archive's free text
    escapes quotes with a backslash, and its last line dates the file."""
    text = data.decode("utf-8", errors="replace")
    as_of = ""
    m = re.search(r"Data as of ([0-9/]+ [0-9:]+ [AP]M)", text[-200:])
    if m:
        as_of = m.group(1)
    reader = csv.DictReader(io.StringIO(text), escapechar="\\")
    cols = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in FAA_REQUIRED if c not in cols]
    if missing:
        raise SchemaError(f"FAA archive lacks columns {missing}")
    kinds, stages = src["structure_types"], src["stage_by_status"]
    kept, read = [], 0
    for raw in reader:
        r = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k}
        if not re.match(r"\d{4}-[A-Z]+-\d+-", r.get("STUDY (ASN)", "")):
            continue  # the blank line and "Data as of" at the end
        read += 1
        lat, lon = _num(r["LATITUDE"]), _num(r["LONGITUDE"])
        kind = kinds.get(r["STRUCTURE TYPE"])
        if lat is None or lon is None or not kind or r["NOTICE OF"] in src["skip_notice"]:
            continue
        if r["STRUCTURE STATE"] not in STATE_CODES:
            continue
        kept.append({"asn": r["STUDY (ASN)"], "lat": lat, "lon": lon, "kind": kind,
                     "stage": stages.get(r["STATUS"], "filed"), "status": r["STATUS"],
                     "received": r["RECEIVED DATE"][:10], "state": r["STRUCTURE STATE"],
                     "sponsor": r.get("SPONSOR NAME", ""), "description": r["PROPOSAL DESCRIPTION"],
                     "height": _num(r["AGL HEIGHT PROPOSED"])})
    return kept, read, as_of


def cluster(points: list[dict], radius_km: float) -> list[list[dict]]:
    """Single-linkage groups of points within radius_km, on a grid so each
    point is compared only with its neighbours."""
    cell = radius_km / 111.0
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, p in enumerate(points):
        grid[(int(p["lat"] // cell), int(p["lon"] // cell))].append(i)
    parent = list(range(len(points)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for (gy, gx), members in grid.items():
        near = [j for dy in (-1, 0, 1) for dx in (-2, -1, 0, 1, 2) for j in grid.get((gy + dy, gx + dx), ())]
        for i in members:
            for j in near:
                if j > i and find(i) != find(j):
                    a, b = points[i], points[j]
                    if km(a["lat"], a["lon"], b["lat"], b["lon"]) <= radius_km:
                        parent[find(i)] = find(j)
    groups: dict[int, list[dict]] = defaultdict(list)
    for i, p in enumerate(points):
        groups[find(i)].append(p)
    return list(groups.values())


def _asn_key(asn: str) -> tuple:
    parts = asn.split("-")
    return (parts[0], int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0, asn)


def faa_signals(filings: list[dict], src: dict, since: str) -> list[dict]:
    filings = [f for f in filings if f["received"] >= since]
    # A filing re-studied under a new number keeps its place; one case per point.
    seen: dict[tuple, dict] = {}
    for f in sorted(filings, key=lambda f: _asn_key(f["asn"])):
        seen[(round(f["lat"], 5), round(f["lon"], 5), f["kind"])] = f
    out = []
    for group in cluster(list(seen.values()), src["cluster_km"]):
        group.sort(key=lambda f: _asn_key(f["asn"]))
        kinds = Counter(f["kind"] for f in group)
        stages = Counter(f["stage"] for f in group)
        if kinds["crane"] and not kinds["turbine"] and not kinds["met_tower"]:
            # Cranes alone: a port or vessel staging area, not a site.
            stage = "crane_only"
        elif kinds["crane"]:
            stage = "under_construction"
        elif stages.keys() <= {"terminated", "withdrawn"}:
            stage = "withdrawn" if stages["withdrawn"] >= stages["terminated"] else "terminated"
        elif not kinds["turbine"]:
            stage = "prospecting"
        else:
            stage = next(s for s in STAGE_ORDER[1:] if stages[s])
        lat = sum(f["lat"] for f in group) / len(group)
        lon = sum(f["lon"] for f in group) / len(group)
        counties = Counter(c for c in (_place(f["lat"], f["lon"]) for f in group) if c)
        sponsors = Counter(f["sponsor"] for f in group if f["sponsor"])
        descs = Counter(_clean(f["description"]) for f in group if f["description"])
        heights = [f["height"] for f in group if f["height"]]
        first = group[0]["asn"]
        out.append({
            "signal_id": f"faa:{first}", "source": "faa_oeaaa", "technology": src["technology"],
            "stage": stage, "name": "", "sponsor": _clean(sponsors.most_common(1)[0][0], 80) if sponsors else "",
            "description": descs.most_common(1)[0][0] if descs else "",
            "state": Counter(f["state"] for f in group).most_common(1)[0][0],
            "county_fips": counties.most_common(1)[0][0] if counties else "",
            "counties_fips": ";".join(sorted(counties)),
            "latitude": round(lat, 5), "longitude": round(lon, 5),
            "structures": kinds["turbine"], "cranes": kinds["crane"], "met_towers": kinds["met_tower"],
            "first_filed": min(f["received"] for f in group), "last_filed": max(f["received"] for f in group),
            "statuses": ";".join(f"{k}:{v}" for k, v in sorted(stages.items())),
            "height_ft_max": int(max(heights)) if heights else "",
            "source_url": src["case_url_template"].format(asn=first),
            "case_ids": ";".join(f["asn"] for f in group[:5]),
            "_points": [(f["lat"], f["lon"]) for f in group],
        })
    return out


def faa_urls(src: dict, since: str, today: date) -> list[str]:
    years = range(int(since[:4]), today.year + 1)
    return [src["url_template"].format(region=r, year=y) for r in src["regions"] for y in years]


# ── OpenStreetMap (Overpass) ────────────────────────────────────────────────

def overpass_query(src: dict, state: str) -> str:
    parts = []
    for sel in src["selectors"]:
        tags = "".join(f'["{k}"="{v}"]' for k, v in sel["tags"].items())
        parts.append(f"nwr{tags}(area.a);")
    return (f'[out:json][timeout:{int(src["timeout_s"])}];'
            f'area["ISO3166-2"="US-{state}"][admin_level=4]->.a;({"".join(parts)});out center tags;')


def _osm_stage(tags: dict, src: dict) -> str | None:
    for sel in src["selectors"]:
        if all(tags.get(k) == v for k, v in sel["tags"].items()):
            return sel["stage"]
    return None


def _osm_technology(tags: dict, src: dict) -> str:
    for key in src["source_keys"]:
        for token in re.split(r"[;,]\s*", tags.get(key, "").lower()):
            if token in src["technology_by_source"]:
                return src["technology_by_source"][token]
    if tags.get("plant:storage") or tags.get("construction:plant:storage"):
        return "battery_storage"
    return ""


def osm_signals(payload: dict, src: dict, state: str) -> list[dict]:
    out = []
    for e in payload.get("elements", []):
        tags = e.get("tags", {})
        stage, tech = _osm_stage(tags, src), _osm_technology(tags, src)
        point = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
        if not stage or not tech or not point:
            continue
        lat, lon = float(point["lat"]), float(point["lon"])
        county = _place(lat, lon)
        mw = re.findall(r"[\d.]+", tags.get("plant:output:electricity", ""))
        out.append({
            "signal_id": f"osm:{e['type']}/{e['id']}", "source": "osm_overpass", "technology": tech,
            "stage": stage, "name": _clean(tags.get("name", ""), 120),
            "sponsor": _clean(tags.get("operator", "") or tags.get("owner", ""), 80),
            "description": _clean(tags.get("description", "")), "state": state,
            "county_fips": county, "counties_fips": county,
            "latitude": round(lat, 5), "longitude": round(lon, 5),
            "structures": "", "cranes": "", "met_towers": "",
            "first_filed": tags.get("start_date", ""), "last_filed": "",
            "statuses": tags.get("plant:output:electricity", "") if mw else "",
            "height_ft_max": "",
            "source_url": src["object_url_template"].format(osm_type=e["type"], osm_id=e["id"]),
            "case_ids": "", "_points": [(lat, lon)],
        })
    return out


# ── Sorting ─────────────────────────────────────────────────────────────────

def load_facilities(rows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        lat, lon = _num(r.get("latitude")), _num(r.get("longitude"))
        if lat is not None and lon is not None:
            by[r["technology"]].append({**r, "_lat": lat, "_lon": lon})
    return by


def load_queue(rows: list[dict], statuses: list[str]) -> dict[tuple[str, str], list[str]]:
    by: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in rows:
        if r.get("status") not in statuses or not r.get("county_fips"):
            continue
        for tech in (r.get("technology") or "").split(";"):
            by[(r["county_fips"], tech.strip())].append(r["queue_project_id"])
    return by


def sort_signal(s: dict, facilities: dict, queue: dict, cfg: dict) -> dict:
    limit = cfg["matching"]["facility_km"].get(s["technology"], 2.0)
    best, best_km = None, None
    for p in facilities.get(s["technology"], []):
        if abs(p["_lat"] - s["latitude"]) > 1 or abs(p["_lon"] - s["longitude"]) > 1.5:
            continue
        d = min(km(lat, lon, p["_lat"], p["_lon"]) for lat, lon in s["_points"])
        if best_km is None or d < best_km:
            best, best_km = p, d
    s["facility_id"] = best["facility_id"] if best and best_km <= limit else ""
    s["facility_status"] = best["status"] if s["facility_id"] else ""
    s["facility_km"] = round(best_km, 2) if s["facility_id"] else ""
    ids = []
    for c in (s["counties_fips"] or "").split(";"):
        ids += queue.get((c, s["technology"]), [])
    s["queue_project_ids"] = ";".join(sorted(set(ids))[:5])
    s["match_status"] = "known_facility" if s["facility_id"] else ("queue_county" if ids else "new")
    return s


def worklist(signals: list[dict], resolved: set[str]) -> list[dict]:
    todo = [s for s in signals if s["match_status"] in ("new", "queue_county")
            and s["signal_id"] not in resolved and s["stage"] not in ENDED and s["county_fips"]]
    todo.sort(key=lambda s: (s["match_status"] != "new", STAGE_ORDER.index(s["stage"])
                             if s["stage"] in STAGE_ORDER else 99, -int(s["structures"] or 0), s["signal_id"]))
    out = []
    for i, s in enumerate(todo, 1):
        county = geo.name(s["county_fips"]) if geo.known(s["county_fips"]) else ""
        who = s["name"] or s["sponsor"]
        tech = s["technology"].replace("battery_storage", "battery storage")
        hint = f'"{who}" {tech}' if who else f"{county} {s['state']} {tech} project"
        out.append({"rank": i, **{k: s[k] for k in WORKLIST_FIELDS if k in s},
                    "county": county, "search_hint": hint})
    return out


# ── Run ─────────────────────────────────────────────────────────────────────

def fetch_all(cfg: dict, only: set[str], session: requests.Session, today: date,
              local_faa: list[Path] | None, local_osm: Path | None) -> tuple[dict, list[dict]]:
    """source -> signal rows (None when the source could not be read), manifest."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results: dict[str, list[dict] | None] = {}
    manifest: list[dict] = []
    faa, osm = cfg["sources"]["faa_oeaaa"], cfg["sources"]["osm_overpass"]
    if "faa_oeaaa" in only:
        filings, ok = [], True
        files = ([(str(p), p.read_bytes()) for p in local_faa] if local_faa
                 else [(u, None) for u in faa_urls(faa, cfg["since"], today)])
        for url, data in files:
            row = {"source": "faa_oeaaa", "url": url, "fetched_at": now}
            try:
                if data is None:
                    resp = session.get(url, timeout=180)
                    resp.raise_for_status()
                    data = resp.content
                kept, read, as_of = read_faa(data, faa)
            except (requests.RequestException, SchemaError) as exc:
                ok = False
                manifest.append({**row, "result": f"failed: {_clean(str(exc), 120)}"})
                continue
            filings += kept
            manifest.append({**row, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                             "data_as_of": as_of, "rows_read": read, "rows_kept": len(kept), "result": "read"})
        results["faa_oeaaa"] = faa_signals(filings, faa, cfg["since"]) if ok else None
    if "osm_overpass" in only:
        rows, ok = [], True
        if local_osm:
            payloads = json.loads(local_osm.read_text(encoding="utf-8"))
            states = [(st, json.dumps(p).encode()) for st, p in payloads.items()]
        else:
            states = [(st, None) for st in sorted(STATE_CODES)]
        for st, data in states:
            row = {"source": "osm_overpass", "url": f"{osm['api_url']} (US-{st})", "fetched_at": now}
            try:
                if data is None:
                    resp = session.post(osm["api_url"], data={"data": overpass_query(osm, st)},
                                        timeout=osm["timeout_s"] + 30)
                    resp.raise_for_status()
                    data = resp.content
                    time.sleep(osm["pause_s"])
                payload = json.loads(data)
            except (requests.RequestException, ValueError) as exc:
                ok = False
                manifest.append({**row, "result": f"failed: {_clean(str(exc), 120)}"})
                continue
            got = osm_signals(payload, osm, st)
            rows += got
            manifest.append({**row, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                             "data_as_of": payload.get("osm3s", {}).get("timestamp_osm_base", ""),
                             "rows_read": len(payload.get("elements", [])), "rows_kept": len(got),
                             "result": "read"})
        # Overpass answers some states with a timeout; a partial pull still
        # stands, and the manifest names every state that failed.
        results["osm_overpass"] = rows if rows or ok else None
    return results, manifest


def assemble(results: dict, previous: list[dict], cfg: dict, facilities: list[dict],
             queue_rows: list[dict], resolutions: list[dict]) -> list[dict]:
    fac = load_facilities(facilities)
    queue = load_queue(queue_rows, cfg["matching"]["queue_statuses"])
    verdicts = {r["signal_id"]: r["verdict"] for r in resolutions if r.get("signal_id")}
    out = []
    for source in cfg["sources"]:
        rows = results.get(source)
        if rows is None:
            # Not fetched this run (or failed): keep the last run's rows.
            for r in previous:
                if r["source"] == source:
                    pts = [(float(r["latitude"]), float(r["longitude"]))]
                    out.append({**r, "latitude": float(r["latitude"]), "longitude": float(r["longitude"]),
                                "_points": pts})
            continue
        out += [s for s in rows if s["technology"] in cfg["technologies"]]
    for s in out:
        sort_signal(s, fac, queue, cfg)
        s["resolution"] = verdicts.get(s["signal_id"], "")
    out.sort(key=lambda s: (s["state"], s["source"], s["signal_id"]))
    return out


def run(args) -> int:
    cfg = load_config()
    local = {k for k, v in (("faa_oeaaa", args.faa), ("osm_overpass", args.osm)) if v}
    only = set(args.only or local or cfg["sources"])
    if args.dry_run:
        for url in faa_urls(cfg["sources"]["faa_oeaaa"], cfg["since"], date.today()):
            print(f"[dry-run] faa_oeaaa: {url}")
        print(f"[dry-run] osm_overpass: {cfg['sources']['osm_overpass']['api_url']}, one query per state")
        print(f"[dry-run] would write {SIGNALS_PATH.relative_to(ROOT)} and {WORKLIST_PATH.relative_to(ROOT)}")
        return 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    results, manifest = fetch_all(cfg, only, session, date.today(), args.faa, args.osm)
    if all(v is None for v in results.values()):
        for m in manifest:
            print(f"{m['source']} {m['url']}: {m['result']}", file=sys.stderr)
        print("No source could be read; nothing written.", file=sys.stderr)
        return 1
    previous = read_csv(SIGNALS_PATH)
    resolutions = read_csv(RESOLUTIONS_PATH)
    signals = assemble(results, previous, cfg, read_csv(FACILITIES_PATH), read_csv(QUEUE_PATH), resolutions)
    old_manifest = [m for m in read_csv(MANIFEST_PATH) if m["source"] not in results]
    write_csv(SIGNALS_PATH, [{k: s.get(k, "") for k in FIELDS} for s in signals], FIELDS)
    write_csv(MANIFEST_PATH, old_manifest + manifest, MANIFEST_FIELDS)
    todo = worklist(signals, {r["signal_id"] for r in resolutions})
    write_csv(WORKLIST_PATH, todo, WORKLIST_FIELDS)
    by = Counter((s["source"], s["match_status"]) for s in signals)
    for (source, status), n in sorted(by.items()):
        print(f"{source} {status}: {n}")
    failed = [m for m in manifest if m["result"] != "read"]
    for m in failed:
        print(f"not read: {m['url']} ({m['result']})")
    print(f"{len(signals)} candidates, {len(todo)} on the worklist")
    return 0


# ── Cards, packets and reconciliation ───────────────────────────────────────

PACKET_KEYS = ["packet", "queue", "key", "agent", "date", "result", "verdict", "technology", "stage",
               "project_name", "developer", "county_fips", "matched_id", "capacity_mw", "source_url",
               "access", "archived_url", "source_kind", "evidence_date", "quote", "opposition_url", "note",
               "attempts"]
AGREE_ON = ["verdict", "technology", "stage", "county_fips", "matched_id"]
SOURCE_KINDS = ["official", "filing", "news", "developer", "inventory"]


def batch(today: date) -> list[str]:
    """The first per_run worklist candidates not logged in the last skip_days
    (a page that failed yesterday does not take today's slot)."""
    cfg = load_config()
    recent = {r["key"] for r in read_csv(LOG_PATH) if r.get("queue") == "development"
              and r.get("date", "") and (today - date.fromisoformat(r["date"][:10])).days < cfg["skip_days"]}
    return [w["signal_id"] for w in read_csv(WORKLIST_PATH) if w["signal_id"] not in recent][: cfg["per_run"]]


def card(signal_id: str) -> dict:
    """What the development-reader gets, and the blind-reviewer too: the
    candidate's own facts from the open sources, never a reading."""
    cfg = load_config()
    rows = {r["signal_id"]: r for r in read_csv(SIGNALS_PATH)}
    if signal_id not in rows:
        raise SystemExit(f"{signal_id}: not in {SIGNALS_PATH.relative_to(ROOT)}")
    s = {k: v for k, v in rows[signal_id].items() if k != "resolution"}
    qids = set(filter(None, s["queue_project_ids"].split(";")))
    queue = [{k: r.get(k, "") for k in ("queue_project_id", "entity", "q_id", "project_name", "developer",
                                         "status", "technology", "capacity_mw", "request_date",
                                         "proposed_online_date", "county")}
             for r in read_csv(QUEUE_PATH) if r["queue_project_id"] in qids]
    fac = next(({k: r.get(k, "") for k in ("facility_id", "source", "name", "operator", "status",
                                           "capacity_mw", "year", "latitude", "longitude")}
                for r in read_csv(FACILITIES_PATH) if r["facility_id"] == s["facility_id"]), None)
    src = cfg["sources"][s["source"]]
    return {"queue": "development", "key": signal_id, "signal": s, "source": src["label"],
            "license": src["license"], "queue_requests": queue, "nearest_facility": fac,
            "verdicts": cfg["verdicts"], "stages": cfg["stages"], "source_kinds": SOURCE_KINDS,
            "expect": {k: "" for k in PACKET_KEYS}}


def check(packet: dict) -> list[str]:
    cfg = load_config()
    errs = []
    for k in PACKET_KEYS:
        if k not in packet:
            errs.append(f"missing {k}")
    if errs:
        return errs
    if packet["packet"] not in ("draft", "review") or packet["queue"] != "development":
        errs.append("packet must be draft or review, queue development")
    if not re.match(r"^agent:development-reader-\d+ |^agent:blind-reviewer-\d+ ", packet["agent"]):
        errs.append("agent: agent:development-reader-<n> (...) or agent:blind-reviewer-<n> (...)")
    if packet["result"] not in ("read", "not_read", "nothing_found"):
        errs.append("result: read | not_read | nothing_found")
    if packet["result"] == "read":
        if packet["verdict"] not in cfg["verdicts"]:
            errs.append(f"verdict: one of {cfg['verdicts']}")
        if packet["access"] not in ("opened", "archived"):
            errs.append("access: opened | archived (search-result text is not a reading)")
        if packet["access"] == "archived" and not packet["archived_url"]:
            errs.append("archived_url is required when access is archived")
        if not packet["source_url"].startswith("http") or not packet["quote"]:
            errs.append("a reading needs source_url and the quote it rests on")
        if packet["source_kind"] not in SOURCE_KINDS:
            errs.append(f"source_kind: one of {SOURCE_KINDS}")
        if packet["verdict"] in ("same_as_facility", "same_as_queue", "duplicate_signal") and not packet["matched_id"]:
            errs.append("matched_id names the facility, queue request or signal it is the same as")
        if packet["verdict"] in ("new_development", "same_as_facility", "same_as_queue"):
            if packet["technology"] not in load_config()["technologies"]:
                errs.append("technology: solar | wind | battery_storage")
            if packet["stage"] not in cfg["stages"]:
                errs.append(f"stage: one of {cfg['stages']}")
            if not (re.fullmatch(r"\d{5}", packet["county_fips"]) and geo.known(packet["county_fips"])):
                errs.append("county_fips: the 2024 county FIPS the document places it in")
        if packet["evidence_date"] and not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", packet["evidence_date"]):
            errs.append("evidence_date: YYYY, YYYY-MM or YYYY-MM-DD")
    elif not packet["attempts"]:
        errs.append("a packet with no reading lists every attempt")
    for k in ("note", "quote", "project_name", "developer"):
        if EMDASH in str(packet.get(k, "")):
            errs.append(f"{k}: no em dash")
    return errs


def reconcile(draft: dict, review: dict, today: str) -> tuple[dict | None, list[str]]:
    """(resolution row or None, disagreements)."""
    problems = check(draft) + check(review)
    if problems:
        return None, problems
    if draft["key"] != review["key"]:
        return None, ["draft and review are about different candidates"]
    drafter, reviewer = draft["agent"].split(" (")[0], review["agent"].split(" (")[0]
    if drafter == reviewer:
        return None, ["the drafter and the reviewer are the same agent"]
    if draft["result"] != "read" or review["result"] != "read":
        return None, ["both readings must have read a document"]
    differ = [f"{k}: draft {draft[k]!r}, review {review[k]!r}" for k in AGREE_ON
              if str(draft[k]).strip() != str(review[k]).strip()]
    if differ:
        return None, differ
    note = (f"Drafted by {draft['agent']}; reviewed by {review['agent']}: agreed. "
            f"{_clean(draft['note'], 600)} Quote: {_clean(draft['quote'], 400)}")
    return ({"signal_id": draft["key"], "verdict": draft["verdict"], "technology": draft["technology"],
             "stage": draft["stage"], "project_name": draft["project_name"], "developer": draft["developer"],
             "county_fips": draft["county_fips"], "matched_id": draft["matched_id"],
             "capacity_mw": draft["capacity_mw"], "evidence_url": draft["source_url"],
             "evidence_date": draft["evidence_date"], "evidence_note": note, "reviewer": review["agent"],
             "access": draft["access"], "archived_url": draft["archived_url"],
             "opposition_url": draft["opposition_url"] or review["opposition_url"], "checked_on": today}, [])


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("batch", "card", "check", "reconcile"):
        cmd, rest = argv[0], argv[1:]
        if cmd == "batch" and not rest:
            print("\n".join(batch(date.today())))
            return 0
        if cmd == "card" and len(rest) == 1:
            print(json.dumps(card(rest[0]), indent=2))
            return 0
        if cmd == "check" and len(rest) == 1:
            errs = check(json.loads(Path(rest[0]).read_text(encoding="utf-8")))
            for e in errs:
                print(f"{rest[0]}: {e}")
            return 1 if errs else 0
        if cmd == "reconcile" and len(rest) == 2:
            d, r = (json.loads(Path(p).read_text(encoding="utf-8")) for p in rest)
            row, differ = reconcile(d, r, date.today().isoformat())
            if row is None:
                for x in differ:
                    print(f"disputed: {x}", file=sys.stderr)
                return 1
            w = csv.DictWriter(sys.stdout, fieldnames=RESOLUTION_FIELDS, lineterminator="\n")
            w.writerow(row)
            return 0
        print(__doc__)
        return 2
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", action="append", choices=["faa_oeaaa", "osm_overpass"])
    ap.add_argument("--faa", type=Path, nargs="+", help="local FAA archive CSVs instead of downloading")
    ap.add_argument("--osm", type=Path, help='a local JSON {"<state>": <Overpass answer>} instead of querying')
    ap.add_argument("--dry-run", action="store_true")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
