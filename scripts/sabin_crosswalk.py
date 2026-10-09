"""Map each 2025 Sabin record (REC- id) onto its September 2026 edition entry.

The 2026 edition renumbers its entries. Published records, and every review
row attached to them (restriction_sources, outcome_resolutions,
place_overrides, group candidates, case candidates), are keyed on the 2025
REC- id through instrument_id sabin:<REC id>. This file says which 2026 entry
each REC- id now is, so build_sabin_seeds.py can keep the id.

Matching (never guessed: anything short of one clear candidate goes to review)
  restrictions   same state and level; local rows also the same jurisdiction
                 (common.jurisdiction_key on the municipality, else the county,
                 so "Town of Morris" and "Morris" agree); state-level rows only
                 when both name the same bill or act (S.B. 583, Public Act No.
                 17-218). A county row with no candidate at its own level
                 lists the 2026 town or township entries in that county; such
                 a match is never automatic (ambiguous, for a reviewer). A
                 candidate must share a technology. Each is scored:
                 technology overlap (Jaccard), plus 1 when the mechanisms
                 share a family (bans, moratoria and the edition's unstated
                 "ban or moratorium" are one family; setbacks, heights,
                 noise, size caps, zoning and other standards are each their
                 own), plus 1 when the adoption years agree.
  projects       same state; the distinctive words of the project names
                 (generic words such as solar, wind, project, farm, energy,
                 LLC dropped) overlap by at least MIN_NAME of the shorter
                 name, or the spellings agree to MIN_SPELLING (the 2025
                 extraction lost some letter pairs), and the technologies
                 overlap (unless the names are the same). Scored by that overlap,
                 plus 1 when the whole names are the same, 0.5 when a county
                 agrees and 0.5 times the technology overlap.
  decision       a best candidate whose mechanisms share no family with the
                 2025 record's and whose adoption year differs, or that sits
                 at another level: ambiguous. (The editions often label one
                 instrument differently, so a same-year entry still matches.)
                 Otherwise one candidate: matched. Several: matched only when the best
                 scores at least MARGIN above the next; otherwise ambiguous.
                 No candidate: not_in_latest_edition. A 2026 entry claimed by
                 two 2025 records makes both ambiguous (a merge or a split is
                 a reviewer's call).

Reviewer decisions survive a rebuild. Set review_decision to a 2026 id
(S26R-.../S26P-...) to match, or to "none" to confirm the record is not in the
edition, with reviewer, reviewed_on and review_note; the next run applies it.

Writes data/review/sabin_edition_crosswalk.csv:
  rec_id, section, state, name_2025 (jurisdiction or project), technology_2025,
  mechanism_2025, status_2025, match (matched | ambiguous |
  not_in_latest_edition), entry_2026, name_2026, technology_2026,
  mechanism_2026, status_2026, status_changed, match_basis, candidates_2026,
  review_decision, reviewer, reviewed_on, review_note

Usage
  python scripts/sabin_crosswalk.py
"""
from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REVIEW_DIR, ROOT, jurisdiction_key, read_csv, write_csv  # noqa: E402

RECORDS_2025 = ROOT / "data" / "renewable_opposition_records.csv"
RECORDS_2026 = ROOT / "data" / "renewable_opposition_records_2026-09.csv"
CROSSWALK_PATH = REVIEW_DIR / "sabin_edition_crosswalk.csv"

FIELDS = ["rec_id", "section", "state", "name_2025", "technology_2025", "mechanism_2025", "status_2025",
          "match", "entry_2026", "name_2026", "technology_2026", "mechanism_2026", "status_2026",
          "status_changed", "match_basis", "candidates_2026", "review_decision", "reviewer", "reviewed_on",
          "review_note"]
REVIEW_FIELDS = ("review_decision", "reviewer", "reviewed_on", "review_note")
MATCHES = ("matched", "ambiguous", "not_in_latest_edition")

MIN_NAME = 0.6
MIN_SPELLING = 0.88
MARGIN = 0.75
DIFFERENT = "no mechanism in common"
CROSS_LEVEL = "same county, entry at town or township level"
RESTRICTION_SECTIONS = ("local_restrictions", "state_level_restrictions")
TECHS = {"solar": "solar", "wind": "wind", "storage": "storage", "battery_storage": "storage",
         "battery": "storage", "transmission": "transmission", "hydro": "hydro", "geothermal": "geothermal"}

