"""Opposition groups: one registry entry per organization, with its sources.

Groups are named on records in two columns, both semicolon lists:
  opposition_groups  the groups the record names
  group_sources      one or more URLs (news articles, filings) that name them;
                     every URL on a row applies to every group on that row
They are read from published contested projects (the seed columns, carried
from data/review/queue.csv on promotion), from data/review/group_candidates.csv
(hand-edited backfill, one group per row, with group_source_url and access),
and from data/reference/data_center_events.csv (scripts/sync_data_center_map.py;
its source_urls name the groups of data-center-map's rows).

Canonical names. Case, punctuation, a leading "The", an "Inc."/"LLC"/"Co."
suffix and a leading "Citizens for" or "Concerned Citizens for" do not make a
new group, so "Citizens for Responsible Solar, Inc." and "responsible solar"
are one entry. "Stop", "Save" and "No" prefixes name the cause and are kept.
Generic labels (residents, local residents, neighbors) are not groups.

Publication. A group occurrence publishes only with a source URL: on a
contested project, a non-empty group_sources; on a candidate row, a
group_source_url whose access is opened or archived (the evidence standard:
opposition activity may rest on a news article, but one that was read). A
group with no publishable source is held: it goes to
data/review/group_review.csv with the record that names it, and the build
blanks it from the published contested project. Nothing here computes or
publishes a per-group outcome or success rate; the registry says who was
active where and when, with the sources.

Outputs (written on every build by build_seed_outputs.py):
  data/processed/group_registry.csv   canonical_id, canonical_name, variants,
                                      n_projects, states, first_seen,
                                      last_seen, source_urls
  data/review/group_review.csv        held groups, one row per occurrence
"""
from __future__ import annotations

import hashlib
import re

from common import PROCESSED_DIR, REVIEW_DIR, ROOT, read_csv, write_csv

REGISTRY_PATH = PROCESSED_DIR / "group_registry.csv"
REVIEW_PATH = REVIEW_DIR / "group_review.csv"
CANDIDATES_PATH = REVIEW_DIR / "group_candidates.csv"
DC_EVENTS_PATH = ROOT / "data" / "reference" / "data_center_events.csv"

REGISTRY_FIELDS = ["canonical_id", "canonical_name", "variants", "n_projects", "states", "first_seen",
                   "last_seen", "source_urls"]
REVIEW_FIELDS = ["canonical_name", "group_name", "record", "state", "date", "reason", "excerpt"]
CANDIDATE_FIELDS = ["source_record_id", "entity", "state", "record_name", "group_name", "excerpt",
                    "group_source_url", "access", "archived_url", "note"]
READ_ACCESS = ("opened", "archived")
GENERIC = {"residents", "local residents", "citizens", "community members", "neighbors", "community",
           "local officials", "na", "none", "unknown", "various", "multiple groups", "local farmers",
           "landowners", "local landowners", "farmers"}

# "Linn County residents", "Residents of Palo": people, not an organization.
_GENERIC_TAIL = re.compile(r"^(?:[\w .'-]+\s)?(?:residents|landowners|homeowners|community members)$|"
                           r"^residents of\b", re.I)


def is_generic(name: str) -> bool:
    k = key(name)
    return not k or k in GENERIC or bool(_GENERIC_TAIL.search(k))


_PREFIX = re.compile(r"^(?:the\s+)?(?:concerned\s+)?citizens\s+for\s+(?:the\s+)?", re.I)
_SUFFIX = re.compile(r"\s+(?:inc|incorporated|llc|co|corp)$", re.I)
_URL = re.compile(r"^https?://\S+$")
_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def split(cell) -> list[str]:
    return [p.strip() for p in _s(cell).split(";") if p.strip()]


def urls(cell) -> list[str]:
    return [u for u in split(cell) if _URL.match(u)]


def key(name: str) -> str:
    """Canonical key: case, punctuation, a leading 'The', an Inc./LLC suffix
    and a leading 'Citizens for' do not distinguish groups."""
    k = re.sub(r"[^\w\s]", " ", _s(name).lower()).replace("_", " ")
    k = " ".join(k.split())
    k = re.sub(r"^the\s+", "", k)
    k = _SUFFIX.sub("", k)
    stripped = _PREFIX.sub("", k)
    return " ".join((stripped or k).split())


def canonical_id(k: str) -> str:
    return "grp_" + hashlib.sha1(k.encode("utf-8")).hexdigest()[:8]


def iso_date(text) -> str:
    """YYYY[-MM[-DD]] from '2024-05-01', 'August 2014', '2014'; '' if none."""
    t = _s(text)
    m = re.search(r"\b(\d{4})-(\d{2})(?:-(\d{2}))?\b", t)
    if m:
        return "-".join(x for x in m.groups() if x)
    m = re.search(r"\b(" + "|".join(_MONTHS) + r")\b\.?\s+(?:\d{1,2},\s+)?(\d{4})\b", t, re.I)
    if m:
        return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"\b(19|20)\d{2}\b", t)
    return m.group(0) if m else ""


