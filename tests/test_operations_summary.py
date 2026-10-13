"""The operations summary counts rows other modules wrote and nothing else.
Synthetic inputs only."""
import json

import operations_summary as ops

METRICS = {"restrictions": {"by_scope": {"renewables_only": {
    "instruments": 10, "severe_instruments": 4, "by_verification": {"verified": 1},
    "by_currency": {"lapsed_unconfirmed": 1}, "severe_where_state_limits_local": 2}}},
    "contested_projects": {"projects": 5, "confirmed_outcomes": 2,
                           "decided": {"guard_days": 90, "young_excluded": 1,
                                       "all": {"projects": 3, "blocked": 2, "blocked_share": 0.667},
                                       "confirmed_only": {"projects": 2, "blocked": 1, "blocked_share": 0.5},
                                       "by_technology": {}}},
    "cases": {"cases": 1}}
HELD = [{"entity": "restrictions", "qc_issues": [{"code": "SCOPE_DATA_CENTER_ONLY", "severity": "HIGH"},
                                                {"code": "DATE_UNPARSEABLE", "severity": "LOW"}]}]
TRAIL = [{"decided_on": "2026-10-13", "file": "queue.csv", "key": "q1", "state": "KS", "place": "X", "action": "held",
          "reason": "missing court"},
         {"decided_on": "2026-10-14", "file": "queue.csv", "key": "q1", "state": "KS", "place": "X",
          "action": "promoted", "reason": ""}]


def build():
    return ops.summarize(
        today="2026-10-14", metrics=METRICS, held=HELD,
        outcomes=[{"tier": "pending", "recheck": "overdue", "decision_language": "approved", "located_url": ""}],
        restrictions=[{"tier": "compiled_record", "currency": "lapsed_unconfirmed", "county_impact": "sole_severe",
                       "located_url": "https://a.gov", "flags": "x"},
                      {"tier": "report_citation", "currency": "in_force", "county_impact": "", "located_url": "",
                       "flags": ""}],
        negative=[{"reason": "check of 2025-01-01 is stale (more than 365 days old)"}, {"reason": "no check on record"}],
        adjacency=[{}], misses=[{"reason": "not_in_lookup"}], trail=TRAIL,
        queue=[{"review_status": "promoted", "entity_type": "restriction"}, {"review_status": "", "entity_type": "case"}],
        candidates=[{"review_status": "promoted"}, {"review_status": "", "court": "Court of X"}, {"review_status": ""}],
        manifest=[{"date": "2026-10-01", "file": "restrictions.csv"}, {"date": "2026-10-13", "file": "restrictions.csv"}],
        history=[{"date": "2026-10-13", "restriction_instruments": "10"}],
        sources=[{"archived_url": "https://web.archive.org/x"}, {"archived_url": ""}])


def test_summary_counts_rows_from_each_trail():
    s = build()
    assert s["headline"]["lapsed_unconfirmed"] == 1 and s["headline"]["severe_where_state_limits_local"] == 2
    assert s["quarantine"] == {"rows": 1, "by_entity": {"restrictions": 1},
                               "by_blocking_code": {"SCOPE_DATA_CENTER_ONLY": 1}}
    w = s["worklists"]
    assert w["outcomes"]["overdue"] == 1 and w["restrictions"]["lapsed"] == 1
    assert w["restrictions"]["by_county_impact"] == {"sole_severe": 1, "none": 1}
    assert w["negative_checks"]["by_reason"] == {"check of 2025-01-01 is stale": 1, "no check on record": 1}
    assert s["promotion_trail"]["by_action"] == {"held": 1, "promoted": 1} and s["promotion_trail"]["recent"][0]["action"] == "promoted"
    assert s["review"] == {"queue_by_status": {"promoted": 1, "pending": 1}, "queue_by_entity": {"restriction": 1, "case": 1},
                           "case_candidates": 3, "case_candidates_started": 1, "case_candidates_promoted": 1}
    assert s["history"]["snapshot_files"] == 1 and s["history"]["latest"] == {"restriction_instruments": "10"}
    assert s["source_archive"] == {"sources": 2, "archived": 1, "archived_share": 0.5}
    json.dumps(s)   # serialisable


def test_render_names_every_section_and_tolerates_missing_inputs():
    text = ops.render(build())
    for heading in ("## Published", "## Held back", "## Worklists", "## Review and promotion", "## History and archive"):
        assert heading in text
    assert "| 2026-10-14 | queue.csv | promoted | KS X |  |" in text
    assert "Decided projects (events older than 90 days): 3, of which 2 blocked" in text
    assert "Sources: 2, of which 1 have an Internet Archive snapshot" in text
    empty = ops.summarize(today="2026-10-14", metrics=None, held=None, outcomes=[], restrictions=[], negative=[],
                          adjacency=[], misses=[], trail=[], queue=[], candidates=[], manifest=[], history=[], sources=[])
    assert empty["headline"] is None and empty["promotion_trail"] is None
    assert "## Published" not in ops.render(empty) and "0 rows quarantined" in ops.render(empty)
