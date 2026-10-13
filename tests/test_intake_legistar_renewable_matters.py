"""The legistar_renewable_matters extractor, offline.

Fixtures are trimmed real responses: tests/fixtures/intake/legistar_<client>_matters.json
holds matters from the Legistar Web API /v1/<client>/matters lists fetched on
2026-10-13 with the filter in config/sources.yaml, each cut to the keys the
extractor reads (MatterId, MatterGuid, MatterFile, MatterName, MatterTitle,
MatterTypeName, MatterStatusName, MatterBodyName, the dates and
MatterRestrictViewViaWeb). Titles are verbatim, dashes and curly quotes included.
"""
import copy
import gzip
import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest

import classify
import common
import fetch
import parse

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "intake"
SOURCE_ID = "legistar_renewable_matters"
CLIENTS = ("sanbernardino", "lakecounty", "baldwincountyal", "dane", "unioncountync", "charlottenc")
EN_DASH, EM_DASH = chr(0x2013), chr(0x2014)


@pytest.fixture(scope="module")
def ex():
    mod = parse.load_extractor(SOURCE_ID)
    assert mod is not None
    return mod


def fixture(client: str) -> Path:
    return FIXTURES / f"legistar_{client}_matters.json"


def manifest_row(client: str, path: Path | None = None) -> dict:
    """A manifest row as fetch.py writes it, for this client's request."""
    src = next(s for s in fetch.load_sources(fetch.CONFIG_PATH) if s["source_id"] == SOURCE_ID)
    url = dict(fetch.build_requests(src)).get(client) or \
        f"https://webapi.legistar.com/v1/{client}/matters?%24top=200"
    return {"source_id": SOURCE_ID, "url": url, "fetch_date": "2026-10-13T00:00:00+00:00",
            "content_type": "application/json; charset=utf-8", "status_code": "200",
            "content_hash": "", "local_path": str(path or fixture(client)), "error": ""}


def leads(ex, client: str, path: Path | None = None, **kw) -> list[dict]:
    return ex.extract(path or fixture(client), manifest_row(client, path), **kw)


def by_id(rows: list[dict]) -> dict[int, dict]:
    return {int(re.search(r"ID=(\d+)", r["source_url"]).group(1)): r for r in rows}


# ── Fixtures and config ─────────────────────────────────────────────────────

def test_fixtures_are_small_valid_real_lists():
    for client in CLIENTS:
        path = fixture(client)
        assert path.stat().st_size <= 40_000, path.name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list) and data
        assert all(m["MatterId"] and m["MatterGuid"] and "MatterTitle" in m for m in data)


def test_every_configured_client_was_verified_and_is_placed_in_a_real_county(ex):
    lookup = json.loads((ROOT / "data" / "county_fips_lookup.json").read_text(encoding="utf-8"))
    clients = ex.load_clients()
    assert set(CLIENTS) <= set(clients)
    for slug, c in clients.items():
        assert re.fullmatch(r"[a-z0-9]+", slug)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["verified_on"]), slug
        assert c["state"] in common.STATE_CODES
        assert c["county"].endswith(" County")
        key = f"{c['county'].lower()}|{common.STATE_NAMES[c['state']].lower()}"
        assert lookup[key] == c["county_fips"], slug


def test_the_client_comes_from_the_manifest_url_fetch_builds(ex):
    src = next(s for s in fetch.load_sources(fetch.CONFIG_PATH) if s["source_id"] == SOURCE_ID)
    reqs = fetch.build_requests(src)
    assert reqs
    for label, url in reqs:
        assert ex.client_from_url(url) == label
        assert "%24filter=substringof" in url and "%24top=200" in url
    with pytest.raises(ValueError):
        ex.client_from_url("https://www.courtlistener.com/api/rest/v4/search/?q=solar")


# ── Relevance and classification ────────────────────────────────────────────

