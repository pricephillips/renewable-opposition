"""Model inputs: county covariates (ACS, Gazetteer, MEDSL) and LBNL Queued Up.

Fixtures only; nothing here touches the network."""
import hashlib
import io
import json
import zipfile
from datetime import datetime

import openpyxl
import pytest
import requests

import fetch_county_covariates as fc
import fetch_queued_up as fq
from common import ROOT

LOOKUP = json.loads((ROOT / "data" / "county_fips_lookup.json").read_text(encoding="utf-8"))


# ── County covariates ───────────────────────────────────────────────────────

def acs(header: str, *lines: str) -> bytes:
    return "\n".join([header, *lines]).encode()


def test_acs_reads_county_rows_only_and_blanks_suppressed_values():
    data = acs("GEO_ID|B19013_E001|B19013_M001",
               "0100000US|80734|166",
               "0400000US01|62027|300",
               "0500000US01001|69841|2000",
               "0500000US35011|-666666666|-222222222",
               "1400000US01001020100|55000|9000")
    rows, read = fc.read_acs_table(data, ["B19013_E001"])
    assert read == 5
    assert rows == {"01001": {"B19013_E001": 69841.0}, "35011": {"B19013_E001": None}}


def test_acs_refuses_a_table_without_its_columns():
    with pytest.raises(fc.SchemaError, match="B01003_E001"):
        fc.read_acs_table(acs("GEO_ID|B01003_X001", "0500000US01001|5"), ["B01003_E001"])


def gazetteer(*rows: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2024_Gaz_counties_national.txt",
                    "USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI   \n" + "\n".join(rows))
    return buf.getvalue()


def test_gazetteer_land_area_with_a_padded_header():
    land = fc.read_gazetteer(gazetteer("AL\t01001\t1\tAutauga County\t1\t1\t594.455"))
    assert land == {"01001": 594.455}


def test_demographic_columns_and_density():
    tables = {"b01003": {"01001": {"B01003_E001": 59285.0}},
              "b19013": {"01001": {"B19013_E001": 69841.0}},
              "b15003": {"01001": {"B15003_E001": 1000.0, "B15003_E022": 200.0, "B15003_E023": 60.0,
                                   "B15003_E024": 15.0, "B15003_E025": 5.0}}}
    out = fc.demographic(tables, {"01001": 594.455}, {"01001": {"state": "AL"}, "01003": {"state": "AL"}})
    assert out["01001"] == {"population": 59285, "land_sqmi": 594.455, "pop_density_sqmi": 99.73,
                            "median_hh_income": 69841, "pct_bachelors_plus": 28.0}
    assert out["01003"]["population"] == "" and out["01003"]["pop_density_sqmi"] == ""


def test_demographic_guard_refuses_a_short_or_implausible_file():
    with pytest.raises(fc.SchemaError, match="frame counties"):
        fc.check_demographic({"01001": {"population": 59285}})
    big = {f"{i:05d}": {"population": 1_000_000} for i in range(fc.MIN_FRAME_COUNTIES)}
    with pytest.raises(fc.SchemaError, match="national population"):
        fc.check_demographic(big)


def medsl(*rows: tuple) -> list[dict]:
    keys = ["year", "state_po", "county_fips", "office", "party", "candidatevotes", "totalvotes", "mode"]
    return [dict(zip(keys, map(str, r))) for r in rows]


FRAME = {"01001": {"state": "AL"}, "46102": {"state": "SD"},
         "09110": {"state": "CT"}, "09120": {"state": "CT"}, "48001": {"state": "TX"}}


