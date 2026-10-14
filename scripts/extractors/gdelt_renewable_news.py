"""Extractor for the GDELT DOC 2.0 ArtList queries (source_id gdelt_renewable_news).

Input: one raw JSON response stored by fetch.py, {"articles": [{url,
url_mobile, title, seendate, socialimage, domain, language, sourcecountry}]},
from one of the five labelled queries in config/sources.yaml (moratorium,
zoning, denial, litigation, organizing). `source` is the data/raw/manifest.csv
row; its url carries the query, which names the label in reviewer_notes.
fetch.py lets any valid JSON through: a payload that is not an object with an
"articles" list gives no leads, and an article that is not an object, or a
field that is not a string, is skipped or read as blank, never an error.

Output: one lead per headline that is about local opposition to a solar, wind
or battery-storage project or rule. GDELT matches the full text, so most
articles it returns mention a renewable technology in passing; only the
headline is judged here, and a headline is kept only if

  - the article is English and from the United States (language,
    sourcecountry);
  - the headline names a renewable technology (TECH_PATTERNS: "solar farm",
    "wind turbines", "battery storage", tolerating GDELT's spaced punctuation,
    "solar - farm"; a bare "wind" is weather and a bare "battery" is a car
    part, "solar system", "solar eclipse" or "solar flare" are not solar
    power, rooftop solar and solar panels on public buildings are not a
    siting fight, and a battery factory or recycler is not storage);
  - it names a mechanism (MECHANISM_HINTS) or opposition (OPPOSITION_GUARD,
    after data-center-map's guard, with setback and words of conflict such
    as dispute, battle and skeptical added; residents or neighbors count only
    as the ones acting, not as the ones a story is told for, and a setback
    that is a loss is not a distance);
  - it is a local US matter (off_scope): not a federal actor alone
    (FEDERAL_ONLY with no local word: an offshore lease cancelled by Interior
    or a USDA funding rule is not a local fight; nor is offshore wind with no
    local word, since the federal government leases and permits it), not
    another country (FOREIGN, unless a US state is named too: sourcecountry is
    the outlet's country, not the story's), not trade policy (an import ban),
    and not a suit between investors or rivals (COMMERCIAL);
  - its domain is not a pure re-host (REHOST_DOMAINS).

Every lead is review_status 'lead' (parse.py): nothing is promoted until a
person has opened the article, so precision is preferred to recall here, and
the raw file keeps every article for a reparse.

Each lead:
  entity_type   restriction when the headline is about an instrument
                (moratorium, ban, ordinance, bylaw, setback, zoning rules, a
                government's pause on a class of development); otherwise
                contested_project (a denial, appeal, petition, lawsuit or
                approval over objections). Never case: a case needs a court
                record, not a headline.
  state, county, municipality
                news_place.locate on the description (see that module; a
                masthead names the outlet's state, not the story's): a county
                only when the headline names it literally and, unless the name
                is unique, its state; a town only with its state named and one
                county; a roundup or an ambiguous name places nothing.
  jurisdiction_type
                restrictions only, and only when the headline names the
                acting government: County (or Parish) for '<Name> County
                commissioners/supervisors/board ...', Township, Town, City or
                Village for '<Name> Township', 'Town of <Name>' and the like.
  project_name  contested projects only, when a sentence-case headline names
                one: '<Capitalized Name> Solar|Wind ...' (title-case headlines
                capitalize every word, so no name is read from them).
  technology    solar, wind, battery_storage named in the headline.
  status        only when the headline states it outright and asks nothing
                (no question, no modal: could, may, to, considers, weighs,
                proposed ...): restrictions 'extended' (extends a moratorium),
                'lifted' (lifts, repeals, rescinds), 'expired' (expires), each
                only when the verb acts on the instrument in its own clause
                ('extends solar moratorium', 'moratorium on solar farms
                lifted'; not 'repeals zoning fee, keeps solar moratorium' or
                'extends comment period on solar ordinance');
                contested projects 'rejected' (denies, rejects, votes down),
                'cancelled' (withdrawn, cancelled, scrapped),
                'approved_after_opposition' (approves despite or over
                opposition), 'approved'. A decision acts on the project only
                when nothing but determiners, sizes, names or the project's
                own permit stands between it and the technology ('denies
                Rainbow Springs Solar rezoning', 'OKs special use permit for
                solar farm'); blank when it acts on something else ("rejects
                lawsuit against solar farm", "denies appeal of solar farm
                permit", "abandons community center land purchase"), and
                blank otherwise. 'active' and 'pending' are never set from a
                headline.
  description   the headline, with GDELT's spaced punctuation closed up and a
                trailing masthead or section label (' | Amsterdam', ', San
                Diego Union-Tribune') removed.
  evidence_text the headline as GDELT gives it (dashes replaced, HTML
                stripped).
  source_url    the article URL, click tracking removed.
  access        'snippet': a headline in a search index, not a read article.
  source_kind   'news'.
  reviewer_notes
                'GDELT <label> query; seen <YYYY-MM-DD> (crawl date); <domain>;
                place <confidence>: <reason>; hints: ...; score N', and
                'also: <url> ...' for identical headlines on other mastheads
                in the same response (kept once, the first).
  mechanisms, severity_score, adopted_date and first_event_date stay blank:
                a hint is not a mechanism in the build vocabulary, and a crawl
                date is not an event date.

Score (reviewer_notes only), after data-center-map signal_harvest.priority():
3 for a mechanism hint, 1.5 more for a moratorium or a withdrawal, 3 / 1.5 /
0.5 for a high / medium / state-only place, 2 less on a demoted domain (an
aggregator or a user platform, DEMOTED_DOMAINS). DCM's recency term is left
out so a reparse gives the same notes.

Re-hosts are dropped, not demoted: msn.com, yahoo.com, aol.com, newsbreak.com
and flipboard.com republish or link other publishers' articles, so the copy
is never the document a record should cite, and the publisher's own copy is
what a reviewer has to find anyway. reddit.com and medium.com are original
posts, not re-hosts: kept, and demoted.

Practice ported from pricephillips/data-center-map signal_harvest.py
(MECHANISM_HINTS, OPPOSITION_GUARD, DEMOTED_DOMAINS, priority()), copied
and adapted, not imported. DCM's MECHANISM_HINTS put \\b on the first
alternative only, so 'sued' matched inside 'issued'; every alternation here
is wrapped in its own group.

Nothing here writes a file. It reads config/sources.yaml (for the query
labels) and, through news_place, the county and place reference files.
"""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml

