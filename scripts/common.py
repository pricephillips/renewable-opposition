"""Shared helpers for the renewable-opposition seed builders."""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seed"
REVIEW_DIR = ROOT / "data" / "review"
PROCESSED_DIR = ROOT / "data" / "processed"

STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}
STATE_CODES = set(STATE_ABBREV.values())
STATE_NAMES = {code: name.title() for name, code in STATE_ABBREV.items()}

# Technology vocabulary shared by every entity. Source-specific spellings are
# mapped onto it with TECH_ALIASES.
TECH_ORDER = ["solar", "wind", "battery_storage", "transmission", "hydro", "geothermal"]
TECH_ALIASES = {"storage": "battery_storage", "battery": "battery_storage", "offshore_wind": "wind"}


def state_code(value: str) -> str:
    """Return the two-letter code for a state name or code; raise on unknown input."""
    v = (value or "").strip()
    if v.upper() in STATE_CODES:
        return v.upper()
    code = STATE_ABBREV.get(v.lower())
    if not code:
        raise ValueError(f"Unknown state: {value!r}")
    return code


def technology_tokens(raw: str) -> list[str]:
    """Split a comma/semicolon list of technologies into ordered vocabulary tokens."""
    tokens = {
        TECH_ALIASES.get(t.strip().lower(), t.strip().lower())
        for t in re.split(r"[,;]", raw or "")
        if t.strip()
    }
    unknown = tokens - set(TECH_ORDER)
    if unknown:
        raise ValueError(f"Unmapped technology token(s): {sorted(unknown)}")
    return [t for t in TECH_ORDER if t in tokens]


def normalize_url(url: str) -> str:
    """Canonical form used for source identity: lowercase scheme/host, no fragment,
    no trailing slash on the path. Query strings are kept (they often identify
    the document)."""
    parts = urlsplit((url or "").strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def source_id_for(url: str) -> str:
    """Stable 12-hex-char id derived from the normalized URL."""
    return "src_" + hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:12]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], preferred_fields: list[str] | None = None) -> list[str]:
    """Write rows with preferred_fields first, then any extra keys in first-seen
    order, so rows from different builders can share one file. Returns the header."""
    fields = list(preferred_fields or [])
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fields})
    return fields


_JURISDICTION_NOISE = re.compile(
    r"\b(county|parish|borough|township|twp|town|city|village|charter|municipality|"
    r"of|the|board|commissioners|supervisors)\b",
    re.I,
)


def jurisdiction_kind(jurisdiction_type: str) -> str:
    """Collapse source jurisdiction types to state | county | municipal."""
    t = (jurisdiction_type or "").strip().lower()
    if t == "state":
        return "state"
    if t in ("county", "parish", "borough", "multi-county"):
        return "county"
    return "municipal"


def jurisdiction_key(state: str, kind: str, name: str) -> str:
    """Loose match key for a jurisdiction: 'Town of Morris' == 'Morris' within
    the same state and kind, so Morris County never matches the Town of Morris."""
    cleaned = _JURISDICTION_NOISE.sub(" ", (name or "").lower())
    cleaned = re.sub(r"\(.*?\)", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned).strip()
    return f"{state_code(state)}::{kind}::{cleaned}"
