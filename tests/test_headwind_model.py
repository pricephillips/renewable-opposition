"""Renewable Headwind Model, project part: the history builder and the model."""
import json

import headwind_compare as hc
import headwind_history as hh
import headwind_model as hm
from common import ROOT


def test_history_selftest():
    assert hh._selftest() == 0


def test_model_selftest():
    assert hm._selftest() == 0


def test_registration_matches_the_code():
    reg = json.loads((ROOT / "config" / "headwind_model_registration.json").read_text(encoding="utf-8"))
    assert list(reg["variables"]) == hh.COUNTY_VARS
    assert reg["registered"] == "2026-11-20"
    assert reg["method"]["cv"] == {"folds": hm.FOLDS, "repeats": hm.REPEATS, "seed": hm.SEED}
    # The label added after the first fit is recorded as an amendment, never an edit in place.
    assert any(a["after_first_fit"] and "withdrawn_3y" in a["change"] for a in reg["amendments"])
    assert set(hm.LABELS) == {"withdrawn", "withdrawn_3y"}


def test_nothing_dated_in_the_request_year_enters_its_snapshot():
    rules = hh.rules_by_county([{"severity_score": "4", "date_enacted_iso": "2018-06-01", "date_text": "",
                                 "technology": "solar", "county_fips_all": "01001"}])["01001"]
    assert hh.local_flags(rules, {"solar"}, 2018)["severe_before"] == 0
    assert hh.local_flags(rules, {"solar"}, 2019)["severe_before"] == 1
    assert hh.local_flags(rules, {"wind"}, 2019)["severe_before"] == 0


def test_compare_selftest():
    assert hc._selftest() == 0


def test_holdouts_only_look_forward():
    for label, folds in hc.HOLDOUTS.items():
        assert label in hm.LABELS
        for train_to, (lo, hi) in folds:
            assert train_to < lo <= hi
