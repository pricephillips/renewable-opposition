"""Placing the last unplaced records (2026-10-06): counties typed as
municipalities, consolidated city-counties, shared town names settled by the
record's own text, and reviewer overrides with evidence."""
import build_sabin_seeds as b
import build_seed_outputs as bso
import classify
import geo
import pytest
import resolutions
from common import STATE_NAMES

LOOKUP = bso.load_fips_lookup()


def place(row, entity="restrictions", places=None):
    return classify.county_fips_all(entity, row, LOOKUP, STATE_NAMES, geo.county_at, places or {})


# ── 1. A county typed as a municipality ──────────────────────────────────────

def test_a_county_typed_as_a_municipality_is_found_but_not_painted():
    row = {"state": "NJ", "jurisdiction": "Atlantic County", "jurisdiction_type": "Municipality"}
    assert place(row) == (["34001"], "name")
    # county_fips is what the map paints, and it follows jurisdiction_type only.
    assert classify.county_fips("restrictions", row, LOOKUP, STATE_NAMES) == ("", "")
    parish = {"state": "LA", "jurisdiction": "Caddo Parish", "jurisdiction_type": "Municipality"}
    assert place(parish) == (["22017"], "name")


def test_a_town_merely_containing_county_is_not_a_county():
    row = {"state": "NJ", "jurisdiction": "County Line Township", "jurisdiction_type": "Municipality"}
    assert place(row) == ([], "")


# ── 2. Consolidated city-counties ────────────────────────────────────────────

def test_honolulu_city_is_the_city_and_county_of_honolulu():
    row = {"state": "HI", "jurisdiction": "Honolulu City", "jurisdiction_type": "Municipality",
           "description": "The Honolulu City Council revised land use regulations for wind power."}
    assert place(row) == (["15003"], "name")
    assert classify.county_fips("restrictions", row, LOOKUP, STATE_NAMES) == ("", "")


def test_every_listed_city_county_is_a_2024_county_of_the_same_name():
    for key, fips in classify.CITY_COUNTIES.items():
        assert geo.known(fips), key
        assert geo.name(fips).lower() == key.split("|")[0], key


def test_a_city_and_county_named_in_the_text_is_placed_when_its_census_place_agrees():
    places = {"carson|NV": ["32510"], "clinton|IA": ["19045"]}
    lookup = {**LOOKUP, "carson county|nevada": "32510"}
    row = {"state": "NV", "jurisdiction": "Carson City", "jurisdiction_type": "Municipality",
           "long_description": "The Board of Supervisors of the City and County of Carson adopted a moratorium."}
    assert classify.county_fips_all("restrictions", row, lookup, STATE_NAMES, None, places) == (["32510"], "name")
    # Same name, but the text never calls it a city and county: an ordinary town.
    town = {"state": "IA", "jurisdiction": "Clinton", "jurisdiction_type": "City",
            "description": "Clinton adopted a solar setback."}
    assert place(town, places=places) == (["19045"], "place")


# ── 3. A shared town name settled by the record's own text ───────────────────

PLACES = {"scandia|MN": ["27119", "27163"], "springfield|WI": ["55025", "55053", "55127"]}


def test_the_text_naming_one_candidate_county_settles_a_shared_town_name():
    row = {"state": "MN", "jurisdiction": "Scandia", "jurisdiction_type": "Municipality",
           "long_description": "In April 2022, the Scandia City Council in Washington County approved a moratorium."}
    assert place(row, places=PLACES) == (["27163"], "place_text")


@pytest.mark.parametrize("text", [
    "The Town of Springfield adopted a solar policy.",                        # no county named
    "Springfield, near Dane County and Walworth County, adopted a policy.",   # two candidates named
    "Springfield copied the Rock County ordinance.",                         # not a candidate
])
def test_a_shared_town_name_stays_ambiguous_unless_the_text_names_exactly_one_candidate(text):
    row = {"state": "WI", "jurisdiction": "Springfield", "jurisdiction_type": "Municipality",
           "long_description": text}
    assert place(row, places=PLACES) == ([], "place_ambiguous")


# ── 4. Reviewer overrides ────────────────────────────────────────────────────

HEADER = "instrument_id,county_fips,evidence_url,evidence_note,reviewer,checked_on\n"


def datasets():
    return {"restrictions": [{"instrument_id": "sabin:REC-0201", "county_fips": None,
                              "county_fips_all": None, "county_fips_method": "place_ambiguous"}] * 1,
            "contested_projects": [{"instrument_id": "sabin:REC-0038", "county_fips": None,
                                    "county_fips_all": None, "county_fips_method": None}]}


def test_an_override_places_every_row_of_its_instrument_last(tmp_path):
    path = tmp_path / "place_overrides.csv"
    path.write_text(HEADER + "sabin:REC-0201,26017,https://example.org/minutes.pdf,Beaver Township Bay County,x,"
                    "2026-10-06\n", encoding="utf-8")
    d = datasets()
    assert resolutions.apply_place_overrides(d, geo.known, path) == []
    row = d["restrictions"][0]
    assert (row["county_fips_all"], row["county_fips_method"], row["county_fips"]) == ("26017", "override", None)


@pytest.mark.parametrize("line,why", [
    ("sabin:REC-0201,26017,,no url,x,", "evidence_url is required"),
    ("sabin:REC-0201,09001,https://example.org/a,old Connecticut county,x,", "is not a 2024 county"),
    ("sabin:REC-0201,26,https://example.org/a,short code,x,", "is not a 2024 county"),
    ("sabin:REC-9999,26017,https://example.org/a,no such record,x,", "no restriction or contested project"),
])
def test_an_override_without_evidence_or_a_2024_county_stops_the_build(tmp_path, line, why):
    path = tmp_path / "place_overrides.csv"
    path.write_text(HEADER + line + "\n", encoding="utf-8")
    errors = resolutions.apply_place_overrides(datasets(), geo.known, path)
    assert len(errors) == 1 and why in errors[0]


def test_the_committed_overrides_all_carry_evidence():
    from common import read_csv
    rows = read_csv(resolutions.PLACE_OVERRIDE_PATH)
    assert list(rows[0].keys()) == resolutions.PLACE_OVERRIDE_FIELDS if rows else True
    for r in rows:
        assert r["evidence_url"].startswith("http") and geo.known(r["county_fips"]), r["instrument_id"]


# ── Connecticut: the town a record names ─────────────────────────────────────

def test_a_connecticut_project_is_placed_by_the_town_its_text_names():
    rec = {"record_id": "REC-0041", "state": "CT", "county": "Hartford", "municipality": "",
           "extraction_source_section": "contested_projects", "project_or_policy_name": "Carter Street Solar",
           "technology": "solar", "status": "pending", "has_litigation": "yes", "opposition_type": "",
           "short_description": "d", "adopted_or_event_date_text": "2024-10", "project_capacity_mw": "",
           "project_area_acres": "", "notes": "",
           "long_description": "The Council rejected a solar facility in Manchester on Carter Street."}
    seed, _, _ = b.build_contested([rec])
    assert seed[0]["municipality"] == "Manchester"
    places = bso.load_place_index()
    assert place(seed[0], "contested_projects", places) == (["09110"], "place")
    with pytest.raises(ValueError, match="not named"):
        b.build_contested([{**rec, "long_description": "A solar facility on Carter Street."}])