from common import normalize_url, read_raw, strip_tracking
from news_place import locate, named_states, title_case

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES_YAML = ROOT / "config" / "sources.yaml"
SOURCE_ID = "gdelt_renewable_news"

# ── relevance ────────────────────────────────────────────────────────────────

_SEP = r"(?:\s*-\s*|\s+)"     # "solar farm", "solar-farm", GDELT's "solar - farm"
_SOLAR_NOT = (r"(?:system|systems|eclipse|eclipses|flares?|storms?|wind|cycle|maximum|minimum|orbiter|"
              r"probe|radiation|activity|plexus|car|cars|powered car)")
TECH_PATTERNS = {
    "solar": re.compile(
        rf"\bsolar\b(?!{_SEP}{_SOLAR_NOT}\b)(?<!\bparker solar)", re.I),
    "wind": re.compile(
        rf"\b(?:wind{_SEP}(?:farms?|turbines?|projects?|energy|power|facilit(?:y|ies)|developments?|"
        rf"developers?|parks?|leases?|ordinances?|zoning|moratori(?:um|ums|a)|towers?|proposals?|"
        rf"installations?|sites?|plants?|compan(?:y|ies)|generation|array|complex)"
        rf"|windfarms?"
        rf"|(?:offshore|onshore){_SEP}wind"
        rf"|wind{_SEP}(?:and|&|or){_SEP}solar"
        rf"|solar{_SEP}(?:and|&|or){_SEP}wind"
        rf"|solar\s*,\s*wind|wind\s*,\s*solar)\b", re.I),
    "battery_storage": re.compile(
        rf"\b(?:(?:battery|batteries){_SEP}(?:energy{_SEP})?(?:storage|farms?|projects?|sites?|"
        rf"systems?|installations?|parks?|facilit(?:y|ies))"
        rf"|(?:energy|power){_SEP}storage"
        rf"|bess)\b", re.I),
}
# Solar on a roof or a balcony is not a siting fight.
_SMALL_SOLAR = re.compile(r"\b(?:rooftop|roof-top|residential|balcony|backyard|portable|home)\s+solar\b|"
                         r"\bsolar(?:-|\s+)(?:powered\s+)?(?:lamps?|lights?|lighting|lanterns?|chargers?|"
                         r"generators?|phone|watch)\b", re.I)
# Solar on a public building is the government buying power, not a siting
# fight ("Richmond city council rejects solar panel deal for city buildings").
_BUILDING_SOLAR = re.compile(
    r"\bsolar(?:\s+(?:panels?|arrays?))?(?:\s+(?:deal|contract|project|installation|plan|proposal))?\s+"
    r"(?:on|for|at|atop)\s+(?:the\s+)?(?:(?:city|county|town|village|township|school|public|municipal|"
    r"government|state)\s+)?(?:buildings?|schools?|roofs?|rooftops?|carports?|parking\s+(?:lots?|garages?))\b",
    re.I)
# Storage as a line of business is not a facility ("Automakers enter energy
# storage business as data centers face backlash").
_STORAGE_TRADE = re.compile(
    r"\b(?:energy|power|battery)\s+storage\s+(?:business|businesses|markets?|stocks?|sector)\b", re.I)
# A battery factory, a car battery or a battery recycler is not storage.
_NOT_STORAGE = re.compile(r"\b(?:manufactur\w*|factory|factories|gigafactory|ev|electric\s+vehicles?|"
                          r"recycl\w*|cells?|lithium-ion\s+batter(?:y|ies)\s+fires?)\b", re.I)

# Mechanism hints: suggestions for the reviewer, never the mechanisms column.
# Every alternative sits in its own group with its own boundaries.
# A government pausing a class of development is a moratorium in all but
# name ("Lyon County pauses data center, solar farm development for six
# months"); data-center-map legistar_probe.py INSTRUMENT counts 'pause'. Only
# a plural or generic object: a developer pausing its one project is not a rule.
PAUSE_RX = re.compile(
    r"\bpaus(?:e|es|ed|ing)\b(?:\s+on)?(?:\s+[\w,'-]+){0,5}?\s+(?:development|projects|farms|facilities|"
    r"applications|permits|permitting|construction)\b", re.I)

MECHANISM_HINTS = [
    (re.compile(r"\b(?:moratori(?:um|ums|a))\b", re.I), "moratorium"),
    (PAUSE_RX, "pause"),
    (re.compile(r"\b(?:bans?|banned|banning|prohibits?|prohibited|prohibiting|prohibition)\b", re.I), "ban"),
    (re.compile(r"\b(?:setbacks?)\b", re.I), "setback"),
    (re.compile(r"\b(?:rezon(?:e|es|ed|ing)|zoning|special(?:-|\s+)(?:use|exception)|conditional(?:-|\s+)use)\b",
                re.I), "zoning"),
    (re.compile(r"\b(?:ordinances?|by-?laws?)\b", re.I), "ordinance"),
    (re.compile(r"\b(?:lawsuits?|sues?|sued|suing|litigation|legal\s+(?:challenge|fight|battle|action))\b",
                re.I), "lawsuit"),
    (re.compile(r"\b(?:appeals?|appealed|appealing)\b", re.I), "appeal"),
    (re.compile(r"\b(?:denies|denied|deny|denial|rejects?|rejected|rejecting|vot(?:es|ed|e|ing)\s+(?:it\s+|them\s+)?(?:down|against)|"
                r"turn(?:s|ed)?\s+down)\b", re.I), "denial"),
    # 'abandoned' alone is an adjective as often ("solar on abandoned mines"),
    # and 'abandons' takes any object ("abandons community center land
    # purchase"): either counts only before a plan, project, proposal or bid.
    (re.compile(r"\b(?:withdr(?:aw|aws|awn|ew)|cancel(?:s|ed|led|ling)?|scrap(?:s|ped)?|"
                r"abandon(?:s|ed)\s+(?:its\s+|the\s+|their\s+)?(?:[\w'-]+\s+){0,3}?"
                r"(?:plans?|projects?|proposals?|bids?|applications?)|"
                r"pull(?:s|ed)?\s+(?:out|the\s+plug))\b", re.I), "withdrawal"),
    (re.compile(r"\b(?:petitions?|referend(?:um|ums|a)|ballot\s+(?:questions?|measures?|issues?|initiatives?)|"
                r"voters\s+(?:to\s+|will\s+)?decide)\b", re.I), "petition"),
    (re.compile(r"\b(?:public\s+(?:hearings?|comments?|meetings?)|town\s+halls?)\b", re.I), "hearing"),
]

