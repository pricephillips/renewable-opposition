"""gdelt_renewable_news: the headline geotagger (scripts/news_place.py) and the
extractor (scripts/extractors/gdelt_renewable_news.py), offline, on trimmed
real GDELT DOC 2.0 ArtList responses in tests/fixtures/intake/.

The fixtures gdelt_renewable_news_<label>.json are real responses to the five
configured queries (config/sources.yaml), fetched with timespan=3m instead of
15d: GDELT's daily volume collapsed after 2026-10-02 and an 8-day window
returned one article (2026-10-14). moratorium was fetched 2026-10-13, the other
four 2026-10-14. Each keeps the response's own article objects, verbatim and
in order, but only some of them (under 40 KB): every article that becomes a
lead or collapses into one, then the dropped ones that name a technology (the
filters' real inputs), then a sample of GDELT's full-text noise."""
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
    # A company's home state is not the story's: the county is Mower, Minnesota.
    ("Ohio developer's Mower County solar farm draws fire", ("medium", "MN", "Mower County")),
    # A town is looked up in the state that frames it, not the first one named.
    ("Iowa developer's solar farm near Rochester, Minnesota draws opposition",
     ("high", "MN", "Olmsted County")),
    ("Iowa regulators weigh solar farm near Rochester, Minnesota", ("high", "MN", "Olmsted County")),
    ("Minnesota's Cannon Falls weighs solar moratorium as Iowa watches", ("high", "MN", "Goodhue County")),
    # In a title-case headline a county its own state frames, or one whose
    # name is no ordinary word, still counts.
    ("Iowa's Story County Board Extends Solar Moratorium", ("high", "IA", "Story County")),
    ("Story County, Iowa Supervisors Extend Solar Moratorium", ("high", "IA", "Story County")),
    ("Oklahoma's Texas County Commissioners Approve Wind Ban", ("high", "OK", "Texas County")),
    ("Darlington County Neighbors Rally Against Proposed Solar Farm", ("medium", "SC", "Darlington County")),
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
    ("Ohio regulators weigh Mower County solar farm", ("none", "", "")),
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
    # Seen in GDELT's stream: outside a town is not in it, and a town beside
    # places in the plural is a roundup.
    ("Outside of Little Rock, Arkansas counties and cities move ahead on data center moratoriums",
     ("state_only", "AR", "")),
    ("Solar farm planned outside Coggon, Iowa draws opposition", ("state_only", "IA", "")),
    # Review findings, 2026-10-14. Punctuation ends a county name.
    ("Residents Oppose Solar Power, County Board Says", ("none", "", "")),
    ("Solar Power: County Board Votes Down Wind Farm Moratorium", ("none", "", "")),
    ("Opposition grows to solar farm near Austin, County officials say", ("none", "", "")),
    ("Letter: Mike Power, County Commissioner, opposes solar farm", ("none", "", "")),
    ("The Solar Story: County Board Rejects Wind Farm", ("none", "", "")),
    # In title case a capital marks no name: an ordinary word or a state name
    # before County is not a county unless its own state frames it, and "a
    # Texas County" is never Texas County.
    ("Wind Power County Ordinance Draws Opposition", ("none", "", "")),
    ("What Will County Do About Solar Farm Opposition?", ("none", "", "")),
    ("Early County Vote Set on Solar Moratorium", ("none", "", "")),
    ("Election Day County Vote on Solar Ban Draws Crowd", ("none", "", "")),
    ("Residents Don't Love County's Solar Farm Plan", ("none", "", "")),
    ("Oklahoma Developer Sues Texas County Over Wind Farm Ban", ("none", "", "")),
    ("Missouri Utility's Wind Farm Fight Moves to a Texas County", ("none", "", "")),
    # A company's home state is not the story's.
    ("Texas-based developer sues Montgomery County over solar farm denial", ("none", "", "")),
    ("Florida developer sues Lake County over solar moratorium", ("none", "", "")),
    # Several states named and no state framing the town: nothing.
    ("Iowa and Minnesota residents fight solar farm near Rochester", ("none", "", "")),
    # A masthead's city is not a town: "San Diego Union-Tribune".
    ("California regulators reject solar farm plan, San Diego Union-Tribune", ("state_only", "CA", "")),
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
    # A company's home state is not named as the story's.
    assert news_place.named_states("Texas-based developer sues Montgomery County") == []
    assert news_place.named_states("Missouri Utility's Wind Farm Fight") == []
    assert news_place.named_states("Iowa wind company sues county") == []
    assert news_place.named_states("Ohio Power Siting Board rejects wind farm") == ["OH"]


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
    # Seen in GDELT responses, 2026-07 to 10: "wind, solar" in either order;
    # solar panels on public buildings are the city buying power.
    ("Knox County wind, solar ban survives federal court challenge", ["solar", "wind"]),
    ("Richmond city council rejects solar panel deal for city buildings", []),
    ("Automakers enter energy storage business as data centers face backlash", []),
    ("Solar farm on farmland near homes draws opposition", ["solar"]),
])
def test_technology_in_the_headline(title, techs):
    assert g.technologies(g.tidy(title)) == techs


