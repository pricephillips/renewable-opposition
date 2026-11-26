"""Model improvement program: frozen vintages (scripts/model_vintage.py), the
forward scorecard (scripts/model_scorecard.py) and config/model_program.json."""
import csv
import datetime as dt
import json

import model_scorecard as sc
import model_vintage as mv
from common import ROOT

D = dt.date


def program(**over):
    spec = {
        "name": "Test model", "kind": "county_forward", "registration": "config/reg.json",
        "scores": {"file": "scores.csv", "rank_column": "rank", "chance_column": "fwd", "chance_window_years": 4},
        "band": {"file": "bands.csv", "columns": ["headwind_band"]},
        "frame": {"file": "labels.csv"}, "outcome": {"file": "restrictions.csv"},
        "horizon_months": 12, "backtest": {"as_of": "2025-12-31"},
        "min_sample": 2, "min_positives": 1,
        "stages": [{"stage": "pilot", "auc_min": 0.6, "brier_skill_min": -10, "ece_max": 1, "periods": 1},
                   {"stage": "sellable", "auc_min": 0.6, "brier_skill_min": -10, "ece_max": 1, "periods": 2}],
        "close_after_misses": 2, "stop_rule": {"stage": "pilot", "by": "2027-12-31"},
    }
    spec.update(over)
    return {"version": "t", "models": {"m": spec}}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def setup(tmp_path, with_chance=True, restrictions=None):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "reg.json").write_text("{}")
    (tmp_path / "config" / "model_program.json").write_text("{}")
    scores = [{"county_fips": f, "state": "AL", "county": f, "rank": r, **({"fwd": p} if with_chance else {})}
              for f, r, p in (("01001", "0.9", "0.5"), ("01003", "0.1", "0.1"), ("01005", "0.5", ""))]
    write(tmp_path / "scores.csv", scores)
    write(tmp_path / "labels.csv", [{"county_fips": "01001", "has_severe": "0"},
                                    {"county_fips": "01003", "has_severe": "0"},
                                    {"county_fips": "01005", "has_severe": "1"}])
    write(tmp_path / "bands.csv", [{"county_fips": "01001", "headwind_band": "higher"}])
    write(tmp_path / "restrictions.csv", restrictions or [
        {"severity_score": "4", "date_enacted_iso": "2026-03-01", "date_text": "", "county_fips_all": "01001"}])
    return tmp_path


def test_horizon_chance_turns_a_four_year_chance_into_one_year():
    assert abs(mv.horizon_chance(0.5, 4, 12) - (1 - 0.5 ** 0.25)) < 1e-12
    assert mv.horizon_chance(None, 4, 12) is None
    assert abs(mv.horizon_chance(0.3, 1, 12) - 0.3) < 1e-12


def test_freeze_live_and_backtest_once_and_never_rewrite(tmp_path):
    root = setup(tmp_path)
    new = mv.freeze(program(), root, D(2026, 11, 26))
    assert [(m["kind"], m["vintage_id"]) for m in new] == [("live", "2026-11-26"), ("backtest", "backtest_2025-12-31")]
    vdir = root / "data" / "model" / "vintages"
    live = list(csv.DictReader((vdir / "m" / "2026-11-26.csv").open()))
    # Live: the counties at risk today. Backtest: the counties with a chance score.
    assert [r["county_fips"] for r in live] == ["01001", "01003"]
    assert live[0]["headwind_band"] == "higher" and live[1]["headwind_band"] == ""
    assert [r["county_fips"] for r in csv.DictReader((vdir / "m" / "backtest_2025-12-31.csv").open())] == ["01001", "01003"]
    before = (vdir / "m" / "2026-11-26.csv").read_bytes()
    # Same month again: nothing new, nothing rewritten, even when scores change.
    write(root / "scores.csv", [{"county_fips": "01001", "state": "AL", "county": "x", "rank": "0.2", "fwd": "0.2"}])
    assert mv.freeze(program(), root, D(2026, 11, 30)) == []
    assert (vdir / "m" / "2026-11-26.csv").read_bytes() == before
    # Next month: one live vintage, and no second backtest.
    assert [m["vintage_id"] for m in mv.freeze(program(), root, D(2026, 12, 6))] == ["2026-12-06"]
    assert len(list(csv.DictReader((vdir / "manifest.csv").open()))) == 3


def test_no_backtest_until_the_chance_column_exists(tmp_path):
    root = setup(tmp_path, with_chance=False)
    assert [m["kind"] for m in mv.freeze(program(), root, D(2026, 11, 26))] == ["live"]


def iv(iso="", text=""):
    return sc.enacted_interval({"date_enacted_iso": iso, "date_text": text})