# After data-center-map signal_harvest.OPPOSITION_GUARD, setback added and
# 'critic' narrowed so 'critical minerals' is not opposition.
OPPOSITION_GUARD = re.compile(
    r"\b(?:oppos\w*|protest\w*|residents?|neighbou?rs?|sue[sd]?|suing|lawsuits?|petitions?|reject\w*|"
    r"denie[sd]|deny|halt\w*|pause[sd]?|block(?:s|ed|ing)?(?!\s+island)|ban(?:s|ned|ning)?|moratori\w*|fights?|"
    r"fighting|backlash|concerns?|pushback|push\s+back|object(?:s|ed|ion|ions)?|critics?|criticism|"
    r"against|opposition|referend\w*|recall|setbacks?|"
    # Added, from headlines GDELT returned that the guard missed: words of
    # conflict ("solar farm dispute", "Battle over large Gillespie County solar
    # farm", "leaves residents skeptical", "Grant Township hires attorney as
    # ... energy storage project moves forward"). Not Battle Creek and the like.
    r"disput\w*|clash\w*|contested|controvers\w*|battl(?:e|es|ed|ing)(?!\s+(?:creek|ground|mountain|lake))|"
    r"frustrat\w*|skeptic\w*|balk\w*|wary|wariness|outcry|uproar|sound(?:s|ed)?\s+off|"
    r"demand(?:s|ed)?\s+(?:closure|removal|answers)|"
    r"(?:hires?|hired|retains?|retained)\s+(?:an?\s+)?(?:attorneys?|lawyers?|legal\s+counsel))\b", re.I)
# Residents and neighbors who act are opposition as often as not ("Angelica
# residents demand transparency", "Several Grove residents unhappy about ...
# battery storage"); residents a story is told for are not ("Cause of La Verne
# battery system fire still unknown, city vows transparency for residents").
# Alone, they count only when no preposition puts them in the object's place.
WEAK_OPPOSITION = frozenset({"resident", "residents", "neighbor", "neighbors", "neighbour", "neighbours"})
_FOR_THEM = re.compile(r"\b(?:for|to|with|from|among|by|of|helps?|serves?|serving)\s+(?:[\w'-]+\s+){0,2}$", re.I)

# Federal or state actors. A headline that names one and nothing local is
# about national policy (a lease cancelled by Interior, a stop-work order), not
# a local fight; it is dropped.
FEDERAL_ONLY = re.compile(
    r"\b(?:trump|biden|white\s+house|administration|interior\s+(?:department|secretary)|"
    r"department\s+of\s+(?:the\s+)?(?:interior|energy|agriculture|defense)|defense\s+department|pentagon|"
    r"boem|burgum|congress|senate|"
    r"house\s+republicans|federal|feds|epa|ferc|usda|faa|doe|executive\s+order|stop-work|tariffs?|"
    r"tax\s+credits?|irs|one\s+big\s+beautiful\s+bill|reconciliation|"
    # The federal offshore wind cancellations of 2025-26 and the suits over them.
    r"lease\s+(?:cancell?ations?|buyouts?)|cancell?ation\s+of\s+(?:offshore\s+)?wind)\b", re.I)
LOCAL_WORD = re.compile(
    r"\b(?:count(?:y|ies)|parish|township|town|towns|city|village|borough|local|residents?|neighbou?rs?|"
    r"landowners?|farmers?|community|communities|commissioners?|supervisors?|council|trustees|"
    r"zoning|planning|rezon\w*|ordinance|moratori\w*|setbacks?|petition|referendum|opponents?)\b", re.I)
# A ban on imports or exports is trade policy, not siting.
TRADE = re.compile(r"\b(?:import|export)\s+(?:bans?|tariffs?|duties)\b", re.I)
# Offshore wind is leased and permitted by the federal government: a headline
# about it with no local actor is a federal fight ("New York, California sue
# to block deals canceling offshore wind projects"), not a local one.
OFFSHORE = re.compile(r"\boffshore\b", re.I)
# A suit between investors or rivals is business, not opposition ("Emmitt
# Smith sued by investor over wind farm project").
# Not 'fraud' or 'contract': residents alleging fraud in an approval are opposition.
COMMERCIAL = re.compile(r"\b(?:investors?|shareholders?|patents?|securities)\b", re.I)
# A headline about another country (GDELT's sourcecountry is the outlet's,
# not the story's): dropped unless it also names a US state.
FOREIGN = re.compile(
    r"\b(?:u\.?k\.?|britain|british|england|scotland|scottish|wales|welsh|ireland|irish|germany|german|"
    r"france|french|spain|spanish|italy|italian|netherlands|dutch|belgium|denmark|danish|norway|norwegian|"
    r"sweden|swedish|finland|poland|polish|romania|greece|portugal|europe|european|eu|canada|canadian|"
    r"ontario|alberta|quebec|british\s+columbia|nova\s+scotia|manitoba|saskatchewan|australia|australian|"
    r"new\s+zealand|china|chinese|japan|japanese|korea|korean|taiwan|philippines|vietnam|indonesia|"
    r"malaysia|thailand|pakistan|bangladesh|sri\s+lanka|nigeria|kenya|south\s+africa|cape\s+town|egypt|"
    r"morocco|brazil|chile|(?<!new\s)mexico|mexican|argentina|colombia|peru|israel|saudi|uae|dubai|qatar|"
    r"ukraine|russia|karnataka|maharashtra|gujarat|haryana|rajasthan|tamil\s+nadu|t\u00fcrkiye|turkiye|"
    r"turkish|izmir|istanbul|ankara|cuba|cuban|havana|"
    # British usage in a US outlet's reprint of a British story.
    r"neighbours|councillors?|planning\s+permission)\b", re.I)