def test_mechanism_hints_have_their_own_boundaries():
    # data-center-map's pattern read 'issued' as 'sued' and 'appealing' anywhere.
    assert g.hints("County issued permits for solar farm") == []
    assert g.hints("Neighbors sued over wind farm; appeal filed") == ["lawsuit", "appeal"]
    assert g.hints("Board approves rezoning, adopts setback ordinance") == ["setback", "zoning", "ordinance"]
    assert g.hints("Supervisors ban solar farms, extend moratoria") == ["moratorium", "ban"]
    # 'abandons' takes any object; it is a withdrawal only before a plan or project.
    assert g.hints("Mount Jackson delays solar vote, abandons community center land purchase") == []
    assert g.hints("Developer abandons its Coggon solar project") == ["withdrawal"]
    assert g.hints("Lyon County pauses data center, solar farm development for six months") == ["pause"]
    assert g.hints("Chesterfield residents approve bylaw for battery energy storage systems") == ["ordinance"]
    # A setback that is a loss is not a distance.
    assert g.hints("Details of BP venture $700m offshore wind setback surface") == []
    assert g.hints("County approves 500-foot setback for solar farms") == ["setback"]


@pytest.mark.parametrize("title,opposed", [
    # Residents count as the ones acting, not as the ones a story is told for.
    ("Cause of La Verne battery system fire still unknown, city vows transparency for residents", False),
    ("Solar farm to bring savings to local residents", False),
    ("Angelica residents demand transparency over battery storage facility", True),
    ("Several Grove residents unhappy about large battery storage center plans nearby", True),
    ("Darlington County neighbors rally against proposed 417-acre solar farm", True),
    # Words of conflict GDELT headlines use; a place named Battle is not one.
    ("Battle over large Gillespie County solar farm heading back to court", True),
    ("Grant Township hires attorney as 375-megawatt energy storage project moves forward", True),
    ("Battle Creek solar farm begins producing power", False),
    # "Block Island" is a place, not a blockade.
    ("WindAction | 7 years after it sank, The Mistress is found near the wind farm off Block Island", False),
])
def test_opposition_words(title, opposed):
    assert g.opposed(title) == opposed


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
    # Seen in GDELT responses, 2026-07 to 10: a pause on a class of
    # development and a bylaw are instruments; a developer pausing its one
    # project is not; a decision on something else sets no status.
    ("Lyon County pauses data center, solar farm development for six months", "restriction", "", ""),
    ("Howard Republican wants to pause solar projects", "restriction", "", ""),
    ("Developer pauses Cedar Creek Solar project after opposition", "contested_project", "", "Cedar Creek Solar"),
    ("Chesterfield residents approve bylaw for battery energy storage systems", "restriction", "", ""),
    ("Mount Jackson delays solar vote, abandons community center land purchase", "contested_project", "", ""),
    ("Cedar Creek Solar farm withdrawn by developer", "contested_project", "cancelled", "Cedar Creek Solar"),
    ("Jefferson County committee approves Watertown solar project, despite City of Watertown opposition",
     "contested_project", "approved_after_opposition", ""),
    ("Rejected Hadley battery project returns amid lawsuit, resident concerns", "contested_project", "", ""),
    # Review findings, 2026-10-14: a decision on a suit, appeal, petition,
    # injunction, resolution or funding is not one on the project ('rejected'
    # would invert the outcome). A bare 'solar' matches by itself, so the
    # object is everything between the verb and it.
    ("Judge rejects lawsuit against solar farm", "contested_project", "", ""),
    ("Court rejects neighbors' lawsuit against solar farm", "contested_project", "", ""),
    ("Commissioners deny appeal of solar farm permit", "contested_project", "", ""),
    ("Supervisors reject petition against solar farm", "contested_project", "", ""),
    ("Board denies appeal, approves solar farm", "contested_project", "", ""),
    ("Judge denies neighbors' injunction against solar farm", "contested_project", "", ""),
    ("State board denies rehearing on wind farm opponents' complaint", "contested_project", "", ""),
    ("Supervisors approve resolution opposing solar farm", "contested_project", "", ""),
    ("Council approves funding for lawsuit against solar farm", "contested_project", "", ""),
    ("Judge Rejects Lawsuit Against Solar Farm", "contested_project", "", ""),
    ("Supervisors Approve Measure Opposing Solar Farm", "contested_project", "", ""),
    ("Niagara County denies highway permits for Bear Ridge Solar", "contested_project", "", "Bear Ridge Solar"),
    # ...but a project's own permit, size or name between them is still the project.
    ("Louisa County board denies permit for $1.2B Southpaw Solar project", "contested_project", "rejected",
     "Southpaw Solar"),
    ("Quincy commission OKs special use permit for solar farm above Huber caves", "contested_project",
     "approved", ""),
    # A restriction's status verb must act on the instrument, in its clause.
    ("Township repeals zoning fee, keeps solar moratorium", "restriction", "", ""),
    ("Solar moratorium stays as board lifts building permit freeze", "restriction", "", ""),
    ("Town adopts battery storage ban; lifts residency requirement", "restriction", "", ""),
    ("County extends comment period on solar ordinance", "restriction", "", ""),
    ("Town board takes steps toward battery storage, data center bans; lifts town job residency requirement",
     "restriction", "", ""),
    ("Moratorium on solar farms lifted", "restriction", "lifted", ""),
    ("Supervisors lift solar ban", "restriction", "lifted", ""),
    ("Solar moratorium expires", "restriction", "expired", ""),
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
    ("Renewable groups sue to end Pentagon total halt of wind power", "federal"),
    # Offshore wind is federal unless a local actor is named; suits between
    # investors are business.
    ("New York, California sue to block deals canceling offshore wind projects", "federal"),
    ("Windtech International-Connecticut joins lawsuits over offshore wind lease cancellations", "federal"),
    ("New York, California sue to block cancellation of wind projects", "federal"),
    ("Town sues over offshore wind cable landing", ""),
    ("Emmitt Smith sued by investor over wind farm project", "commercial"),
    ("Residents allege fraud in solar farm approval, file lawsuit", ""),
    # A setback that is a loss is not a distance, and offshore wind is federal.
    ("Details of BP venture $700m offshore wind setback surface", "federal"),
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


