"""Standing improvement structure: config/improvement_program.json graded by
scripts/improvement_scorecard.py."""
import csv
import datetime as dt
import json

import improvement_scorecard as isc
from common import ROOT

D = dt.date


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_each_kind_reads_its_file(tmp_path):
    write(tmp_path / "r.csv", [{"sev": "3", "v": "verified", "d": "", "t": "Adopted 2024"},
                               {"sev": "4", "v": "", "d": "", "t": "no date"},
                               {"sev": "1", "v": "verified", "d": "2020", "t": ""}])
    share = {"kind": "csv_share", "file": "r.csv", "denominator": {"sev": ["3", "4"]},
             "numerator": {"sev": ["3", "4"], "v": ["verified"]}}
    assert isc.value_of(share, tmp_path) == 0.5
    dated = dict(share, numerator={"sev": ["3", "4"], "_has_year": ["d", "t"]})
    assert isc.value_of(dated, tmp_path) == 0.5
    assert isc.value_of({"kind": "csv_count", "file": "r.csv", "where": {"v": ["verified"]}}, tmp_path) == 2
    write(tmp_path / "log.csv", [{"f": "01001"}, {"f": "01001"}, {"f": "01003"}, {"f": ""}])
    write(tmp_path / "frame.csv", [{"x": str(i)} for i in range(8)])
    assert isc.value_of({"kind": "csv_distinct_share", "file": "log.csv", "column": "f",
                         "denominator_file": "frame.csv"}, tmp_path) == 0.25
    (tmp_path / "s.json").write_text(json.dumps({"a": {"b": 0.4, "state": "open"}, "tools": [{"outcome": "kept"}, {}],
                                                 "wanted": [{"id": "x"}, {"id": "y"}], "inputs": [{"fills": "x"}]}))
    assert isc.value_of({"kind": "json_value", "file": "s.json", "path": "a.b"}, tmp_path) == 0.4
    assert isc.value_of({"kind": "json_value", "file": "s.json", "path": "a.state", "equals": "open"}, tmp_path) == 1
    assert isc.value_of({"kind": "json_value", "file": "s.json", "path": "tools", "count_field": "outcome"},
                        tmp_path) == 1
    assert isc.value_of({"kind": "json_fills_share", "file": "s.json"}, tmp_path) == 0.5
    assert isc.value_of({"kind": "file_exists", "file": "none.lock"}, tmp_path) == 0
    assert isc.value_of({"kind": "json_value", "file": "none.json", "path": "a"}, tmp_path) is None


def test_grade_against_target_and_pace():
    m = {"target": 1.0, "by": "2027-11-01"}
    first = (D(2026, 11, 1), 0.0)
    assert isc.grade(m, 1.0, first, D(2027, 1, 1)) == "met"
    # Halfway through the year the straight line is at 0.5.
    assert isc.grade(m, 0.55, first, D(2027, 5, 3)) == "on_pace"
    assert isc.grade(m, 0.40, first, D(2027, 5, 3)) == "behind"
    assert isc.grade(m, 0.9, first, D(2027, 11, 2)) == "behind"
    assert isc.grade(m, None, first, D(2027, 1, 1)) == "missing"
    low = {"target": 20, "by": "2027-11-01", "lower_is_better": True}
    assert isc.grade(low, 50, (D(2026, 11, 1), 120), D(2027, 5, 3)) == "on_pace"
    assert isc.grade(low, 100, (D(2026, 11, 1), 120), D(2027, 5, 3)) == "behind"
    mile = {"target": 1, "by": "2027-03-31", "milestone": True}
    assert isc.grade(mile, 0, None, D(2027, 1, 1)) == "on_pace"
    assert isc.grade(mile, 0, None, D(2027, 4, 1)) == "behind"


def test_history_replaces_the_month_and_flags_two_behind_in_a_row(tmp_path):
    (tmp_path / "f.json").write_text(json.dumps({"v": 0.1}))
    prog = {"tracks": {"depth": {"label": "Depth", "measures": [
        {"id": "m1", "goal": "R1", "label": "M", "kind": "json_value", "file": "f.json", "path": "v",
         "target": 1.0, "by": "2027-11-01", "moved_by": "a routine"}]}}}
    card, hist = isc.build(prog, tmp_path, D(2026, 11, 1), [])
    assert [h["status"] for h in hist] == ["on_pace"] and card["needs_action"] == []
    card, hist = isc.build(prog, tmp_path, D(2026, 11, 20), hist)
    assert len(hist) == 1
    card, hist = isc.build(prog, tmp_path, D(2027, 3, 1), hist)
    assert hist[-1]["status"] == "behind" and card["needs_action"] == []
    card, hist = isc.build(prog, tmp_path, D(2027, 4, 1), hist)
    assert len(card["needs_action"]) == 1 and "moved by a routine" in card["needs_action"][0]
    assert "| R1 | M |" in isc.report(card)


def test_the_real_program_reads_every_measure():
    prog = json.loads((ROOT / "config" / "improvement_program.json").read_text())
    ids = [m["id"] for t in prog["tracks"].values() for m in t["measures"]]
    assert len(ids) == len(set(ids))
    assert set(prog["tracks"]) == {"depth", "breadth"}
    for t in prog["tracks"].values():
        for m in t["measures"]:
            dt.date.fromisoformat(m["by"])
            assert m.get("moved_by") and m.get("goal")
            # Every file a measure reads exists today, except outputs a later monthly run writes.
            if m["kind"] not in ("file_exists",) and m["file"] != "data/model/model_scorecard.json":
                assert isc.value_of(m, ROOT) is not None, m["id"]