def test_political_counts_total_mode_folds_renamed_counties_and_falls_back_to_the_state():
    recs = medsl(
        # Autauga: TOTAL rows win over the per-mode rows.
        (2024, "AL", "1001", "US PRESIDENT", "DEMOCRAT", 30, 100, "TOTAL"),
        (2024, "AL", "1001", "US PRESIDENT", "REPUBLICAN", 70, 100, "TOTAL"),
        (2024, "AL", "1001", "US PRESIDENT", "DEMOCRAT", 999, 100, "ELECTION DAY"),
        # Shannon County SD (46113) is now Oglala Lakota (46102).
        (2016, "SD", "46113", "US PRESIDENT", "DEMOCRAT", 80, 100, "TOTAL"),
        (2016, "SD", "46113", "US PRESIDENT", "REPUBLICAN", 20, 100, "TOTAL"),
        # Connecticut reports its retired counties: statewide values.
        (2024, "CT", "9001", "US PRESIDENT", "DEMOCRAT", 60, 100, "TOTAL"),
        (2024, "CT", "9001", "US PRESIDENT", "REPUBLICAN", 40, 100, "TOTAL"),
        (2024, "CT", "9003", "US PRESIDENT", "DEMOCRAT", 40, 100, "TOTAL"),
        (2024, "CT", "9003", "US PRESIDENT", "REPUBLICAN", 60, 100, "TOTAL"),
        # Not a presidential race.
        (2024, "TX", "48001", "US SENATE", "DEMOCRAT", 50, 100, "TOTAL"),
    )
    pol = fc.political(recs, FRAME)
    assert pol["01001"]["dem_share_2p_2024"] == 0.3 and pol["01001"]["margin_dr_2024"] == -0.4
    assert pol["01001"]["geo_basis_2024"] == "county" and pol["01001"]["geo_basis_2016"] == ""
    assert pol["46102"]["dem_share_2p_2016"] == 0.8 and pol["46102"]["geo_basis_2016"] == "county"
    assert pol["09110"]["geo_basis_2024"] == pol["09120"]["geo_basis_2024"] == "state"
    assert pol["09110"]["dem_share_2p_2024"] == 0.5 and pol["09110"]["margin_dr_2024"] == 0.0
    assert pol["48001"]["geo_basis_2024"] == "" and pol["48001"]["margin_dr_2024"] == ""


def test_share_change_needs_both_years():
    recs = medsl((2020, "AL", "1001", "US PRESIDENT", "DEMOCRAT", 40, 100, "TOTAL"),
                 (2020, "AL", "1001", "US PRESIDENT", "REPUBLICAN", 60, 100, "TOTAL"),
                 (2024, "AL", "1001", "US PRESIDENT", "DEMOCRAT", 30, 100, "TOTAL"),
                 (2024, "AL", "1001", "US PRESIDENT", "REPUBLICAN", 70, 100, "TOTAL"))
    row = fc.political(recs, {"01001": {"state": "AL"}})["01001"]
    assert row["dem_share_2p_chg_2020_2024"] == -0.1 and row["dem_share_2p_chg_2016_2020"] == ""


def test_medsl_missing_column_is_refused():
    with pytest.raises(fc.SchemaError, match="mode"):
        fc.read_medsl(b"year,state_po,county_fips,office,party,candidatevotes,totalvotes\n2024,AL,1001,x,y,1,2\n")


def test_a_stale_medsl_copy_fails_with_the_steps_to_replace_it():
    data = b"year,state_po\n"
    meta = {"md5": "0" * 32, "version": "21.0", "license": "CC0 1.0", "file_name": "countypres_2000-2024.csv"}
    with pytest.raises(fc.SchemaError, match="guestbook"):
        fc.check_medsl_copy(data, meta)
    fc.check_medsl_copy(data, {**meta, "md5": hashlib.md5(data).hexdigest()})


def test_every_output_column_is_in_the_catalog_with_leakage_class_none():
    assert set(fc.FIELDS) == set(fc.COLUMNS)


def test_committed_covariates_cover_the_frame():
    rows = fc.read_csv(fc.COVARIATES_PATH)
    assert len(rows) == 3144 and len({r["county_fips"] for r in rows}) == 3144
    assert not any(r["county_fips"].startswith("72") for r in rows)
    assert sum(1 for r in rows if r["population"]) == 3144
    catalog = json.loads(fc.CATALOG_PATH.read_text(encoding="utf-8"))
    assert {c["leakage_class"] for c in catalog["columns"].values()} == {"none"}


# ── Queued Up ───────────────────────────────────────────────────────────────

HEADER = ["q_id", "q_status", "q_date", "prop_date", "on_date", "wd_date", "ia_date", "IA_phase_raw",
          "IA_phase_clean", "county", "state", "fips_code", "poi_name", "region", "project_name", "utility",
          "entity", "developer", "cluster", "service", "project_type", "type_1", "type_2", "type_3",
          "type_clean", "mw_1", "mw_2", "mw_3", "q_year", "prop_year"]


def request(**kw) -> list:
    base = {"q_id": "Q1", "q_status": "withdrawn", "q_date": datetime(2019, 2, 15), "wd_date": datetime(2021, 3, 1),
            "IA_phase_clean": "Withdrawn", "county": "Autauga", "state": "AL", "fips_code": 1001,
            "poi_name": "Sub 69kV", "region": "Southeast (non-ISO)", "utility": "Alabama Power",
            "entity": "Southern", "service": "ERIS", "project_type": "Generation", "type_1": "Solar",
            "type_clean": "Solar", "mw_1": 80}
    base.update(kw)
    return [base.get(c) for c in HEADER]


