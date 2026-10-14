#!/usr/bin/env python3
"""What the pipeline did and holds, in one small file a page can load.

Adapted from pricephillips/data-center-map operations_summary.py (copied in
spirit, not imported). The build already records how it maintains itself:
the QC gate's quarantine, the promotion trail, the review worklists, the
snapshot manifest and the headline history, the source archive. None of that
was readable in one place, so the claim that the pipeline keeps itself honest
could only be made by pointing at six files. This module reads those trails
and writes data/processed/operations_summary.json (for a page) and .md (for a
reader). It computes nothing new: every number is a count of rows some other
module wrote, so it can be checked against that file.

Reads   data/processed/headline_metrics.json, quarantine.json, sources.csv
        data/review/outcome_worklist.csv, restriction_worklist.csv,
        negative_check_worklist.csv, adjacency_worklist.csv, fips_misses.csv,
        promotion_trail.csv, queue.csv, cases_candidates.csv,
        restriction_sources.csv, outcome_resolutions.csv (what checking found,
        by source family: how often a compiled row survived a reading of its
        primary source)
        data/snapshots/manifest.csv, headline_history.csv (scripts/headline_history.py)
        data/raw/manifest.csv, parse_state.csv (live intake: what each source
        returned, when its content last changed, what parse.py queued)
Writes  data/processed/operations_summary.json, operations_summary.md

Usage
  python scripts/operations_summary.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, REVIEW_DIR, ROOT, read_csv  # noqa: E402

OUT_JSON = PROCESSED_DIR / "operations_summary.json"
OUT_MD = PROCESSED_DIR / "operations_summary.md"
SNAPSHOTS = ROOT / "data" / "snapshots"
RAW = ROOT / "data" / "raw"
RECENT = 8  # trail decisions shown


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def headline_section(metrics: dict | None) -> dict | None:
    if not metrics:
        return None
    ren = metrics["restrictions"]["by_scope"]["renewables_only"]
    proj = metrics["contested_projects"]
    return {
        "restriction_instruments": ren["instruments"], "severe": ren["severe_instruments"],
        "verified": ren["by_verification"].get("verified", 0),
        "lapsed_unconfirmed": ren.get("by_currency", {}).get("lapsed_unconfirmed", 0),
        "severe_where_state_limits_local": ren.get("severe_where_state_limits_local", 0),
        "projects": proj["projects"], "projects_confirmed": proj["confirmed_outcomes"],
        "decided": proj.get("decided"),
        "cases": metrics["cases"]["cases"],
        "county_coverage": metrics.get("county_coverage"),
    }


def quarantine_section(held: list[dict] | None) -> dict:
    held = held or []
    codes = Counter(i["code"] for r in held for i in r.get("qc_issues", []) if i.get("severity") in ("HIGH", "CRITICAL"))
    return {"rows": len(held), "by_entity": dict(Counter(_s(r.get("entity")) for r in held)),
            "by_blocking_code": dict(codes.most_common())}


def worklists_section(outcomes: list[dict], restrictions: list[dict], negative: list[dict],
                      adjacency: list[dict], misses: list[dict]) -> dict:
    return {
        "outcomes": {"rows": len(outcomes), "by_tier": dict(Counter(_s(r.get("tier")) for r in outcomes)),
                     "overdue": sum(1 for r in outcomes if _s(r.get("recheck"))),
                     "with_decision_language": sum(1 for r in outcomes if _s(r.get("decision_language"))),
                     "with_located_url": sum(1 for r in outcomes if _s(r.get("located_url")))},
        "restrictions": {"rows": len(restrictions),
                         "by_tier": dict(Counter(_s(r.get("tier")) for r in restrictions)),
                         "lapsed": sum(1 for r in restrictions if _s(r.get("currency")) == "lapsed_unconfirmed"),
                         "by_county_impact": dict(Counter(_s(r.get("county_impact")) or "none" for r in restrictions)),
                         "with_located_url": sum(1 for r in restrictions if _s(r.get("located_url"))),
                         "flagged": sum(1 for r in restrictions if _s(r.get("flags")))},
        "negative_checks": {"rows": len(negative),
                            "by_reason": dict(Counter(_s(r.get("reason")).split(" (")[0] for r in negative))},
        "adjacency": {"rows": len(adjacency)},
        "fips_misses": {"rows": len(misses), "by_reason": dict(Counter(_s(r.get("reason")) for r in misses))},
    }


def trail_section(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    dates = sorted({_s(r.get("decided_on")) for r in rows} - {""})
    return {"decisions": len(rows), "by_action": dict(Counter(_s(r.get("action")) for r in rows).most_common()),
            "by_file": dict(Counter(_s(r.get("file")) for r in rows)),
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
            "recent": [{"date": _s(r.get("decided_on")), "file": _s(r.get("file")), "action": _s(r.get("action")),
                        "what": " ".join(x for x in (_s(r.get("state")), _s(r.get("place"))) if x),
                        "reason": _s(r.get("reason"))} for r in rows[-RECENT:][::-1]]}


def review_section(queue: list[dict], candidates: list[dict]) -> dict:
    started = [c for c in candidates if _s(c.get("review_status")) != "promoted"
               and any(_s(c.get(f)) for f in ("case_name", "court", "court_level", "case_source_url"))]
    return {"queue_by_status": dict(Counter(_s(r.get("review_status")) or "pending" for r in queue)),
            "queue_by_entity": dict(Counter(_s(r.get("entity_type")) for r in queue)),
            "case_candidates": len(candidates),
            "case_candidates_started": len(started),
            "case_candidates_promoted": sum(1 for c in candidates if _s(c.get("review_status")) == "promoted")}


def history_section(manifest: list[dict], history: list[dict]) -> dict:
    dates = sorted({_s(r.get("date")) for r in history} - {""})
    return {"snapshot_rows": len(manifest),
            "snapshot_files": len({_s(r.get("file")) for r in manifest}),
            "headline_history_rows": len(history),
            "headline_first_change": dates[0] if dates else None,
            "headline_last_change": dates[-1] if dates else None,
            "latest": {k: v for k, v in history[-1].items() if k != "date"} if history else None}


def _family(instrument_id: str) -> str:
    return {"mn": "Moratorium Nation", "sabin": "Sabin", "nrel": "NREL", "queue": "review queue"}.get(
        _s(instrument_id).split(":")[0], "other")


def evidence_checks_section(sources: list[dict], resolutions: list[dict]) -> dict:
    """What reviewers found when they read primary sources: per source family,
    how many instruments were checked, confirmed or contradicted, and how the
    document was seen. A compiled source's reliability, measured on what was
    checked, never extrapolated."""
    by_family: dict[str, Counter] = {}
    for r in sources:
        c = by_family.setdefault(_family(r.get("instrument_id")), Counter())
        c["checked"] += 1
        c[_s(r.get("verdict")) or "no_verdict"] += 1
        c[f"access_{_s(r.get('access')) or 'unknown'}"] += 1
    outcomes = Counter(_s(r.get("outcome")) for r in resolutions)
    access = Counter(_s(r.get("access")) or "unknown" for r in resolutions)
    return {"restriction_sources": {fam: dict(sorted(c.items())) for fam, c in sorted(by_family.items())},
            "outcome_resolutions": {"rows": len(resolutions), "by_outcome": dict(outcomes.most_common()),
                                    "by_access": dict(sorted(access.items()))}}


def intake_section(raw_manifest: list[dict], parse_state: list[dict], queue: list[dict]) -> dict:
    """Live intake by source, from data/raw/manifest.csv (one row per request:
    stored, unchanged or failed), data/raw/parse_state.csv (raw files parsed and
    leads queued) and the queue (leads still untriaged, and what triage made of
    the rest). Counts only."""
    out: dict[str, dict] = {}
    for r in raw_manifest:
        sid = _s(r.get("source_id"))
        e = out.setdefault(sid, {"requests": 0, "stored": 0, "unchanged": 0, "failed": 0, "last_fetch": None,
                                 "last_changed": None, "last_error": None})
        e["requests"] += 1
        day = _s(r.get("fetch_date"))[:10] or None
        e["last_fetch"] = max(filter(None, (e["last_fetch"], day)), default=None)
        if _s(r.get("error")):
            e["failed"] += 1
            e["last_error"] = f"{day}: {_s(r.get('error'))[:160]}"
        elif _s(r.get("local_path")) == "unchanged":
            e["unchanged"] += 1
        elif _s(r.get("local_path")):
            e["stored"] += 1
            e["last_changed"] = max(filter(None, (e["last_changed"], day)), default=None)
    for r in parse_state:
        e = out.get(_s(r.get("source_id")))
        if e is not None:
            e["files_parsed"] = e.get("files_parsed", 0) + 1
            e["leads_queued"] = e.get("leads_queued", 0) + int(_s(r.get("candidate_count")) or 0)
    for r in queue:
        e = out.get(_s(r.get("source_id")))
        if e is not None:
            status = _s(r.get("review_status")) or "pending"
            e.setdefault("queue_by_status", Counter())[status] += 1
    for e in out.values():
        if "queue_by_status" in e:
            e["queue_by_status"] = dict(sorted(e["queue_by_status"].items()))
    return dict(sorted(out.items()))


def archive_section(sources: list[dict]) -> dict:
    archived = sum(1 for s in sources if _s(s.get("archived_url")))
    return {"sources": len(sources), "archived": archived,
            "archived_share": round(archived / len(sources), 3) if sources else None}


def summarize(*, today: str, metrics, held, outcomes, restrictions, negative, adjacency, misses, trail, queue,
              candidates, manifest, history, sources, restriction_sources=(), outcome_resolutions=(),
              raw_manifest=(), parse_state=()) -> dict:
    return {
        "generated": today,
        "note": "Every number counts rows another module wrote; check it against the file named in the key.",
        "headline": headline_section(metrics),
        "quarantine": quarantine_section(held),
        "worklists": worklists_section(outcomes, restrictions, negative, adjacency, misses),
        "promotion_trail": trail_section(trail),
        "review": review_section(queue, candidates),
        "history": history_section(manifest, history),
        "source_archive": archive_section(sources),
        "evidence_checks": evidence_checks_section(list(restriction_sources), list(outcome_resolutions)),
        "intake": intake_section(list(raw_manifest), list(parse_state), queue),
    }


def render(s: dict) -> str:
    h, q, w, t, r, hi, a = (s.get(k) for k in ("headline", "quarantine", "worklists", "promotion_trail", "review",
                                               "history", "source_archive"))
    L = ["# Operations summary", "",
         f"Generated {s['generated']} by `scripts/operations_summary.py`. {s['note']}", ""]
    if h:
        L += ["## Published", "",
              f"{h['restriction_instruments']} renewables-only restriction instruments ({h['severe']} severe, "
              f"{h['verified']} verified, {h['lapsed_unconfirmed']} past their end date with no confirmed extension, "
              f"{h['severe_where_state_limits_local']} severe ones in states whose siting law limits local reach); "
              f"{h['projects']} contested projects ({h['projects_confirmed']} confirmed); {h['cases']} cases.", ""]
        d = h.get("decided")
        if d:
            every, confirmed = d["all"], d["confirmed_only"]
            L += [f"Decided projects (events older than {d['guard_days']} days): {every['projects']}, of which "
                  f"{every['blocked']} blocked; confirmed outcomes only: {confirmed['projects']}, "
                  f"{confirmed['blocked']} blocked. Conditional on opposition being tracked; see headline_metrics.md.",
                  ""]
    L += ["## Held back", "",
          f"{q['rows']} rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): "
          + (", ".join(f"{n} {c}" for c, n in q["by_blocking_code"].items()) or "none") + ".", ""]
    L += ["## Worklists", "", "| Worklist | Rows | Notes |", "|---|---:|---|",
          f"| outcome_worklist.csv | {w['outcomes']['rows']} | {w['outcomes']['overdue']} overdue, "
          f"{w['outcomes']['with_decision_language']} with decision language in their text, "
          f"{w['outcomes']['with_located_url']} with a located source |",
          f"| restriction_worklist.csv | {w['restrictions']['rows']} | {w['restrictions']['lapsed']} lapsed, "
          f"{w['restrictions']['by_county_impact'].get('sole_severe', 0)} sole severe in a county, "
          f"{w['restrictions']['with_located_url']} with a located source |",
          f"| negative_check_worklist.csv | {w['negative_checks']['rows']} | "
          + (", ".join(f"{n} {k}" for k, n in w['negative_checks']['by_reason'].items()) or "") + " |",
          f"| adjacency_worklist.csv | {w['adjacency']['rows']} | neighbours of blocked projects not yet examined |",
          f"| fips_misses.csv | {w['fips_misses']['rows']} | "
          + (", ".join(f"{n} {k}" for k, n in w['fips_misses']['by_reason'].items()) or "") + " |", ""]
    L += ["## Review and promotion", "",
          f"Queue: " + (", ".join(f"{n} {k}" for k, n in r['queue_by_status'].items()) or "empty") + ". "
          f"Case candidates: {r['case_candidates']} ({r['case_candidates_promoted']} promoted, "
          f"{r['case_candidates_started']} started by a reviewer)."]
    if t:
        L += ["", f"Promotion trail: {t['decisions']} decisions from {t['first']} to {t['last']} "
              "(new or changed decisions only): " + ", ".join(f"{n} {k}" for k, n in t["by_action"].items()) + ".",
              "", "| Date | File | Action | What | Reason |", "|---|---|---|---|---|"]
        L += [f"| {x['date']} | {x['file']} | {x['action']} | {x['what']} | {x['reason']} |" for x in t["recent"]]
    ev = s.get("evidence_checks") or {}
    if ev.get("restriction_sources") or (ev.get("outcome_resolutions") or {}).get("rows"):
        L += ["", "## What checking found", "",
              "Reviewers' verdicts on primary sources, by the source family of the instrument checked "
              "(`data/review/restriction_sources.csv`). A reliability measured on what was checked, never extrapolated "
              "to the rows nobody has read.", "",
              "| Source family | Instruments checked | Confirmed | Contradicted | Opened | Archived | Snippet |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for fam, c in ev.get("restriction_sources", {}).items():
            L.append(f"| {fam} | {c.get('checked', 0)} | {c.get('confirmed', 0)} | {c.get('contradicts', 0)} | "
                     f"{c.get('access_opened', 0)} | {c.get('access_archived', 0)} | {c.get('access_snippet', 0)} |")
        o = ev.get("outcome_resolutions", {})
        if o.get("rows"):
            L += ["", f"Outcome resolutions: {o['rows']} ("
                  + ", ".join(f"{n} {k}" for k, n in o["by_outcome"].items()) + "; by access "
                  + ", ".join(f"{n} {k}" for k, n in o["by_access"].items()) + ")."]
    intake = s.get("intake") or {}
    if intake:
        L += ["", "## Live intake and fetched sources", "",
              "Per source in `data/raw/manifest.csv`: requests made, new content stored, unchanged and failed; "
              "when the content last changed; leads parse.py queued (`data/raw/parse_state.csv`) and what review "
              "made of them in the queue. A lead is never published until a reviewer triages it.", "",
              "| Source | Requests | Stored | Unchanged | Failed | Last fetch | Last changed | Leads queued | Queue now |",
              "|---|---:|---:|---:|---:|---|---|---:|---|"]
        for sid, e in intake.items():
            qs = ", ".join(f"{n} {k}" for k, n in (e.get("queue_by_status") or {}).items())
            L.append(f"| {sid} | {e['requests']} | {e['stored']} | {e['unchanged']} | {e['failed']} | "
                     f"{e['last_fetch'] or ''} | {e['last_changed'] or ''} | {e.get('leads_queued', '')} | {qs} |")
        errors = [(sid, e["last_error"]) for sid, e in intake.items() if e.get("last_error")]
        if errors:
            L += ["", "Last error by source: " + "; ".join(f"{sid} ({err})" for sid, err in errors) + "."]
    L += ["", "## History and archive", "",
          f"{hi['snapshot_rows']} snapshot rows over {hi['snapshot_files']} published files; "
          f"{hi['headline_history_rows']} headline changes recorded"
          + (f" ({hi['headline_first_change']} to {hi['headline_last_change']})" if hi["headline_history_rows"] else "")
          + f". Sources: {a['sources']}, of which {a['archived']} have an Internet Archive snapshot.", ""]
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    s = summarize(
        today=date.today().isoformat(),
        metrics=_json(PROCESSED_DIR / "headline_metrics.json"),
        held=_json(PROCESSED_DIR / "quarantine.json"),
        outcomes=read_csv(REVIEW_DIR / "outcome_worklist.csv"),
        restrictions=read_csv(REVIEW_DIR / "restriction_worklist.csv"),
        negative=read_csv(REVIEW_DIR / "negative_check_worklist.csv"),
        adjacency=read_csv(REVIEW_DIR / "adjacency_worklist.csv"),
        misses=read_csv(REVIEW_DIR / "fips_misses.csv"),
        trail=read_csv(REVIEW_DIR / "promotion_trail.csv"),
        queue=read_csv(REVIEW_DIR / "queue.csv"),
        candidates=read_csv(REVIEW_DIR / "cases_candidates.csv"),
        manifest=read_csv(SNAPSHOTS / "manifest.csv"),
        history=read_csv(SNAPSHOTS / "headline_history.csv"),
        sources=read_csv(PROCESSED_DIR / "sources.csv"),
        restriction_sources=read_csv(REVIEW_DIR / "restriction_sources.csv"),
        outcome_resolutions=read_csv(REVIEW_DIR / "outcome_resolutions.csv"),
        raw_manifest=read_csv(RAW / "manifest.csv"),
        parse_state=read_csv(RAW / "parse_state.csv"),
    )
    OUT_JSON.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render(s), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