def test_enacted_interval_by_precision():
    assert iv("2026-03-05") == (D(2026, 3, 5), D(2026, 3, 5))
    assert iv("2026-02") == (D(2026, 2, 1), D(2026, 2, 28))
    assert iv("2026") == (D(2026, 1, 1), D(2026, 12, 31))
    assert iv("", "Adopted in 2019") == (D(2019, 1, 1), D(2019, 12, 31))
    assert iv("", "no date") is None


def test_outcome_places_only_what_the_dates_allow():
    s, e = D(2025, 12, 31), D(2026, 12, 31)
    assert sc.outcome([], s, e) == (0, "")
    assert sc.outcome([iv("2026-04-01")], s, e) == (1, "")
    assert sc.outcome([iv("2026")], s, e) == (1, "")
    assert sc.outcome([iv("2027-02-01")], s, e) == (0, "")
    assert sc.outcome([None], s, e) == (None, "undated")
    # Enacted before the vintage but recorded later: the county was never at risk.
    assert sc.outcome([iv("2024-05-01"), iv("2026-04-01")], s, e) == (None, "on_or_before_vintage")
    assert sc.outcome([iv("2025")], D(2025, 6, 30), e) == (None, "straddles_vintage")
    assert sc.outcome([iv("2026")], s, D(2026, 6, 30)) == (None, "straddles_horizon_end")


def test_auc_matches_the_pairwise_definition():
    assert sc.auc([0.9, 0.1, 0.5], [1, 0, 0]) == 1.0
    assert sc.auc([0.5, 0.5], [1, 0]) == 0.5
    assert sc.auc([0.1, 0.9], [1, 0]) == 0.0
    assert sc.auc([0.1], [1]) is None


def card_for(states):
    return {"models": {"m": {"name": "Test model", "stop_rule_reached": False,
                             "stages": {k: {"state": v} for k, v in states.items()}}}}


def test_stage_rule_opens_after_its_periods_and_closes_after_two_misses():
    spec = program()["models"]["m"]

    def chain(*aucs):
        return [{"vintage_id": str(i), "measures": {"n": 5, "positives": 2, "auc": a, "brier_skill": 0, "ece": 0}}
                for i, a in enumerate(aucs)]
    st = sc.stage_states(chain(0.7), spec)
    assert st["pilot"]["state"] == "open" and st["sellable"]["state"] == "closed"
    assert sc.stage_states(chain(0.7, 0.7), spec)["sellable"]["state"] == "open"
    # One miss keeps an open stage open; two in a row close it.
    assert sc.stage_states(chain(0.7, 0.5), spec)["pilot"]["state"] == "open"
    assert sc.stage_states(chain(0.7, 0.5, 0.5), spec)["pilot"]["state"] == "closed"


def test_periods_are_one_horizon_apart_chained_from_the_latest():
    vs = [{"vintage_id": d, "as_of": d} for d in ("2026-12-06", "2027-01-06", "2027-06-06", "2027-12-06", "2028-01-06")]
    assert [v["vintage_id"] for v in sc.periods(vs, 12)] == ["2027-01-06", "2028-01-06"]


def test_scorecard_end_to_end_and_change_detection(tmp_path):
    root = setup(tmp_path)
    mv.freeze(program(), root, D(2025, 12, 31))
    card = sc.build(program(), root, D(2027, 1, 15))
    m = card["models"]["m"]
    live = next(v for v in m["vintages"] if v["kind"] == "live")
    assert live["matured"] and live["measures"]["n"] == 2 and live["measures"]["positives"] == 1
    assert live["measures"]["auc"] == 1.0
    # Only the matured live vintage counts as a period; the backtest never does.
    assert m["periods"] == ["2025-12-31"] and m["stages"]["pilot"]["state"] == "open"
    assert sc.changes(card_for({"pilot": "closed", "sellable": "closed"}), card) == \
        ["Test model: stage pilot closed -> open"]
    assert sc.changes(card, card) == []
    assert "| 2025-12-31 | live |" in sc.report(card, program())


def test_the_real_program_config_is_consistent():
    prog = json.loads((ROOT / "config" / "model_program.json").read_text())
    for name, spec in prog["models"].items():
        header = (ROOT / spec["scores"]["file"]).read_text().split("\n", 1)[0].split(",")
        assert spec["scores"]["rank_column"] in header, name
        assert (ROOT / spec["registration"]).exists()
        stages = spec["stages"]
        # Each stage is stricter than the one before it.
        for a, b in zip(stages, stages[1:]):
            assert b["auc_min"] >= a["auc_min"] and b["brier_skill_min"] >= a["brier_skill_min"]
            assert b["ece_max"] <= a["ece_max"] and b["periods"] >= a["periods"]
    # The pilot band is cut from the score the scorecard ranks.
    import county_record_score
    assert prog["models"]["headwind_county"]["scores"]["rank_column"] == county_record_score.PROFILE_COLUMN