# Republish or link other publishers' articles: dropped (module docstring).
REHOST_DOMAINS = {"msn.com", "yahoo.com", "news.yahoo.com", "finance.yahoo.com", "aol.com",
                  "newsbreak.com", "flipboard.com"}
# Kept but scored down: user platforms (data-center-map DEMOTED_DOMAINS, less
# the re-hosts dropped above).
DEMOTED_DOMAINS = {"reddit.com", "medium.com"}

# ── classification ───────────────────────────────────────────────────────────

# An instrument named outright: the headline is about the rule.
INSTRUMENT_RX = re.compile(
    r"\b(?:moratori(?:um|ums|a)|bans?|banned|banning|prohibits?|prohibited|prohibiting|prohibition|"
    r"ordinances?|by-?laws?)\b", re.I)
# Rule words that also turn up in project fights ("denied over setback
# concerns"): an instrument only when no project fight is described.
RULE_RX = re.compile(
    r"\b(?:setbacks?|"
    r"zoning\s+(?:rules?|regulations?|amendments?|changes?|restrictions?|ordinances?|codes?|standards?|"
    r"laws?|updates?|text)|"
    r"(?:rules?|regulations?|restrictions?|limits?|standards?)\s+(?:on|for|governing|to\s+regulate)|"
    r"local\s+laws?|"
    r"(?:solar|wind|turbines?|storage|bess|array|farm)\s+(?:regulations?|rules?|standards?|laws?|codes?))\b",
    re.I)
# A project fight: the project itself was denied, appealed, sued over,
# petitioned against, withdrawn, rezoned or permitted.
PROJECT_FIGHT = re.compile(
    r"\b(?:denies|denied|deny|denial|rejects?|rejected|vot(?:es|ed|ing)\s+(?:it\s+)?down|turn(?:s|ed)\s+down|"
    r"appeals?|appealed|lawsuits?|sues?|sued|suing|petitions?|withdr(?:aw|aws|awn|ew)|rezon(?:e|es|ed|ing)|"
    r"permits?)\b", re.I)
# ...or approved: an approval acting on a project, not on a rule (no rule
# word between the verb and the project: "approves solar farm", not
# "approves setback for solar farms").
PROJECT_APPROVAL = re.compile(
    r"\bapprov(?:e|es|ed|al)\b((?:\s+[\w'\-,]+){0,5}?)\s+(?:solar|wind|battery|storage|bess)"
    r"(?:\s+[\w'\-]+){0,2}?\s+(?:farms?|projects?|facilit(?:y|ies)|arrays?|plants?|sites?|developments?|"
    r"proposals?|parks?|centers?|installations?)\b"
    r"(?!\s+(?:regulations?|rules?|ordinances?|standards?|laws?|codes?|moratori\w*|bans?|setbacks?|zoning))",
    re.I)

# A headline that asks, proposes or predicts states no outcome.
NOT_OUTRIGHT = re.compile(
    r"\?|\b(?:could|may|might|would|will|should|to|set\s+to|poised|expected|considers?|considering|"
    r"consider|weighs?|weighing|mulls?|mulling|eyes?|eyeing|seeks?|seeking|propos(?:es|ed|al)|plans?|"
    r"planned|asks?|asking|urges?|urging|wants?|wanting|debates?|debating|discuss(?:es|ed)?|hearing|"
    r"recommends?|recommended|recommendation|vote\s+on|pending|possible|potential|if|whether|after\s+all|"
    # Back again: "Rejected Hadley battery project returns amid lawsuit".
    r"returns?|returning|revived?|revives|resurfaces?|refiled|refiles|resubmit\w*|reappl\w*)\b",
    re.I)
_DENIED = re.compile(r"\b(?:deny|denies|denied|reject|rejects|rejected|vot(?:e|es|ed)\s+down|"
                     r"turn(?:s|ed)?\s+down)\b", re.I)
_CANCELLED = re.compile(r"\b(?:withdr(?:aws|awn|ew)|cancel(?:s|ed|led)|scrap(?:s|ped)|abandon(?:s|ed))\b", re.I)
_APPROVED = re.compile(r"\b(?:approve|approves|approved|oks|okays|greenlights|green-lights)\b", re.I)
_OVER_OBJECTIONS = re.compile(
    r"\b(?:despite|over|amid)\s+(?:[\w'’]+\s+){0,3}(?:opposition|objections?|concerns|protests?|pushback|"
    r"residents|neighbou?rs|opponents|outcry)\b", re.I)
# The decision word acts on something other than the project ("rejects
# lawsuit against solar farm", "withdraws appeal").
_OTHER_OBJECT = re.compile(
    r"\b(?:appeals?|lawsuits?|suits?|challenges?|complaints?|petitions?|motions?|referend\w*|opposition|"
    r"objections?|requests?\s+to\s+(?:stop|block|halt)|bid\s+to|efforts?|moratori\w*|bans?|ordinances?|by-?laws?|"
    r"rules?|regulations?|restrictions?|setbacks?|support|zoning\s+change|resolutions?|funding|settlements?|"
    r"agreements?|injunctions?|rehearings?|fees?)\b", re.I)