def workbook(*rows: list, header: list | None = None, sheet: str = "03. Complete Queue Data") -> bytes:
    wb = openpyxl.Workbook()
    wb.active.title = "Contents"
    ws = wb.create_sheet(sheet)
    ws.append(["RETURN TO CONTENTS"])
    ws.append(header or HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build(*rows: list) -> list[dict]:
    out, _ = fq.build(fq.KNOWN_URL, workbook(*rows), "test", LOOKUP)
    return out


def test_keeps_solar_wind_and_storage_and_drops_the_rest():
    rows, manifest = fq.build(fq.KNOWN_URL, workbook(
        request(q_id="A"),
        request(q_id="B", type_1="Gas", type_clean="Gas", mw_1=500),
        request(q_id="C", type_1="Gas", type_2="Battery", type_clean="Gas+Battery", mw_1=300, mw_2=100),
        request(q_id="D", state="MX", fips_code=None),
        request(q_id="E", type_1="Offshore Wind", type_clean="Offshore Wind", mw_1=800, state="NJ",
                county="Cape May", fips_code=34009),
    ), "test", LOOKUP)
    by = {r["q_id"]: r for r in rows}
    assert sorted(by) == ["A", "C", "E"]
    assert by["C"]["technology"] == "battery_storage" and by["C"]["storage_mw"] == "100"
    assert by["C"]["other_mw"] == "300" and by["C"]["capacity_mw"] == "400"
    assert by["E"]["technology"] == "wind" and by["E"]["offshore"] == "yes" and by["E"]["wind_mw"] == "800"
    assert manifest["rows_read"] == 5 and manifest["rows_kept"] == 3
    assert manifest["rows_dropped"] == "no_solar_wind_or_storage 1; outside_the_us_states 1"
    assert manifest["release"] == "Queued Up, data through 2025"


def test_dates_status_and_one_line_text():
    (r,) = build(request(q_status="Operational", on_date=datetime(2023, 6, 30), wd_date=None,
                         project_name="Big\nSky  Solar"))
    assert (r["status"], r["request_date"], r["operational_date"], r["withdrawn_date"]) == \
        ("operational", "2019-02-15", "2023-06-30", "")
    assert r["project_name"] == "Big Sky Solar"


def test_placement_trusts_a_2024_code_in_the_state_and_never_guesses():
    rows = build(
        request(q_id="ok"),
        # The code belongs to another state: the name decides.
        request(q_id="name", county="Baldwin", fips_code=13009),
        # Connecticut's retired counties are not 2024 counties.
        request(q_id="ct", state="CT", county="Hartford", fips_code=9003),
        request(q_id="nostate", state=None, fips_code=None),
        request(q_id="nocounty", county=None, fips_code=None),
        request(q_id="wrong", state="OR", county="Klickitat", fips_code=53039),
    )
    got = {r["q_id"]: (r["county_fips"], r["county_fips_method"], r["county_miss"]) for r in rows}
    assert got == {"ok": ("01001", "source_fips", ""), "name": ("01003", "name", ""),
                   "ct": ("", "", "not_a_2024_county"), "nostate": ("", "", "no_state"),
                   "nocounty": ("", "", "no_county"), "wrong": ("", "", "not_in_lookup")}
    assert {r["q_id"]: r["source_fips"] for r in rows}["ct"] == "09003"


def test_ids_are_unique_when_queue_ids_repeat_or_are_missing():
    rows = build(request(q_id="not assigned", county="Autauga"),
                 request(q_id="not assigned", county="Baldwin", fips_code=1003),
                 request(q_id="Q9"), request(q_id="Q9"))
    ids = [r["queue_project_id"] for r in rows]
    assert len(set(ids)) == 4
    assert all(i.startswith("southern:") for i in ids)
    assert sum(1 for i in ids if "~" in i) == 4


def test_a_changed_layout_is_refused():
    with pytest.raises(fq.SchemaError, match="type_clean"):
        fq.read_workbook(workbook(header=[c for c in HEADER if c != "type_clean"]))
    with pytest.raises(fq.SchemaError, match="Complete Queue Data"):
        fq.read_workbook(workbook(request(), sheet="Queue"))
    with pytest.raises(fq.SchemaError, match="xlsx"):
        fq.read_workbook(b"<html>blocked</html>")


def test_workbook_and_edition_links_newest_first():
    html = ('<a href="https://eta-publications.lbl.gov/sites/default/files/2025-04/lbnl_ix_queue_data_file_thru2024.xlsx">'
            '<a href="https://eta-publications.lbl.gov/sites/default/files/2026-05/lbnl_ix_queue_data_file_thru2025.xlsx">')
    assert [y for y, _ in fq.workbook_links(html)] == [2025, 2024]
    page = '<a href="/publications/queued-2025-edition-x"><a href="/publications/queued-2026-edition-characteristics">'
    assert fq.edition_pages(page) == ["https://emp.lbl.gov/publications/queued-2026-edition-characteristics",
                                      "https://emp.lbl.gov/publications/queued-2025-edition-x"]


class Refused:
    def get(self, url, timeout):
        raise requests.ConnectionError("403")


def test_refused_pages_fall_back_to_the_last_known_url():
    url, how = fq.find_workbook(Refused())
    assert url == fq.last_known_url() and how.startswith("last known URL")


def test_committed_queue_file_has_unique_ids_and_placed_rows():
    rows = fq.read_csv(fq.QUEUE_PATH)
    assert len({r["queue_project_id"] for r in rows}) == len(rows) > 30000
    placed = [r for r in rows if r["county_fips"]]
    assert len(placed) / len(rows) > 0.9
    assert all(not r["county_miss"] for r in placed) and all(r["county_miss"] for r in rows if not r["county_fips"])


# ── Queue matches ───────────────────────────────────────────────────────────

import queue_matches as qm  # noqa: E402


def queued(**kw) -> dict:
    base = {"queue_project_id": "caiso:1", "project_name": "Fountain Wind", "state": "CA",
            "county_fips": "06089", "technology": "wind", "capacity_mw": "216", "status": "active",
            "request_date": "2015-04-30", "ia_date": "", "withdrawn_date": "", "operational_date": ""}
    base.update(kw)
    base["_core"] = qm.fm.core(base["project_name"])
    base["_tech"] = qm.fm.techs(base["technology"])
    return base


def contested(**kw) -> dict:
    base = {"id": "con_1", "source_record_id": "REC-1", "state": "CA", "county": "Shasta",
            "project_name": "Fountain Wind Project", "technology": "wind", "capacity_mw": "216",
            "county_fips_all": "06089", "outcome": "pending", "finality_evidence": "none"}
    base.update(kw)
    return base


def by_state(*reqs):
    out = {}
    for r in reqs:
        out.setdefault(r["state"], []).append(r)
    return out


def test_several_queue_positions_stay_one_strong_match_with_their_date_range():
    (row,) = qm.match_rows([contested()], by_state(
        queued(),
        queued(queue_project_id="caiso:2", project_name="Fountain Wind 2", status="withdrawn",
               request_date="2012-01-10", withdrawn_date="2014-06-01")))
    assert row["match"] == "strong" and row["n_requests"] == 2
    assert row["queue_project_ids"] == "caiso:1;caiso:2"
    assert (row["first_request_date"], row["last_withdrawn_date"]) == ("2012-01-10", "2014-06-01")
    assert row["queue_status"] == "active" and row["conflict"] == ""


def test_other_county_technology_or_size_weakens_or_drops_the_match():
    assert qm.match_rows([contested()], by_state(queued(county_fips="06035")))[0]["match"] == "possible"
    assert qm.match_rows([contested()], by_state(queued(technology="solar"))) == []
    far = qm.match_rows([contested()], by_state(queued(capacity_mw="2000")))[0]
    assert far["match"] == "possible" and "a different capacity" in far["matched_on"]
    assert qm.match_rows([contested()], by_state(queued(state="NV"))) == []


def test_unnamed_requests_are_never_candidates(tmp_path):
    path = tmp_path / "q.csv"
    fields = ["queue_project_id", "project_name", "state", "county_fips", "technology", "capacity_mw"]
    qm.write_csv(path, [{"queue_project_id": "a", "project_name": "", "state": "CA", "county_fips": "06089",
                         "technology": "wind", "capacity_mw": "216"},
                        {"queue_project_id": "b", "project_name": "Solar 1", "state": "CA",
                         "county_fips": "06089", "technology": "solar", "capacity_mw": "5"}], fields)
    assert qm.load(path) == {}


@pytest.mark.parametrize("outcome,status,flag", [
    ("blocked_unverified", "operational", "is operational"),
    ("advanced_confirmed", "withdrawn", "every matched queue request was withdrawn"),
    ("pending", "withdrawn", "every matched queue request was withdrawn"),
    ("needs_review", "operational", "is operational"),
    ("blocked_confirmed", "withdrawn", ""),
    ("advanced_confirmed", "operational", ""),
    ("pending", "active", ""),
])
def test_conflicts_with_the_published_outcome(outcome, status, flag):
    got = qm.conflict(outcome, status)
    assert (flag in got) if flag else got == ""


def test_group_status_prefers_operational_then_still_queued():
    assert qm.group_status([{"status": "withdrawn"}, {"status": "operational"}]) == "operational"
    assert qm.group_status([{"status": "withdrawn"}, {"status": "suspended"}]) == "active"
    assert qm.group_status([{"status": "withdrawn"}]) == "withdrawn"