# MatterId -> the entity it becomes, or '' when it is dropped (each decided by hand).
EXPECTED = {
    "sanbernardino": {
        80838: "contested_project",   # Appeal of the Planning Commission Denial of the Bear Valley Solar Project
        80437: "",                    # membership agreement with a solar research consortium
        80013: "contested_project",   # appeal of the decision approving the Sienna Solar Project
        79168: "contested_project",   # zoning amendment and CUP for the named Overnight Solar Facility Project
        78826: "",                    # residential accessory wind energy systems
        72747: "contested_project",   # Lockhart Solar zoning amendment and CUPs
        72440: "",                    # SolarWinds software licence
        72105: "",                    # installation of solar at affordable housing
        71593: "contested_project",   # Resurgence Solar I & II Power Facility Appeal
        69260: "",                    # rescinds the MND for the Joshua Tree Solar Farm, adopts nothing
        67384: "restriction",         # amendment to the Renewable Energy and Conservation Element
        66181: "contested_project",   # EIR and well permits for the Soda Mountain Solar, LLC solar energy project
        66357: "contested_project",   # three appeals, Joshua Tree Solar Farm (two matters, one title)
        66349: "contested_project",
        59619: "",                    # the county's position on a federal plan (DRECP)
        61162: "contested_project",   # appeal of a 44 MW photovoltaic CUP in Daggett
        60590: "contested_project",   # appeal over a 578 kW system at Silver Lakes ("accessory use")
        60865: "contested_project",   # appeal by the Landers Association of a 3 MW CUP
        60668: "contested_project",   # EIR and well permits for the Desert Stateline, LLC solar project
        7063: "restriction",          # ordinance on commercial solar energy generation facilities
        36762: "restriction",         # interim urgency ordinance: temporary moratorium on commercial solar
        59017: "contested_project",   # resolution opposing the Black Lava Butte Wind Project
        58658: "",                    # donated solar powered message board trailer
        55252: "",                    # contract with Desert Stateline for preparing an EIR
        16106: "",                    # closed-session litigation list naming Ivanpah
        14198: "",                    # industrial park for "Solar Atmospheres" (a company)
    },
    "lakecounty": {
        34086: "",                    # CUP for an unnamed commercial solar energy system
        33774: "",                    # permit fee schedule
        33730: "restriction",         # text amendments: commercial solar and wind facilities, energy storage
        33054: "",                    # "Solarge" (a company)
        32829: "",                    # solar group buy
        32545: "",                    # accessory small-scale solar CUP
        32265: "",                    # stormwater guidance
        29402: "",                    # CUP; "RPIL Solar 1, LLC" is the applicant, not a facility name
        28031: "restriction",         # text amendments, sustainable energy facilities
        18701: "",                    # power purchase agreement
        17151: "restriction",         # resolution directing the ZBA to hear solar text amendments
        5167: "restriction",          # model ordinance for solar and geothermal energy systems
        4615: "restriction",          # resolution amending the UDO: wind energy facilities
    },
    "baldwincountyal": {
        29540: "restriction",         # 180-day moratorium on data centers and renewable energy projects
        29064: "", 27870: "",         # solar powered message signs
        28759: "",                    # consultant services for solar permitting review
        26257: "",                    # tax abatement, Foley Solar, LLC
        12021: "restriction", 11997: "restriction",   # zoning ordinance amendment on WECS (two matters)
        12022: "restriction", 11998: "restriction",   # WECS ordinance (two matters)
        11479: "",                    # "Discussion - Apex Wind Energy, Inc."
    },
    "dane": {
        31365: "",                    # donated solar pavilion
        29676: "",                    # CUP, unnamed solar array, no contest shown
        27124: "",                    # lease with Dane County Solar, LLC
        26980: "",                    # agrivoltaics on county land
        20362: "contested_project", 20364: "contested_project",   # comments regarding Koshkonong Solar
        19839: "",                    # informational overview of a potential solar farm
    },
    "unioncountync": {1641: "contested_project", 1572: "contested_project"},
    "charlottenc": {22098: "", 17552: "", 5372: ""},
}


@pytest.mark.parametrize("client", CLIENTS)
def test_relevance_and_classification(ex, client):
    got = {m["MatterId"]: entity for m, entity, _ in ex.explain(fixture(client))}
    assert got == EXPECTED[client]


@pytest.mark.parametrize("matter_id,reason", [
    (80437, "customer"), (72105, "customer"), (55252, "customer"), (78826, "small-scale"),
    (72440, "no renewable facility"), (14198, "no renewable facility"), (58658, "no renewable facility"),
    (69260, "undoes something"), (16106, "closed-session"), (59619, "renewable energy named generally"),
])
def test_drop_reasons(ex, matter_id, reason):
    reasons = {m["MatterId"]: r for m, _, r in ex.explain(fixture("sanbernardino"))}
    assert reason in reasons[matter_id]