@pytest.mark.parametrize("title,description", [
    # Mastheads GDELT left on real headlines: they name the outlet, not the story.
    ("Tupper Lake Moratoriums on Battery Energy Storage Systems | Adirondack Daily Enterprise",
     "Tupper Lake Moratoriums on Battery Energy Storage Systems"),
    ("Twelve Month Moratorium Approved for White County, WRUL-FM", "Twelve Month Moratorium Approved for White County"),
    ("Zionsville officials oppose LEAP wastewater plan, pass data center pause, Inside INdiana Business",
     "Zionsville officials oppose LEAP wastewater plan, pass data center pause"),
    ("Renewable groups sue to end Pentagon total halt of wind power-Las Vegas Sun News",
     "Renewable groups sue to end Pentagon total halt of wind power"),
    ("Planning commissioners must produce documents within 30 days in solar farm dispute, judge rules | News, "
     "Sports, Jobs-Lawrence Journal-World: news, information, headlines and events in Lawrence, Kansas",
     "Planning commissioners must produce documents within 30 days in solar farm dispute, judge rules"),
    ("Solar company, landowner sue Sangamon County-Illinois Times, the capital city weekly source of news",
     "Solar company, landowner sue Sangamon County"),
    ("California sues to block deals canceling offshore wind projects, NBC Los Angeles",
     "California sues to block deals canceling offshore wind projects"),
    # A hyphenated masthead, and an outlet's sections after one (real GDELT titles).
    ("California regulators reject solar farm plan, San Diego Union-Tribune",
     "California regulators reject solar farm plan"),
    ("Pelosi says Biden inner circle should have acted: 4 takeaways from California political summit, "
     "Loveland Reporter-Herald",
     "Pelosi says Biden inner circle should have acted: 4 takeaways from California political summit"),
    ("BIG PIVOTS: A Coal Mine Closes, and Solar Comes On, Pagosa Daily Post News Events & Video for Pagosa "
     "Springs Colorado", "BIG PIVOTS: A Coal Mine Closes, and Solar Comes On"),
    ("DiDomenico votes to save ratepayers money on energy costs, Chelsea Record",
     "DiDomenico votes to save ratepayers money on energy costs"),
    # Not mastheads: a hyphenated name, a place after a comma, an ordinary noun
    # glued on with a hyphen or ending a list.
    ("County Releases Battery-Energy Storage Report", "County Releases Battery-Energy Storage Report"),
    ("Solar farm draws opposition in Coggon, Iowa", "Solar farm draws opposition in Coggon, Iowa"),
    ("Wind Farm Gets State-Level Review", "Wind Farm Gets State-Level Review"),
    ("Governor Signs Data Center Bills Addressing Noise Reporting, Water Use, And CEQA Review",
     "Governor Signs Data Center Bills Addressing Noise Reporting, Water Use, And CEQA Review"),
])
def test_trailing_masthead_removed(title, description):
    assert g.description_of(g.tidy(title)) == description