# Same-family mechanisms (build_sabin_seeds.MECHANISM_TYPE spellings and the
# 2026 extraction's): a 2025 "ban/prohibition" and a 2026 "ban or moratorium"
# describe the same kind of instrument.
FAMILY = [
    (r"ban|moratori|pause|extension|prohibit", "ban_moratorium"),
    (r"setback|buffer", "setback"),
    (r"height", "height"),
    (r"noise", "noise"),
    (r"cap on|area limit|size", "size"),
    (r"zoning|overlay|ag_land|land preservation|use", "zoning"),
    (r"flicker|visual|viewshed", "standard"),
]
GENERIC = {
    "project", "projects", "solar", "wind", "energy", "farm", "farms", "center", "centre", "facility",
    "facilities", "power", "llc", "inc", "the", "of", "and", "park", "plant", "station", "storage",
    "battery", "generating", "renewable", "renewables", "array", "company", "co", "a", "in", "at", "on",
    "for", "i", "ii", "iii", "iv", "1", "2", "3", "4", "phase", "llcs", "s", "proposed", "utility",
    "scale", "pv", "photovoltaic", "bess", "system", "systems", "resource", "area", "offshore",
    "transmission", "line", "county", "township", "town", "city", "mw", "megawatt",
}
_BILL = re.compile(
    r"\b(s\.?\s?b\.?|h\.?\s?b\.?|l\.?\s?d\.?|senate bill|house bill|assembly bill|a\.?\s?b\.?|"
    r"public act(?: no\.?)?|act(?: no\.?)?|law|p\.?\s?a\.?)\s*([0-9]{1,4}(?:-[0-9]{1,4})?)\b", re.I)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def techs(raw: str) -> set[str]:
    return {TECHS[t] for t in re.split(r"[,;|+\s]+", _s(raw).lower()) if t in TECHS}


def families(mech: str) -> set[str]:
    out = set()
    for part in re.split(r",", _s(mech).lower()):
        part = re.sub(r"\([^)]*\)", "", part).strip()
        for pat, fam in FAMILY:
            if part and re.search(pat, part):
                out.add(fam)
                break
    return out


def bills(text: str) -> set[str]:
    out = set()
    for m in _BILL.finditer(text):
        kind = re.sub(r"[^a-z]", "", m.group(1).lower())
        kind = {"senatebill": "sb", "housebill": "hb", "assemblybill": "ab", "publicact": "pa",
                "publicactno": "pa", "actno": "act"}.get(kind, kind)
        out.add(f"{kind}{m.group(2)}")
    return out


def year(text: str) -> str:
    m = _YEAR.search(_s(text))
    return m.group(0) if m else ""


def name_words(name: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9]+", " ", _s(name).lower()).split() if w not in GENERIC}


def _norm_name(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _s(name).lower().replace("\u2019", "'")).split())


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


# ── Record views ─────────────────────────────────────────────────────────────

def restriction_place(r: dict) -> tuple[str, str]:
    """(kind, jurisdiction) as build_sabin_seeds reads them."""
    from build_sabin_seeds import JURISDICTION_OVERRIDES
    if r.get("record_id") in JURISDICTION_OVERRIDES:
        return JURISDICTION_OVERRIDES[r["record_id"]]
    if r.get("extraction_source_section") == "state_level_restrictions":
        return "state", ""
    if _s(r.get("municipality")):
        return "municipal", _s(r["municipality"])
    if _s(r.get("county")):
        return "county", _s(r["county"])
    return "state", ""


def project_name(r: dict) -> str:
    from build_sabin_seeds import PROJECT_LIKE
    name, muni = _s(r.get("project_or_policy_name")), _s(r.get("municipality"))
    if PROJECT_LIKE.search(muni):
        return muni  # the 2025 extraction put some names in the municipality column
    return name


def label(r: dict) -> str:
    if r["extraction_source_section"] == "contested_projects":
        return project_name(r)
    kind, j = restriction_place(r)
    return j or _s(r.get("project_or_policy_name")) or f"{r['state']} (state)"


