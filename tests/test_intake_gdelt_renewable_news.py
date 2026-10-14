"""gdelt_renewable_news: the headline geotagger (scripts/news_place.py) and the
extractor (scripts/extractors/gdelt_renewable_news.py), offline, on trimmed
real GDELT DOC 2.0 ArtList responses in tests/fixtures/intake/."""
import gzip
import importlib.util
import json
import re
from pathlib import Path

import build_sabin_seeds
import classify
import common
import news_place
import parse
import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "intake"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
EM, EN = chr(0x2014), chr(0x2013)


def _load_extractor():
    spec = importlib.util.spec_from_file_location(
        "extractors.gdelt_renewable_news", ROOT / "scripts" / "extractors" / "gdelt_renewable_news.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = _load_extractor()


# ── placement ────────────────────────────────────────────────────────────────

def where(text):
    p = news_place.locate(text)
    return p.confidence, p.state, p.county


@pytest.mark.parametrize("text,expected", [
    # A literal county with its state named: high.
    ("Linn County, Iowa supervisors extend solar moratorium", ("high", "IA", "Linn County")),
    ("Iowa's Linn County weighs solar zoning", ("high", "IA", "Linn County")),
    ("St. Clair County, Michigan, adopts wind turbine ordinance", ("high", "MI", "St. Clair County")),
    ("Mower County , Minnesota solar farm draws opposition", ("high", "MN", "Mower County")),
    ("Benton County, Washington approves wind moratorium", ("high", "WA", "Benton County")),
    # Unique nationally, no state named: medium.
    ("Solar farm proposal in Mower County draws opposition", ("medium", "MN", "Mower County")),
    # A town with its state named and one county: high.
    ("Coggon, Iowa residents push back on solar farm", ("high", "IA", "Linn County")),
    # The state alone.
    ("West Virginia county adopts setback for solar farms", ("state_only", "WV", "")),
    ("Eastern Washington residents fight wind farm", ("state_only", "WA", "")),
    ("Ohio River solar farm in Kentucky draws lawsuit", ("state_only", "KY", "")),
])
def test_placed(text, expected):
    assert where(text) == expected


@pytest.mark.parametrize("text,expected", [
    # A county name shared by several states, and no state named: nothing.
    ("Linn County supervisors extend solar moratorium", ("none", "", "")),
    ("Montgomery County residents oppose battery storage facility", ("none", "", "")),
    ("Washington County board denies solar farm rezoning", ("none", "", "")),
    # A bare county name never counts.
    ("Minnesota Power solar project draws residents' concerns", ("state_only", "MN", "")),
    ("Texas lawmakers weigh new limits on wind and solar farms", ("state_only", "TX", "")),
    ("Cedar Rapids council weighs solar setbacks", ("none", "", "")),
    # "Texas County" is a county, not Texas; it is in two states.
    ("Texas County commissioners approve solar ban", ("none", "", "")),
    # "Washington" alone is not the state.
    ("Trump administration halts offshore wind work, Washington says", ("none", "", "")),
    # Several states, nothing pinning one.
    ("Indiana Michigan Power wind project in Indiana faces opposition", ("none", "", "")),
    # A county named that is not in the named state: a contradiction.
    ("Ohio developer's Mower County solar farm draws fire", ("none", "", "")),
    # A town in several counties of the state: the state only.
    ("Fairfield, Iowa council considers solar ban", ("state_only", "IA", "")),
    # Ordinary words that are also places are not towns.
    ("Iowa Prairie Solar fight continues", ("state_only", "IA", "")),
    # Roundups: three counties, or '<A> and <B> counties'.
    ("Madison County, Greene County and Clark County consider solar moratoriums in Ohio",
     ("state_only", "OH", "")),
    ("Linn and Benton counties adopt solar rules in Iowa", ("state_only", "IA", "")),
    # Lower case is not a name.
    ("Residents hand county a petition against wind farm", ("none", "", "")),
    # Seen in GDELT's stream: a storm is not Hurricane, NC; a masthead is not a state.
    ("North Carolina Piedmont could see impacts from Hurricane Isaias: rain, wind", ("state_only", "NC", "")),
    ("US solar producers near breakthrough, The Arkansas Democrat-Gazette reports", ("none", "", "")),
    ("Wind advisory in place for Los Angeles County", ("medium", "CA", "Los Angeles County")),
])
def test_refused(text, expected):
    assert where(text) == expected


def test_place_reports_its_reason_fips_and_town():
    p = news_place.locate("Town of Coggon in Iowa weighs solar ordinance")
    assert (p.county_fips, p.municipality) == ("19113", "Coggon")
    assert "one county" in p.reason
    assert "4 states" in news_place.locate("Linn County board meets on solar").reason
    assert news_place.locate("Lake Michigan offshore wind plan draws opponents").state == ""


def test_named_states_masks_and_guards():
    assert news_place.named_states("West Virginia and Virginia regulators") == ["WV", "VA"]
    assert news_place.named_states("Kansas City and Texas Roadhouse") == []
    assert news_place.named_states("Washington state siting council") == ["WA"]
    assert news_place.named_states("Washington, D.C. lawmakers") == []


# ── headline judgements ──────────────────────────────────────────────────────

@pytest.mark.parametrize("title,techs", [
    ("Neighbors oppose solar - farm near Coggon", ["solar"]),
    ("County weighs wind and solar setbacks", ["solar", "wind"]),
    ("Residents fight battery energy storage system", ["battery_storage"]),
    ("Opponents pack hearing on BESS proposal", ["battery_storage"]),
    ("Offshore wind lawsuit filed by residents", ["wind"]),
    ("Residents protest as solar eclipse draws crowds", []),
    ("Solar flare warning; residents urged to prepare", []),
    ("Wind advisory: residents brace for gusts", []),
    ("HOA bans rooftop solar panels, residents object", []),
    ("Battery plant opponents rally against EV factory", []),
    ("Residents oppose battery storage facility near school", ["battery_storage"]),
    ("Opponents fight battery facility at gigafactory site", []),
    ("Solar Lamp Theft from Bank Raises Security Concerns", []),
    ("South El Monte Puts 45 Day Moratorium on Data Center and Battery Facility Development",
     ["battery_storage"]),
])
def test_technology_in_the_headline(title, techs):
    assert g.technologies(g.tidy(title)) == techs


def test_mechanism_hints_have_their_own_boundaries():
    # data-center-map's pattern read 'issued' as 'sued' and 'appealing' anywhere.
    assert g.hints("County issued permits for solar farm") == []
    assert g.hints("Neighbors sued over wind farm; appeal filed") == ["lawsuit", "appeal"]
    assert g.hints("Board approves rezoning, adopts setback ordinance") == ["setback", "zoning", "ordinance"]
    assert g.hints("Supervisors ban solar farms, extend moratoria") == ["moratorium", "ban"]


@pytest.mark.parametrize("title,entity,status,name", [
    ("Linn County supervisors extend solar moratorium", "restriction", "extended", ""),
    ("Board extends moratorium on wind farms", "restriction", "extended", ""),
    ("Board to consider extending moratorium on wind farms", "restriction", "", ""),
    ("County lifts ban on solar farms", "restriction", "lifted", ""),
    ("Township adopts setback rules for wind turbines", "restriction", "", ""),
    ("Commissioners deny Rainbow Springs Solar rezoning", "contested_project", "rejected",
     "Rainbow Springs Solar"),
    ("Judge rejects lawsuit against Big Sky Wind farm", "contested_project", "", "Big Sky Wind"),
    ("Developer withdraws Cedar Creek Solar application after opposition", "contested_project",
     "cancelled", "Cedar Creek Solar"),
    ("County approves solar farm despite neighbors' objections", "contested_project",
     "approved_after_opposition", ""),
    ("Solar farm appeal denied", "contested_project", "", ""),
    ("Will the county deny the solar farm?", "contested_project", "", ""),
    ("Commissioners Deny Rainbow Springs Solar Rezoning", "contested_project", "rejected", ""),
    # Headlines seen in GDELT's stream, 2026-10-06 to 10-12.
    ("Athens sets public hearing on battery-energy storage law", "restriction", "", ""),
    ("Bethany Planning And Zoning Commission Approves Solar Array Regulations, Reviews Subdivision Plans",
     "restriction", "", ""),
    ("Commissioners OK amended solar ordinance on first reading, 2-1", "restriction", "", ""),
    ("Judges recommend denial of Shepherd's Run solar farm in Copake", "contested_project", "", ""),
    ("County approves 500-foot setback for solar farms", "restriction", "", ""),
    ("Commissioners approve 200-acre solar farm, new setback rules", "contested_project", "approved", ""),
])
def test_classification_status_and_project_name(title, entity, status, name):
    t = g.tidy(title)
    pn = g.project_name(t)
    etype = g.entity_type(t, pn)
    assert (etype, g.status(t, etype), pn if etype == "contested_project" else "") == (entity, status, name)


@pytest.mark.parametrize("title,why", [
    ("Trump administration halts offshore wind project", "federal"),
    ("Environmental Groups Sue Trump Administration, USDA Over Rural Solar Funding Cutoff", "federal"),
    ("Residents sue Interior Department over offshore wind approval", ""),
    # Headlines seen in GDELT's own stream, 2026-10-06 to 10-12.
    ("German energy minister denies choking renewables rollout, then scraps wind and solar unit", "foreign"),
    ("UK: Pathfinder Clean Energy wins appeal for Wheatenhurst Solar Farm in Gloucestershire", "foreign"),
    ("FG rejects solar import ban to protect energy transition", "trade"),
    ("Court halts solar power project in İzmir after 6,000 olive trees cut down", "foreign"),
    ("Billionaire wins fight with neighbours to build 40-acre solar farm", "foreign"),
    ("New Mexico county weighs solar farm moratorium", ""),
    ("Dunkirk BESS moratorium 'legally deficient,' mayor says", ""),
])
def test_off_scope(title, why):
    assert g.off_scope(title) == why


def test_dashes_html_and_spacing():
    assert g.plain("Solar farm " + EM + " residents object &amp; <b>sue</b>") == "Solar farm, residents object & sue"
    assert g.plain("2025" + EN + "2026 moratorium") == "2025-2026 moratorium"
    assert g.tidy("Linn County ' s solar - farm : 9 , 000 acres , residents") == \
        "Linn County's solar-farm: 9,000 acres, residents"


# ── the extractor on real responses ──────────────────────────────────────────

LABELS = ("moratorium", "zoning", "denial", "litigation", "organizing")
DASH = re.compile("[" + "".join(map(chr, (0x2012, 0x2013, 0x2014, 0x2015, 0x2212))) + "]")
RESTRICTION_STATUS = {"", "active", "extended", "pending", "lifted", "expired"}


def manifest_row(label: str, path: Path) -> dict:
    """The manifest row fetch.py writes for one configured request."""
    import fetch
    src = next(s for s in fetch.load_sources(fetch.CONFIG_PATH) if s["source_id"] == "gdelt_renewable_news")
    url = dict(fetch.build_requests(src))[label]
    return {"source_id": "gdelt_renewable_news", "url": url, "fetch_date": "2026-10-13T21:00:00+00:00",
            "content_type": "application/json; charset=utf-8", "status_code": "200",
            "content_hash": "0" * 64, "local_path": f"data/raw/gdelt_renewable_news/{path.name}", "error": ""}


def fixture(label: str) -> Path:
    return FIXTURES / f"gdelt_renewable_news_{label}.json"


def leads(label: str) -> list[dict]:
    return g.extract(fixture(label), manifest_row(label, fixture(label)))


def all_leads() -> list[tuple[str, dict]]:
    return [(label, lead) for label in LABELS for lead in leads(label)]


def test_fixtures_are_small_valid_artlist_json():
    for label in LABELS:
        path = fixture(label)
        assert path.stat().st_size <= 40_000, path.name
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload["articles"], list) and payload["articles"], path.name
        assert {"url", "title", "seendate", "domain", "language", "sourcecountry"} <= set(payload["articles"][0])


