"""Agreed status readings (data/review/status_resolutions.csv) laid over the
published status of a restriction instrument, and what the build does with a
lifted or expired one."""
from datetime import date

import classify
import geo
import pytest
import resolutions

HEAD = "instrument_id,status,end_date,evidence_url,checked_on,reviewer,access,archived_url\n"
URL = "https://furnascounty.ne.gov/zoning.pdf"


def nrel(tech, **kw):
    return {"instrument_id": "nrel:wind:31065", "technology": tech, "state": "NE", "status": "",
            "severity_score": "2", **kw}


def _write(path, lines):
    path.write_text(HEAD + "".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def test_an_active_reading_puts_every_row_of_the_instrument_in_force(tmp_path):
    rows = [nrel("wind"), nrel("solar")]
    assert classify.currency(rows[0]) == "unknown"
    f = _write(tmp_path / "s.csv", [f"nrel:wind:31065,active,,{URL},2026-10-16,a + b,opened,"])
    assert resolutions.apply_status_resolutions(rows, f) == []
    for r in rows:
        assert r["status"] == "active" and r["status_checked_on"] == "2026-10-16"
        assert r["status_evidence_url"] == URL and classify.currency(r) == "in_force"
        assert classify.status_as_of(r) == "2026-10-16"


def test_a_settled_status_confirms_a_moratorium_past_its_old_end_date(tmp_path):
    row = nrel("wind", status="active", current_end_date_iso="2026-03-01")
    today = date(2026, 10, 17)
    assert classify.currency(row, today) == "lapsed_unconfirmed"
    f = _write(tmp_path / "s.csv", [f"nrel:wind:31065,extended,2027-03-01,{URL},2026-10-16,a + b,opened,"])
    assert resolutions.apply_status_resolutions([row], f) == []
    assert row["current_end_date_iso"] == "2027-03-01" and classify.currency(row, today) == "in_force"
    stale = nrel("wind", status="active", current_end_date_iso="2026-03-01")
    g = _write(tmp_path / "t.csv", [f"nrel:wind:31065,active,,{URL},2026-02-01,a + b,opened,"])
    assert resolutions.apply_status_resolutions([stale], g) == []
    assert classify.currency(stale, today) == "lapsed_unconfirmed"     # read before the end date


@pytest.mark.parametrize("line, msg", [
    (f"nrel:wind:99999,active,,{URL},2026-10-16,a + b,opened,", "no restriction"),
    (f"nrel:wind:31065,repealed,,{URL},2026-10-16,a + b,opened,", "status 'repealed'"),
    ("nrel:wind:31065,active,,,2026-10-16,a + b,opened,", "evidence_url"),
    (f"nrel:wind:31065,lifted,,{URL},2026-10-16,a + b,opened,", "needs the end_date"),
    (f"nrel:wind:31065,expired,June 2026,{URL},2026-10-16,a + b,opened,", "YYYY"),
    (f"nrel:wind:31065,active,,{URL},2026-10-16,a + b,snippet,", "never settles"),
    (f"nrel:wind:31065,extended,2027-01,{URL},2026-10-16,a + b,opened,", "full YYYY-MM-DD"),
    (f"nrel:wind:31065,lifted,2026-12-01,{URL},2026-10-16,a + b,opened,", "after the reading"),
    (f"nrel:wind:31065,active,,{URL},2026-10-16,a + b,seen,", "access"),
])
def test_a_bad_status_row_is_an_error_and_changes_nothing(tmp_path, line, msg):
    rows = [nrel("wind")]
    errors = resolutions.apply_status_resolutions(rows, _write(tmp_path / "s.csv", [line]))
    assert len(errors) == 1 and msg in errors[0], errors
    assert rows[0]["status"] == "" and "status_checked_on" not in rows[0]


def test_an_instrument_listed_twice_is_an_error(tmp_path):
    line = f"nrel:wind:31065,active,,{URL},2026-10-16,a + b,opened,"
    errors = resolutions.apply_status_resolutions([nrel("wind")], _write(tmp_path / "s.csv", [line, line]))
    assert len(errors) == 1 and "twice" in errors[0]


def test_a_lifted_instrument_is_withdrawn_and_its_place_override_skipped(tmp_path):
    f = _write(tmp_path / "s.csv", [f"nrel:wind:31065,lifted,2025-11-04,{URL},2026-10-16,a + b,opened,",
                                    f"nrel:wind:1,active,,{URL},2026-10-16,a + b,opened,"])
    assert resolutions.withdrawn_ids(f) == {"nrel:wind:31065"}
    overrides = tmp_path / "o.csv"
    overrides.write_text("instrument_id,county_fips,evidence_url,reviewer,checked_on,access,archived_url\n"
                         f"nrel:wind:31065,31065,{URL},a + b,2026-10-16,opened,\n", encoding="utf-8")
    datasets = {"restrictions": [], "contested_projects": []}
    assert resolutions.apply_place_overrides(datasets, geo.known, overrides, withdrawn={"nrel:wind:31065"}) == []
    assert "no restriction" in resolutions.apply_place_overrides(datasets, geo.known, overrides)[0]