def test_a_contest_overrides_customer_and_scale_words(ex):
    rows = by_id(leads(ex, "sanbernardino"))
    # "does not qualify as an accessory use", and the appeal: kept as a contest.
    assert rows[60590]["entity_type"] == "contested_project"
    assert "appellant named: Silver Lakes Association" in rows[60590]["reviewer_notes"]
    # "Zoning Board of Appeals" is a board, not an appeal: the text amendment stays a restriction.
    lake = by_id(leads(ex, "lakecounty"))
    assert lake[17151]["entity_type"] == "restriction"


def test_project_names_come_from_the_title(ex):
    names = {}
    for client in CLIENTS:
        names.update({k: r["project_name"] for k, r in by_id(leads(ex, client)).items()})
    assert names[80838] == "Bear Valley Solar Project"
    assert names[71593] == "Resurgence Solar I & II Power Facility"
    assert names[72747] == "Lockhart Solar"
    assert names[66357] == "Joshua Tree Solar Farm"
    assert names[66181] == "Soda Mountain Solar"         # "the Soda Mountain Solar, LLC solar energy project"
    assert names[60668] == "Desert Stateline"            # "the Desert Stateline, LLC solar project"
    assert names[59017] == "Black Lava Butte Wind Project"
    assert names[20364] == "Koshkonong Solar"
    assert names[1641] == "Blue Star Solar"
    assert names[61162] == ""                            # an unnamed 44 MW facility
    assert all(r["project_name"] == "" for r in leads(ex, "lakecounty"))   # restrictions carry none
    assert ex.facility_name("RPIL Solar 1, LLC, 44 Montgomery Street, is acting as the applicant") == ("", "")
    assert ex.facility_name("PETITION: CUP 02472 CUP DESCRIPTION: SOLAR ARRAY FARM") == ("", "")


def test_technologies(ex):
    tech = {}
    for client in CLIENTS:
        tech.update({k: r["technology"] for k, r in by_id(leads(ex, client)).items()})
    assert tech[33730] == "solar;wind;battery_storage"
    assert tech[28031] == "solar;wind"
    assert tech[4615] == "wind" and tech[59017] == "wind"
    assert tech[29540] == "" and tech[67384] == ""       # "renewable energy" only: left for the reviewer
    notes = by_id(leads(ex, "baldwincountyal"))[29540]["reviewer_notes"]
    assert "technology not named" in notes and "also names data centers" in notes


# ── One document, one lead ──────────────────────────────────────────────────

def test_matters_with_one_title_become_one_lead(ex):
    sb = by_id(leads(ex, "sanbernardino"))
    assert 66357 in sb and 66349 not in sb
    assert "same title as matter HIST-255568 (ID 66349" in sb[66357]["reviewer_notes"]
    union = leads(ex, "unioncountync")
    assert len(union) == 1 and "same title as matter 21-495" in union[0]["reviewer_notes"]
    baldwin = by_id(leads(ex, "baldwincountyal"))
    assert set(baldwin) == {29540, 12021, 12022}       # the regular meeting, not the work session
    dane = leads(ex, "dane")
    assert len(dane) == 1 and dane[0]["project_name"] == "Koshkonong Solar"


def test_each_matter_is_emitted_once_and_restricted_matters_not_at_all(ex, tmp_path):
    data = json.loads(fixture("sanbernardino").read_text(encoding="utf-8"))
    bear = next(m for m in data if m["MatterId"] == 80838)
    hidden = copy.deepcopy(next(m for m in data if m["MatterId"] == 80013))
    hidden["MatterRestrictViewViaWeb"] = True
    path = tmp_path / "dup.json"
    path.write_text(json.dumps([bear, bear, hidden]), encoding="utf-8")
    rows = leads(ex, "sanbernardino", path)
    assert [r["project_name"] for r in rows] == ["Bear Valley Solar Project"]


# ── Placement ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("client,state,county", [
    ("sanbernardino", "CA", "San Bernardino County"), ("lakecounty", "IL", "Lake County"),
    ("baldwincountyal", "AL", "Baldwin County"), ("dane", "WI", "Dane County"),
    ("unioncountync", "NC", "Union County"),
])
def test_a_county_client_places_its_leads_in_its_county(ex, client, state, county):
    rows = leads(ex, client)
    assert rows
    for r in rows:
        assert (r["state"], r["county"], r["municipality"], r["jurisdiction_type"]) == (state, county, "", "County")
        assert "from config/legistar_clients.json (client checked 2026-10-13)" in r["reviewer_notes"]