def test_every_lead_meets_the_extractor_contract():
    found = all_leads()
    assert found
    for label, lead in found:
        assert set(lead) <= set(parse.QUEUE_FIELDS) and not set(lead) & set(parse.OWN_FIELDS)
        assert lead["entity_type"] in ("restriction", "contested_project")
        tokens = common.technology_tokens(lead["technology"])
        assert tokens and set(tokens) <= {"solar", "wind", "battery_storage"}
        assert ";".join(tokens) == lead["technology"]
        if lead["entity_type"] == "restriction":
            assert lead["status"] in RESTRICTION_STATUS and not lead["project_name"]
        else:
            assert lead["status"] in {""} | set(build_sabin_seeds.OUTCOME)
        assert not lead.get("mechanisms") and not lead.get("severity_score")
        assert not lead.get("adopted_date") and not lead.get("first_event_date")
        assert lead["access"] == "snippet"
        assert lead["source_kind"] == "news" and lead["source_kind"] in classify.SOURCE_KINDS
        assert lead["source_url"].startswith(("http://", "https://"))
        assert lead["source_url"] == common.strip_tracking(lead["source_url"])
        assert 0 < len(lead["evidence_text"]) <= 1000 and lead["description"]
        assert lead["state"] == "" or lead["state"] in common.STATE_CODES
        assert lead["county"] == "" or re.search(r" (County|Parish)$", lead["county"])
        assert not lead["county"] or lead["state"]
        assert lead["reviewer_notes"].startswith(f"GDELT {label} query; seen 20")
        assert "(crawl date)" in lead["reviewer_notes"] and "; score " in lead["reviewer_notes"]
        for key, value in lead.items():
            assert not DASH.search(str(value)), (key, value)
            assert "<" not in str(value), (key, value)