# A restriction's status verb must act on the instrument, in its own clause:
# 'extends solar moratorium', 'lifts ban on wind farms', 'moratorium on solar
# farms lifted', 'solar moratorium expires'. Not 'repeals zoning fee, keeps
# solar moratorium', 'lifts building permit freeze', 'extends comment period
# on solar ordinance' (a preposition makes the instrument something else's).
_INSTRUMENT_NOUN = r"(?:moratori(?:um|ums|a)|bans?|ordinances?|by-?laws?)"
_OBJECT_WORD = (r"(?!(?:on|of|for|to|in|at|with|from|by|about|over|and|or|as|but|while|after|before|into|"
                r"against|amid|despite)\b)[^\s,;:|]+")
_SUBJECT_WORD = (r"(?!(?:and|or|as|but|while|after|before|when|because|since|though|although|until|amid|"
                 r"despite|so|then|keeps?|kept|stays?|stayed|remains?|remained)\b)[^\s,;:|]+")


def _acts_on_instrument(active: str, passive: str) -> re.Pattern:
    """'<active verb> ... <instrument>' or '<instrument> ... (is|was)? <passive>'."""
    alternatives = [rf"\b{_INSTRUMENT_NOUN}(?:\s+{_SUBJECT_WORD}){{0,4}}?\s+"
                    rf"(?:(?:is|was|are|were|has|have)\s+)?(?:been\s+)?(?:{passive})\b"]
    if active:
        alternatives.insert(0, rf"\b(?:{active})\s+(?:{_OBJECT_WORD}\s+){{0,4}}?{_INSTRUMENT_NOUN}\b")
    return re.compile("|".join(alternatives), re.I)


_EXTENDED = _acts_on_instrument(r"extend|extends|extended", r"extended")
_LIFTED = _acts_on_instrument(r"lift|lifts|lifted|repeal|repeals|repealed|rescind|rescinds|rescinded",
                              r"lifted|repealed|rescinded")
_EXPIRED = _acts_on_instrument("", r"expires|expired")

# '<Name> Solar|Wind ...' in a sentence-case headline.
_PROJECT_NAME = re.compile(
    r"\b((?:[A-Z][\w'’&.-]*\s+){1,4}?)(Solar|Wind|Energy\s+Storage|Battery\s+Storage|BESS)"
    r"(?:\s+(Farm|Project|Energy\s+Center|Energy\s+Park|Park|Center|Facility|Ranch|Energy|Array|I{1,3}|LLC))?\b")
_NOT_A_NAME = {
    "the", "a", "an", "new", "proposed", "planned", "large", "big", "massive", "huge", "local", "rural",
    "county", "city", "town", "township", "village", "state", "board", "commission", "council", "residents",
    "neighbors", "opponents", "utility", "commercial", "industrial", "community", "offshore", "onshore",
    "utility-scale", "grid-scale", "more", "no", "anti", "pro", "and", "or", "of", "in", "on", "for", "at",
    "us", "u.s.", "american", "national", "federal", "clean", "green", "renewable", "why", "how", "what",
    "when", "where", "who", "this", "that", "these", "those", "another", "first", "second", "latest",
}
_PLACE_WORDS = {"county", "parish", "township", "city", "town", "village", "state", "board", "commission",
                "council", "the"}
_GOVERNMENT_AFTER_COUNTY = re.compile(
    r"\b(?:county|parish)\s+(?:board|commission|commissioners?|supervisors?|council|legislat\w*|fiscal\s+court|"
    r"planning|zoning|officials?|leaders?|lawmakers|government|judge|administrators?|adopts?|adopted|approves?|"
    r"approved|passes|passed|extends?|extended|enacts?|enacted|imposes?|imposed|bans?|banned|votes?|voted)\b",
    re.I)
_MUNICIPAL_FORM = [
    (re.compile(r"\btownship\b", re.I), "Township"),
    (re.compile(r"\btown\s+of\b|\btown\s+(?:board|council)\b", re.I), "Town"),
    (re.compile(r"\bcity\s+of\b|\bcity\s+(?:council|commission)\b", re.I), "City"),
    (re.compile(r"\bvillage\s+of\b|\bvillage\s+(?:board|council)\b", re.I), "Village"),
]

# ── text ─────────────────────────────────────────────────────────────────────

_DASHES = "".join(map(chr, (0x2012, 0x2013, 0x2014, 0x2015, 0x2212)))  # figure, en, em, bar, minus
_TAG = re.compile(r"<[^>]+>")


def no_dashes(text: str) -> str:
    """En and em dashes (and their kin) out: '-' between digits, ', '
    elsewhere."""
    t = re.sub(rf"(?<=\d)\s*[{_DASHES}]\s*(?=\d)", "-", text or "")
    t = re.sub(rf"\s*[{_DASHES}]+\s*", ", ", t)
    return re.sub(r",\s*,", ",", t).strip(" ,")


def plain(text: str) -> str:
    """HTML stripped and unescaped, whitespace collapsed, no dashes."""
    t = html.unescape(_TAG.sub(" ", text or ""))
    return no_dashes(" ".join(t.split()))


def tidy(title: str) -> str:
    """GDELT's spaced punctuation closed up: 'solar - farm' -> 'solar-farm',
    'county ' s' -> "county's", '9 , 000' -> '9,000', ' , ' -> ', '. Quotes
    are left as GDELT gives them."""
    t = re.sub(r"(?<=\w)\s+-\s+(?=\w)", "-", title)
    t = re.sub(r"(?<=\w)\s*['’]\s*(?=(?:s|t|re|ve|ll|d)\b)", "'", t)
    t = re.sub(r"(?<=\d)\s+,\s+(?=\d{3}\b)", ",", t)
    t = re.sub(r"(?<=\d)\s+\.\s+(?=\d)", ".", t)
    t = re.sub(r"\s+([,;:.!?%)])", r"\1", t)
    t = re.sub(r"([($])\s+", r"\1", t)
    return " ".join(t.split()).strip()


