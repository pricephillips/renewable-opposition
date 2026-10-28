"""New York local law filings extractor (scripts/extractors/ny_dos_local_laws.py),
offline, on a trimmed copy of real search results (tests/fixtures/intake/
ny_dos_local_laws.json): the query in config/sources.yaml, fetched 2026-10-28,
three pages of 100. The fixture keeps the first page's header and 32 of the 300
items, each verbatim except _links (a signed download link of about 1 KB that
the extractor does not read). Items changed in a test to reach a case the real
filings do not show are marked hypothetical."""
import copy
import gzip
import json
import re
from dataclasses import asdict
from pathlib import Path

import classify
import common
import fetch
import parse
import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ID = "ny_dos_local_laws"
FIXTURE = ROOT / "tests" / "fixtures" / "intake" / f"{SOURCE_ID}.json"
SOURCE = {"source_id": SOURCE_ID, "url": "https://locallaws.static-assets.ny.gov/api/search",
          "fetch_date": "2026-10-28T20:45:00+00:00", "content_type": "application/json", "status_code": "200",
          "content_hash": "e" * 64, "local_path": f"data/raw/{SOURCE_ID}/x.json.gz", "error": ""}
DOC_URL = re.compile(r"https://itswebny\.widen\.net/content/[a-z0-9]+/pdf/[0-9a-f]+\.pdf")


@pytest.fixture
def ex():
    mod = parse.load_extractor(SOURCE_ID)
    assert mod is not None
    return mod


