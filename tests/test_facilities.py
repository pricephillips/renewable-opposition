"""Federal plant inventories: reading them, and matching contested projects to them."""
import csv
import io
import zipfile

import pytest

import facility_matches as fm
import fetch_facilities as ff


def plant(**kw):
    base = {"facility_id": "eia:1:operating", "source": "eia860m", "release": "EIA-860M August 2026",
            "plant_id": "1", "eia_plant_id": "1", "name": "Ripley", "operator": "MN8 Energy LLC",
            "state": "MD", "county": "Charles", "county_fips": "24017", "technology": "solar",
            "status": "operating", "status_detail": "(OP) Operating", "capacity_mw": "27.5",
            "year": "2023", "month": "4", "units": "1", "latitude": "38.5", "longitude": "-77.0"}
    base.update(kw)
    base["_core"] = fm.core(base["name"])
    base["_tech"] = fm.techs(base["technology"])
    return base


def project(**kw):
    base = {"id": "con_x", "source_record_id": "REC-1", "state": "MD", "county": "Charles County",
            "project_name": "Ripley Road Solar Project", "technology": "solar", "capacity_mw": "27.5",
            "county_fips_all": "24017", "outcome": "blocked_unverified", "finality_evidence": "outcome_label_only"}
    base.update(kw)
    return base


def by_state(*plants):
    out = {}
    for p in plants:
        out.setdefault(p["state"], []).append(p)
    return out


def test_core_drops_generic_words_and_phase_numbers():
    assert fm.core("Ripley Road Solar Project") == {"ripley", "road"}
    assert fm.core("Bluegrove Wind, LLC") == fm.core("Bluegrove Wind Project II") == {"bluegrove"}
    assert fm.core("Kibby Expansion Wind Power Project") == {"kibby", "expansion"}
    assert fm.core("Duane Arnold Solar I (50 MW)") == {"duane", "arnold"}


def test_capacity_text_in_other_units_gives_no_figure():
    assert fm.capacities("35-40 MW") == [(35.0, 40.0)]
    assert fm.capacities("1.2 GW") == [(1200.0, 1200.0)]
    assert fm.capacities("22 turbines") == [] and fm.capacities("4,700 acres") == []
    assert fm.capacity_agrees("35-40 MW", "42") and not fm.capacity_agrees("35-40 MW", "60")
    # Only a gap of more than three times rules a plant out: the record's
    # figure is sometimes a turbine count typed as megawatts.
    assert fm.capacity_differs("360", "20") and not fm.capacity_differs("84", "150")
    assert not fm.capacity_differs("", "20")


def test_part_of_the_name_needs_county_and_capacity():
    found = fm.candidates(project(), by_state(plant()))
    assert [(p["match"], p["matched_on"]) for p in found] == [("strong", "part of the name and county and capacity")]
    found = fm.candidates(project(capacity_mw=""), by_state(plant()))
    assert found[0]["match"] == "possible"


def test_same_name_in_another_county_is_only_possible():
    found = fm.candidates(project(project_name="Ripley Solar"), by_state(plant(county_fips="24009")))
    assert found[0]["match"] == "possible"
    # No county on the record: the name alone is enough within the state.
    found = fm.candidates(project(project_name="Ripley Solar", county_fips_all=""), by_state(plant()))
    assert found[0]["match"] == "strong"


def test_far_apart_capacities_veto_a_strong_match():
    found = fm.candidates(project(project_name="Ripley Solar", capacity_mw="360"), by_state(plant()))
    assert found[0]["match"] == "possible" and "a different capacity" in found[0]["matched_on"]


def test_technology_and_state_must_agree():
    assert fm.candidates(project(technology="wind"), by_state(plant())) == []
    assert fm.candidates(project(state="VA"), by_state(plant())) == []


def test_two_plants_make_the_match_possible():
    a = plant(name="Beech Ridge Energy", facility_id="eia:1:operating", eia_plant_id="1")
    b = plant(name="Beech Ridge II", facility_id="eia:2:operating", eia_plant_id="2")
    found = fm.candidates(project(project_name="Beech Ridge Wind Farm", capacity_mw=""), by_state(a, b))
    assert {p["match"] for p in found} == {"possible"}
    assert all("one of 2 plants" in p["matched_on"] for p in found)