# A masthead GDELT leaves on the end of a headline: after a bar ('| News,
# Sports, Jobs-Lawrence Journal-World: news, information ... in Lawrence,
# Kansas'), after a comma where the source had a dash (', KIWA Radio',
# ', WRUL-FM', ', Inside INdiana Business'), or glued on with a hyphen
# ('-Las Vegas Sun News', '-Illinois Times, the capital city weekly ...'),
# sometimes with the outlet's tagline after it. It names the outlet, not the
# story, so it must neither place a lead nor stay in its description.
_MASTHEAD_WORD = (r"(?:News|Times|Journal|Tribune|Gazette|Herald|Post|Press|Daily|Radio|Coalition|Enterprise|"
                  r"Chronicle|Dispatch|Register|Courier|Observer|Sentinel|Leader|Sun|Business|Reporter|Today|"
                  r"Weekly|Bulletin|Democrat|Republican|Independent|Telegraph|Examiner|Patch)")
# Masthead words that are ordinary nouns too: a masthead after a comma
# (', San Diego Union-Tribune', ', Sacramento Bee'), never when glued on with
# a hyphen ('Wind Farm Gets State-Level Review').
_MASTHEAD_NOUN = (r"(?:Telegram|Statesman|Constitution|Union|Star|Record|Review|Globe|Bee|Ledger|Advocate|"
                  r"Citizen|Californian)")
_MASTHEAD_TAIL = re.compile(
    # The masthead word may carry a hyphen-glued prefix: 'Union-Tribune'.
    r"(,\s+|-)((?:The\s+)?((?:[A-Z][\w.&'-]*\s+){0,5})(?:[A-Z][\w.&']*-)?"
    r"(?:" + _MASTHEAD_WORD + r"|(?P<noun>" + _MASTHEAD_NOUN + r"))"
    + r"|[KW][A-Z]{2,3}(?:-(?:FM|AM|TV))?(?:\s+Radio)?"
    # A network affiliate: ', NBC Los Angeles', ', Fox 5 Atlanta'.
    r"|(?:NBC|ABC|CBS|FOX|Fox|PBS|NPR|CW)(?:\s+\d+)?(?:\s+[A-Z][\w.'-]*){1,3})"
    # The outlet's tagline: ': news, information ...', or its sections
    # (' News Events & Video for Pagosa Springs Colorado').
    r"(?:\s*[,:]\s+[a-z][^|]*|\s+(?:News\s+)?(?:Events|Video|Sports|Jobs|Obituaries|Opinion|Weather)\b[^|]*)?"
    r"\s*$")


def description_of(title: str) -> str:
    """The tidied headline without a trailing masthead or section label
    ('... sets public hearing | Amsterdam', '..., KIWA Radio')."""
    m = re.match(r"(.{20,}?)\s*\|\s*(.+)$", title)
    if m and ((len(m.group(2)) <= 40 and len(m.group(2).split()) <= 4)
              or re.search(rf"\b(?:{_MASTHEAD_WORD}|{_MASTHEAD_NOUN})\b", m.group(2))):
        title = m.group(1).rstrip(" ,;:")
    m = _MASTHEAD_TAIL.search(title)
    # An ordinary noun is a masthead only after a comma and a name of its own
    # (', Chelsea Record'), not a list's last item (', And CEQA Review').
    if m and m.group("noun") and (m.group(1) == "-" or not m.group(3)
                                  or m.group(3).split()[0] in ("And", "Or")):
        m = None
    if m and m.start() >= 20:
        before = title[:m.start()].split()
        # Glued on with a hyphen after a capitalized word, a masthead needs two
        # words of its own: "Prairie Edge-West Central Tribune" is one,
        # "Battery-Energy Storage Report" in a title-case headline is not.
        if (m.group(1) != "-" or (before and before[-1].islower())
                or len((m.group(3) or "").split()) >= 1):
            return title[:m.start()].rstrip(" ,;:")
    return title


def fold_title(title: str) -> str:
    """Identity of a headline within one response: lowercase words only."""
    return " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))


# ── per-headline judgements ──────────────────────────────────────────────────

def technologies(title: str) -> list[str]:
    t = _STORAGE_TRADE.sub(" ", _BUILDING_SOLAR.sub(" ", _SMALL_SOLAR.sub(" ", title)))
    found = [tech for tech, rx in TECH_PATTERNS.items() if rx.search(t)]
    if "battery_storage" in found and _NOT_STORAGE.search(t):
        found.remove("battery_storage")
    return found


# A setback that is a loss, not a distance ("Details of BP venture $700m
# offshore wind setback surface", "developer faces setbacks"): read as 'loss'
# wherever a setback would count as a rule, a hint or a local word.
_SETBACK_LOSS = re.compile(
    r"(?:\b(?:fac(?:e|es|ed|ing)|suffer(?:s|ed|ing)?|another|major|big|financial|costly)\b|\$[\d.,]+\s*[mbk]\w*)"
    r"(?:\s+[\w$.,'-]+){0,4}?\s+setbacks?\b|\bsetbacks?\s+(?:surfaces?|hits?)\b", re.I)


def _no_losses(title: str) -> str:
    return _SETBACK_LOSS.sub(lambda m: re.sub(r"(?i)setback", "loss", m.group(0)), title)


def hints(title: str) -> list[str]:
    title = _no_losses(title)
    return list(dict.fromkeys(name for rx, name in MECHANISM_HINTS if rx.search(title)))


def opposition_words(title: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).lower() for m in OPPOSITION_GUARD.finditer(_no_losses(title))))


def opposed(title: str) -> bool:
    """An opposition word; residents or neighbors only as the ones acting."""
    title = _no_losses(title)
    for m in OPPOSITION_GUARD.finditer(title):
        if m.group(0).lower() not in WEAK_OPPOSITION or not _FOR_THEM.search(title[:m.start()]):
            return True
    return False


def federal_only(title: str) -> bool:
    return bool(FEDERAL_ONLY.search(title)) and not LOCAL_WORD.search(_no_losses(title))


def foreign(title: str) -> bool:
    return bool(FOREIGN.search(title)) and not named_states(title)


