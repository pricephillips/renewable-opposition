import json

import headline_history as hh
from common import read_csv


def _metrics(n, verified=None, coverage=True):
    ren = {"instruments": n, "severe_instruments": n // 2}
    if verified is not None:
        ren["by_verification"] = {"verified": verified} if verified else {"unverified": n}
    m = {"restrictions": {"by_scope": {"renewables_only": ren, "multi_sector_data_centers": {"instruments": 1}}},
         "contested_projects": {"projects": 5, "confirmed_outcomes": 1}, "cases": {"cases": 2}}
    if coverage:
        m["county_coverage"] = {"with_any_record": 10, "with_neither": 90}
    return m


def test_a_missing_figure_stays_blank_and_a_missing_verified_count_is_zero():
    old = hh.figures(_metrics(390, coverage=False))
    assert old["restrictions"] == "390" and old["verified_restrictions"] == "" and old["counties_with_records"] == ""
    new = hh.figures(_metrics(400, verified=0))
    assert new["verified_restrictions"] == "0" and new["counties_not_examined"] == "90"


def test_rows_change_only_when_the_figures_do():
    a, b = hh.figures(_metrics(1, 0)), hh.figures(_metrics(2, 1))
    rows = hh.add([], "2026-10-01", a)
    assert hh.add(rows, "2026-10-02", a) == rows             # unchanged: no row
    rows = hh.add(rows, "2026-10-02", b)
    assert [r["date"] for r in rows] == ["2026-10-01", "2026-10-02"]
    rows = hh.add(rows, "2026-10-02", hh.figures(_metrics(3, 1)))
    assert [r["restrictions"] for r in rows] == ["1", "3"]     # a day keeps its last build
    rows = hh.add(rows, "2026-10-02", a)
    assert [r["date"] for r in rows] == ["2026-10-01"]         # back to the day before: one row


def test_default_mode_appends_today_and_is_idempotent(tmp_path, monkeypatch):
    metrics = tmp_path / "headline_metrics.json"
    metrics.write_text(json.dumps(_metrics(7, 2)))
    history = tmp_path / "headline_history.csv"
    monkeypatch.setattr(hh, "METRICS", metrics)
    monkeypatch.setattr(hh, "HISTORY", history)
    monkeypatch.setattr(hh, "ROOT", tmp_path)
    assert hh.main([]) == 0
    first = history.read_bytes()
    assert hh.main([]) == 0
    assert history.read_bytes() == first
    assert read_csv(history)[0]["restrictions"] == "7"