def test_an_entry_with_no_eia_id_folds_into_the_eia_plant():
    a = plant(name="Osborn Wind", technology="wind", facility_id="eia:9:operating", eia_plant_id="9")
    b = plant(name="Osborn Wind Energy", technology="wind", source="uswtdb", facility_id="uswtdb:MD:abc",
              eia_plant_id="", status="operating")
    found = fm.candidates(project(project_name="Osborn Wind Project", technology="wind", capacity_mw=""),
                          by_state(a, b))
    assert len(found) == 1 and found[0]["match"] == "strong" and len(found[0]["rows"]) == 2


def test_conflicts():
    assert fm.conflict("blocked_unverified", "operating").startswith("outcome blocked_unverified")
    assert fm.conflict("pending", "canceled_or_postponed")
    assert fm.conflict("advanced_confirmed", "canceled_or_postponed")
    assert fm.conflict("blocked_confirmed", "canceled_or_postponed") == ""
    assert fm.conflict("advanced_unverified", "operating") == ""
    assert fm.conflict("pending", "planned") == ""


def test_stamp_publishes_strong_matches_and_never_changes_the_outcome():
    rows = [project(), project(id="con_y", source_record_id="REC-2", project_name="Elsewhere Solar")]
    work = fm.stamp(rows, by_state(plant()))
    assert rows[0]["outcome"] == "blocked_unverified"
    assert rows[0]["facility_match"] == "strong" and rows[0]["facility_status"] == "operating"
    assert rows[0]["facility_conflict"] == "outcome blocked_unverified, but the plant is operating"
    assert rows[0]["facility_latitude"] == 38.5
    assert "plant ID 1 'Ripley'" in rows[0]["facility_note"]
    assert "says nothing about the opposition" in rows[0]["facility_note"]
    assert "facility_match" not in rows[1]
    assert [w["priority"] for w in work] == [1]
    assert work[0]["draft_outcome"] == "advanced_confirmed" and work[0]["draft_evidence_date"] == "2023-04"


def test_stamp_clears_columns_from_an_earlier_run():
    row = project(facility_match="strong", facility_status="operating")
    fm.stamp([row], {})
    assert "facility_match" not in row and "facility_status" not in row


def test_worklist_puts_conflicts_first():
    rows = [project(id="a", source_record_id="A", outcome="advanced_unverified"),
            project(id="b", source_record_id="B", outcome="pending")]
    work = fm.stamp(rows, by_state(plant()))
    assert [w["source_record_id"] for w in work] == ["B", "A"]


# ── Reading the inventories ─────────────────────────────────────────────────

