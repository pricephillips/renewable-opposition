"""The county sweep's batch picker (scripts/examination_batch.py): worklist
rank, nothing attempted in the last SKIP_DAYS days, no county with a held
draft, numbered into waves."""
from datetime import date

import examination_batch as eb

TODAY = date(2026, 10, 17)


def w(fips, rank, state="NE", drafted_by=""):
    return {"rank": str(rank), "state": state, "county_fips": fips, "county": f"C{fips}",
            "who_decides": "local_government", "census_local_governments": "4",
            "neighbors_with_restrictions": "1", "drafted_by": drafted_by}


def test_rank_order_numbered_into_waves():
    rows = [w("31003", 3), w("31001", 1), w("31005", 2), w("31007", 4), w("31009", 5)]
    batch = eb.pick(rows, [], TODAY, n=5, wave_size=2)
    assert [b["county_fips"] for b in batch] == ["31001", "31005", "31003", "31007", "31009"]
    assert [b["wave"] for b in batch] == ["1", "1", "2", "2", "3"]


def test_recent_attempts_and_held_drafts_are_skipped_and_old_attempts_come_back():
    rows = [w("31001", 1), w("31003", 2), w("31005", 3, drafted_by="agent:county-examiner-1"), w("31007", 4)]
    log = [{"date": "2026-10-01", "county_fips": "31001", "result": "leads"},
           {"date": "2026-07-01", "county_fips": "31003", "result": "not_read"},     # 108 days ago
           {"date": "not a date", "county_fips": "31007", "result": "leads"}]
    batch = eb.pick(rows, log, TODAY, n=5)
    assert [b["county_fips"] for b in batch] == ["31003", "31007"]
    assert batch[0]["last_attempt"] == "2026-07-01" and batch[1]["last_attempt"] == ""
    assert [b["county_fips"] for b in eb.pick(rows, log, date(2026, 12, 15), n=5)] == ["31001", "31003", "31007"]


def test_state_filter_and_count():
    rows = [w("50015", 1, "VT"), w("31001", 2), w("33001", 3, "NH"), w("31003", 4)]
    assert [b["county_fips"] for b in eb.pick(rows, [], TODAY, n=5, states=("vt", "NH"))] == ["50015", "33001"]
    assert len(eb.pick(rows, [], TODAY, n=2)) == 2
    assert eb.pick(rows, [], TODAY, n=0) == []


def test_the_log_header_matches_the_documented_columns():
    with eb.LOG.open(encoding="utf-8") as f:
        assert f.readline().strip().split(",") == eb.LOG_FIELDS
