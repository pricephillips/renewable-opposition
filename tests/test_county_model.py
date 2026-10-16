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