def test_a_gzipped_raw_file_gives_the_same_leads(tmp_path):
    gz = tmp_path / "abc.json.gz"
    gz.write_bytes(gzip.compress(fixture("organizing").read_bytes()))
    assert g.extract(gz, manifest_row("organizing", gz)) == leads("organizing")


def _one_article(label: str, **changes) -> dict:
    """The first article of a fixture that the extractor keeps, changed."""
    payload = json.loads(fixture(label).read_text(encoding="utf-8"))
    kept = {lead["source_url"] for lead in leads(label)}
    art = next(a for a in payload["articles"] if common.strip_tracking(a["url"]) in kept)
    return {**art, **changes}


def _run(tmp_path, articles, label="organizing"):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"articles": articles}), encoding="utf-8")
    return g.extract(path, manifest_row(label, path))


def test_language_country_and_rehost_filters(tmp_path):
    art = _one_article("organizing")
    assert len(_run(tmp_path, [art])) == 1
    assert _run(tmp_path, [{**art, "language": "Spanish"}]) == []
    assert _run(tmp_path, [{**art, "sourcecountry": "United Kingdom"}]) == []
    assert _run(tmp_path, [{**art, "domain": "msn.com", "url": "https://www.msn.com/en-us/news/x"}]) == []
    demoted = _run(tmp_path, [{**art, "domain": "reddit.com", "url": "https://www.reddit.com/r/x"}])
    assert len(demoted) == 1 and "reddit.com" in demoted[0]["reviewer_notes"]


