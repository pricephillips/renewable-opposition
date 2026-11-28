"""Stage two of the model program: rolling-origin yearly backtests
(scripts/headwind_forward.py)."""
import json

import numpy as np

import headwind_forward as hf
from common import ROOT


def r(sev="3", iso="", text="", fips="01001"):
    return {"severity_score": sev, "date_enacted_iso": iso, "date_text": text, "county_fips_all": fips}


def test_first_severe_takes_the_earliest_dated_and_drops_undated_counties():
    first, undated = hf.first_severe([r(text="2023"), r(text="2019"), r(sev="2", text="2010"),
                                      r(text="2024", fips="01003"), r(text="", fips="01003"),
                                      r(text="2025", fips="01005")])
    assert first == {"01001": 2019, "01005": 2025} and undated == {"01003"}


def test_ceiling_is_one_for_a_perfect_ranking_and_none_without_events():
    y = np.array([0, 0, 0, 1, 1])
    assert hf.ceiling(np.array([0.1, 0.2, 0.3, 0.8, 0.9]), y) == 1.0
    assert hf.ceiling(np.array([0.1, 0.2]), np.array([0, 0])) is None


def synthetic_panel(seed=0):
    rng = np.random.default_rng(seed)
    p = {}
    for t in range(2010, 2026):
        x = rng.normal(size=(400, 3))
        y = (rng.random(400) < 1 / (1 + np.exp(-(-3.5 + 1.5 * x[:, 0])))).astype(int)
        p[t] = {"fips": [str(i) for i in range(400)], "x": x, "y": y, "y4": y}
    return p


def test_run_scores_every_challenger_on_every_test_year_and_applies_the_gate():
    spec = {"stage_two": {"first_train_year": 2010, "test_years": [2023, 2024, 2025], "C": 1.0,
                          "gate": {"brier_skill_min": 0.05, "years_needed": 2,
                                   "auc_reference": "window_annualized", "auc_tolerance": 0.0}}}
    out = hf.run(synthetic_panel(), spec)
    assert set(out["results"]) == {"window_annualized", "yearly", "yearly_recal", "yearly_level", "yearly_recent"}
    for by_year in out["results"].values():
        assert list(by_year) == ["2023", "2024", "2025"]
    # A strong single signal: the yearly model ranks and calibrates well enough to pass.
    assert out["verdicts"]["yearly"]["passes"]
    assert out["chosen"] in {n for n, v in out["verdicts"].items() if v["passes"]}
    strict = dict(spec["stage_two"], gate=dict(spec["stage_two"]["gate"], brier_skill_min=0.99))
    assert hf.run(synthetic_panel(), {"stage_two": strict})["chosen"] is None
    assert "| yearly | 2023 |" in hf.report(out)


def test_the_real_config_names_a_reference_challenger():
    s2 = json.loads((ROOT / "config" / "model_program.json").read_text())["models"]["headwind_county"]["stage_two"]
    assert s2["gate"]["auc_reference"] == "window_annualized"
    assert s2["first_train_year"] < min(s2["test_years"])
