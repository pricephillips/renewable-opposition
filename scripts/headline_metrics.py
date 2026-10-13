"""Headline numbers, counted by instrument. Pure functions: no I/O.

build_seed_outputs.py writes the result to data/processed/headline_metrics.json
and headline_metrics.md on every build. Any number quoted outside this
repository should come from those files, not from counting rows: a seed row is
one technology of one instrument (classify.instrument_id), so row counts
overstate how many ordinances, moratoria or projects there are.

Rules
  - One instrument counts once, whatever technologies it covers. Its severity
    is the highest of its rows (in practice they agree).
  - Restrictions are split by scope. The headline figure is renewables_only;
    multi_sector_data_centers is reported beside it, never folded in.
    data_center_only instruments are quarantined by qc_gate and never counted.
  - Each scope is also broken down by currency (classify.currency): how many
    instruments are in force today, how many are past their own end date with
    no confirmed extension (lapsed_unconfirmed), pending, or of unknown status.
    A lapsed instrument stays in the instrument count with the status its
    source gave it; the breakdown is what lets a reader subtract it.
  - Every count is also broken down by evidence_level, so a reader can see how
    much of a number rests on a primary source, and by verification
    (classify.verification): verified, located or unverified under the
    evidence standard. An instrument counts as verified only when every one
    of its rows is (in practice they agree).
  - Every count is also broken down by source (SOURCES: Sabin 2026 edition,
    Sabin 2025 edition rows not in the 2026 edition, NREL, Moratorium Nation,
    the review queue), each with its verification.
  - County coverage: of the counties in the 2024 boundary file (50 states
    and DC; Puerto Rico apart), how many have any published record (a
    restriction, a contested project or an NREL siting standard placed in
    them, by county_fips_all), how many have a documented "checked, nothing
    found" (data/review/negative_checks.csv), and how many have neither.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from classify import latest_date

SEVERE = {3, 4}
# The decided-outcome rate (after pricephillips/data-center-map's headline:
# "decided-case confirmed-block rate ... incidents younger than 90 days
# excluded (right-censoring guard)"). A project counts as decided when its
# outcome is one of DECIDED; one whose event is younger than YOUNG_DAYS is
# left out, since a decision that fresh is the least likely to be final or
# fully reported. The rate is conditional on opposition being tracked at all:
# this dataset holds projects because they drew opposition, so it says
# nothing about projects that proceeded without a recorded fight.
DECIDED = ("blocked_confirmed", "blocked_unverified", "advanced_confirmed", "advanced_unverified",
           "restricted_conditional")
YOUNG_DAYS = 90


def _instruments(rows: list[dict]) -> dict[str, dict]:
    """instrument_id -> a representative row carrying the max severity and
    the union of technologies."""
    out: dict[str, dict] = {}
    for r in rows:
        iid = r.get("instrument_id") or r.get("id")
        cur = out.get(iid)
        sev = r.get("severity_score") or 0
        techs = {t for t in str(r.get("technology") or "").split(";") if t}
        if cur is None:
            out[iid] = {**r, "severity_score": sev, "_techs": techs}
        else:
            cur["severity_score"] = max(cur["severity_score"] or 0, sev)
            cur["_techs"] |= techs
    return out


VERIFICATION_RANK = {"verified": 0, "located": 1, "unverified": 2}


def _instrument_verification(rows: list[dict]) -> dict[str, str]:
    """instrument_id -> its weakest verification across rows."""
    out: dict[str, str] = {}
    for r in rows:
        iid = r.get("instrument_id") or r.get("id")
        v = r.get("verification") or "unverified"
        if iid not in out or VERIFICATION_RANK.get(v, 2) > VERIFICATION_RANK.get(out[iid], 2):
            out[iid] = v
    return out


def _counter(items, key) -> dict[str, int]:
    return dict(sorted(Counter(key(i) or "" for i in items).items()))


SOURCES = ("Sabin 2026", "Sabin 2025 (not in 2026 edition)", "NREL", "Moratorium Nation", "review queue",
           "other")


def source_of(row: dict) -> str:
    iid = str(row.get("instrument_id") or "")
    if iid.startswith("sabin:"):
        return "Sabin 2025 (not in 2026 edition)" if row.get("sabin_edition") == "2025-06" else "Sabin 2026"
    if iid.startswith("nrel:"):
        return "NREL"
    if iid.startswith("mn:"):
        return "Moratorium Nation"
    if iid.startswith("queue:"):
        return "review queue"
    return "other"


def by_source(inst: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for src in SOURCES:
        group = [i for i in inst.values() if source_of(i) == src]
        if group:
            out[src] = {"instruments": len(group),
                        "severe_instruments": sum(1 for i in group if i["severity_score"] in SEVERE),
                        "by_verification": _counter(group, lambda i: i.get("verification"))}
    return out


def _fips(row: dict) -> set[str]:
    return {f for f in str(row.get("county_fips_all") or row.get("county_fips") or "").split(";") if f}


def county_coverage(datasets: dict[str, list[dict]], standards: list[dict], checks: list[dict],
                    all_counties: list[str]) -> dict:
    counties = {f for f in all_counties if not f.startswith("72")}
    restricted = set().union(*(_fips(r) for r in datasets.get("restrictions", []))) & counties
    projects = set().union(*(_fips(r) for r in datasets.get("contested_projects", []))) & counties
    standard = set().union(*(_fips(r) for r in standards)) & counties
    any_record = restricted | projects | standard
    checked = {str(c.get("county_fips", "")).strip().zfill(5) for c in checks} & counties
    return {
        "counties": len(counties),
        "with_any_record": len(any_record),
        "with_restriction": len(restricted),
        "with_contested_project": len(projects),
        "with_siting_standard": len(standard),
        "with_negative_check": len(checked),
        "with_negative_check_and_no_record": len(checked - any_record),
        "with_neither": len(counties - any_record - checked),
    }


def _share(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def decided_rate(inst: dict[str, dict], today: date) -> dict:
    """Blocked share of decided projects, with the young-record guard, for all
    decided projects and for the confirmed ones alone."""
    decided, young = [], 0
    for i in inst.values():
        if str(i.get("outcome") or "") not in DECIDED:
            continue
        when = latest_date(str(i.get("event_date_text") or ""))
        if when and (today - when).days < YOUNG_DAYS:
            young += 1
            continue
        decided.append(i)

    def block(group):
        blocked = sum(1 for i in group if str(i.get("outcome") or "").startswith("blocked"))
        return {"projects": len(group), "blocked": blocked, "blocked_share": _share(blocked, len(group))}

    confirmed = [i for i in decided if str(i.get("outcome") or "").endswith("_confirmed")]
    by_tech: dict[str, dict] = {}
    for t in sorted({t for i in decided for t in i["_techs"]}):
        by_tech[t] = block([i for i in decided if t in i["_techs"]])
    return {"guard_days": YOUNG_DAYS, "young_excluded": young, "all": block(decided),
            "confirmed_only": block(confirmed), "by_technology": by_tech}


def compute(datasets: dict[str, list[dict]], standards: list[dict] | None = None,
            policies: list[dict] | None = None, checks: list[dict] | None = None,
            all_counties: list[str] | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    out: dict = {}
    rows = datasets.get("restrictions", [])
    inst = _instruments(rows)
    for iid, v in _instrument_verification(rows).items():
        inst[iid]["verification"] = v
    by_scope: dict[str, dict] = {}
    for sc in ("renewables_only", "multi_sector_data_centers"):
        group = [i for i in inst.values() if i.get("scope") == sc]
        by_scope[sc] = {
            "instruments": len(group),
            "severe_instruments": sum(1 for i in group if i["severity_score"] in SEVERE),
            "states": len({i.get("state") for i in group if i.get("state")}),
            "by_status": _counter(group, lambda i: i.get("status")),
            "by_technology": dict(sorted(Counter(t for i in group for t in i["_techs"]).items())),
            "by_evidence_level": _counter(group, lambda i: i.get("evidence_level")),
            "by_verification": _counter(group, lambda i: i.get("verification")),
            "by_currency": _counter(group, lambda i: i.get("currency")),
            # Severe instruments in states whose verified siting law limits
            # local reach for the technology (classify.state_context): a
            # context for the count, never a subtraction from it.
            "severe_where_state_limits_local": sum(
                1 for i in group if i["severity_score"] in SEVERE and i.get("state_limits_local") == "yes"),
        }
    out["restrictions"] = {"rows": len(rows), "instruments": len(inst), "by_scope": by_scope,
                           "by_source": by_source(inst),
                           "by_verification": _counter(inst.values(), lambda i: i.get("verification"))}

    rows = datasets.get("contested_projects", [])
    inst = _instruments(rows)
    for iid, v in _instrument_verification(rows).items():
        inst[iid]["verification"] = v
    out["contested_projects"] = {
        "rows": len(rows),
        "projects": len(inst),
        "confirmed_outcomes": sum(1 for i in inst.values()
                                  if str(i.get("outcome") or "").endswith("_confirmed")),
        "by_outcome": _counter(inst.values(), lambda i: i.get("outcome")),
        "by_evidence_level": _counter(inst.values(), lambda i: i.get("evidence_level")),
        "by_verification": _counter(inst.values(), lambda i: i.get("verification")),
        "by_source": by_source(inst),
        "facility_matches": _counter((i for i in inst.values() if i.get("facility_match")),
                                     lambda i: i.get("facility_status")),
        "facility_conflicts": sum(1 for i in inst.values() if i.get("facility_conflict")),
        "decided": decided_rate(inst, today),
        "by_concern": dict(sorted(Counter(c for i in inst.values()
                                          for c in str(i.get("concerns") or "").split(";") if c).items(),
                                  key=lambda kv: (-kv[1], kv[0]))),
        "with_no_concern_named": sum(1 for i in inst.values() if not i.get("concerns")),
        "in_county_with_severe_restriction": sum(1 for i in inst.values()
                                                 if i.get("county_severe_restriction_ids")),
    }

    rows = datasets.get("cases", [])
    inst = _instruments(rows)
    for iid, v in _instrument_verification(rows).items():
        inst[iid]["verification"] = v
    out["cases"] = {
        "rows": len(rows),
        "cases": len(inst),
        "by_case_status": _counter(inst.values(), lambda i: i.get("case_status")),
        "by_verification": _counter(inst.values(), lambda i: i.get("verification")),
    }
    standards = standards or []
    out["siting_standards"] = {
        "rows": len(standards),
        "jurisdictions": len({(r.get("state"), r.get("jurisdiction"), r.get("technology")) for r in standards}),
        "by_technology": _counter(standards, lambda r: r.get("technology")),
        "by_verification": _counter(standards, lambda r: r.get("verification")),
        "restricting_rows": sum(1 for r in standards if r.get("restricting") == "yes"),
    }
    policies = policies or []
    out["state_policies"] = {
        "rows": len(policies), "states": len({r.get("state") for r in policies}),
        "by_policy_type": _counter(policies, lambda r: r.get("policy_type")),
        "by_verification": _counter(policies, lambda r: r.get("verification")),
    }
    if all_counties:
        out["county_coverage"] = county_coverage(datasets, standards, checks or [], all_counties)
    return out


def render(m: dict) -> str:
    r = m["restrictions"]
    ren, multi = r["by_scope"]["renewables_only"], r["by_scope"]["multi_sector_data_centers"]
    c, k = m["contested_projects"], m["cases"]
    lines = [
        "# Headline metrics",
        "",
        "Generated by `scripts/build_seed_outputs.py` (`scripts/headline_metrics.py`).",
        "Counted by instrument: one ordinance, moratorium, project or case counts once",
        "however many technologies it covers. Quote these, not row counts.",
        "",
        "## Restrictions",
        "",
        "| | Renewables only | Also covers data centers |",
        "|---|---:|---:|",
        f"| Instruments | {ren['instruments']} | {multi['instruments']} |",
        f"| Severe (severity 3 or 4) | {ren['severe_instruments']} | {multi['severe_instruments']} |",
        f"| States | {ren['states']} | {multi['states']} |",
    ]
    for level in sorted(set(ren["by_evidence_level"]) | set(multi["by_evidence_level"])):
        lines.append(f"| Evidence: {level} | {ren['by_evidence_level'].get(level, 0)} | "
                     f"{multi['by_evidence_level'].get(level, 0)} |")
    for v in ("verified", "located", "unverified"):
        lines.append(f"| Verification: {v} | {ren['by_verification'].get(v, 0)} | "
                     f"{multi['by_verification'].get(v, 0)} |")
    for cur in ("in_force", "lapsed_unconfirmed", "pending", "unknown"):
        lines.append(f"| Currency: {cur} | {ren.get('by_currency', {}).get(cur, 0)} | "
                     f"{multi.get('by_currency', {}).get(cur, 0)} |")
    lines += [
        "",
        "Verified: checked against the instrument itself or the minutes that adopted it, opened or "
        "read in an archived copy. Located: that document is found but not yet read. Unverified: "
        "a news article or a compiled tracker locates the instrument but does not verify it.",
        "",
        f"Of the severe instruments, {ren.get('severe_where_state_limits_local', 0)} (renewables only) and "
        f"{multi.get('severe_where_state_limits_local', 0)} (also covering data centers) sit in a state whose "
        "verified siting law limits how far a local instrument reaches for that technology (a size threshold "
        "above which a state body decides, or a preemption rule; `state_limits_local` on the row). The count "
        "is a context, not a subtraction: the law's effect on a given instrument is for a reader to judge.",
        "",
        "Currency: in_force means the status is active or extended and no end date has passed. "
        "lapsed_unconfirmed means the instrument's own end date is before the build date and no reviewer "
        "has confirmed an extension; it keeps its source status and severity, so subtract it before "
        "quoting what is in force today. unknown is a row with no status (NREL ordinance features).",
        "",
        f"{r['rows']} published rows describe {r['instruments']} instruments.",
        "",
        "## Contested projects",
        "",
        f"{c['projects']} projects; {c['confirmed_outcomes']} with a confirmed outcome; "
        f"{c['by_verification'].get('verified', 0)} verified (backed by a news article or court record "
        f"that was read), {c['by_verification'].get('unverified', 0)} resting on a compiled report only.",
        "",
        "| Outcome | Projects |",
        "|---|---:|",
    ]
    lines += [f"| {o} | {n} |" for o, n in c["by_outcome"].items()]
    fm = c.get("facility_matches") or {}
    if fm:
        lines += ["", f"{sum(fm.values())} projects match a plant in the federal inventories (EIA-860M, "
                  "USWTDB, USPVDB) by name, county and size. What the inventories record for that plant:", "",
                  "| Plant status | Projects |", "|---|---:|"]
        lines += [f"| {st} | {n} |" for st, n in fm.items()]
        lines += ["", f"{c.get('facility_conflicts', 0)} of them carry an outcome the plant's status contradicts "
                  "(see `data/review/facility_matches.csv`). A plant's status says what became of it, not "
                  "whether opposition had anything to do with it; no outcome is changed by a match."]
    d = c.get("decided")
    if d:
        a, co = d["all"], d["confirmed_only"]
        pct = (lambda x: f"{round(100 * x)}%" if x is not None else "n/a")
        lines += ["", "### Decided projects", "",
                  "This dataset holds projects because they drew opposition, so every rate below is conditional "
                  "on a fight visible enough to enter the record; projects that proceeded without tracked "
                  "opposition are absent by construction. Decided means an outcome of "
                  f"{', '.join(DECIDED)}; a project whose event is younger than {d['guard_days']} days is left out "
                  f"({d['young_excluded']} today), since the freshest decisions are the least likely to be final.", "",
                  "| | Decided projects | Blocked | Blocked share |", "|---|---:|---:|---:|",
                  f"| All decided | {a['projects']} | {a['blocked']} | {pct(a['blocked_share'])} |",
                  f"| Confirmed outcomes only | {co['projects']} | {co['blocked']} | {pct(co['blocked_share'])} |"]
        for t, g in d["by_technology"].items():
            lines.append(f"| {t} | {g['projects']} | {g['blocked']} | {pct(g['blocked_share'])} |")
        lines += ["", "Quote the confirmed-only figure when the claim is about what happened; the all-decided figure "
                  "rests partly on the source's label alone."]
    bc = c.get("by_concern")
    if bc is not None:
        lines += ["", "### Concerns named in the record", "",
                  f"What the record's own text names, by a fixed keyword table (`docs/codebook.md`); "
                  f"{c.get('with_no_concern_named', 0)} projects name none. A concern is what was raised, not why "
                  "the project ended as it did.", "", "| Concern | Projects |", "|---|---:|"]
        lines += [f"| {k2} | {n} |" for k2, n in bc.items()]
        lines += ["", f"{c.get('in_county_with_severe_restriction', 0)} projects share a county with a severe "
                  "renewables-only restriction for the same technology (`county_severe_restriction_ids`); a fact "
                  "about the county, not a link between the records."]
    lines += ["", "## Cases", "", f"{k['cases']} cases; {k['by_verification'].get('verified', 0)} "
              "with a court record.", "", "| Status | Cases |", "|---|---:|"]
    lines += [f"| {s or '(blank)'} | {n} |" for s, n in k["by_case_status"].items()]
    lines += ["", "## By source", "",
              "Instruments (restrictions) and projects by the source they came from, with their verification.",
              "", "| Entity | Source | Count | Severe | Verified | Located | Unverified |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for entity, label in (("restrictions", "Restrictions"), ("contested_projects", "Contested projects")):
        for src, g in m[entity].get("by_source", {}).items():
            v = g["by_verification"]
            severe = g["severe_instruments"] if entity == "restrictions" else ""
            lines.append(f"| {label} | {src} | {g['instruments']} | {severe} | {v.get('verified', 0)} | "
                         f"{v.get('located', 0)} | {v.get('unverified', 0)} |")
    st, sp = m.get("siting_standards"), m.get("state_policies")
    if st:
        lines += ["", "## Siting standards (NREL)", "",
                  f"{st['rows']} feature rows for {st['jurisdictions']} jurisdiction and technology pairs "
                  f"({', '.join(f'{t} {n}' for t, n in st['by_technology'].items())}); "
                  f"{st['by_verification'].get('verified', 0)} verified against the ordinance, "
                  f"{st['by_verification'].get('unverified', 0)} unverified. NREL compiled them with language "
                  "models; unverified rows are NREL's reading, not a checked fact."]
    if sp:
        lines += ["", "## State siting law", "",
                  f"{sp['rows']} state policy rows in {sp['states']} states, each verified against the statute."]
    cc = m.get("county_coverage")
    if cc:
        lines += ["", "## County coverage", "",
                  f"Of {cc['counties']} counties and county equivalents (50 states and DC):", "",
                  "| | Counties |", "|---|---:|",
                  f"| Any published record | {cc['with_any_record']} |",
                  f"| A restriction | {cc['with_restriction']} |",
                  f"| A contested project | {cc['with_contested_project']} |",
                  f"| An NREL siting standard | {cc['with_siting_standard']} |",
                  f"| A documented negative check | {cc['with_negative_check']} |",
                  f"| A negative check and no record | {cc['with_negative_check_and_no_record']} |",
                  f"| Neither a record nor a check | {cc['with_neither']} |", "",
                  "A county with neither has not been looked at; it is not evidence that nothing happened."]
    return "\n".join(lines) + "\n"
