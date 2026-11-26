"""The development scout: FAA turbine filings and OSM construction tags into
candidate projects, sorted against the inventories. Fixtures only; no network."""
import json

import pytest

import development_scout as ds

CFG = ds.load_config()
FAA = CFG["sources"]["faa_oeaaa"]
OSM = CFG["sources"]["osm_overpass"]
HEAD = ("STUDY (ASN),PRIOR ASN,STATUS,DETERMINATION,ENTERED DATE,RECEIVED DATE,LATITUDE,LONGITUDE,"
        "STRUCTURE COUNTY NAME,STRUCTURE STATE,PROPOSAL DESCRIPTION,NOTICE OF,STRUCTURE TYPE,"
        "AGL HEIGHT PROPOSED,\"SPONSOR NAME \"")


def faa_csv(*rows: str) -> bytes:
    return "\n".join([HEAD, *rows, '""', "Data as of 11/21/2026 04:34 AM"]).encode()


def filing(asn, lat, lon, status="Studying", kind="WINDMILL", notice="New Construction",
           received="2025-03-01", sponsor="Prairie Wind LLC", desc="Proposed wind turbines."):
    return f"{asn},,{status},,{received},{received},{lat},{lon},Kiowa,KS,{desc},{notice},{kind},650,{sponsor}"


# Two turbines 1 km apart, a third 30 km away, an existing structure and a crane.
FILE = faa_csv(
    filing("2025-WTE-1-OE", 37.56, -99.25),
    filing("2025-WTE-2-OE", 37.569, -99.25, status="Determined - No Hazard"),
    filing("2025-WTE-3-OE", 37.83, -99.25),
    filing("2025-WTE-4-OE", 37.60, -99.30, notice="Existing"),
    filing("2025-WTE-5-OE", 37.565, -99.251, kind="CRANE$WINDMILL"),
    filing("2023-WTE-9-OE", 37.10, -99.10, received="2023-05-01"),
    filing("2025-WTE-6-OE", 41.0, -71.0, kind="CRANE$WINDMILL", sponsor="Vessel Co"),
)


def test_faa_reader_keeps_new_turbine_filings_and_dates_the_file():
    kept, read, as_of = ds.read_faa(FILE, FAA)
    assert read == 7 and as_of == "11/21/2026 04:34 AM"
    assert {f["asn"] for f in kept} == {"2025-WTE-1-OE", "2025-WTE-2-OE", "2025-WTE-3-OE", "2025-WTE-5-OE",
                                        "2023-WTE-9-OE", "2025-WTE-6-OE"}  # the existing one is dropped
    assert {f["kind"] for f in kept} == {"turbine", "crane"}


def test_faa_reader_refuses_a_changed_layout():
    with pytest.raises(ds.SchemaError):
        ds.read_faa(b"ASN,LAT\n1,2\n", FAA)


def test_turbines_near_each_other_are_one_project_and_a_crane_marks_construction():
    kept, _, _ = ds.read_faa(FILE, FAA)
    sig = {s["signal_id"]: s for s in ds.faa_signals(kept, FAA, "2024-01-01")}
    assert set(sig) == {"faa:2025-WTE-1-OE", "faa:2025-WTE-3-OE", "faa:2025-WTE-6-OE"}  # 2023 is before since
    a = sig["faa:2025-WTE-1-OE"]
    assert (a["structures"], a["cranes"], a["stage"]) == (2, 1, "under_construction")
    assert a["county_fips"] == "20097" and a["sponsor"] == "Prairie Wind LLC"
    assert a["source_url"] == "https://oeaaa.faa.gov/oeaaa/services/case/2025-WTE-1-OE"
    assert sig["faa:2025-WTE-3-OE"]["stage"] == "filed"
    assert sig["faa:2025-WTE-6-OE"]["stage"] == "crane_only"


