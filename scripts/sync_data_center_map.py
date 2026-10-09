"""Copy data-center-map's local events into data/reference/data_center_events.csv.

The same county governments often act on both data centers and renewables, so
a site profile shows data center activity beside the renewable records. This
reads pricephillips/data-center-map's master_opposition.csv and writes one row
per placed event:

  state, county, county_fips, jurisdiction, date, event_type, status,
  summary, source_urls, opposition_groups, dc_row_ref

Input: --dc-map PATH, else $RO_DATA_CENTER_MAP, else
../data-center-map/master_opposition.csv (a sibling checkout).

Placement uses this repository's own county logic (classify.county_fips_all):
the county named on the row, a multi-county name split into its parts, the
row's coordinates inside a 2024 county polygon, or its city in the Census
place index. A row that places nowhere is left out and counted; nothing is
guessed. county_fips is every county found, semicolon-joined.

Left out:
  - data_source signal_harvest_auto rows with no state, no type, or a generic
    or unrelated headline: automatic harvesting picks up off-topic stories
    (an immigration arrest geotagged to "Cedar" county from a Cedar Rapids
    story). Generic is a headline of fewer than four words; unrelated is one
    whose text names no data center, hyperscaler or crypto mining.
  - any row with no type whose text names no data center: the same failure
    from other harvesters (a nuclear plant loan filed under a county).

The evidence label is not stored; site_profile.py derives it from source_urls
(evidence_label): "verified" only when a source is the instrument or official
minutes, by its address (a government host and a document path, or a
municipal records host); otherwise "reported". These sources were not read in
this repository.

Usage
  python scripts/sync_data_center_map.py [--dc-map PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify  # noqa: E402
import geo  # noqa: E402
from build_seed_outputs import load_fips_lookup, load_place_index  # noqa: E402
from common import ROOT, STATE_NAMES, state_code, write_csv  # noqa: E402
from group_registry import is_generic  # noqa: E402

DC_MAP_ENV = "RO_DATA_CENTER_MAP"
DEFAULT_DC_MAP = ROOT.parent / "data-center-map" / "master_opposition.csv"
OUT = ROOT / "data" / "reference" / "data_center_events.csv"
FIELDS = ["state", "county", "county_fips", "jurisdiction", "date", "event_type", "status", "summary",
          "source_urls", "opposition_groups", "dc_row_ref"]

DC_TEXT = re.compile(r"data[ -]?cent(?:er|re)s?|datacenter|hyperscal|server farm|crypto|bitcoin|"
                     r"\bai (?:campus|facility|factory)|\bxai\b|colossus", re.I)
_URL = re.compile(r"https?://[^\s;'\"}\]<>]+")
# Hosts that publish official records (agendas, minutes, ordinances) for many
# local governments.
RECORD_HOSTS = re.compile(r"(?:^|\.)(?:destinyhosted\.com|legistar\.com|municode\.com|ecode360\.com|"
                          r"boarddocs\.com|granicus\.com|civicclerk\.com|agendacenter\.com|"
                          r"municipal\.codes|codelibrary\.amlegal\.com)$", re.I)
GOV_HOST = re.compile(r"(?:\.gov|\.us|\.gov\.\w+)$", re.I)
DOC_PATH = re.compile(r"minutes|agenda|ordinance|resolution|proceedings|\.pdf$|viewfile|documentcenter|"
                      r"showpublisheddocument", re.I)


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def source_urls(row: dict) -> list[str]:
    out: list[str] = []
    for u in _URL.findall(" ".join((_s(row.get("Source URL")), _s(row.get("Sources"))))):
        u = u.rstrip(".,)")
        if u not in out:
            out.append(u)
    return out


def evidence_label(urls: list[str]) -> str:
    """'verified' when a source is the instrument or official minutes, by its
    address; otherwise 'reported'."""
    for u in urls:
        m = re.match(r"https?://([^/]+)(/[^?#]*)?", u)
        if not m:
            continue
        host, path = m.group(1).lower(), m.group(2) or ""
        if RECORD_HOSTS.search(host) or (GOV_HOST.search(host) and DOC_PATH.search(path)):
            return "verified"
    return "reported"


def headline(row: dict) -> str:
    return _s(row.get("Incident")) or _s(row.get("Summary"))


def keep(row: dict) -> tuple[bool, str]:
    """(keep, reason left out)."""
    text = " ".join(_s(row.get(k)) for k in ("Incident", "Summary", "Objective", "Project Name", "Company"))
    names_dc = bool(DC_TEXT.search(text))
    has_type = bool(_s(row.get("Opposition Type")))
    if _s(row.get("data_source")) == "signal_harvest_auto":
        if not _s(row.get("State")):
            return False, "signal_harvest_auto: no state"
        if not has_type:
            return False, "signal_harvest_auto: no type"
        if len(headline(row).split()) < 4:
            return False, "signal_harvest_auto: generic headline"
        if not names_dc:
            return False, "signal_harvest_auto: unrelated headline"
    if not has_type and not names_dc:
        return False, "no type and the text names no data center"
    return True, ""


def clean(text) -> str:
    """One line, with em dashes as commas: profiles print this text, and
    nothing user-facing carries an em dash."""
    return " ".join(_s(text).replace("\u2014", ", ").split()).replace(" ,", ",")


def one_line(text: str, limit: int = 200) -> str:
    """The first sentence, at most limit characters."""
    t = clean(text)
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", t)[0]
    return first if len(first) <= limit else first[:limit - 3].rstrip() + "..."


def groups(cell: str) -> list[str]:
    out = []
    for g in re.split(r"[;|]", _s(cell)):
        g = clean(g)
        if g and not is_generic(g) and g not in out:
            out.append(g)
    return out


def place(row: dict, lookup, places, locate) -> list[str]:
    """Every 2024 county the row touches, by this repository's own rules."""
    try:
        st = state_code(_s(row.get("State")))
    except ValueError:
        return []
    probe = {"state": st, "county": _s(row.get("County")), "municipality": _s(row.get("City")),
             "description": " ".join((_s(row.get("Incident")), _s(row.get("Summary")))),
             "latitude": _s(row.get("lat")), "longitude": _s(row.get("lon"))}
    try:
        found, _ = classify.county_fips_all("contested_projects", probe, lookup, STATE_NAMES, locate, places)
    except ValueError:
        probe["latitude"] = probe["longitude"] = ""
        found, _ = classify.county_fips_all("contested_projects", probe, lookup, STATE_NAMES, locate, places)
    return found


