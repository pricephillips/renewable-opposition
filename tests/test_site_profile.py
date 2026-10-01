"""Site profiles, county placement and the fixes the first three-county run exposed
(Nicholas KY, Linn IA, Cherokee KS, 2026-10-01)."""
import build_place_index
import build_sabin_seeds as b
import classify
import geo
import pytest
import site_profile as sp

LOOKUP = {"fleming county|kentucky": "21069", "mason county|kentucky": "21161",
          "de witt county|illinois": "17039", "baltimore county|maryland": "24005",
          "carroll|maryland": "24013", "frederick|maryland": "24021",
          "clark|nevada": "32003", "nye|nevada": "32023"}
NAMES = {"KY": "Kentucky", "IL": "Illinois", "MD": "Maryland", "NV": "Nevada", "AL": "Alabama"}


# ── geo ──────────────────────────────────────────────────────────────────────

def test_neighbors_cross_state_lines():
    assert geo.neighbors("20021") == ["20037", "20099", "29097", "29145", "40035", "40115"]
    assert "20021" not in geo.neighbors("20021")


def test_point_in_county_and_centroid():
    assert geo.county_at(34.444255, -85.719689) == "01049"   # Fort Payne, AL is in DeKalb
    assert geo.county_at(0.0, 0.0) == ""
    lat, lon = geo.centroid("21181")
    assert 38.2 < lat < 38.5 and -84.2 < lon < -83.9


# ── classify ─────────────────────────────────────────────────────────────────

def test_spacing_insensitive_name_is_still_exact_spelling():
    row = {"state": "IL", "county": "DeWitt County"}
    assert classify.county_fips("contested_projects", row, LOOKUP, NAMES) == ("17039", "")
    row = {"state": "IL", "county": "DeWit County"}
    assert classify.county_fips("contested_projects", row, LOOKUP, NAMES) == ("", "not_in_lookup")


@pytest.mark.parametrize("county,expected", [
    ("Fleming County (Mason County)", ["21069", "21161"]),
    ("Bal>more, Carroll, Frederick", ["24005", "24013", "24021"]),
    ("Various (Clark, Nye)", ["32003", "32023"]),
])
def test_multi_county_names_list_every_county(county, expected):
    st = {"21": "KY", "24": "MD", "32": "NV"}[expected[0][:2]]
    found, method = classify.county_fips_all("contested_projects", {"state": st, "county": county},
                                             LOOKUP, NAMES)
    assert (found, method) == (expected, "names")


def test_town_rows_are_placed_by_point_then_by_unique_place_name():
    town = {"state": "AL", "jurisdiction": "Fort Payne", "jurisdiction_type": "City"}
    assert classify.county_fips_all("restrictions", {**town, "latitude": 34.444255, "longitude": -85.719689},
                                    LOOKUP, NAMES, geo.county_at) == (["01049"], "point")
    places = {"fort payne|AL": ["01049"], "washington|AL": ["01001", "01003"]}
    assert classify.county_fips_all("restrictions", town, LOOKUP, NAMES, geo.county_at, places) == \
        (["01049"], "place")
    twin = {**town, "jurisdiction": "Washington Township"}
    assert classify.county_fips_all("restrictions", twin, LOOKUP, NAMES, geo.county_at, places) == \
        ([], "place_ambiguous")


def test_place_key_strips_census_descriptions_and_prefixes():
    assert classify.place_key("Village of Teutopolis") == "teutopolis"
    assert classify.place_key("Shawnee township") == "shawnee"
    assert classify.place_key("St. Clair charter township") == "st clair"


def test_place_index_build_keeps_every_county_for_a_shared_name():
    cousubs = [{"GEOID": "4200112345", "USPS": "PA", "NAME": "Washington township"},
               {"GEOID": "4212512345", "USPS": "PA", "NAME": "Washington township"}]
    places = [{"USPS": "AL", "NAME": "Fort Payne city", "INTPTLAT": "34.444255", "INTPTLONG": "-85.719689"}]
    assert build_place_index.build(cousubs, places) == {
        "fort payne|AL": ["01049"], "washington|PA": ["42001", "42125"]}


# ── build_sabin_seeds ────────────────────────────────────────────────────────

def test_severity_basis_never_prints_a_zero_multiplier():
    _, basis = b.restriction_severity({"setback", "height_limit"}, "wind", "active", "5,250-foot setback")
    assert basis == "wind setback 5250 ft"
    _, basis = b.restriction_severity({"setback"}, "wind", "active", "13 times the turbine height")
    assert basis == "wind setback 13x height"


def test_restriction_type_is_the_mechanism_that_set_the_severity():
    types = {"setback", "noise_limit", "height_limit"}
    assert b.driving_type(types, "wind setback 5250 ft") == "setback"
    assert b.driving_type(types, "wind height limit") == "height_limit"
    assert b.driving_type({"ban", "setback"}, "ban/prohibition") == "ban"
    assert b.driving_type(types, "restricting mechanism (default)") == "height_limit"


# ── site_profile against the published data ──────────────────────────────────

@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """Build the processed data from the seeds into a temp dir, so these tests
    check the code in this tree rather than whatever was last committed."""
    import build_seed_outputs as bso
    out = tmp_path_factory.mktemp("processed")
    mp = pytest.MonkeyPatch()
    mp.setattr(bso, "PROCESSED_DIR", out)
    mp.setattr(bso, "FIPS_MISSES", out / "fips_misses.csv")
    assert bso.main() == 0
    mp.setattr(sp, "PROCESSED", out)
    d = sp.Data()
    mp.undo()
    return d


def run(d, state, county, **kw):
    fips, name, st = sp.resolve(d, state, county)
    return sp.profile(d, fips, name, st, **kw)


def test_resolve_accepts_common_spellings_and_suggests_on_a_miss(data):
    assert sp.resolve(data, "ky", "Nicholas Co.")[0] == "21181"
    assert sp.resolve(data, "IA", "Linn County")[0] == "19113"
    with pytest.raises(SystemExit, match="Did you mean"):
        sp.resolve(data, "KS", "Cherokey")


def test_cherokee_ks_ordinance_is_a_setback_and_neighbors_cross_into_ok(data):
    p = run(data, "KS", "Cherokee")
    (r,) = p["in_county"]["restrictions"]
    assert r["restriction_type"] == "setback" and r["severity_score"] == "3"
    assert "0x" not in r["severity_basis"]
    assert "40035" in p["adjacent"]      # Craig County, OK: Cabin Creek Wind Farm


def test_linn_ia_shows_the_held_back_moratorium_and_not_linn_ks(data):
    p = run(data, "IA", "Linn")
    held = [r["source_record_id"] for r in p["not_published"]["held_back"]]
    assert "REC-0118" in held
    assert all(r["state"] == "IA" for r in p["in_county"]["restrictions"])
    assert any("KS" in f for f in p["flags"])          # same-name warning
    assert any("No contested projects" in f for f in p["flags"])


def test_nicholas_ky_finds_the_multi_county_flemingsburg_project_next_door(data):
    p = run(data, "KY", "Nicholas")
    names = [r["project_name"] for g in p["adjacent"].values() for r in g["contested_projects"]]
    assert "Flemingsburg Wind Project" in names


def test_render_has_no_em_dashes(data):
    text = sp.render(run(data, "KS", "Cherokee", radius=40))
    assert "—" not in text