def _eia_workbook(sheets=("Operating", "Planned", "Retired", "Canceled or Postponed")):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    common = ["Entity ID", "Entity Name", "Plant ID", "Plant Name", "Google Map", "Bing Map", "Plant State",
              "County", "Balancing Authority Code", "Sector", "Generator ID", "Unit Code",
              "Nameplate Capacity (MW)", "Net Summer Capacity (MW)", "Net Winter Capacity (MW)", "Technology",
              "Energy Source Code", "Prime Mover Code"]
    extra = {"Operating": ["Operating Month", "Operating Year", "Status", "Latitude", "Longitude"],
             "Planned": ["Planned Operation Month", "Planned Operation Year", "Status", "Latitude", "Longitude"],
             "Retired": ["Operating Month", "Operating Year", "Retirement Month", "Retirement Year",
                         "Latitude", "Longitude"],
             "Canceled or Postponed": ["Latitude", "Longitude"]}
    rows = {
        "Operating": [[1, "Dev", 10, "Sun Farm", "", "", "MD", "Charles", "", "", "G1", "", 20, 0, 0,
                       "Solar Photovoltaic", "SUN", "PV", 4, 2023, "(OP) Operating", 38.5, -77.0],
                      [1, "Dev", 10, "Sun Farm", "", "", "MD", "Charles", "", "", "G2", "", 7.5, 0, 0,
                       "Solar Photovoltaic", "SUN", "PV", 6, 2024, "(OP) Operating", 38.5, -77.0],
                      [2, "Gas Co", 11, "Gas Plant", "", "", "MD", "Charles", "", "", "G1", "", 100, 0, 0,
                       "Natural Gas Fired Combustion Turbine", "NG", "GT", 1, 2000, "(OP) Operating", 38.5, -77.0]],
        "Planned": [[3, "Dev", 12, "Wind Hill", "", "", "MD", "Allegany", "", "", "W1", "", 50, 0, 0,
                     "Onshore Wind Turbine", "WND", "WT", 12, 2026,
                     "(V) Under construction, more than 50 percent complete", 39.6, -78.8]],
        "Retired": [], "Canceled or Postponed": [[4, "Dev", 13, "Gone Wind", "", "", "MD", "Garrett", "", "",
                                                  "W1", "", 80, 0, 0, "Onshore Wind Turbine", "WND", "WT",
                                                  39.5, -79.2]],
    }
    for name in sheets:
        ws = wb.create_sheet(name)
        ws.append([f"Inventory as of August 2026"])
        ws.append([""])
        ws.append(common + extra[name])
        for r in rows[name]:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_read_eia_groups_generators_into_plants():
    release, plants, read = ff.read_eia(_eia_workbook())
    assert release == "EIA-860M August 2026" and read == 5
    by_id = {p["facility_id"]: p for p in plants}
    assert set(by_id) == {"eia:10:operating", "eia:12:under_construction", "eia:13:canceled_or_postponed"}
    sun = by_id["eia:10:operating"]
    assert sun["capacity_mw"] == "27.5" and sun["units"] == 2 and (sun["year"], sun["month"]) == ("2023", "4")
    assert by_id["eia:12:under_construction"]["technology"] == "wind"


def test_the_schema_guard_refuses_a_changed_workbook():
    with pytest.raises(ff.SchemaError):
        ff.read_eia(_eia_workbook(sheets=("Operating", "Planned", "Retired")))
    with pytest.raises(ff.SchemaError):
        ff.read_eia(b"<html>not yet released</html>")


def _zip(name, rows):
    buf = io.BytesIO()
    text = io.StringIO()
    w = csv.DictWriter(text, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text.getvalue())
    return buf.getvalue()


def test_read_uswtdb_groups_turbines_into_projects():
    t = {"case_id": "1", "eia_id": "57979", "t_state": "VT", "t_county": "Orleans County", "t_fips": "50019",
         "p_name": "Kingdom Community", "p_year": "2012", "p_tnum": "21", "p_cap": "63", "t_offshore": "0",
         "xlong": "-72.3", "ylat": "44.8"}
    data = _zip("uswtdb_V9_1_20260928.csv", [t, {**t, "case_id": "2", "xlong": "-72.4"}])
    release, rows, read = ff.read_uswtdb(data)
    assert release == "USWTDB v9.1 (2026-09-28)" and read == 2 and len(rows) == 1
    assert rows[0]["facility_id"] == "uswtdb:VT:57979" and rows[0]["units"] == 2
    assert rows[0]["capacity_mw"] == "63" and rows[0]["county_fips"] == "50019"
    with pytest.raises(ff.SchemaError):
        ff.read_uswtdb(_zip("uswtdb_V9_1_20260928.csv", [{"case_id": "1"}]))


def test_eia_candidates_are_newest_first():
    html = ('<a href="/electricity/data/eia860m/archive/xls/july_generator2026.xlsx">'
            '<a href="/electricity/data/eia860m/xls/december_generator2025.xlsx">'
            '<a href="/electricity/data/eia860m/xls/august_generator2026.xlsx">')
    assert [u.rsplit("/", 1)[1] for u in ff.eia_candidates(html)] == [
        "august_generator2026.xlsx", "july_generator2026.xlsx", "december_generator2025.xlsx"]