def occurrences(projects: list[dict], candidates: list[dict], dc_events: list[dict]) -> list[dict]:
    """One dict per (group, record): name, record, state, date, sources."""
    out = []
    for r in projects:
        when = iso_date(r.get("resolution_date")) or iso_date(r.get("event_date_text"))
        for g in split(r.get("opposition_groups")):
            out.append({"name": g, "record": _s(r.get("instrument_id") or r.get("id")), "state": _s(r.get("state")),
                        "date": when, "sources": urls(r.get("group_sources")),
                        "excerpt": _s(r.get("description"))[:200], "why": "no group_sources on the record"})
    on_records = {(o["record"], key(o["name"])) for o in out}
    for r in candidates:
        if (f"sabin:{_s(r.get('source_record_id'))}", key(r.get("group_name"))) in on_records:
            continue   # copied onto the published project row; counted there
        url = _s(r.get("group_source_url"))
        read = _URL.match(url) and _s(r.get("access")) in READ_ACCESS
        why = ("no group_source_url yet" if not url else
               "group_source_url was not opened or archived (access is not opened/archived)")
        out.append({"name": _s(r.get("group_name")), "record": _s(r.get("source_record_id")),
                    "state": _s(r.get("state")), "date": "", "sources": [url] if read else [],
                    "excerpt": _s(r.get("excerpt"))[:200], "why": why})
    for r in dc_events:
        for g in split(r.get("opposition_groups")):
            out.append({"name": g, "record": f"data-center-map: {_s(r.get('dc_row_ref'))}",
                        "state": _s(r.get("state")), "date": iso_date(r.get("date")),
                        "sources": urls(r.get("source_urls")), "excerpt": _s(r.get("summary"))[:200],
                        "why": "no source_urls on the data-center-map row"})
    return [o for o in out if not is_generic(o["name"])]


def build(occ: list[dict]) -> tuple[list[dict], list[dict]]:
    """(registry rows, held rows). A group publishes once any occurrence has a
    source; its unsourced occurrences still go to review."""
    groups: dict[str, dict] = {}
    held = []
    for o in occ:
        k = key(o["name"])
        if not o["sources"]:
            held.append(o)
            continue
        g = groups.setdefault(k, {"variants": {}, "records": set(), "states": set(), "dates": [], "urls": []})
        g["variants"][o["name"]] = g["variants"].get(o["name"], 0) + 1
        g["records"].add(o["record"])
        if o["state"]:
            g["states"].add(o["state"])
        if o["date"]:
            g["dates"].append(o["date"])
        g["urls"] += [u for u in o["sources"] if u not in g["urls"]]
    registry = []
    for k, g in groups.items():
        # The most frequent spelling; on a tie, the fullest.
        name = max(g["variants"].items(), key=lambda t: (t[1], len(t[0]), t[0]))[0]
        registry.append({"canonical_id": canonical_id(k), "canonical_name": name,
                         "variants": "; ".join(sorted(g["variants"])), "n_projects": len(g["records"]),
                         "states": ";".join(sorted(g["states"])), "first_seen": min(g["dates"], default=""),
                         "last_seen": max(g["dates"], default=""), "source_urls": "; ".join(g["urls"])})
    registry.sort(key=lambda r: (r["canonical_name"].lower(), r["canonical_id"]))
    names = {key(r["canonical_name"]): r["canonical_name"] for r in registry}
    review = [{"canonical_name": names.get(key(o["name"]), o["name"]), "group_name": o["name"],
               "record": o["record"], "state": o["state"], "date": o["date"],
               "reason": o["why"], "excerpt": o["excerpt"]} for o in held]
    review.sort(key=lambda r: (r["state"], r["canonical_name"].lower(), r["record"]))
    return registry, review


def hold_unsourced(projects: list[dict]) -> int:
    """Blank opposition_groups on published contested projects that have no
    group_sources: a group without a source is held for review, never
    published. Returns how many rows were blanked."""
    n = 0
    for r in projects:
        if split(r.get("opposition_groups")) and not urls(r.get("group_sources")):
            r["opposition_groups"] = None
            n += 1
    return n


def run(projects: list[dict]) -> tuple[list[dict], list[dict]]:
    """Build the registry from the published contested projects (before
    hold_unsourced), the candidate file and the data-center-map events, and
    write both outputs."""
    occ = occurrences(projects, read_csv(CANDIDATES_PATH), read_csv(DC_EVENTS_PATH))
    registry, review = build(occ)
    write_csv(REGISTRY_PATH, registry, REGISTRY_FIELDS)
    write_csv(REVIEW_PATH, review, REVIEW_FIELDS)
    return registry, review