def test_each_document_once_and_identical_headlines_collapsed(tmp_path):
    art = _one_article("organizing")
    tracked = {**art, "url": art["url"] + ("&" if "?" in art["url"] else "?") + "utm_source=feed"}
    syndicated = {**art, "url": "https://another-paper.example.com/story", "domain": "another-paper.example.com",
                  "title": art["title"].upper()}
    out = _run(tmp_path, [art, tracked, syndicated])
    assert len(out) == 1
    assert out[0]["source_url"] == common.strip_tracking(art["url"])
    assert out[0]["reviewer_notes"].endswith("also: https://another-paper.example.com/story")


def test_query_label_is_recovered_from_the_manifest_url():
    for label in LABELS:
        assert g.query_label(manifest_row(label, fixture(label))["url"]) == label
    assert g.query_label(GDELT + "?query=%22solar+farm%22+moratorium&mode=artlist") == "'\"solar farm\" moratorium'"
    assert g.query_label("") == "unlabelled"


def test_round_trip_through_parse_dedupe():
    from dataclasses import asdict
    cands = []
    for label in LABELS:
        got = parse.run_extractor(g, fixture(label), manifest_row(label, fixture(label)),
                                  rel_path=f"data/raw/gdelt_renewable_news/{label}.json.gz")
        assert got is not None
        cands += got
    assert cands and all(c.review_status == "lead" and c.source_id == "gdelt_renewable_news" for c in cands)
    empty = {"restriction": [], "contested_project": [], "case": []}
    kept, dropped = parse.dedupe(cands, parse.Known([], empty))
    # Within one response each document and headline comes once; across the
    # five queries the same article can return, and dedupe drops the copy.
    assert kept and len(kept) + len(dropped) == len(cands)
    parse.assign_queue_ids(kept, set())
    assert len({c.queue_id for c in kept}) == len(kept)
    # Queued once, never again: the next run finds every lead already held.
    again = [parse.CandidateRecord(**asdict(c)) for c in kept]
    kept2, dropped2 = parse.dedupe(again, parse.Known([asdict(c) for c in kept], empty))
    assert kept2 == [] and len(dropped2) == len(kept)