def test_a_city_client_places_in_its_city_and_county(ex):
    cfg = ex.load_clients()["charlottenc"]
    loc, note = ex.placement("charlottenc", cfg, "Municipal Solar Energy Generating Systems")
    assert loc == {"state": "NC", "county": "Mecklenburg County", "municipality": "Charlotte",
                   "jurisdiction_type": "City"}
    assert "City of Charlotte" in note


def test_a_title_naming_another_county_is_not_placed_in_a_county(ex, tmp_path):
    data = json.loads(fixture("sanbernardino").read_text(encoding="utf-8"))
    # Real title: the closed-session list names the County of Los Angeles.
    closed = next(m for m in data if m["MatterId"] == 16106)
    loc, note = ex.placement("sanbernardino", ex.load_clients()["sanbernardino"], ex.matter_text(closed))
    assert loc["state"] == "CA" and loc["county"] == "" and "Los Angeles County" in note
    # The county's own name, in any form, is not another county.
    assert ex.other_counties("Mojave Desert region of San Bernardino County; County of San Bernardino",
                             "San Bernardino County") == []
    assert ex.other_counties("Unincorporated Baldwin County, Alabama", "Baldwin County") == []
    # An edited copy of a kept matter whose title names Kern County too.
    bear = copy.deepcopy(next(m for m in data if m["MatterId"] == 80838))
    bear["MatterTitle"] += " in Kern County"
    path = tmp_path / "kern.json"
    path.write_text(json.dumps([bear]), encoding="utf-8")
    (row,) = leads(ex, "sanbernardino", path)
    assert row["state"] == "CA" and row["county"] == ""
    assert "names Kern County besides San Bernardino County" in row["reviewer_notes"]


def test_a_client_missing_from_the_config_places_nothing(ex):
    rows = ex.extract(fixture("sanbernardino"),
                      {"url": "https://webapi.legistar.com/v1/sanbernardino/matters?%24top=200"}, clients={})
    assert rows and all((r["state"], r["county"], r["municipality"]) == ("", "", "") for r in rows)
    assert all("not in config/legistar_clients.json" in r["reviewer_notes"] for r in rows)


# ── The queue contract ──────────────────────────────────────────────────────

def all_leads(ex) -> list[dict]:
    return [r for client in CLIENTS for r in leads(ex, client)]


def test_every_lead_keeps_the_queue_contract(ex):
    rows = all_leads(ex)
    assert len(rows) == 25
    url_rx = re.compile(r"https://[a-z0-9]+\.legistar\.com/LegislationDetail\.aspx\?ID=\d+&GUID=[0-9A-Fa-f-]{36}")
    for r in rows:
        assert set(r) <= set(parse.QUEUE_FIELDS)
        assert not set(r) & set(parse.OWN_FIELDS)
        assert r["entity_type"] in ("restriction", "contested_project")
        assert r["technology"] == ";".join(common.technology_tokens(r["technology"]))
        assert set(common.technology_tokens(r["technology"])) <= {"solar", "wind", "battery_storage"}
        assert r["status"] == "" and r["mechanisms"] == "" and r["severity_score"] == ""
        assert r["first_event_date"] == ""
        assert r["access"] == "snippet"
        assert r["source_kind"] == "other" and r["source_kind"] in classify.SOURCE_KINDS
        assert r["source_kind"] not in classify.INSTRUMENT_KINDS + classify.EVENT_KINDS
        assert url_rx.fullmatch(r["source_url"]) and r["source_url"] == common.strip_tracking(r["source_url"])
        assert 0 < len(r["evidence_text"]) <= 1000
        assert r["state"] in common.STATE_CODES
        assert r["county"] == "" or r["county"].endswith(" County")
        assert r["description"].endswith(".") and "\n" not in r["description"]
        assert r["reviewer_notes"].startswith("Legistar ")
        assert r["adopted_date"] == "" or (r["entity_type"] == "restriction"
                                           and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["adopted_date"]))
        for k, v in r.items():
            assert EM_DASH not in v and EN_DASH not in v, (k, v)
            assert not re.search(r"<[a-z/][^>]*>", v, re.I), (k, v)