def counties(r: dict) -> set[str]:
    return {re.sub(r"\s+(county|parish)$", "", c.strip().lower()) for c in re.split(r"[;|,]", _s(r.get("county")))
            if c.strip()}


# ── Candidates ───────────────────────────────────────────────────────────────

def restriction_candidates(old: dict, new: list[dict]) -> list[tuple[float, dict, str]]:
    level = old["extraction_source_section"]
    kind, j = restriction_place(old)
    ot = techs(old["technology"])
    out = []
    for n in new:
        if n["state"] != old["state"] or n["extraction_source_section"] not in RESTRICTION_SECTIONS:
            continue
        nkind, nj = restriction_place(n)
        if level == "state_level_restrictions" or kind == "state":
            if nkind != "state":
                continue
            shared = bills(" ".join([old.get("project_or_policy_name", ""), old.get("short_description", ""),
                                     old.get("long_description", "")])) & \
                bills(" ".join([n.get("project_or_policy_name", ""), n.get("long_description", "")]))
            if not shared:
                continue
            basis = [f"same bill {', '.join(sorted(shared))}"]
        elif nkind == kind and jurisdiction_key(old["state"], kind, j) == jurisdiction_key(n["state"], nkind, nj):
            basis = ["same jurisdiction"]
        elif kind == "county" and nkind == "municipal" and _county_word(j) in counties(n):
            basis = [CROSS_LEVEL]
        else:
            continue
        nt = techs(n["technology"])
        if ot and nt and not ot & nt:
            continue
        score = jaccard(ot, nt)
        of, nf = families(old["policy_mechanism"]), families(n["policy_mechanism"])
        if of & nf:
            score += 1
            basis.append("mechanism family")
        elif of and nf:
            basis.append(DIFFERENT)
        if year(old["adopted_or_event_date_text"]) and \
                year(old["adopted_or_event_date_text"]) == year(n["adopted_or_event_date_text"]):
            score += 1
            basis.append("year")
        out.append((score, n, "; ".join(basis)))
    if any(CROSS_LEVEL not in c[2] for c in out):
        out = [c for c in out if CROSS_LEVEL not in c[2]]
    return sorted(out, key=lambda x: -x[0])


def _county_word(name: str) -> str:
    return re.sub(r"\s+(county|parish)$", "", _s(name).lower())


def project_candidates(old: dict, new: list[dict]) -> list[tuple[float, dict, str]]:
    ow, ot, oc = name_words(project_name(old)), techs(old["technology"]), counties(old)
    out = []
    for n in new:
        if n["state"] != old["state"] or n["extraction_source_section"] != "contested_projects":
            continue
        same = _norm_name(project_name(old)) == _norm_name(n["project_or_policy_name"])
        nt = techs(n["technology"])
        if ot and nt and not ot & nt and not same:
            continue
        nw = name_words(n["project_or_policy_name"])
        sim = len(ow & nw) / min(len(ow), len(nw)) if ow and nw else 0.0
        basis = [f"name {sim:.2f}"]
        if sim < MIN_NAME:
            # The 2025 extraction lost some letter pairs ("Garrison Buje" for
            # Butte, "AtlanDc" for Atlantic): compare the spelling instead.
            sim = SequenceMatcher(None, _norm_name(project_name(old)), _norm_name(n["project_or_policy_name"])).ratio()
            if sim < MIN_SPELLING:
                continue
            basis = [f"spelling {sim:.2f}"]
        score = sim
        if same:
            score += 1
            basis.append("same name")
        if oc & counties(n):
            score += 0.5
            basis.append("county")
        score += 0.5 * jaccard(ot, nt)
        out.append((score, n, "; ".join(basis)))
    return sorted(out, key=lambda x: -x[0])