def test_the_same_inputs_give_the_same_ids():
    kept, _, _ = ds.read_faa(FILE, FAA)
    one = [s["signal_id"] for s in ds.faa_signals(kept, FAA, "2024-01-01")]
    two = [s["signal_id"] for s in ds.faa_signals(list(reversed(kept)), FAA, "2024-01-01")]
    assert sorted(one) == sorted(two)


OVERPASS = {"elements": [
    {"type": "way", "id": 11, "center": {"lat": 37.56, "lon": -99.25},
     "tags": {"construction:power": "plant", "plant:source": "solar", "name": "Kiowa Solar"}},
    {"type": "node", "id": 12, "lat": 37.7, "lon": -99.3,
     "tags": {"power": "proposed", "proposed": "plant", "plant:source": "battery"}},
    {"type": "way", "id": 13, "center": {"lat": 37.7, "lon": -99.3},
     "tags": {"construction:power": "plant", "plant:source": "gas"}},
    {"type": "way", "id": 14, "center": {"lat": 37.7, "lon": -99.3}, "tags": {"power": "plant", "plant:source": "solar"}},
]}


def test_osm_keeps_solar_wind_and_storage_under_construction_or_proposed():
    rows = {r["signal_id"]: r for r in ds.osm_signals(OVERPASS, OSM, "KS")}
    assert set(rows) == {"osm:way/11", "osm:node/12"}
    assert (rows["osm:way/11"]["technology"], rows["osm:way/11"]["stage"]) == ("solar", "under_construction")
    assert (rows["osm:node/12"]["technology"], rows["osm:node/12"]["stage"]) == ("battery_storage", "proposed")
    assert rows["osm:way/11"]["source_url"] == "https://www.openstreetmap.org/way/11"


def test_overpass_query_asks_for_each_selector_in_the_state():
    q = ds.overpass_query(OSM, "KS")
    assert 'area["ISO3166-2"="US-KS"]' in q and q.count("nwr[") == len(OSM["selectors"])


def facility(fid, tech, lat, lon):
    return {"facility_id": fid, "technology": tech, "status": "operating", "latitude": str(lat), "longitude": str(lon)}


def test_sorting_finds_known_plants_then_queue_requests_in_the_county():
    kept, _, _ = ds.read_faa(FILE, FAA)
    signals = ds.faa_signals(kept, FAA, "2024-01-01")
    queue = [{"queue_project_id": "spp:1", "status": "active", "county_fips": "20097", "technology": "wind"}]
    out = ds.assemble({"faa_oeaaa": signals, "osm_overpass": ds.osm_signals(OVERPASS, OSM, "KS")}, [], CFG,
                      [facility("uswtdb:1", "wind", 37.83, -99.26)], queue,
                      [{"signal_id": "osm:way/11", "verdict": "new_development"}])
    by = {s["signal_id"]: s for s in out}
    assert by["faa:2025-WTE-3-OE"]["match_status"] == "known_facility"
    assert by["faa:2025-WTE-3-OE"]["facility_id"] == "uswtdb:1"
    assert by["faa:2025-WTE-1-OE"]["match_status"] == "queue_county"
    assert by["faa:2025-WTE-1-OE"]["queue_project_ids"] == "spp:1"
    assert by["osm:node/12"]["match_status"] == "new" and by["osm:way/11"]["resolution"] == "new_development"
    todo = [w["signal_id"] for w in ds.worklist(out, {"osm:way/11"})]
    # New before queue matches; resolved, known and crane-only candidates are left out.
    assert todo == ["osm:node/12", "faa:2025-WTE-1-OE"]


def test_a_source_that_failed_keeps_its_last_rows():
    prev = [{"signal_id": "osm:way/9", "source": "osm_overpass", "technology": "solar", "stage": "proposed",
             "state": "KS", "county_fips": "20097", "counties_fips": "20097", "latitude": "37.5",
             "longitude": "-99.2", "structures": "", "match_status": "new"}]
    out = ds.assemble({"faa_oeaaa": [], "osm_overpass": None}, prev, CFG, [], [], [])
    assert [s["signal_id"] for s in out] == ["osm:way/9"]


