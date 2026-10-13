import geoid_match as gm

GOV = [
    {"geoid": "3606607", "kind": "place", "state": "NY", "county_fips": "36007", "name": "Binghamton city", "funcstat": "A"},
    {"geoid": "3600706618", "kind": "county_subdivision", "state": "NY", "county_fips": "36007",
     "name": "Binghamton town", "funcstat": "A"},
    {"geoid": "3604660", "kind": "place", "state": "NY", "county_fips": "36101", "name": "Bath village", "funcstat": "A"},
    {"geoid": "3610104550", "kind": "county_subdivision", "state": "NY", "county_fips": "36101",
     "name": "Bath town", "funcstat": "A"},
    {"geoid": "2309515500", "kind": "county_subdivision", "state": "ME", "county_fips": "23029",
     "name": "Cutler town", "funcstat": "A"},
    {"geoid": "4261832", "kind": "place", "state": "PA", "county_fips": "42133", "name": "St. Marys city", "funcstat": "A"},
    {"geoid": "2582000", "kind": "place", "state": "MA", "county_fips": "25027", "name": "Worcester city", "funcstat": "A"},
    {"geoid": "2502782000", "kind": "county_subdivision", "state": "MA", "county_fips": "25027",
     "name": "Worcester city", "funcstat": "A"},
]
IDX = gm.index(GOV)
NY = {"36007": "Broome", "36101": "Steuben"}


def test_split_names_both_ways():
    assert gm.census_split("Binghamton city") == ("binghamton", "city")
    assert gm.census_split("Porter charter township") == ("porter", "township")
    assert gm.record_split("Town of Cutler") == ("cutler", "town", "")
    assert gm.record_split("Binghamton City", "Municipality") == ("binghamton", "city", "")
    assert gm.record_split("Allen (Allegany County)", "Town") == ("allen", "town", "Allegany County")
    assert gm.record_split("West Tisbury", "Municipality") == ("west tisbury", None, "")
    assert gm.norm("St. Marys") == gm.norm("Saint Marys")


def test_city_and_town_of_one_name_get_two_geoids():
    city = gm.match(IDX, "NY", "Municipality", "Binghamton City", {"36007"}, NY, "36")
    town = gm.match(IDX, "NY", "Municipality", "Binghamton Town", {"36007"}, NY, "36")
    assert (city["geoid"], city["kind"], city["method"]) == ("3606607", "place", "name_type_county")
    assert (town["geoid"], town["kind"]) == ("3600706618", "county_subdivision")


def test_refuses_to_guess_between_a_village_and_a_town():
    m = gm.match(IDX, "NY", "Municipality", "Bath", {"36101"}, NY, "36")
    assert m["geoid"] == "" and m["method"] == "ambiguous" and m["candidates"] == 2
    assert gm.match(IDX, "NY", "Village", "Bath", {"36101"}, NY, "36")["geoid"] == "3604660"


def test_a_county_that_disagrees_is_not_matched():
    m = gm.match(IDX, "NY", "Municipality", "Binghamton City", {"36101"}, NY, "36")
    assert m["geoid"] == "" and m["method"] == "county_differs"


def test_unplaced_records_match_on_name_and_type_alone():
    m = gm.match(IDX, "ME", "Municipality", "Town of Cutler", set(), {}, "23")
    assert (m["geoid"], m["method"]) == ("2309515500", "name_type")
    assert gm.match(IDX, "PA", "City", "Saint Marys", set(), {}, "42")["geoid"] == "4261832"


def test_an_independent_city_recorded_twice_is_one_government():
    m = gm.match(IDX, "MA", "Municipality", "Worcester City", {"25027"}, {"25027": "Worcester"}, "25")
    assert (m["geoid"], m["kind"]) == ("2582000", "place")


def test_counties_and_states():
    assert gm.match(IDX, "NY", "County", "Steuben County", {"36101"}, NY, "36")["geoid"] == "36101"
    # A municipality named "<X> County" is the county (README, "Placement").
    assert gm.match(IDX, "NY", "Municipality", "Broome County", set(), NY, "36")["geoid"] == "36007"
    assert gm.match(IDX, "NY", "State", "New York", set(), NY, "36") == \
        {"geoid": "36", "kind": "state", "method": "state", "candidates": 1}
    assert gm.match(IDX, "NY", "Municipality", "Nowhere", set(), NY, "36")["method"] == "no_match"


def test_fallbacks_are_narrow_and_labelled():
    gov = [
        {"geoid": "4059850", "kind": "place", "state": "OK", "county_fips": "40071", "name": "Ponca City city", "funcstat": "A"},
        {"geoid": "4073850", "kind": "place", "state": "OK", "county_fips": "40141", "name": "Tipton town", "funcstat": "A"},
        {"geoid": "4250528", "kind": "place", "state": "PA", "county_fips": "42003", "name": "Monroeville municipality",
         "funcstat": "A"},
        {"geoid": "4206088", "kind": "place", "state": "PA", "county_fips": "42095", "name": "Bethlehem city", "funcstat": "A"},
    ]
    idx = gm.index(gov)
    assert gm.match(idx, "OK", "Municipality", "Ponca City", {"40071"}, {}, "40")["geoid"] == "4059850"
    tipton = gm.match(idx, "OK", "Municipality", "Tipton City", {"40141"}, {}, "40")
    assert (tipton["geoid"], tipton["method"]) == ("4073850", "name_county_other_type")
    # ...but not when the only Tipton is in another county.
    assert gm.match(idx, "OK", "Municipality", "Tipton City", {"40001"}, {}, "40")["geoid"] == ""
    assert gm.match(idx, "PA", "Municipality", "Monroeville Municipality", {"42003"}, {}, "42")["geoid"] == "4250528"
    beth = gm.match(idx, "PA", "Municipality", "Bethlehem City", {"42077"}, {}, "42", {"42077": {"42095"}})
    assert (beth["geoid"], beth["method"]) == ("4206088", "name_type_adjacent_county")
    assert gm.match(idx, "PA", "Municipality", "Bethlehem City", {"42001"}, {}, "42", {"42001": {"42041"}})["method"] == \
        "county_differs"


def test_a_city_named_for_its_kind_beats_another_kind_of_the_short_name():
    # NREL codes "Rogers City" as Rogers City city; Rogers township is the
    # same county's other government.
    idx = gm.index([
        {"geoid": "2614169240", "kind": "county_subdivision", "state": "MI", "county_fips": "26141",
         "name": "Rogers township", "funcstat": "A"},
        {"geoid": "2614169260", "kind": "county_subdivision", "state": "MI", "county_fips": "26141",
         "name": "Rogers City city", "funcstat": "A"},
    ])
    m = gm.match(idx, "MI", "Municipality", "Rogers City", {"26141"}, {}, "26")
    assert (m["geoid"], m["method"]) == ("2614169260", "name_type_county")