def off_scope(title: str) -> str:
    """Why a renewable headline with an opposition word is still not a local
    US fight, or ''."""
    if federal_only(title) or (OFFSHORE.search(title) and not LOCAL_WORD.search(_no_losses(title))):
        return "federal"
    if foreign(title):
        return "foreign"
    if TRADE.search(title):
        return "trade"
    if COMMERCIAL.search(title):
        return "commercial"
    return ""


def project_fight(title: str) -> bool:
    if PROJECT_FIGHT.search(title):
        return True
    return any(not (INSTRUMENT_RX.search(m.group(1)) or RULE_RX.search(m.group(1) + " for")
                    or re.search(r"\b(?:rules?|regulations?|restrictions?|limits?|standards?|zoning)\b",
                                 m.group(1), re.I))
               for m in PROJECT_APPROVAL.finditer(title))


def entity_type(title: str, project_name: str) -> str:
    """restriction for a headline about an instrument (a moratorium, ban,
    ordinance, bylaw or a pause on a class of development, unless it is about
    a named project's fight; setback or zoning rules, unless any project fight
    is described); else contested_project."""
    title = _no_losses(title)
    if ((INSTRUMENT_RX.search(title) or PAUSE_RX.search(title))
            and not (project_name and project_fight(title))):
        return "restriction"
    if RULE_RX.search(title) and not project_fight(title):
        return "restriction"
    return "contested_project"


def status(title: str, entity: str) -> str:
    """The status only when the headline states it outright (module docstring)."""
    if NOT_OUTRIGHT.search(title):
        return ""
    if entity == "restriction":
        if _LIFTED.search(title):
            return "lifted"
        if _EXPIRED.search(title):
            return "expired"
        if _EXTENDED.search(title):
            return "extended"
        return ""
    for rx, value in ((_CANCELLED, "cancelled"), (_DENIED, "rejected"), (_APPROVED, "approved")):
        m = rx.search(title)
        if not m:
            continue
        decided = _decided_object(title, m)
        if decided is None or _OTHER_OBJECT.search(decided):
            return ""
        if value == "approved" and _OVER_OBJECTIONS.search(title):
            return "approved_after_opposition"
        return value
    return ""


# Words that can follow a passive or intransitive decision ("Solar farm appeal
# denied by board", "... withdrawn 4-1"): the decision still acts on the subject.
_AFTER_PASSIVE = re.compile(
    r"(?:by|in|at|on|after|before|for|amid|despite|over|again|unanimously|twice|today|tuesday|monday|"
    r"wednesday|thursday|friday|saturday|sunday|\d[\d-]*)\b", re.I)


# What may stand between a decision verb and the project it decides: a
# determiner, a size or sum, a capitalized name, or the project's own
# permission ("denies permit for $1.2B Southpaw Solar project", "OKs special
# use permit for solar farm").
_PROJECT_WORDS = {
    "the", "a", "an", "its", "their", "his", "her", "our", "this", "that", "these", "those", "another",
    "two", "three", "four", "five", "second", "third", "new", "proposed", "planned", "controversial",
    "contested", "disputed", "embattled", "large", "larger", "big", "massive", "huge", "small", "utility-scale",
    "grid-scale", "commercial", "industrial", "community", "local", "rural", "remaining", "final", "latest",
    "more", "all", "both", "several", "acre", "acres", "megawatt", "megawatts", "mw", "gw", "mwh", "million",
    "billion", "special", "conditional", "use", "special-use", "conditional-use", "site", "siting", "building",
    "zoning",
}
_PERMISSION_NOUNS = {"permit", "permits", "rezoning", "application", "applications", "plan", "plans", "proposal",
                     "proposals", "approval", "request", "certificate"}
_SIZE = re.compile(r"^\$?\d[\d,.]*[kmb]?(?:-[a-z]+)?$|^\$\d", re.I)
# A preposition or conjunction puts the project in another phrase ("rejects
# lawsuit against solar farm"), whatever the case ("Lawsuit Against Solar Farm").
_LINK_WORDS = {"against", "of", "for", "on", "over", "to", "with", "from", "about", "by", "in", "at", "into",
               "near", "after", "before", "amid", "despite", "and", "or", "versus", "vs"}
# In title case a capital marks no name: "Approves Measure Opposing Solar Farm".
_OPPOSING = re.compile(r"\b(?:oppos\w*|against)\b", re.I)


def _tech_start(title: str, pos: int) -> int:
    """Offset of the first technology the headline names at or after pos, or
    -1 (technologies(), with its exclusions blanked to the same length)."""
    def blank(m):
        return " " * len(m.group(0))
    masked = _STORAGE_TRADE.sub(blank, _BUILDING_SOLAR.sub(blank, _SMALL_SOLAR.sub(blank, title)))
    starts = [m.start() for tech in technologies(title) if (m := TECH_PATTERNS[tech].search(masked, pos))]
    return min(starts, default=-1)


def _project_words(between: str) -> bool:
    """Whether the words between a decision verb and the technology are only
    what a project is named, sized or permitted by (_PROJECT_WORDS)."""
    if re.search(r"[,;:|]", between):
        return False
    words = between.split()
    for i, w in enumerate(words):
        lw = w.lower().strip("'’\".")
        if lw in _PROJECT_WORDS or lw in _PERMISSION_NOUNS or _SIZE.match(lw):
            continue
        if lw in ("for", "of") and i and words[i - 1].lower() in _PERMISSION_NOUNS:
            continue
        if w[:1].isupper() and lw not in _LINK_WORDS:
            continue
        return False
    return not (_OTHER_OBJECT.search(between) or _OPPOSING.search(between))