def test_evidence_is_the_title_with_dashes_replaced(ex):
    lake = by_id(leads(ex, "lakecounty"))
    # MatterName "ZBA #000857-2023 <en dash> Proposed text amendments ..." adds words to the title.
    assert "| ZBA #000857-2023, Proposed text amendments" in lake[28031]["evidence_text"]
    sb = by_id(leads(ex, "sanbernardino"))
    assert sb[80838]["evidence_text"] == "Appeal of the Planning Commission Denial of the Bear Valley Solar Project"
    assert sb[80838]["description"] == ("San Bernardino County legislative matter 14372: Appeal of the Planning "
                                        "Commission Denial of the Bear Valley Solar Project.")
    long = sb[66357]["evidence_text"]
    assert len(long) <= 1000 and long.endswith("...")
    assert sb[80838]["reviewer_notes"].startswith(
        "Legistar sanbernardino matter 14372 (Discussion, Passed, introduced 2026-06-10, passed 2026-06-23)")


def test_adopted_date_only_for_a_passed_adoption(ex):
    lake = by_id(leads(ex, "lakecounty"))
    assert lake[4615]["adopted_date"] == "2011-03-15"    # "Resolution amending the UDO ...", Passed
    assert lake[17151]["adopted_date"] == ""             # passed, but it directs a hearing on proposed amendments
    assert lake[5167]["adopted_date"] == ""              # a model ordinance
    baldwin = by_id(leads(ex, "baldwincountyal"))
    assert baldwin[12022]["adopted_date"] == "2013-08-06"
    assert baldwin[29540]["adopted_date"] == ""          # Agenda Ready, no passed date
    sb = by_id(leads(ex, "sanbernardino"))
    assert sb[7063]["adopted_date"] == ""                # status "Historical" does not say passed
    assert all(r["adopted_date"] == "" for r in sb.values() if r["entity_type"] == "contested_project")


def test_gzipped_raw_and_a_non_list_body(ex, tmp_path):
    gz = tmp_path / "abc.json.gz"
    gz.write_bytes(gzip.compress(fixture("unioncountync").read_bytes()))
    assert leads(ex, "unioncountync", gz) == leads(ex, "unioncountync")
    err = tmp_path / "err.json"
    err.write_text(json.dumps({"Message": "An error has occurred."}), encoding="utf-8")
    assert leads(ex, "unioncountync", err) == []
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert leads(ex, "troup", empty) == []


# ── Through parse.py ────────────────────────────────────────────────────────

def test_round_trip_through_parse_dedupe(ex):
    mod = parse.load_extractor(SOURCE_ID)
    cands = []
    for client in CLIENTS:
        got = parse.run_extractor(mod, fixture(client), manifest_row(client), rel_path=f"data/raw/{SOURCE_ID}/x.json.gz")
        assert got is not None
        cands += got
    assert len(cands) == 25 and all(c.review_status == "lead" and c.source_id == SOURCE_ID for c in cands)
    empty = {"restriction": [], "contested_project": [], "case": []}
    kept, dropped = parse.dedupe(list(cands), parse.Known([], empty))
    assert len(kept) == 25 and dropped == []
    taken: set[str] = set()
    parse.assign_queue_ids(kept, taken)
    assert len({c.queue_id for c in kept}) == 25
    # Next week the same matters are already queued: nothing new.
    again = parse.run_extractor(mod, fixture("sanbernardino"), manifest_row("sanbernardino"))
    kept2, dropped2 = parse.dedupe(again, parse.Known([asdict(c) for c in kept], empty))
    assert kept2 == [] and len(dropped2) == len(again)
    assert all("same source document as queue row from legistar_renewable_matters" in d for d in dropped2)
    # A matter page already cited as a restriction's primary source is dropped.
    one = by_id(leads(ex, "lakecounty"))[4615]["source_url"]
    seeds = {**empty, "restriction": [{"state": "IL", "jurisdiction": "Lake County", "pinned_id": "res_1",
                                       "source_url": "https://report.example.org/",
                                       "primary_source_url": one}]}
    lake = parse.run_extractor(mod, fixture("lakecounty"), manifest_row("lakecounty"))
    kept3, dropped3 = parse.dedupe(lake, parse.Known([], seeds))
    assert len(kept3) == len(lake) - 1 and "primary_source_url of seed res_1" in dropped3[0]
