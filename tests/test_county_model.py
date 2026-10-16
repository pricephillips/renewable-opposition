"""County restriction model: labels (scripts/county_labels.py) and the registration."""
import json

import county_labels as cl
from common import ROOT


def r(sev="3", iso="", text="", source="Sabin Center", fips="01001"):
    return {"severity_score": sev, "date_enacted_iso": iso, "date_text": text, "source": source,
            "county_fips_all": fips}


def test_year_prefers_the_iso_date_then_the_text():
    assert cl.year_of(r(iso="2023-04-01", text="2019")) == 2023
    assert cl.year_of(r(text="Adopted May 2018, amended 2021")) == 2018
    assert cl.year_of(r(text="Ordinance 12-345")) is None


def test_window_label_frame_and_positives():
    assert cl.window_label([]) == (1, 0, 0)
    assert cl.window_label([r(text="2023")]) == (1, 1, 0)
    assert cl.window_label([r(text="2026")]) == (1, 0, 1)
    assert cl.window_label([r(text="2026"), r(text="2024")]) == (1, 1, 0)
    # A severe restriction before 2022, or one with no year, takes the county out of the frame.
    assert cl.window_label([r(text="2019"), r(text="2024")]) == (0, 0, 0)
    assert cl.window_label([r(text=""), r(text="2024")]) == (0, 0, 0)


def frame(*fips):
    return [{"county_fips": f, "state": "AL", "county": f} for f in fips]


def test_only_severe_rows_count_and_every_touched_county_gets_them():
    rows = cl.label_rows([r(sev="2", text="2023", fips="01001"),
                          r(sev="4", text="2023", fips="01003;01005")], frame("01001", "01003", "01005"))
    got = {x["county_fips"]: (x["has_severe"], x["has_severity_4"], x["new_severe_2022_2025"]) for x in rows}
    assert got == {"01001": (0, 0, 0), "01003": (1, 1, 1), "01005": (1, 1, 1)}


def test_nrel_sensitivity_columns():
    rows = cl.label_rows([r(text="2023", source="NREL U.S. Wind Siting"),
                          r(text="2019", source="Sabin Center", fips="01003"),
                          r(text="2024", source="NREL U.S. Solar Siting", fips="01003")],
                         frame("01001", "01003"))
    a, b = rows
    assert (a["new_severe_2022_2025"], a["positive_rests_on_nrel_year"], a["nrel_new_severe_2022_2025"]) == (1, 1, 1)
    # Sabin's 2019 row takes 01003 out of the all-source frame but not the NREL-only one.
    assert (b["at_risk_2022"], b["nrel_at_risk_2022"], b["nrel_new_severe_2022_2025"]) == (0, 1, 1)


def test_registration_names_the_labels_the_builder_writes():
    reg = json.loads((ROOT / "config" / "county_model_registration.json").read_text(encoding="utf-8"))
    names = [reg["labels"]["primary"]["name"]] + [s["name"] for s in reg["labels"]["secondary"]] \
        + [reg["labels"]["held_back"]["name"]]
    assert set(names) <= set(cl.FIELDS)
    assert reg["calibration_gate"]["ece_max"] == 0.15 and reg["method"]["cv"] == \
        {"folds": 5, "repeats": 5, "stratified": True, "seed": 20261016}


# ── Selection rule and calibration gate ─────────────────────────────────────

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import calibration_gate as cg  # noqa: E402
import county_restriction_model as crm  # noqa: E402


def test_sign_stability_and_which_variable_goes_first():
    assert crm.is_sign_stable([0.2, 0.9]) and crm.is_sign_stable([-0.1, -0.3])
    assert not crm.is_sign_stable([-0.1, 0.3]) and not crm.is_sign_stable([0.0, 0.3]) and not crm.is_sign_stable([])
    folds = {"a": [0.5, 0.6], "b": [-0.2, 0.2], "c": [-0.1, 0.4]}
    # b straddles zero evenly (instability 1.0), c less so (0.25): b goes first.
    assert crm.least_trustworthy(folds) == "b"
    assert crm.least_trustworthy({"a": [0.5, 0.6]}) is None


def test_selection_keeps_signal_and_drops_noise():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(600, 4))
    y = (x[:, 0] - x[:, 1] + rng.normal(scale=0.8, size=600) > 1.0).astype(int)
    sel = crm.select(x, y, ["s1", "s2", "n1", "n2"], ["s1", "s2", "n1", "n2"])
    ch = sel["chosen"]
    assert ch is not None and not sel["stopped"] and ch["sign_stable"]
    assert {"s1", "s2"} <= set(ch["variables"]) and len(ch["variables"]) >= crm.MIN_VARS
    assert np.median(ch["coefs"]["s1"]) > 0 > np.median(ch["coefs"]["s2"])
    assert ch["auc_median"] > 0.8


def test_gate_promotes_calibrated_skill_and_holds_otherwise():
    y = [1] * 30 + [0] * 70
    good = [0.8] * 30 + [0.1] * 70
    assert cg.gate(good, y)["verdict"] == "PROMOTE"
    flat = [0.3] * 100
    held = cg.gate(flat, y)
    assert held["verdict"] == "HOLD" and any("NO_SKILL" in r for r in held["reasons"])
    small = cg.gate([0.9] * 10 + [0.1] * 40, [1] * 10 + [0] * 40)
    assert any("INSUFFICIENT_DATA: n 50" in r for r in small["reasons"])
    assert any("positives 10" in r for r in small["reasons"])
    over = cg.gate([0.95] * 100, y)
    assert any("MISCALIBRATED" in r for r in over["reasons"])


def test_ece_weights_bins_by_size():
    assert cg.ece([0.1, 0.1, 0.9, 0.9], [0, 0, 1, 1]) == pytest.approx(0.1)


def test_exposure_counts_plants_operating_at_the_cut(monkeypatch):
    plants = [
        {"status": "operating", "county_fips": "01001", "year": "2015", "capacity_mw": "10", "technology": "solar"},
        {"status": "operating", "county_fips": "01001", "year": "2023", "capacity_mw": "50", "technology": "solar"},
        # Retired in 2019: closed before the cut. Retired in 2024: running at it.
        {"status": "retired", "county_fips": "01001", "year": "2019", "capacity_mw": "7", "technology": "wind"},
        {"status": "retired", "county_fips": "01001", "year": "2024", "capacity_mw": "3", "technology": "wind"},
        {"status": "planned", "county_fips": "01001", "year": "2020", "capacity_mw": "99", "technology": "wind"},
    ]
    queue = [{"county_fips": "01001", "request_date": "2020-05-01", "solar_mw": "100", "wind_mw": "",
              "storage_mw": "20"},
             {"county_fips": "01001", "request_date": "2023-05-01", "solar_mw": "300", "wind_mw": "", "storage_mw": ""}]
    monkeypatch.setattr(crm, "read_csv", lambda path: plants if path == crm.FACILITIES_PATH else queue)
    assert crm.exposure(2021)["01001"] == {"solar": 10.0, "wind": 3.0, "queue": 120.0}
    assert crm.exposure(None)["01001"] == {"solar": 60.0, "wind": 10.0, "queue": 420.0}