def transform(rows: list[dict], lookup, places, locate) -> tuple[list[dict], dict[str, int]]:
    out, dropped = [], {}
    for i, r in enumerate(rows, start=2):
        ok, why = keep(r)
        if not ok:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        found = place(r, lookup, places, locate)
        if not found:
            dropped["placed in no county"] = dropped.get("placed in no county", 0) + 1
            continue
        out.append({
            "state": state_code(_s(r.get("State"))), "county": _s(r.get("County")),
            "county_fips": ";".join(found), "jurisdiction": clean(r.get("City")) or clean(r.get("County")),
            "date": _s(r.get("Date")), "event_type": _s(r.get("Opposition Type")), "status": _s(r.get("Status")),
            "summary": one_line(_s(r.get("Summary")) or headline(r)),
            "source_urls": "; ".join(source_urls(r)), "opposition_groups": "; ".join(groups(r.get("Opposition Groups"))),
            "dc_row_ref": f"master_opposition.csv row {i}: {one_line(headline(r), 120)}"})
    out.sort(key=lambda x: (x["state"], x["county_fips"], x["date"], x["dc_row_ref"]))
    return out, dropped


def dc_map_path(arg: str | None) -> Path:
    return Path(arg or os.environ.get(DC_MAP_ENV) or DEFAULT_DC_MAP).expanduser()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dc-map", help=f"path to master_opposition.csv (default ${DC_MAP_ENV}, then {DEFAULT_DC_MAP})")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    src = dc_map_path(a.dc_map)
    if not src.exists():
        print(f"{src} not found; pass --dc-map or set {DC_MAP_ENV}", file=sys.stderr)
        return 1
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    events, dropped = transform(rows, load_fips_lookup(), load_place_index(), geo.county_at)
    print(f"{len(rows)} data-center-map rows: {len(events)} placed events; left out: "
          + (", ".join(f"{k} {v}" for k, v in sorted(dropped.items())) or "none"))
    if not a.dry_run:
        write_csv(OUT, events, FIELDS)
        print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
