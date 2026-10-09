"""Neighbor watch: unchecked counties next to a recent restriction. Synthetic
rows and a synthetic adjacency map only."""
from datetime import date

import adjacency_worklist as aw

NEIGHBORS = {"00001": ["00002", "00003", "00004"], "00005": ["00006"]}


def r(**kw):
    return {"id": "res_x", "instrument_id": "mn:a", "jurisdiction": "A County", "state": "KS",
            "restriction_type": "moratorium", "status": "active", "technology": "solar",
            "date_enacted_iso": "2026-06-01", "county_fips_all": "00001", **kw}


def run(rows, checks=()):
    return aw.build(rows, list(checks), date(2026, 10, 9), lambda f: NEIGHBORS.get(f, []),
                    lambda f: f"N{f}", lambda f: "KS")


def test_lists_unrestricted_unchecked_neighbors_of_a_recent_instrument():
    rows = [r(), r(id="res_y", technology="wind"),
            r(id="res_z", instrument_id="mn:b", county_fips_all="00002", date_enacted_iso="2019-01-01")]
    checks = [{"county_fips": "00003", "scope": "restrictions"}, {"county_fips": "00004", "scope": "projects"}]
    out = run(rows, checks)
    # 00002 has a restriction, 00003 a check; a projects-only check does not count.
    assert [(x["county_fips"], x["trigger_instrument_id"], x["trigger_technologies"]) for x in out] == [
        ("00004", "mn:a", "solar;wind")]
    assert out[0]["suggested_query"] == '"N00004 County" Kansas moratorium OR ordinance solar OR wind OR "battery storage"'
    assert list(out[0]) == aw.FIELDS


def test_the_window_is_18_months_and_partial_dates_count_to_their_last_day():
    assert run([r(date_enacted_iso="2025-04-09")]) and not run([r(date_enacted_iso="2025-04-08")])
    assert run([r(date_enacted_iso="2025-04")])        # April 2025 may be inside the window
    assert not run([r(date_enacted_iso="")]) and not run([r(date_enacted_iso="2027-01-01")])
    assert aw.months_before(date(2026, 8, 31), 18) == date(2025, 2, 28)