def test_a_masthead_never_places_a_lead():
    # "Inside INdiana Business" named the state that placed Zionsville in Boone County.
    title = "Zionsville officials oppose LEAP wastewater plan, pass data center pause, Inside INdiana Business"
    assert news_place.locate(g.description_of(g.tidy(title))).state == ""
    # "San Diego Union-Tribune" placed a statewide story in San Diego County.
    title = "California regulators reject solar farm plan, San Diego Union-Tribune"
    assert where(g.description_of(g.tidy(title))) == ("state_only", "CA", "")
    title = ("BIG PIVOTS: A Coal Mine Closes, and Solar Comes On, Pagosa Daily Post News Events & Video for "
             "Pagosa Springs Colorado")
    assert where(g.description_of(g.tidy(title))) == ("none", "", "")


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


def test_real_responses_keep_local_fights_and_drop_the_rest():
    """The fixtures' leads were judged by hand (2026-10-14): these pin the
    judgements, so a change that moves one is seen and checked again."""
    found = all_leads()
    text = " | ".join(lead["description"] for _, lead in found)
    # Off topic, and dropped: federal offshore wind suits, an investor's suit, a
    # shipwreck off Block Island, a BESS fire, a city's own panels, a business,
    # a setback that is a loss.
    for gone in ("Emmitt Smith", "Windtech", "Block Island", "deals canceling offshore wind", "La Verne",
                 "Richmond city council", "Automakers enter", "BP venture"):
        assert gone not in text, gone
    by = {lead["description"]: lead for _, lead in found}
    assert by["Knox County wind, solar ban survives federal court challenge"]["technology"] == "solar;wind"
    assert by["Chesterfield residents approve bylaw for battery energy storage systems"]["entity_type"] == "restriction"
    assert by["Rejected Hadley battery project returns amid lawsuit, resident concerns"]["status"] == ""
    assert by["Jefferson County committee approves Watertown solar project, despite City of Watertown "
              "opposition"]["status"] == "approved_after_opposition"
    # Every placement in the fixtures, each checked against the article: no
    # masthead ("NBC Los Angeles", "Lawrence Journal-World ... Kansas") places one.
    placed = {(lead["state"], lead["county"]) for _, lead in found if lead["state"]}
    assert placed == {("CA", "Solano County"), ("IL", "Sangamon County"), ("IL", "Will County"),
                      ("IN", "LaPorte County"), ("LA", "Iberville Parish"), ("MI", ""),
                      ("MI", "Grand Traverse County"), ("OR", ""), ("SC", "Darlington County"),
                      ("TX", "Gillespie County")}


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


def test_unexpected_json_shapes_give_no_leads_not_errors(tmp_path):
    """fetch.py lets any valid JSON through; a raw file the extractor raised on
    would be retried three times and then skipped with all its articles."""
    art = _one_article("organizing")
    path = tmp_path / "r.json"

    def run(payload):
        path.write_text(json.dumps(payload), encoding="utf-8")
        return g.extract(path, manifest_row("organizing", path))

    for payload in ([], "text", 3, None, {}, {"articles": None}, {"articles": {"a": 1}}, {"articles": "x"}):
        assert run(payload) == [], payload
    # An article that is not an object is skipped; the others are still read.
    assert len(run({"articles": [1, "x", None, art]})) == 1
    # A field that is not a string reads as blank.
    assert run({"articles": [{**art, "title": 12345}]}) == []
    assert run({"articles": [{**art, "url": 5}]}) == []
    assert run({"articles": [{**art, "language": 1}]}) == []
    assert run({"articles": [{**art, "sourcecountry": ["United States"]}]}) == []
    out = run({"articles": [{**art, "seendate": 20261010, "domain": 7}]})
    assert len(out) == 1 and "seen  (crawl date)" in out[0]["reviewer_notes"]


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