def packet(kind, agent, **kw):
    p = {k: "" for k in ds.PACKET_KEYS}
    p.update({"packet": kind, "queue": "development", "key": "faa:2025-WTE-1-OE", "agent": agent,
              "date": "2026-11-26", "result": "read", "verdict": "new_development", "technology": "wind",
              "stage": "determined", "project_name": "Prairie Wind", "county_fips": "20097",
              "source_url": "https://example.org/permit", "access": "opened", "source_kind": "official",
              "evidence_date": "2025-04", "quote": "a conditional use permit for the Prairie Wind project",
              "note": "County minutes.", "attempts": []})
    p.update(kw)
    return p


DRAFTER = "agent:development-reader-1 (Claude Code, 2026-11-26)"
REVIEWER = "agent:blind-reviewer-1 (Claude Code, 2026-11-26)"


def test_check_refuses_a_reading_without_a_document_or_a_match():
    assert ds.check(packet("draft", DRAFTER)) == []
    assert ds.check(packet("draft", DRAFTER, access="snippet"))
    assert ds.check(packet("draft", DRAFTER, verdict="same_as_queue"))  # no matched_id
    assert ds.check(packet("draft", DRAFTER, county_fips="99999"))
    assert ds.check(packet("draft", DRAFTER, note="a — b"))
    assert ds.check(packet("draft", DRAFTER, result="not_read", attempts=[]))


def test_reconcile_writes_a_row_only_when_both_readings_agree():
    row, differ = ds.reconcile(packet("draft", DRAFTER), packet("review", REVIEWER), "2026-11-26")
    assert differ == [] and row["verdict"] == "new_development" and row["reviewer"] == REVIEWER
    assert set(row) == set(ds.RESOLUTION_FIELDS)
    row, differ = ds.reconcile(packet("draft", DRAFTER), packet("review", REVIEWER, stage="filed"), "2026-11-26")
    assert row is None and differ and "stage" in differ[0]
    row, differ = ds.reconcile(packet("draft", DRAFTER), packet("review", DRAFTER), "2026-11-26")
    assert row is None


def test_the_card_carries_no_reading(tmp_path, monkeypatch):
    sig = tmp_path / "signals.csv"
    sig.write_text(",".join(ds.FIELDS) + "\n" + ",".join(
        {"signal_id": "faa:x", "source": "faa_oeaaa", "resolution": "new_development"}.get(f, "") for f in ds.FIELDS)
        + "\n", encoding="utf-8")
    monkeypatch.setattr(ds, "SIGNALS_PATH", sig)
    monkeypatch.setattr(ds, "QUEUE_PATH", tmp_path / "none.csv")
    monkeypatch.setattr(ds, "FACILITIES_PATH", tmp_path / "none.csv")
    c = ds.card("faa:x")
    assert "resolution" not in c["signal"] and "new_development" not in json.dumps(c["signal"])
    assert set(c["expect"]) == set(ds.PACKET_KEYS)


def test_the_resolutions_file_has_the_columns_reconcile_writes():
    head = ds.RESOLUTIONS_PATH.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head == ds.RESOLUTION_FIELDS


def test_the_batch_skips_candidates_logged_in_the_last_two_weeks(tmp_path, monkeypatch):
    from datetime import date
    wl, log = tmp_path / "wl.csv", tmp_path / "log.csv"
    wl.write_text("rank,signal_id\n" + "".join(f"{i},faa:{i}\n" for i in range(1, 6)), encoding="utf-8")
    log.write_text("date,queue,key,outcome,note\n2026-11-20,development,faa:1,not_read,x\n"
                   "2026-10-01,development,faa:2,not_read,x\n2026-11-20,outcome,faa:3,written,x\n", encoding="utf-8")
    monkeypatch.setattr(ds, "WORKLIST_PATH", wl)
    monkeypatch.setattr(ds, "LOG_PATH", log)
    assert ds.batch(date(2026, 11, 26)) == ["faa:2", "faa:3", "faa:4"]