def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write(tmp_path: Path, data: dict, name: str = "page.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def leads(ex, path: Path = FIXTURE) -> list[dict]:
    return ex.extract(path, SOURCE)


def by_place(rows) -> dict[str, dict]:
    return {r["municipality"] or r["county"]: r for r in rows}


def item_for(data: dict, name: str, law: str) -> dict:
    return next(i for i in data["items"] if i["metadata"]["fields"]["municipalityName"] == [name]
                and i["metadata"]["fields"]["lawNumber"] == [law])


# ── The fixture and the registry ─────────────────────────────────────────────

def test_the_fixture_is_a_small_real_response():
    data = payload()
    assert data["query_syntax_ok"] is True and data["total_count"] == 3551 and len(data["items"]) == 32
    assert FIXTURE.stat().st_size <= 50_000
    for item in data["items"]:
        assert "_links" not in item and item["external_id"] and item["filename"].endswith(".pdf")
        assert set(item["metadata"]["fields"]) >= {"municipalityType", "municipalityName", "lawNumber", "year",
                                                   "dateFiled", "subject1"}


def test_the_registry_entry_asks_for_what_the_extractor_reads():
    sources = {s["source_id"]: s for s in fetch.load_sources(fetch.CONFIG_PATH)}
    entry = sources[SOURCE_ID]
    assert entry["url"] == SOURCE["url"] and entry["expect"] == "json" and entry.get("compress")
    assert entry["expect_contains"] in FIXTURE.read_text(encoding="utf-8")
    params = entry["params"]
    assert params["query"] == payload()["query"], "the fixture must come from the configured query"
    assert params["sort"] == "-dateFiled" and params["expand"] == "metadata"
    # fetch.with_params sends str(value): a YAML boolean would go out as "False".
    assert params["search_document_text"] == "false"
    (label, url), = fetch.build_requests(entry)
    assert url.startswith(SOURCE["url"] + "?query=cat%3A%28Local+Laws%29+AND+subject1%3A%28solar+OR+")
    assert "search_document_text=false" in url and "limit=100" in url
    intake = [s["source_id"] for s in fetch.active_sources(list(sources.values()), intake=True)]
    assert SOURCE_ID in intake and intake[-1] == "gdelt_renewable_news"
    assert "itswebny.widen.net/content/{external_id}/pdf/{filename}" in entry["parser_hint"]


# ── What is kept ─────────────────────────────────────────────────────────────

def test_kept_and_dropped(ex):
    read = ex.explain(FIXTURE)
    assert len(read) == 32 and sum(keep for _f, keep, _r in read) == 24
    dropped = [(f["name"], f["law"], reason) for f, keep, reason in read if not keep]
    assert dropped == [
        ("PLEASANT VALLEY", "5", "tax, exemption or payment in lieu of taxes (taxtion)"),
        ("MONTICELLO", "1", "no renewable facility technology named in the subject"),
        ("BELFAST", "5", "undoes an earlier law (repealing) and adopts nothing new"),
        ("NEW YORK", "103", "solar-powered devices, not facility siting"),
        ("WARSAW", "5", "small-scale, accessory or residential systems only"),
        ("MARCELLUS", "1", "tax, exemption or payment in lieu of taxes (tax)"),
        ("SCHODACK", "3", "a rezoning of one site, not a rule for where facilities may go"),
        ("LYSANDER", "3", "undoes an earlier law (rescind, terminates) and adopts nothing new"),
    ]
    # Marcellus filed its moratorium and its RPTL 487 opt-in both as law 1 of
    # 2026: the opt-in is dropped, the moratorium kept.
    kept = [(f["name"], f["law"], reason) for f, keep, reason in read if keep]
    assert ("MARCELLUS", "1", "a local law on battery storage") in kept
    # 24 filings, 22 laws: Grand Island and the Village of Florida each filed one law twice.
    assert len(leads(ex)) == 22


@pytest.mark.parametrize("subject, techs, generic", [
    ("BATTERY ENERGY STORAGE SYSTEMS MORATORIUM", ["battery_storage"], False),
    ("IMPOSING A SIX MONTH MORATORIUM OF APPLICATIONS FOR BATTRY BASED ENERGY STORAGE SYSTEMS", ["battery_storage"],
     False),
    ("EXTENDING MORATORIUM ON BATTREY ENERGY STORAGE SYSTEMS", ["battery_storage"], False),
    ("ESTABLISHING A MORATORIUM ON BATTERT ENERGY STORAGE SYSTEMS", ["battery_storage"], False),
    ("MORATORIUM ON ALL ENERGY STORAGE SYSTEMS DEVELOPMENT", ["battery_storage"], False),
    ("IMPOSING A ONE (1) YEAR MORATORIUM ON COMMERCIAL FREE STANDING SOLAR PHOTOVOLTAIC (PV) SYSTEMS", ["solar"],
     False),
    ("TO ESTABLISH A MORATORIUM ON WIND ENERGY DRIVING TOWERS AND TRANSMISSION FACILITIES", ["wind"], False),
    ("ENACTING A MORATORIUM ON WEST ENERGY CONVERSION SYSTEMS AND WIND ENERGY FACILITIES", ["wind"], False),
    ("RENEWABLE ENERGY PROJECT TEMPORARY MORATORIUM LAW", [], True),
    ('ADDING CHAPTER 124 ENTITLED "WINDOWS GUARDS AND FALL PROTECTION"', [], False),
    ("STOP SIGNS ON WINDWARD LANE", [], False),
    ("ARTICLE 19 OF THE NEW YORK STATE URBAN RENEWABLE LAW", [], False),
    ("TOWN OF WINDSOR BUILDING CODE", [], False),
    ("A MORATORIUM ON SELF STORAGE FACILITIES", [], False),
])
def test_technologies_from_the_subject(ex, subject, techs, generic):
    assert ex.technologies(subject) == (techs, generic)


@pytest.mark.parametrize("subject, reason", [
    ("TO AUTHORIZE THE OPTING IN OF REAL PROPERTY TAX EXEMPTION FOR SOLAR OR WIND ENERGY SYSTEMS PER REAL "
     "PROPERTY TAX LAW SECTION 487", "tax, exemption or payment in lieu of taxes (tax)"),
    ('ADDING A NEW ARTICLE ENTITLED "BATTERY STORAGE SYSTEMS PILOT LAW"',
     "tax, exemption or payment in lieu of taxes (pilot)"),
    ("REPEALING LOCAL LAW NO. 2 OF 2025 ENTITLED SOLAR ENERGY MORATORIUM",
     "undoes an earlier law (repealing) and adopts nothing new"),
    ("ACCESSORY SOLAR ENERGY SYSTEMS", "small-scale, accessory or residential systems only"),
    ("RESIDENTIAL SOLAR PANELS", "small-scale, accessory or residential systems only"),
])
def test_drop_reasons(ex, subject, reason):
    assert ex.classify(subject)[:2] == (False, reason)


@pytest.mark.parametrize("subject", [
    # A repeal that adopts something new is kept (Frankfort, DeWitt, Colesville).
    "REPEALING AND REPLACING LOCAL LAW #4 OF 2025 AND ESTABLISHING A NEW SIX MONTH MORATORIUM ON SOLAR ENERGY SYSTEMS",
    "TO REPEAL ARTICLE XXIII ENTITLED MORATORIUM ON BATTERY ENERGY STORAGE SYSTEMS & ENACT NEW ARTICLE XXIII "
    "ENTITLED BATTERY ENERGY STORAGE SYSTEMS",
    'REPEALING AND REPLACING LOCAL LAW NO. 2 OF THE YEAR 2018 WITH A NEW LOCAL LAW ENTITLED "SOLAR ENERGY SYSTEMS"',
    # A size word that also names larger systems, or that does not qualify the technology.
    "AMENDING LOCAL LAW 4 OF 2021 ENTITLED COMMERCIAL AND RESIDENTIAL SOLAR ENERGY SYSTEMS",
    "A MORATORIUM ON EV CHARGING STATIONS NOT FULLY CONTAINED WITHIN RESIDENTIAL STRUTURE AND BATTERY ENERGY SYSTEMS",
])
def test_kept_despite_a_drop_word(ex, subject):
    assert ex.classify(subject)[0] is True


@pytest.mark.parametrize("subject, hints", [
    ("IMPOSING A TWELVE (12) MONTH MORATRIUM ON BATTERY ENERGY STORAGE SYSTEMS (BESS)", ["moratorium"]),
    ("ESTABLISH A TEMPORARY MORTORIUM ON BATTERY ENERGY STORAGE SYSTEMS", ["moratorium"]),
    ("A LOCAL LAW ENTENDING MORATORIUM ON WIND ENERGY CONVERSION SYSTEMS", ["moratorium", "extension"]),
    ("PROHIBITING COMMERCIAL BATTERY ENERGY STORAGE SYSTEMS IN THE TOWN OF FORT ANN", ["prohibition"]),
    ("REGULATING SOLAR ENERGY SYSTEMS", ["regulation"]),
    ("SOLAR ENERGY FACILITIES LAW", []),
])
def test_mechanism_hints(ex, subject, hints):
    assert ex.classify(subject)[2]["hints"] == hints


# ── Placement ────────────────────────────────────────────────────────────────

def test_placement_from_the_census_the_parentheses_and_the_county_itself(ex):
    rows = by_place(leads(ex))
    assert rows["Town of Hope"]["county"] == "Hamilton County"
    assert "placed in Hamilton County by data/census_governments_2024.csv" in rows["Town of Hope"]["reviewer_notes"]
    # The census writes "De Witt town" and "LaGrange town".
    assert rows["Town of Dewitt"]["county"] == "Onondaga County"
    assert rows["Town of La Grange"]["county"] == "Dutchess County"
    # Shared names: the Department of State adds the county.
    assert rows["Town of Clinton"]["county"] == "Clinton County"
    assert rows["Village of Albion"]["county"] == "Orleans County"
    assert "in parentheses (ALBION (ORLEANS COUNTY))" in rows["Village of Albion"]["reviewer_notes"]
    jefferson = rows["Jefferson County"]
    assert (jefferson["county"], jefferson["municipality"], jefferson["jurisdiction_type"]) == \
        ("Jefferson County", "", "County")
    assert "a village can extend into a neighboring county" in rows["Village of Florida"]["reviewer_notes"]
    assert {r["jurisdiction_type"] for r in rows.values()} == {"Town", "Village", "City", "County"}
    assert all(r["state"] == "NY" for r in rows.values())


def test_a_type_the_census_does_not_list_places_no_county(ex):
    # The filing says City of Cleveland; the census lists only a village of Cleveland.
    row = by_place(leads(ex))["City of Cleveland"]
    assert row["county"] == "" and "the census lists no city of Cleveland in New York" in row["reviewer_notes"]


def test_a_shared_name_is_placed_only_by_the_county_the_subject_names(ex, tmp_path):
    # Hypothetical: Clinton without the Department of State's parentheses. The
    # census lists a town of Clinton in Clinton and Dutchess counties.
    data = payload()
    item = item_for(data, "CLINTON (CLINTON COUNTY)", "3")
    data["items"] = [item]
    item["metadata"]["fields"]["municipalityName"] = ["CLINTON"]
    row, = leads(ex, write(tmp_path, data, "plain.json"))
    assert row["county"] == "" and "county left blank: the census lists a town of Clinton in" in row["reviewer_notes"]
    item["metadata"]["fields"]["subject1"] = ["BATTERY ENERGY STORAGE SYSTEMS LAW OF THE TOWN OF CLINTON, "
                                              "DUTCHESS COUNTY"]
    row, = leads(ex, write(tmp_path, data, "named.json"))
    assert row["county"] == "Dutchess County" and "the one the subject names" in row["reviewer_notes"]


def test_a_subject_naming_another_county_than_the_census_places_no_county(ex, tmp_path):
    # Hypothetical: the Town of Hope's subject naming Essex County instead of Hamilton.
    data = payload()
    item = item_for(data, "HOPE", "2")
    data["items"] = [item]
    item["metadata"]["fields"]["subject1"] = ["BATTERY ENERGY STORAGE SYSTEMS MORATORIUM, ESSEX COUNTY"]
    row, = leads(ex, write(tmp_path, data))
    assert row["county"] == "" and row["municipality"] == "Town of Hope"
    assert "the census puts the town of Hope in Hamilton County, but the subject names Essex County" in \
        row["reviewer_notes"]


def test_subject_counties(ex):
    lookup = ex.load_lookup()
    names = ex.county_names()
    named = [names[f] for f in ex.subject_counties("PROHIBITING COMMERCIAL BESS WITHIN THE TOWN OF SALEM WASHINGTON "
                                                   "COUNTY, NEW YORK", lookup)]
    assert named == ["Washington County"]
    named = [names[f] for f in ex.subject_counties("IN THE TOWN OF ELLERY, COUNTY OF CHAUTAUQUA AND STATE OF NEW YORK",
                                                   lookup)]
    assert named == ["Chautauqua County"]
    assert [names[f] for f in ex.subject_counties("THE TOWN OF HOPKINTON, ST. LAWRENCE COUNTY", lookup)] == \
        ["St. Lawrence County"]
    assert ex.subject_counties("A MORATORIUM ON SOLAR ON COUNTY ROUTE 5", lookup) == []


# ── The lead ─────────────────────────────────────────────────────────────────

def test_every_lead_keeps_the_queue_contract(ex):
    rows = leads(ex)
    for r in rows:
        assert set(r) <= set(parse.QUEUE_FIELDS) and not set(r) & set(parse.OWN_FIELDS)
        assert r["entity_type"] == "restriction"
        assert r["technology"] == ";".join(common.technology_tokens(r["technology"]))
        assert r["status"] == "" and r["mechanisms"] == "" and r["severity_score"] == ""
        assert r["adopted_date"] == "" and r["end_date"] == ""
        assert r["access"] == "snippet"
        # The filed copy is the instrument itself.
        assert r["source_kind"] == "official_copy" and r["source_kind"] in classify.INSTRUMENT_KINDS
        assert DOC_URL.fullmatch(r["source_url"]) and r["source_url"] == common.strip_tracking(r["source_url"])
        assert 0 < len(r["evidence_text"]) <= 1000
        assert r["county"] == "" or r["county"].endswith(" County")
        assert r["description"].endswith('".') and "\n" not in r["description"]
        assert r["reviewer_notes"].startswith("NY DOS local law filing: ")
        for k, v in r.items():
            assert "—" not in v and "–" not in v, (k, v)
    assert len({r["source_url"] for r in rows}) == len(rows)


def test_description_evidence_and_notes(ex):
    hope = by_place(leads(ex))["Town of Hope"]
    assert hope["source_url"] == "https://itswebny.widen.net/content/ylqgkzihth/pdf/09021343803feb16.pdf"
    assert hope["evidence_text"] == ("BATTERY ENERGY STORAGE SYSTEMS MORATORIUM 2026 FOR THE TOWN OF HOPE, "
                                     "HAMILTON COUNTY, NY")
    assert hope["description"] == ('Town of Hope local law 2 of 2026, filed with the New York Department of State on '
                                   '2026-10-21: "BATTERY ENERGY STORAGE SYSTEMS MORATORIUM 2026 FOR THE TOWN OF HOPE, '
                                   'HAMILTON COUNTY, NY".')
    assert hope["reviewer_notes"].startswith("NY DOS local law filing: Town of Hope, local law 2 of 2026, filed "
                                             "2026-10-21 (DOS key HOPE20262); source_url is the filed copy of the law")
    assert hope["reviewer_notes"].endswith("mechanism hints: moratorium")
    rows = by_place(leads(ex))
    assert "also names data centers (multi-sector scope)" in rows["Town of Orangetown"]["reviewer_notes"]
    assert "also names electric vehicle charging" in rows["Village of Munsey Park"]["reviewer_notes"]
    assert rows["Village of Lowville"]["technology"] == ""
    assert "technology not named (renewable energy generally)" in rows["Village of Lowville"]["reviewer_notes"]
    assert "also repealing: check what it replaced" in rows["Town of Frankfort"]["reviewer_notes"]
    assert rows["Village of Avoca"]["evidence_text"].startswith("eighteen month moratorium")


def test_a_law_filed_twice_is_one_lead(ex):
    rows = by_place(leads(ex))
    gi = rows["Town of Grand Island"]
    assert gi["evidence_text"] == "CORRECTION: BATTERY ENERGY STORAGE SYSTEM LAW"
    assert 'same law also filed as 09021343803f0e33.pdf (filed 2026-08-17: "BATTERY ENERGY STORAGE SYSTEM LAW")' in \
        gi["reviewer_notes"]
    assert "same law also filed as" in rows["Village of Florida"]["reviewer_notes"]
    assert "same law also filed as" not in rows["Town of Marcellus"]["reviewer_notes"]


# ── A response that changed shape ────────────────────────────────────────────

def test_a_changed_response_raises(ex, tmp_path):
    with pytest.raises(ValueError, match="no items list"):
        leads(ex, write(tmp_path, {"error_message": "bad request"}))
    bad = payload()
    bad["query_syntax_ok"] = False
    with pytest.raises(ValueError, match="refused the query"):
        leads(ex, write(tmp_path, bad))
    with pytest.raises(ValueError, match="matched nothing"):
        leads(ex, write(tmp_path, {**payload(), "items": [], "total_count": 0}))
    renamed = payload()
    for item in renamed["items"]:
        item["metadata"]["fields"]["title"] = item["metadata"]["fields"].pop("subject1")
    with pytest.raises(ValueError, match="no item carries subject1"):
        leads(ex, write(tmp_path, renamed))


def test_gzipped_and_plain_raw_files_read_the_same(ex, tmp_path):
    gz = tmp_path / "abc.json.gz"
    gz.write_bytes(gzip.compress(FIXTURE.read_bytes()))
    assert leads(ex, gz) == leads(ex)


# ── Through parse.py ─────────────────────────────────────────────────────────

def test_round_trip_through_parse_dedupe(ex):
    mod = parse.load_extractor(SOURCE_ID)
    cands = parse.run_extractor(mod, FIXTURE, SOURCE, rel_path=SOURCE["local_path"])
    assert len(cands) == 22 and all(c.review_status == "lead" and c.source_id == SOURCE_ID for c in cands)
    empty = {"restriction": [], "contested_project": [], "case": []}
    kept, dropped = parse.dedupe(list(cands), parse.Known([], empty))
    assert len(kept) == 22 and dropped == []
    parse.assign_queue_ids(kept, set())
    assert len({c.queue_id for c in kept}) == 22
    # Next week the same filings are already queued: nothing new.
    again = parse.run_extractor(mod, FIXTURE, SOURCE)
    kept2, dropped2 = parse.dedupe(again, parse.Known([asdict(c) for c in kept], empty))
    assert kept2 == [] and len(dropped2) == 22
    assert all("same source document as queue row from ny_dos_local_laws" in d for d in dropped2)
    # A filed copy already cited as a restriction's primary source is dropped.
    hope = next(c for c in again if c.municipality == "Town of Hope")
    seeds = {**empty, "restriction": [{"state": "NY", "jurisdiction": "Town of Hope", "pinned_id": "res_1",
                                       "source_url": "https://report.example.org/",
                                       "primary_source_url": hope.source_url}]}
    kept3, dropped3 = parse.dedupe(copy.deepcopy(again), parse.Known([], seeds))
    assert len(kept3) == 21 and "primary_source_url of seed res_1" in dropped3[0]