def _decided_object(title: str, verb: re.Match) -> str | None:
    """What the decision word acts on: the words between it and the first
    technology after it, when that is within six words; they must be only a
    project's determiners, sizes, names or permission (_project_words), or
    the decision is on something else (None: "rejects lawsuit against solar
    farm", "denies appeal of solar farm permit"). When no technology follows
    within six words, the subject before it ("Solar farm appeal denied"),
    unless the verb has an object of its own in its clause, which is then not
    the project (None: "Mount Jackson delays solar vote, abandons community
    center land purchase")."""
    start = _tech_start(title, verb.end())
    between = title[verb.end():start] if start >= 0 else ""
    if start >= 0 and len(between.split()) <= 6:
        return between if _project_words(between) else None
    rest = re.split(r"[,;:|]", title[verb.end():], maxsplit=1)[0].strip()
    if rest and not _AFTER_PASSIVE.match(rest):
        return None
    return title[:verb.start()]


def project_name(title: str) -> str:
    """'<Name> Solar' in a sentence-case headline, else ''."""
    if title_case(title):
        return ""
    for m in _PROJECT_NAME.finditer(title):
        words = m.group(1).split()
        if m.start(1) == 0:
            # The headline's first word is capitalized anyway.
            while words and words[0].lower().strip(".,'") in _NOT_A_NAME:
                words.pop(0)
            if len(words) == len(m.group(1).split()) == 1:
                continue
        if not words or any(w.lower().strip(".,'") in _PLACE_WORDS for w in words):
            continue
        name = " ".join(words + [m.group(2)] + ([m.group(3)] if m.group(3) else []))
        return " ".join(name.split())
    return ""


def jurisdiction_type(title: str, entity: str, place) -> str:
    if entity != "restriction" or not place.county and not place.municipality:
        return ""
    if place.municipality:
        for rx, value in _MUNICIPAL_FORM:
            if rx.search(title):
                return value
        return ""
    if _GOVERNMENT_AFTER_COUNTY.search(title):
        return "Parish" if place.county.endswith(" Parish") else "County"
    return ""


def score(hint_list: list[str], confidence: str, domain: str) -> float:
    """After data-center-map signal_harvest.priority(), without recency."""
    s = 0.0
    if hint_list:
        s += 3.0
    if "moratorium" in hint_list or "withdrawal" in hint_list:
        s += 1.5
    s += {"high": 3.0, "medium": 1.5, "state_only": 0.5}.get(confidence, 0.0)
    if _domain_in(domain, DEMOTED_DOMAINS):
        s -= 2.0
    return round(s, 1)


def _domain_in(domain: str, domains: set[str]) -> bool:
    d = (domain or "").lower().removeprefix("www.")
    return any(d == x or d.endswith("." + x) for x in domains)


def seen_date(value: str) -> str:
    m = re.match(r"(\d{4})(\d{2})(\d{2})", value or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


# ── query label ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _labels() -> dict[str, str]:
    """query text -> label, from this source's requests in config/sources.yaml."""
    try:
        cfg = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    for s in cfg.get("sources", []):
        if s.get("source_id") == SOURCE_ID:
            return {" ".join(str((r.get("params") or {}).get("query", "")).split()): r.get("label", "")
                    for r in s.get("requests", []) if r.get("label")}
    return {}


def query_label(url: str) -> str:
    """The configured label of the query in a manifest URL, else the query text."""
    query = " ".join((parse_qs(urlsplit(url or "").query).get("query") or [""])[0].split())
    if not query:
        return "unlabelled"
    return _labels().get(query) or f"'{query[:80]}'"


# ── extract ──────────────────────────────────────────────────────────────────

def _text(art: dict, key: str) -> str:
    """A field of an article, '' when it is missing or not a string."""
    value = art.get(key)
    return value if isinstance(value, str) else ""


def extract(raw_path: Path, source: dict) -> list[dict]:
    payload = json.loads(read_raw(Path(raw_path)).decode("utf-8-sig"))
    # Any valid JSON gets past fetch.py; a payload of another shape has no
    # articles, and an article or field of another shape is skipped or blank.
    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        return []
    label = query_label(source.get("url", ""))
    kept: dict[str, dict] = {}        # folded title -> lead
    seen_urls: set[str] = set()
    for art in articles:
        if not isinstance(art, dict):
            continue
        if _text(art, "language").strip() != "English":
            continue
        if _text(art, "sourcecountry").strip() != "United States":
            continue
        url = strip_tracking(_text(art, "url"))
        if not url.startswith(("http://", "https://")):
            continue
        key = normalize_url(url)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        domain = (_text(art, "domain") or urlsplit(url).netloc).lower().removeprefix("www.")
        if _domain_in(domain, REHOST_DOMAINS):
            continue
        raw_title = plain(_text(art, "title"))
        title = tidy(raw_title)
        techs = technologies(title)
        found = hints(title)
        if not techs or not (found or opposed(title)) or off_scope(title):
            continue
        folded = fold_title(description_of(title))
        if folded in kept:
            kept[folded]["_also"].append(url)
            continue
        place = locate(description_of(title))
        name = project_name(title)
        etype = entity_type(title, name)
        if etype == "restriction":
            name = ""
        hint_note = ", ".join(found) if found else "none; opposition words: " + ", ".join(opposition_words(title))
        notes = [
            f"GDELT {label} query",
            f"seen {seen_date(_text(art, 'seendate'))} (crawl date)",
            domain,
            f"place {place.confidence}: {place.reason}",
            f"hints: {hint_note}",
            f"score {score(found, place.confidence, domain)}",
        ]
        kept[folded] = {
            "entity_type": etype,
            "state": place.state,
            "county": place.county,
            "municipality": place.municipality,
            "jurisdiction_type": jurisdiction_type(title, etype, place),
            "project_name": name,
            "technology": ";".join(techs),
            "description": description_of(title),
            "source_url": url,
            "evidence_text": raw_title[:1000],
            "access": "snippet",
            "source_kind": "news",
            "status": status(title, etype),
            "reviewer_notes": "; ".join(n for n in notes if n),
            "_also": [],
        }
    out = []
    for lead in kept.values():
        also = lead.pop("_also")
        if also:
            lead["reviewer_notes"] += "; also: " + " ".join(also)
        out.append({k: no_dashes(v) if isinstance(v, str) and k != "source_url" else v for k, v in lead.items()})
    return out
