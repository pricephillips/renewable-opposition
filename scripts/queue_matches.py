"""Match contested projects to their interconnection requests in LBNL Queued Up.

data/reference/queue_projects.csv (scripts/fetch_queued_up.py) lists every
interconnection request with a solar, wind or storage part, with the date it
entered the queue and, where they happened, the dates it signed an
interconnection agreement, was withdrawn or began operating. This module finds
the requests each contested project (data/processed/contested_projects.csv)
filed, so the project gains dates that bound when it was proposed and decided
(docs/predictive_foundation_design.md, step 3).

Names are compared exactly as facility_matches.py compares plant names: the
distinctive words after the generic ones are dropped. A request is a
candidate only in the project's state and only when the two share a
technology.

  strong    the distinctive words are the same and the request lies in one of
            the project's counties (or the project names no county); or one
            set contains the other, the request lies in one of the project's
            counties and the capacities agree.
  possible  the same distinctive words in another county, or one set
            containing the other within the project's county; and any
            otherwise strong request whose capacity is more than three times
            off.

A project usually holds several queue positions (a re-filing after a
withdrawal, a later phase, the storage part filed apart), so unlike plants,
several strong requests stay one strong match: their ids are listed together,
with the earliest request date and the latest withdrawal date across them.
Only about a third of requests carry a project name (most in ERCOT, CAISO,
PJM, NYISO and ISO-NE); an unnamed request is never matched, because county,
technology and size alone do not identify a project.

A match never changes an outcome. The queue says what happened to an
interconnection request, which is not the same as what happened to the
project: a project can withdraw one position and proceed on another. Where a
strong match contradicts the published outcome (a blocked project with an
operational request; an advanced one whose every request was withdrawn), the
row is flagged in `conflict` for a reviewer, as facility_matches.py flags
plants; so is a pending (or needs_review) project whose requests are all
withdrawn or one of which is operational.

Writes data/reference/queue_matches.csv, one row per contested project with a
strong or possible match, and data/reference/queue_matches_report.md with the
counts.

Usage
  python scripts/queue_matches.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facility_matches as fm  # noqa: E402
from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

QUEUE_PATH = ROOT / "data" / "reference" / "queue_projects.csv"
PROJECTS_PATH = PROCESSED_DIR / "contested_projects.csv"
MATCHES_PATH = ROOT / "data" / "reference" / "queue_matches.csv"
REPORT_PATH = ROOT / "data" / "reference" / "queue_matches_report.md"

FIELDS = ["id", "source_record_id", "state", "county", "project_name", "technology", "capacity_mw",
          "outcome", "finality_evidence", "match", "conflict", "n_requests", "queue_project_ids",
          "queue_names", "queue_status", "first_request_date", "last_ia_date", "last_withdrawn_date",
          "first_operational_date", "queue_capacity_mw", "matched_on"]


def load(path: Path | None = None) -> dict[str, list[dict]]:
    """State -> named queue requests, each with its name core and technologies."""
    by_state: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv(path or QUEUE_PATH):
        r["_core"] = fm.core(r["project_name"])
        if not r["_core"]:
            continue
        r["_tech"] = fm.techs(r["technology"])
        by_state[r["state"]].append(r)
    return by_state


def candidates(project: dict, by_state: dict[str, list[dict]]) -> dict[str, list[tuple[dict, list[str]]]]:
    """{"strong": [(request, matched_on words)], "possible": [...]} for one project."""
    pcore = fm.core(project.get("project_name") or "")
    ptech = fm.techs(project.get("technology") or "")
    out: dict[str, list[tuple[dict, list[str]]]] = {"strong": [], "possible": []}
    if not pcore or not ptech:
        return out
    counties = {c for c in (project.get("county_fips_all") or "").split(";") if c}
    cap_text = project.get("capacity_mw") or ""
    for r in by_state.get(project.get("state") or "", []):
        rcore = r["_core"]
        if not (ptech & r["_tech"]):
            continue
        if rcore == pcore:
            rel = "name"
        elif (rcore < pcore or pcore < rcore) and any(len(w) >= 4 for w in rcore & pcore):
            rel = "part of the name"
        else:
            continue
        in_county = r["county_fips"] in counties
        cap_ok = fm.capacity_agrees(cap_text, r["capacity_mw"])
        cap_off = fm.capacity_differs(cap_text, r["capacity_mw"])
        if cap_off:
            level = "possible"
        elif rel == "name" and (in_county or not counties):
            level = "strong"
        elif rel == "part of the name" and in_county and cap_ok:
            level = "strong"
        elif rel == "name" or in_county:
            level = "possible"
        else:
            continue
        on = [rel] + (["county"] if in_county else []) + (["capacity"] if cap_ok else []) \
            + (["a different capacity"] if cap_off else [])
        out[level].append((r, on))
    return out


def group_status(requests: list[dict]) -> str:
    """operational if any request is; else active if any is still in a queue
    (active or suspended); else withdrawn; else unknown."""
    st = {r["status"] for r in requests}
    for s, label in (("operational", "operational"), ("active", "active"), ("suspended", "active"),
                     ("withdrawn", "withdrawn")):
        if s in st:
            return label
    return "unknown"


def conflict(outcome: str, status: str) -> str:
    outcome = outcome or ""
    if outcome.startswith("blocked") and status == "operational":
        return f"outcome {outcome}, but a matched queue request is operational"
    if outcome.startswith("advanced") and status == "withdrawn":
        return f"outcome {outcome}, but every matched queue request was withdrawn"
    if outcome in ("pending", "needs_review") and status in ("operational", "withdrawn"):
        if status == "operational":
            return f"outcome {outcome}, but a matched queue request is operational"
        return f"outcome {outcome}, but every matched queue request was withdrawn"
    return ""


def _dates(requests: list[dict], key: str) -> list[str]:
    return sorted(r[key] for r in requests if r[key])


def match_rows(projects: list[dict], by_state: dict[str, list[dict]]) -> list[dict]:
    out = []
    for p in projects:
        found = candidates(p, by_state)
        level = "strong" if found["strong"] else "possible" if found["possible"] else ""
        if not level:
            continue
        hits = found[level]
        reqs = [r for r, _ in hits]
        words = {w for _, on in hits for w in on}
        order = ["name", "part of the name", "county", "capacity", "a different capacity"]
        status = group_status(reqs)
        caps = sorted({r["capacity_mw"] for r in reqs if r["capacity_mw"]}, key=float)
        out.append({
            "id": p.get("id"), "source_record_id": p.get("source_record_id"), "state": p.get("state"),
            "county": p.get("county"), "project_name": p.get("project_name"),
            "technology": p.get("technology"), "capacity_mw": p.get("capacity_mw"),
            "outcome": p.get("outcome"), "finality_evidence": p.get("finality_evidence"),
            "match": level, "conflict": conflict(p.get("outcome"), status) if level == "strong" else "",
            "n_requests": len(reqs),
            "queue_project_ids": ";".join(sorted(r["queue_project_id"] for r in reqs)),
            "queue_names": "; ".join(sorted({r["project_name"] for r in reqs})),
            "queue_status": status,
            "first_request_date": (_dates(reqs, "request_date") or [""])[0],
            "last_ia_date": (_dates(reqs, "ia_date") or [""])[-1],
            "last_withdrawn_date": (_dates(reqs, "withdrawn_date") or [""])[-1],
            "first_operational_date": (_dates(reqs, "operational_date") or [""])[0],
            "queue_capacity_mw": ";".join(caps),
            "matched_on": " and ".join(w for w in order if w in words),
        })
    out.sort(key=lambda m: (m["match"] != "strong", not m["conflict"], m["state"] or "", m["project_name"] or ""))
    return out


def report(projects: list[dict], rows: list[dict], queue_rows: int, named: int) -> str:
    strong = [r for r in rows if r["match"] == "strong"]
    by_outcome = Counter(r["outcome"] for r in strong)
    eligible = [p for p in projects if fm.techs(p.get("technology") or "") & {"solar", "wind", "battery_storage"}]
    lines = [
        "# Queued Up matches",
        "",
        "Written by `scripts/queue_matches.py`. Do not edit by hand.",
        "",
        f"- Contested projects: {len(projects)}, of which {len(eligible)} are solar, wind or storage.",
        f"- Queue requests: {queue_rows}, of which {named} carry a project name and can be matched.",
        f"- Strong matches: {len(strong)} projects "
        f"({sum(int(r['n_requests']) for r in strong)} requests).",
        f"- Possible matches only: {sum(1 for r in rows if r['match'] == 'possible')} projects.",
        f"- No match: {len(eligible) - len(rows)} solar, wind or storage projects.",
        f"- Conflicts with the published outcome (strong matches only): {sum(1 for r in strong if r['conflict'])}.",
        "",
        "| Outcome | Strong matches | With a request date | With a withdrawal date | With an operation date |",
        "|---|---:|---:|---:|---:|",
    ]
    for outcome, n in sorted(by_outcome.items()):
        sub = [r for r in strong if r["outcome"] == outcome]
        lines.append(f"| {outcome} | {n} | {sum(1 for r in sub if r['first_request_date'])} | "
                     f"{sum(1 for r in sub if r['last_withdrawn_date'])} | "
                     f"{sum(1 for r in sub if r['first_operational_date'])} |")
    lines += ["", "A match never changes an outcome; a conflict is a prompt to review the project, "
              "not a correction."]
    return "\n".join(lines) + "\n"


def main() -> int:
    if not QUEUE_PATH.exists():
        print(f"{QUEUE_PATH.relative_to(ROOT)} is missing; run scripts/fetch_queued_up.py first", file=sys.stderr)
        return 1
    projects = read_csv(PROJECTS_PATH)
    by_state = load()
    queue_rows = sum(1 for _ in read_csv(QUEUE_PATH))
    named = sum(len(v) for v in by_state.values())
    rows = match_rows(projects, by_state)
    write_csv(MATCHES_PATH, rows, FIELDS)
    text = report(projects, rows, queue_rows, named)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"Wrote {MATCHES_PATH.relative_to(ROOT)} ({len(rows)} projects)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