def decide(cands: list[tuple[float, dict, str]]) -> tuple[str, dict | None, str]:
    if not cands:
        return "not_in_latest_edition", None, ""
    if CROSS_LEVEL in cands[0][2]:
        return "ambiguous", None, f"only {CROSS_LEVEL}: a reviewer decides"
    if DIFFERENT in cands[0][2] and "year" not in cands[0][2].split("; "):
        return "ambiguous", None, f"best candidate has {DIFFERENT}: a reviewer decides"
    if len(cands) == 1 or cands[0][0] - cands[1][0] >= MARGIN:
        return "matched", cands[0][1], cands[0][2]
    return "ambiguous", None, f"{len(cands)} candidates within {MARGIN} of each other"


def build(old_records: list[dict], new_records: list[dict], existing: list[dict] | None = None) -> list[dict]:
    """One crosswalk row per 2025 record."""
    by_id = {n["record_id"]: n for n in new_records}
    prior = {r["rec_id"]: r for r in existing or [] if r.get("rec_id")}
    rows, claims = [], {}
    for old in old_records:
        section = old["extraction_source_section"]
        cands = (project_candidates if section == "contested_projects" else restriction_candidates)(old,
                                                                                                      new_records)
        match, entry, basis = decide(cands)
        row = {"rec_id": old["record_id"], "section": section, "state": old["state"], "name_2025": label(old),
               "technology_2025": old["technology"], "mechanism_2025": old["policy_mechanism"],
               "status_2025": old["status"], "match": match, "entry_2026": entry["record_id"] if entry else "",
               "match_basis": basis,
               "candidates_2026": "; ".join(f"{c[1]['record_id']} {label(c[1])} ({c[0]:.2f})" for c in cands[:5])}
        rev = prior.get(old["record_id"], {})
        for f in REVIEW_FIELDS:
            row[f] = _s(rev.get(f))
        rows.append(row)
        if entry:
            claims.setdefault(entry["record_id"], []).append(row)
    for entry_id, claimants in claims.items():
        if len(claimants) > 1:
            for row in claimants:
                row["match"], row["entry_2026"] = "ambiguous", ""
                row["match_basis"] = (f"{entry_id} is the best match for {len(claimants)} 2025 records "
                                      f"({', '.join(c['rec_id'] for c in claimants)})")
    for row in rows:  # a reviewer's decision wins
        d = row["review_decision"]
        if d.lower() == "none":
            row["match"], row["entry_2026"], row["match_basis"] = "not_in_latest_edition", "", "reviewer"
        elif d:
            if d not in by_id:
                raise SystemExit(f"{CROSSWALK_PATH.name}: {row['rec_id']} review_decision {d!r} "
                                 "is not a 2026 entry")
            row["match"], row["entry_2026"], row["match_basis"] = "matched", d, "reviewer"
    taken: dict[str, str] = {}
    for row in rows:
        if row["match"] == "matched":
            if row["entry_2026"] in taken:
                raise SystemExit(f"{CROSSWALK_PATH.name}: {row['entry_2026']} is matched to both "
                                 f"{taken[row['entry_2026']]} and {row['rec_id']}")
            taken[row["entry_2026"]] = row["rec_id"]
        n = by_id.get(row["entry_2026"], {})
        row["name_2026"] = label(n) if n else ""
        row["technology_2026"] = n.get("technology", "")
        row["mechanism_2026"] = n.get("policy_mechanism", "")
        row["status_2026"] = n.get("status", "")
        row["status_changed"] = "yes" if n and n.get("status") != row["status_2025"] else ""
    return rows


def load(path: Path = CROSSWALK_PATH) -> list[dict]:
    return read_csv(path)


def summary(rows: list[dict]) -> dict[str, int]:
    out = {m: 0 for m in MATCHES}
    for r in rows:
        out[r["match"]] += 1
    out["status_changed"] = sum(1 for r in rows if r.get("status_changed") == "yes")
    return out


def main() -> int:
    old, new = read_csv(RECORDS_2025), read_csv(RECORDS_2026)
    rows = build(old, new, load())
    write_csv(CROSSWALK_PATH, rows, FIELDS)
    s = summary(rows)
    matched = {r["entry_2026"] for r in rows if r["match"] == "matched"}
    print(f"Wrote {CROSSWALK_PATH.relative_to(ROOT)}: {len(rows)} 2025 records; "
          + ", ".join(f"{k}={v}" for k, v in s.items())
          + f"; {len(new) - len(matched)} 2026 entries have no 2025 record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
