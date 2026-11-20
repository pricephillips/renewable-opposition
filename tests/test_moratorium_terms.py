"""Moratorium terms (scripts/moratorium_terms.py) and how the record score reads them."""
import json
from datetime import date

import county_record_score as rs
import moratorium_terms as mt
import record_score_fit
from common import ROOT

T = date(2026, 11, 19)
CFG = json.loads((ROOT / "config" / "county_record_score.json").read_text(encoding="utf-8"))


def test_selftests():
    mt._selftest()
    assert record_score_fit._selftest() == 0


def test_a_ban_is_permanent_and_a_moratorium_is_a_pause():
    assert mt.derive({"restriction_type": "ban", "description": "Utility-scale solar is prohibited."}, T)["term"] \
        == "permanent"
    assert mt.derive({"restriction_type": "ban", "description": "A temporary ban for 12 months."}, T)["term"] \
        == "temporary"
    assert mt.derive({"restriction_type": "moratorium"}, T)["term"] == "temporary"


def test_conditional_extension_wording_is_not_an_extension():
    r = mt.derive({"restriction_type": "moratorium", "date_enacted_iso": "2026-07-02",
                   "description": "Runs to 2027-07-02 unless zoning amendments take effect sooner or it is extended."},
                  T)
    assert r["extensions"] == "0" and r["ends_on"] == "2027-07-02" and r["ends_on_basis"] == "text"


def test_an_as_of_date_is_not_an_extension_date():
    r = mt.derive({"restriction_type": "moratorium", "status": "extended",
                   "description": "Active/extended as of 2026-09-23. Extended on May 12, 2026."}, T)
    assert r["extensions"] == "1" and r["last_extended_on"] == "2026-05-12"


def _inst(**kw):
    return {"severity": 4, "currency": "in_force", "jurisdiction_type": "County", "techs": {"solar"},
            "term": "temporary", "extensions": 0, "months_in_force": 0.0, "drafting": "", **kw}


def test_term_factor_lowers_a_new_pause_and_never_raises_a_score():
    new = rs.instrument_points(_inst(), CFG)
    long = rs.instrument_points(_inst(extensions=2, months_in_force=24), CFG)
    drafting = rs.instrument_points(_inst(drafting="active"), CFG)
    ban = rs.instrument_points(_inst(term="permanent"), CFG)
    unclear = rs.instrument_points(_inst(term="unclear"), CFG)
    assert drafting < new < long <= ban == unclear == 40
    assert rs.instrument_points(_inst(extensions=9, months_in_force=120), CFG) == 40
    assert rs.instrument_points(_inst(severity=2), CFG) == 12      # standards are not pauses


def test_weights_table_lists_the_term_weights():
    factors = {w["factor"] for w in rs.weights(CFG) if w["part"] == "Moratorium terms"}
    assert "Rules being drafted" in factors and "Each extension on record" in factors


def test_a_stated_term_gives_an_approximate_end_date():
    r = mt.derive({"restriction_type": "moratorium", "date_enacted_iso": "2026-09-18",
                   "description": "Ordinance No. 18-01, a one-year moratorium on solar energy systems."}, T)
    assert r["ends_on"] == "2027-09-18" and r["ends_on_basis"] == "term"
    r = mt.derive({"restriction_type": "moratorium", "date_enacted_iso": "2026-01-31",
                   "description": "The board adopted a moratorium for 6 months."}, T)
    assert r["ends_on"] == "2026-07-31" and r["ends_on_basis"] == "term"
    # A month-only start gives a month-only end, read as the end of that month.
    assert mt.derive({"restriction_type": "moratorium", "date_enacted_iso": "2026-09",
                      "description": "A one-year moratorium."}, T)["ends_on"] == "2027-09"
    # No start at all, in the field or the text: no end date.
    assert mt.derive({"restriction_type": "moratorium", "description": "A one-year moratorium."}, T)["ends_on"] == ""


def test_a_pause_whose_own_text_says_it_ended_reads_lapsed():
    import classify
    row = {"restriction_type": "moratorium", "status": "active", "state": "KS", "jurisdiction": "Example County",
           "technology": "solar",
           "description": "In September 2023, the county enacted a 6-month moratorium on solar applications."}
    classify.stamp("restrictions", row, T)
    assert (row["ends_on"], row["currency"]) == ("2024-03", "lapsed_unconfirmed")
    row = {**row, "description": "A moratorium while the county drafts rules. In 2025 the county adopted new "
                                 "regulations, officially ending the moratorium."}
    classify.stamp("restrictions", row, T)
    assert row["drafting"] == "adopted" and row["currency"] == "lapsed_unconfirmed"
    settled = {**row, "status_checked_on": "2026-11-01"}
    classify.stamp("restrictions", settled, T)
    assert settled["currency"] == "in_force"
