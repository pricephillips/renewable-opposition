"""Extractor for Legistar legislative matters (source_id legistar_renewable_matters).

Input: one raw JSON list of matters from the Granicus Legistar Web API,
https://webapi.legistar.com/v1/<client>/matters filtered on renewable terms in
MatterTitle (config/sources.yaml), as stored by fetch.py (gzipped). fetch.py
makes one request per active client in config/legistar_clients.json, so the
raw file belongs to the client named in the manifest row's url
(/v1/<client>/matters); that client's entry, read here read-only, says which
government it is: state, county, jurisdiction and jurisdiction_type.

After pricephillips/data-center-map legistar_probe.py: its INSTRUMENT, UNDO and
ADOPTED_STATUS patterns, the public LegislationDetail link and the rule that a
client is trusted only once its body names match its government are copied
here (with attribution, never imported).

Output: leads (parse.py sets review_status 'lead') for matters whose title is
about SITING solar, wind or battery storage facilities. A matter is read on its
MatterTitle plus MatterName, and kept only when all of these hold:

  1. A renewable technology is named as a facility, as whole words: "solar"
     followed within three words by energy, power, farm, facility, project,
     array, generating, garden, system and the like (so "Solar Powered
     Portable Message Signs", "SolarWinds" and "Solar Atmospheres" are not),
     "photovoltaic", "commercial solar", "wind" followed by energy, farm,
     turbine, facility, conversion and the like, "windmill", "battery ...
     storage", "energy storage", "BESS", or a named facility ("Bear Valley
     Solar Project"). "Renewable energy" with no technology counts only with a
     strong instrument (a moratorium, ban or prohibition, a zoning, text or code
     amendment, a development code, or an element of the general plan), a
     contest, or a decision on a named facility; its technology is left blank
     for the reviewer.
  2. The county is not acting as an energy customer, landlord or funder:
     contracts, bids, purchases, leases, grants, rebates, donations, power
     purchase or net-metering agreements, renewable energy credits, group
     buys, PACE, bonds and tax abatements, payments, consultant services,
     installations of solar at county buildings, solar-powered devices, EV
     charging, buses, memberships, MOUs and endorsements are dropped
     (CUSTOMER). A contest (below) overrides this, since "Grant the appeal"
     is not a grant.
  3. It does not only undo something: pricephillips/data-center-map
     legistar_probe.py UNDO (repeal, rescind, lift, terminate, end the
     moratorium; copied, not imported) drops a matter unless it also adopts
     something new (repeal and replace, establish, impose, "and adopt").
  4. It is not about accessory, rooftop, residential or small systems
     ("Residential Accessory Wind Energy Systems", "accessory small-scale
     solar energy system"), unless it is a contest, and it is not a
     closed-session list of litigation (which names cases, never the
     county's position). A matter hidden from the web
     (MatterRestrictViewViaWeb) has no public page and is skipped.
  5. It carries a signal, which also decides the entity:
       contest      appeal, denial, opposing, objection, protest, or public
                    comments regarding a facility: contested_project, named
                    or not. (Names such as "Zoning Board of Appeals" are
                    removed before matching.)
       decision     conditional or special use permit, use permit, special
                    exception, rezoning or zone change, site plan,
                    environmental impact report, negative declaration,
                    development agreement, certification, well permits,
                    approval: contested_project, but only for a NAMED
                    facility. A routine permit on an unnamed "Commercial Solar
                    Energy System" shows neither a contest nor a name a
                    reviewer could follow, so it is dropped (the raw file
                    keeps it).
       instrument   data-center-map legistar_probe.py INSTRUMENT (moratorium,
                    prohibit, ban, pause, temporary suspension; copied), plus
                    ordinance, a zoning, text or code amendment, development
                    code, unified development ordinance, code of ordinances,
                    setback, overlay, regulations, land use plan or element,
                    general or comprehensive plan, siting standards:
                    restriction.
     A contest wins over a decision, and a decision on a named facility wins
     over an instrument ("Zoning Amendment and Conditional Use Permit for the
     Overnight Solar Facility Project" is a project, not a restriction).

project_name is the facility name when the title gives one: capitalized words
before Solar, Wind or a storage term, with any capitalized suffix (Project,
Farm, Facility, Power Facility, I & II), and nothing taken from words such as
Commercial, Utility-scale or County. An applicant entity ("RPIL Solar 1, LLC")
is a name only when the title calls it a project ("the Soda Mountain Solar,
LLC solar energy project") or it carries a facility suffix ("Joshua Tree Solar
Farm, LLC"). Titles in capitals are not read for names.

Within one raw file each matter (MatterId) is emitted once, and matters with
the same title (a work session and the regular meeting, a hearing continued
to a later date) become one lead: the one with a passed date and the latest
introduction, the others listed in reviewer_notes.

Fields. source_url is the matter's public page,
https://{client}.legistar.com/LegislationDetail.aspx?ID={MatterId}&GUID={MatterGuid},
through common.strip_tracking. evidence_text is the title verbatim (plus
MatterName when it adds words), whitespace collapsed, em and en dashes
replaced, HTML removed, at most 1000 characters. description is one sentence
from the title's own words. state, county, municipality and jurisdiction_type
come from the client's entry: a county client places every lead in its county
(the client was verified against its body names), a city client in its city
and county. A title that names another county ("... of Riverside County" in a
San Bernardino matter) keeps the state but gets county '' and a reviewer note,
and a client missing from config/legistar_clients.json places nothing. No
town is filled from the title; a "Town of X" it names is noted instead.

status is always '': the matter status (Agenda Ready, Passed, Filed) is the
clerk's record of this file, not the instrument's status or the project's
outcome; it goes in reviewer_notes with the dates. mechanisms and
severity_score stay '' (hints such as moratorium or setback go in
reviewer_notes). adopted_date, for restrictions only, is MatterPassedDate[:10]
when the matter has one, its MatterStatusName says it passed
(data-center-map's ADOPTED_STATUS: adopt, pass, approve, enact, final action)
and its title does not describe a proposal, discussion, presentation,
referral or model (Legistar also fills MatterPassedDate for committee items
that were only filed or discussed, and a resolution directing a hearing on
proposed amendments is not their adoption). first_event_date stays ''.

source_kind is 'other'. A matter page is the clerk's record of a legislative
file: it usually attaches the ordinance, resolution or staff report, but the
page itself is neither the instrument, nor its minutes, nor an official copy of
either (classify.SOURCE_KINDS). promote_reviewed.evidence makes a restriction
whose source_kind is instrument, minutes or official_copy and whose access is
opened or archived a primary source, verified; with 'minutes' or
'official_copy' here, a reviewer who opened the matter page and flipped access
without reading the attachment would verify a restriction by accident. 'other'
is in neither classify.INSTRUMENT_KINDS nor EVENT_KINDS, so nothing this module
writes can verify a restriction or a project outcome; a reviewer who reads the
attached instrument or minutes sets source_url and source_kind for what they
read. access is 'snippet': an API record is not a read document.

reviewer_notes: "Legistar <client> matter <MatterFile> (<MatterTypeName>,
<MatterStatusName>, introduced <date>, passed <date>)", then the body, the
signal that kept the matter and its words, how the lead was placed, and any
hints (mechanism words, appellants named, data centers named, matters merged).

Reads only: the raw file and config/legistar_clients.json. Writes nothing.
"""
from __future__ import annotations

import html
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from common import ROOT, read_raw, strip_tracking

CLIENTS_PATH = ROOT / "config" / "legistar_clients.json"
WEB = "https://{client}.legistar.com/LegislationDetail.aspx?ID={id}&GUID={guid}"
CLIENT_IN_URL = re.compile(r"^https?://webapi\.legistar\.com/v1/([A-Za-z0-9_-]+)/matters\b", re.I)
MAX_EVIDENCE = 1000
MAX_SUMMARY = 240
log = logging.getLogger(__name__)

# ── Text cleaning ────────────────────────────────────────────────────────────

_TAG = re.compile(r"<[^>]+>")
_SPACED_DASH = re.compile(r"\s+[\u2012\u2013\u2014\u2015\u2212]+\s+")
_DASH = re.compile(r"[\u2012\u2013\u2014\u2015\u2212]+")


def clean(text: str | None) -> str:
    """HTML removed, entities decoded, em and en dashes replaced (', ' when
    spaced, '-' when not), whitespace collapsed."""
    t = html.unescape(_TAG.sub(" ", text or ""))
    t = _SPACED_DASH.sub(", ", t.replace("\u00a0", " "))
    t = _DASH.sub("-", t)
    return " ".join(t.split())


def cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "..."


def mostly_capitals(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.7


# ── Technology ───────────────────────────────────────────────────────────────

_NEAR = r"(?:[\s,/&+-]+(?:and|or|[a-z][\w'-]*)){0,3}?[\s,/&+-]+"
SOLAR_NOUNS = (r"(?:energy|power|farms?|facilit(?:y|ies)|projects?|arrays?|generat\w*|electric\w*|gardens?|"
               r"plants?|fields?|developments?|installations?|systems?|parks?|centers?|stations?|pv|panels?|"
               r"collectors?|uses?|ordinances?|zoning|overlay|regulations?|moratori(?:um|a)|siting|thermal)")
WIND_NOUNS = (r"(?:energy|power|farms?|facilit(?:y|ies)|projects?|turbines?|generat\w*|conversion|systems?|"
              r"resources?|developments?|ordinances?|overlay|towers?|regulations?|moratori(?:um|a)|siting|"
              r"permits?|electric\w*)")
TECH = {
    "solar": re.compile(
        rf"\bsolar(?:[- ]photovoltaic)?{_NEAR}{SOLAR_NOUNS}\b|\bphotovoltaics?\b|"
        r"\b(?:commercial|utility[- ]scale|community|large[- ]scale|ground[- ]mounted|industrial|"
        r"principal[- ]use)\s+solar\b", re.I),
    "wind": re.compile(rf"\bwind{_NEAR}{WIND_NOUNS}\b|\bwind\s*mills?\b|\bWECS\b|"
                       r"\b(?:commercial|utility[- ]scale|large[- ]scale|industrial)\s+wind\b", re.I),
    "battery_storage": re.compile(rf"\bbatter(?:y|ies){_NEAR}storage\b|\benergy[\s-]+storage\b|\bBESS\b", re.I),
}
RENEWABLE = re.compile(r"\brenewable\s+energy\b|\brenewable\s+(?:generation|facilit\w*|projects?|developments?)\b",
                       re.I)

# ── Signals ──────────────────────────────────────────────────────────────────

# Board names and agenda boilerplate that contain signal words but are not signals.
BOARD_NAMES = re.compile(r"\b(?:zoning\s+)?board\s+of\s+(?:zoning\s+)?(?:appeals?|adjustments?)\b|\bZBA\b|"
                         r"\bappeals?\s+board\b|\bcourt\s+of\s+appeals?\b|"
                         r"\bapprove(?:,\s*(?:conditionally\s+approve|modify))*,?\s+or\s+deny\b", re.I)
CONTEST = re.compile(
    r"\bappeal(?:s|ed|ing)?\b|\bappellants?\b|\bden(?:y|ies|ied|ying|ial)\b|\boppos(?:e|es|ed|ing|ition)\b|"
    r"\bobjections?\b|\bprotests?\b|\bcomments?\s+(?:made\s+|received\s+)?(?:by|from|regarding|concerning|on)\b",
    re.I)
DECISION = re.compile(
    r"\bconditional\s+use\b|\bspecial\s+use\b|\buse\s+permits?\b|\bCUP\b|\bSUP\b|\bspecial\s+exceptions?\b|"
    r"\brezon(?:e|es|ed|ing)\b|\bzone\s+change\b|\bzoning\s+(?:map\s+)?amendment\b|\bsite\s+plans?\b|"
    r"\benvironmental\s+impact\s+(?:report|statement)\b|\bEIR\b|\bnegative\s+declaration\b|"
    r"\bdevelopment\s+agreement\b|\bcertif(?:y|ied|ication)\b|\bwell\s+permits?\b|\bgroundwater\s+wells?\b|"
    r"\bapprov(?:e|es|ed|al|ing)\b|\bpolicy\s+plan\s+amendment\b|\bgeneral\s+plan\s+amendment\b", re.I)
# data-center-map legistar_probe.py INSTRUMENT, copied verbatim.
DCM_INSTRUMENT = re.compile(
    r"\b(moratori(um|a)|prohibit\w*|ban|bans|banning|pause|"
    r"temporary (suspension|halt|stay))\b", re.I)
STRONG_INSTRUMENT = re.compile(
    r"\b(?:zoning|text|code|ordinance|development\s+code)\s+amendments?\b|\bamendments?\s+to\s+the\s+text\b|"
    r"\bamend(?:s|ed|ing)?\s+(?:the\s+)?(?:\w+\s+){0,3}?(?:development|zoning|land\s+use)\s+code\b|"
    r"\bdevelopment\s+code\b|\bunified\s+development\s+ordinance\b|\bzoning\s+ordinance\b|"
    r"\bland\s+(?:use|development)\s+(?:code|ordinance)\b|\belement\s+of\s+the\s+(?:county\s+)?general\s+plan\b|"
    r"\binterim\s+(?:urgency\s+)?ordinance\b", re.I)
INSTRUMENT = re.compile(
    r"\bordinances?\b|\bcode\s+of\s+ordinances\b|\bsetbacks?\b|\boverlays?\b|"
    r"\bregulat(?:e|es|ed|ing|ions?)\b|\bland\s+use\s+(?:plan|element|district|zoning|regulations?|code)\b|"
    r"\b(?:general|comprehensive)\s+plan\b|\b(?:siting|development|performance)\s+standards\b", re.I)

# data-center-map legistar_probe.py UNDO and ADOPTED_STATUS, copied verbatim.
UNDO = re.compile(r"\b(repeal\w*|rescind\w*|rescission|lift\w*|terminat\w*|"
                  r"end(s|ing)? the moratorium)\b", re.I)
ADOPTED_STATUS = re.compile(r"\b(adopt\w*|pass\w*|approv\w*|enact\w*|final action)\b",
                            re.I)
ADOPTS_NEW = re.compile(r"\breplac\w*|\bestablish\w*|\bimpos\w*|\band\s+(?:adopt|enact)\w*|"
                        r"\b(?:adopt|enact)\w*\s+(?:a\s+|the\s+)?(?:new|revised|updated|amended)\b", re.I)
NOT_AN_ADOPTION = re.compile(r"\bpropos\w*|\bdirect(?:ing|s)?\b|\bdiscussion\b|\bpresentation\b|\bintroduc\w*|"
                             r"\bupdate\b|\bmodel\b|\bworkshop\b|\bstudy\b|\bconsider(?:ation)?\b", re.I)
SMALL_SCALE = re.compile(
    r"\b(?:accessory|rooftop|roof[- ]mounted|residential|small[- ]scale|small|on[- ]site)\s+(?:[\w-]+\s+){0,2}?"
    r"(?:solar|wind|windmill|photovoltaic)", re.I)

# The county as an energy customer, landlord or funder. (label, pattern). Each
# pattern is narrow enough not to fire on a siting ordinance's own words
# (decommissioning bonds, lighting standards, operation and maintenance).
# Acronyms are matched in capitals only ("PACE", not "the pace of").
CUSTOMER = [
    ("contract", re.compile(r"\b(?:sub)?contracts?\b|\bchange\s+order\b", re.I)),
    ("bid or purchase", re.compile(r"\bbids?\b|\bprocure\w*|\bpurchas\w*|\brequest\s+for\s+(?:proposals?|"
                                   r"qualifications)\b|(?-i:\bRF[PQ]\b)", re.I)),
    ("lease or county property", re.compile(r"\blease\w*\b|\blicense\s+agreement\b|\bdeed\b|\bcounty[- ]owned\b|"
                                            r"\bcounty\s+property\b|\bowned\s+by\s+(?:the\s+)?(?:\w+\s+){0,3}county\b",
                                            re.I)),
    ("grant or funding", re.compile(r"\bgrants?\b(?!\s+(?:the\s+)?(?:appeal|petition|request|approval|variance|"
                                    r"permit))|\bfunding\b|\bfund\s+transfer\b|\bdiscretionary\s+fund\b|"
                                    r"\bappropriations?\b|\bbudget\b|\brebates?\b|\bincentives?\b|\bdonat\w*|"
                                    r"(?-i:\bARPA\b)", re.I)),
    ("energy purchase", re.compile(r"\bpower\s+purchase\b|\bnet[- ]metering\b|\brenewable\s+energy\s+credits?\b|"
                                   r"\belectricity\s+rates?\b|\bsubscri\w+|\bgroup\s+buy\b|\bclearinghouse\b|"
                                   r"\bproperty\s+assessed\s+clean\s+energy\b|\benergy\s+produced\s+by\b|"
                                   r"\boffset\b[^.;]{0,40}\benergy\s+usage\b|(?-i:\b(?:PPA|RECs|PACE)\b)", re.I)),
    ("finance or payment", re.compile(r"(?-i:\b(?:TEFRA|PILOT)\b)|\btax\s+abatement\b|\bpayment\s+in\s+lieu\b|"
                                      r"\b(?:revenue|conduit|tax[- ]exempt|general\s+obligation)\s+bonds?\b|"
                                      r"\bpayments?\s+(?:to|from)\s+the\s+county\b|\bregarding\s+payments?\b|"
                                      r"\bfair\s+share\b|\bcontribution\s+agreement\b", re.I)),
    ("installation at a county site", re.compile(
        r"\binstall\w*\s+(?:of\s+)?(?:an?\s+|the\s+|additional\s+)*(?:solar|photovoltaic|pv)\b|"
        r"\bsolar\s+(?:panel\s+|pv\s+|energy\s+system\s+)?installations?\b|"
        r"\b(?:county|facility)\s+(?:facility\s+)?operations\b|\bfor\s+(?:the\s+)?county(?:'s|\u2019s)?\s+"
        r"(?:buildings?|facilit\w*|operations?|sites?)\b", re.I)),
    ("services", re.compile(r"\bconsultants?\b|\bconsulting\b|\b(?:engineering|professional|design|support)\s+"
                            r"services\b|\bservices?\s+agreement\b|\bmaintenance\s+(?:agreement|contract|services|"
                            r"terms|plan)\b|\bsupport\s+and\s+maintenance\b|\bsoftware\b", re.I)),
    ("device or vehicle", re.compile(r"\bsolar[- ]powered\b|\bmessage\s+(?:signs?|boards?)\b|"
                                     r"\bsolar[- ]?(?:street\s*)?light(?:s|ing)?\b|\blighting\s+project\b|"
                                     r"\bsolar\s+(?:water\s+)?pumps?\b|\bsolar\s+(?:control\s+)?film\b|\bpavilion\b|"
                                     r"\bcharg\w+\s+stations?\b|\belectric\s+vehicles?\b|(?-i:\bEVs?\b)|"
                                     r"\bbus(?:es)?\b|\bstreetcar\b|\bbatter(?:y|ies)\s+(?:backups?|monitoring)\b|"
                                     r"\bwater\s+monitors?\b|\broofing\b", re.I)),
    ("membership or study", re.compile(r"\bmembership\b|\bconsortium\b|\bresearch\b|\bcuratorial\b|\bpaleontolog\w*|"
                                       r"\bmuseum\b|\bfeasibility\b|\bworkforce\b|\bindustry\s+cluster\b", re.I)),
    ("MOU or endorsement", re.compile(r"\bmemorandum\s+of\s+understanding\b|(?-i:\bMOU\b)|\bendors\w*|\bproclam\w*",
                                      re.I)),
    ("fee waiver", re.compile(r"\bwaiv\w*\b[^.;]{0,60}\bfees?\b", re.I)),
]
# "Installation" is the county's own project unless the title is about the
# rules for installing ("an ordinance regulating solar installations").
SITING_RULE = re.compile(r"\b(?:zoning|development\s+code|land\s+use|setbacks?|siting|moratori\w+|"
                         r"regulat(?:e|es|ing|ions?)|standards\s+for|requirements\s+for)\b", re.I)

# Mechanism words worth a reviewer's eye (never written to mechanisms).
HINTS = [
    ("moratorium", r"\bmoratori(?:um|a)\b"), ("prohibition", r"\bprohibit\w*|\bbans?\b|\bbanning\b"),
    ("setback", r"\bsetbacks?\b"), ("height", r"\bheight\b"), ("noise", r"\bnoise\b"),
    ("overlay district", r"\boverlays?\b"), ("fee", r"\bfees?\b"), ("decommissioning", r"\bdecommission\w*"),
    ("acreage", r"\bacre(?:age)?\s+(?:limit|cap)\w*|\bper\s+acre\b"), ("buffer", r"\bbuffers?\b"),
    ("permit requirement", r"\b(?:conditional|special)\s+use\s+permits?\b"),
]
HINTS = [(label, re.compile(rx, re.I)) for label, rx in HINTS]
CLOSED_SESSION = re.compile(r"\bconference\s+with\s+(?:legal\s+)?counsel\b|\bclosed\s+session\b", re.I)
DATA_CENTER = re.compile(r"\bdata\s*-?\s*cent(?:er|re)s?\b", re.I)
APPELLANT = re.compile(r"\bappellants?\s*(?:/\s*applicant)?\s*:\s*([^.;(]{3,120}?)(?=\s{2,}|[.;(]|\s+original\b|"
                       r"\s+applicants?\s*:|$)|"
                       r"\bappeals?\s+(?:filed\s+)?by\s+([A-Z][^.;,]{2,60}?)\s+of\s+(?:a|the)\b", re.I)
TOWN = re.compile(r"\b(?i:town|township|village|city|community)\s+of\s+([A-Z][\w'-]*(?:\s+(?!Grant\b|Deny\b|"
                  r"Approve\b|Adopt\b|Appellants?\b|Applicants?\b)[A-Z][\w'-]*){0,2})")

# ── Facility names ───────────────────────────────────────────────────────────

_CAP = r"[A-Z][A-Za-z'\u2019.-]*"
NAME_RX = re.compile(
    rf"(?<![\w-])((?:{_CAP}\s+){{1,5}}?)"
    r"(Solar|Wind|Battery\s+Energy\s+Storage|Battery\s+Storage|Energy\s+Storage|BESS)"
    r"((?:\s+(?:&|(?:I{1,3}|IV|V|\d{1,2}|Power|Energy|Farms?|Projects?|Facility|Center|Centre|Arrays?|Gardens?|"
    r"Plant|Station|Ranch|Generating|Storage|Thermal)\b))*)")
SUFFIX_WORDS = {"power", "energy", "farm", "farms", "project", "projects", "facility", "center", "centre",
                "array", "arrays", "garden", "gardens", "plant", "station", "ranch", "generating", "storage"}
NAME_STOP = {
    "appeal", "approve", "approval", "approving", "adopt", "adoption", "conduct", "consideration", "consider",
    "rezoning", "case", "commercial", "residential", "accessory", "municipal", "community", "utility",
    "utility-scale", "county", "planning", "commission", "board", "denial", "decision", "ordinance",
    "resolution", "policy", "plan", "zoning", "amendment", "conditional", "use", "permit", "permits",
    "proposed", "proposal", "large", "small", "large-scale", "small-scale", "ground-mounted", "installation",
    "contract", "the", "a", "an", "of", "for", "and", "discussion", "presentation", "update", "report",
    "model", "regulatory", "guidance", "energy", "renewable", "joint", "public", "hearing", "new", "existing",
    "all", "facility", "facilities", "project", "projects", "interim", "urgency", "temporary", "moratorium",
    "battery", "wind", "solar", "petition", "applicant", "application", "location", "description", "cup",
    "sup", "industrial", "principal", "grow", "switch", "together", "on", "in", "at", "to", "by", "with",
    "regarding", "comments", "certify", "final", "environmental", "impact", "development", "unincorporated",
    "photovoltaic", "electric", "power", "generating", "systems", "system", "lease", "site", "agreement",
}
# What may follow a name: end, punctuation, or one of these words.
NAME_FOLLOW = re.compile(
    r"\s*(?:$|[,;:.)(\]|]|(?:and|zoning|rezoning|appeal|appeals|conditional|cup|site|application|amendment|"
    r"permit|permits|project|projects|facility|facilities|in|on|at|near|located|to|by|for|was|is|proposal|"
    r"proposed|development|expansion|phase|llc|inc|l\.l\.c\.)\b)", re.I)
ENTITY_AFTER = re.compile(r"\s*,?\s*(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|LP|L\.P\.|Company)\b", re.I)
ENTITY_PROJECT = re.compile(
    rf"(?<![\w-])((?:{_CAP}\s+){{0,3}}{_CAP}),?\s+(?:LLC|L\.L\.C\.|Inc\.?)\.?,?\s+(?:\(\w+\)\s+)?"
    r"(?:a\s+)?(?:solar|wind|battery|photovoltaic)(?:\s+\w+){0,2}?\s+(?:project|facility|farm)\b")


TECH_WORDS = frozenset({"solar", "wind", "energy", "power", "battery", "storage", "photovoltaic"})


def _trim_prefix(words: list[str], keep: frozenset = frozenset()) -> list[str]:
    """The name's own words: those after the last stop word (words in keep
    are not stop words here: an entity's name may contain Solar)."""
    kept: list[str] = []
    for w in words:
        if w.lower().strip(".") in NAME_STOP - keep:
            kept = []
        else:
            kept.append(w)
    return kept


def facility_name(title: str) -> tuple[str, str]:
    """(name, how) for the facility a title names, or ('', '')."""
    if mostly_capitals(title):
        return "", ""
    for m in NAME_RX.finditer(title):
        prefix = _trim_prefix(m.group(1).split())
        if not prefix:
            continue
        suffix = m.group(3).split()
        rest = title[m.end():]
        if not NAME_FOLLOW.match(rest):
            continue
        has_suffix = any(w.lower() in SUFFIX_WORDS for w in suffix)
        if ENTITY_AFTER.match(rest) and not has_suffix:
            continue        # an applicant entity, not a facility (unless named as a project below)
        # A lowercase or connector suffix is not part of the name.
        while suffix and suffix[-1] in {"&"}:
            suffix.pop()
        return " ".join(prefix + [" ".join(m.group(2).split())] + suffix), "title"
    m = ENTITY_PROJECT.search(title)
    if m:
        words = _trim_prefix(m.group(1).split(), keep=TECH_WORDS)
        if words:
            return " ".join(words), "applicant entity the title calls the project"
    return "", ""


# ── Client config ────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def load_clients(path: str = str(CLIENTS_PATH)) -> dict[str, dict]:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    return {c["client"].lower(): c for c in spec.get("clients", []) if c.get("client")}


def client_from_url(url: str) -> str:
    m = CLIENT_IN_URL.match((url or "").strip())
    if not m:
        raise ValueError(f"not a Legistar matters URL: {url!r}")
    return m.group(1).lower()


_COUNTY_NAMED = re.compile(r"\b((?:[A-Z][\w.'\u2019-]*\s+){1,3})County\b|\bCounty\s+of\s+((?:[A-Z][\w.'\u2019-]*\s?){1,3})")
_COUNTY_WORD_STOP = {"the", "this", "each", "unincorporated", "entire", "said", "such", "a", "other", "adjacent",
                     "neighboring", "every", "any", "our", "your", "home", "of", "and", "for", "in", "approve",
                     "acting", "authorize", "adopt", "with", "between", "lease", "regular", "special"}


def _base(name: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\s+(county|parish|borough)$", "", (name or "").strip(), flags=re.I).lower())


def other_counties(text: str, own_county: str) -> list[str]:
    """Counties the text names that are not the client's own."""
    t = text.title() if mostly_capitals(text) else text
    own = _base(own_county)
    out = []
    for m in _COUNTY_NAMED.finditer(t):
        words = (m.group(1) or m.group(2) or "").split()
        while words and words[0].lower().strip(".,") in _COUNTY_WORD_STOP:
            words = words[1:]
        if not words:
            continue
        # The client's name may be preceded by other capitalized words
        # ("Unincorporated Baldwin County", "Mojave Desert region of San Bernardino County").
        joined = _base(" ".join(words))
        if own and (joined == own or joined.endswith(own) or own.endswith(joined) and len(joined) > 3):
            continue
        name = " ".join(words) + " County"
        if name not in out:
            out.append(name)
    return out


def placement(client: str, cfg: dict | None, text: str) -> tuple[dict, str]:
    """Location fields for a lead and the note that says how they were set."""
    if cfg is None:
        return ({"state": "", "county": "", "municipality": "", "jurisdiction_type": ""},
                f"not placed: client {client} is not in config/legistar_clients.json, so its government is unverified")
    jtype = (cfg.get("jurisdiction_type") or "").strip()
    juris = (cfg.get("jurisdiction") or "").strip()
    county = (cfg.get("county") or "").strip()
    municipality = ""
    if jtype.lower() not in {"county", "parish", "borough"}:
        m = re.match(r"^(City|Town|Village|Borough|Township)\s+of\s+(.+)$", juris, re.I)
        municipality = m.group(2) if m else juris
        jtype = m.group(1).title() if m else jtype
    fields = {"state": (cfg.get("state") or "").strip().upper(), "county": county, "municipality": municipality,
              "jurisdiction_type": jtype[:1].upper() + jtype[1:]}
    verified = cfg.get("verified_on") or "not yet verified"
    note = f"placed in {juris or county} ({fields['state']}) from config/legistar_clients.json (client checked {verified})"
    others = other_counties(text, county)
    if others:
        fields["county"] = ""
        note = (f"county left blank: the title names {', '.join(others)} besides {county or 'the client'}; "
                f"state {fields['state']} from config/legistar_clients.json")
    return fields, note


# ── Classification ───────────────────────────────────────────────────────────

def technologies(text: str) -> tuple[list[str], bool]:
    """(technology tokens in vocabulary order, whether renewable energy is named generally)."""
    techs = [t for t, rx in TECH.items() if rx.search(text)]
    name, _ = facility_name(text)
    if name:
        low = name.lower()
        if "solar" in low and "solar" not in techs:
            techs.append("solar")
        if "wind" in low and "wind" not in techs:
            techs.append("wind")
        if ("storage" in low or "bess" in low) and "battery_storage" not in techs:
            techs.append("battery_storage")
    order = ["solar", "wind", "battery_storage"]
    return [t for t in order if t in techs], bool(RENEWABLE.search(text))


def _words(rx: re.Pattern, text: str) -> list[str]:
    out = []
    for m in rx.finditer(text):
        w = " ".join(m.group(0).split()).lower()
        if w not in out:
            out.append(w)
    return out


def classify(text: str) -> tuple[str, str, dict]:
    """(entity_type or '', reason, details) for a matter's cleaned title text.
    entity_type '' means drop, and reason says why."""
    sig = BOARD_NAMES.sub(" ", text)
    techs, generic = technologies(sig)
    if not techs and not generic:
        return "", "no renewable facility technology named", {}
    if CLOSED_SESSION.search(sig):
        return "", "closed-session list of litigation (the county's position is not stated)", {}
    contest = _words(CONTEST, sig)
    if not contest:
        for label, rx in CUSTOMER:
            if rx.search(sig) and not (label.startswith("installation") and SITING_RULE.search(sig)):
                return "", f"county as customer, landlord or funder ({label})", {}
    undo = _words(UNDO, sig)
    if undo and not ADOPTS_NEW.search(sig):
        return "", f"undoes something ({', '.join(undo)}) and adopts nothing new", {}
    if not contest and SMALL_SCALE.search(sig):
        return "", "accessory, rooftop, residential or small-scale systems", {}
    decision = _words(DECISION, sig)
    strong = _words(DCM_INSTRUMENT, sig) + _words(STRONG_INSTRUMENT, sig)
    instrument = strong + [w for w in _words(INSTRUMENT, sig) if w not in strong]
    name, how = facility_name(text)
    details = {"techs": techs, "generic": generic, "name": name, "name_how": how, "undo": undo}
    if contest:
        return "contested_project", "contest: " + ", ".join(contest[:4]), details
    if decision and name:
        return "contested_project", "decision on a named facility: " + ", ".join(decision[:4]), details
    if instrument and (techs or strong):
        return "restriction", "instrument: " + ", ".join(instrument[:4]), details
    if instrument:
        return "", "renewable energy named generally, without a moratorium, ban or code amendment", {}
    if decision:
        return "", "permit or approval for an unnamed facility, with no contest shown", {}
    return "", "no siting instrument or project decision", {}


# ── Rows ─────────────────────────────────────────────────────────────────────

def _date(value) -> str:
    v = (value or "").strip() if isinstance(value, str) else ""
    return v[:10] if re.match(r"\d{4}-\d{2}-\d{2}", v) else ""


def matter_text(m: dict) -> str:
    title, name = clean(m.get("MatterTitle")), clean(m.get("MatterName"))
    if not title:
        return name
    if name and name.lower() not in title.lower():
        return f"{title} | {name}"
    return title


def summary(text: str) -> str:
    """The title's own words, one sentence: the [TXT] part of an old
    'NN:: [Dept]; [SUB]: ...; [TXT]: ...' title, else the title, to its first
    sentence break."""
    t = text.split(" | ")[0]
    m = re.search(r"\[TXT\]:\s*(.+)$", t)
    if m:
        t = m.group(1)
    t = re.sub(r"^\d+\.\s+", "", t)
    first = re.split(r"(?<=[a-z0-9)\]])\.\s+(?=[A-Z0-9(])|;\s+|:\s+(?=Appellants?\b)", t, maxsplit=1)[0]
    return cap(first.rstrip(" .;:,"), MAX_SUMMARY)


def sentence(text: str) -> str:
    """Text ending in one full stop."""
    return text if text.endswith((".", "...", "?", "!")) else text + "."


def _passed(m: dict) -> bool:
    return bool(_date(m.get("MatterPassedDate"))) or bool(ADOPTED_STATUS.search(m.get("MatterStatusName") or ""))


def _title_key(text: str) -> str:
    t = text.lower()
    t = re.sub(r"^(?:\*+|continued\s+from\s+\w+,?\s+\w+\s+\d{1,2},?\s+\d{4},?\s+item\s*#?\s*\d+\s*-?)\s*", "", t)
    return " ".join(re.findall(r"[a-z0-9]+", t))


def lead(m: dict, client: str, cfg: dict | None, entity: str, reason: str, details: dict, text: str,
         merged: list[dict]) -> dict:
    file_ = clean(str(m.get("MatterFile") or m.get("MatterId") or ""))
    mtype, status = clean(m.get("MatterTypeName")) or "matter", clean(m.get("MatterStatusName")) or "no status"
    intro, passed = _date(m.get("MatterIntroDate")), _date(m.get("MatterPassedDate"))
    loc, place_note = placement(client, cfg, text)
    juris = loc["municipality"] or loc["county"] or (cfg or {}).get("jurisdiction") or f"Legistar client {client}"
    notes = [f"Legistar {client} matter {file_} ({mtype}, {status}, "
             f"introduced {intro or 'no date'}, passed {passed or 'no date'})"]
    body = clean(m.get("MatterBodyName"))
    if body:
        notes.append(f"body {body}")
    notes.append(f"kept on {reason}")
    notes.append(place_note)
    if not details["techs"]:
        notes.append("technology not named (renewable energy generally): read it from the instrument")
    if details["name"] and details["name_how"] != "title":
        notes.append(f"project name from the {details['name_how']}")
    if entity == "contested_project" and not details["name"]:
        notes.append("the title names no facility")
    if details["undo"]:
        notes.append(f"also {', '.join(details['undo'])}: check what it replaced")
    hints = [label for label, rx in HINTS if rx.search(text)]
    if hints:
        notes.append("mechanism hints: " + ", ".join(hints))
    appellants = [" ".join((a or b).split()) for a, b in APPELLANT.findall(text)]
    if appellants:
        notes.append("appellant named: " + "; ".join(dict.fromkeys(appellants)))
    towns = list(dict.fromkeys(TOWN.findall(text.title() if mostly_capitals(text) else text)))
    if towns:
        notes.append("title names " + ", ".join(towns) + " (not used to place the lead)")
    if DATA_CENTER.search(text):
        notes.append("also names data centers (multi-sector scope)")
    if entity == "contested_project" and not CONTEST.search(BOARD_NAMES.sub(" ", text)):
        notes.append("a permit or approval is not by itself opposition: find the record of it")
    adopted = ""
    if entity == "restriction" and passed and ADOPTED_STATUS.search(status) and not NOT_AN_ADOPTION.search(
            clean(m.get("MatterTitle")) or text):
        adopted = passed
        notes.append("adopted_date is the matter's passed date: check it is the instrument's adoption")
    if merged:
        notes.append("same title as " + ", ".join(
            f"matter {clean(str(o.get('MatterFile') or o.get('MatterId')))} (ID {o.get('MatterId')}, "
            f"introduced {_date(o.get('MatterIntroDate')) or 'no date'})" for o in merged))
    url = strip_tracking(WEB.format(client=client, id=m.get("MatterId"), guid=m.get("MatterGuid") or ""))
    row = {
        "entity_type": entity,
        **loc,
        "project_name": details["name"] if entity == "contested_project" else "",
        "technology": ";".join(details["techs"]),
        "description": f"{juris} legislative matter {file_}: {sentence(summary(text))}",
        "source_url": url,
        "evidence_text": cap(text, MAX_EVIDENCE),
        "adopted_date": adopted,
        "first_event_date": "",
        "status": "",
        "mechanisms": "",
        "severity_score": "",
        "access": "snippet",
        "source_kind": "other",
        "reviewer_notes": "; ".join(notes),
    }
    return {k: clean(v) if isinstance(v, str) and k != "source_url" else v for k, v in row.items()}


def extract(raw_path: Path, source: dict, clients: dict[str, dict] | None = None) -> list[dict]:
    client = client_from_url(source.get("url", ""))
    cfg = (clients if clients is not None else load_clients()).get(client)
    payload = json.loads(read_raw(Path(raw_path)).decode("utf-8"))
    if not isinstance(payload, list):
        log.warning("legistar %s: response is not a list of matters (%s); nothing extracted",
                    client, str(payload)[:120])
        return []
    seen_ids: set = set()
    groups: dict[tuple, list] = {}
    order: list[tuple] = []
    for m in payload:
        if not isinstance(m, dict) or m.get("MatterId") in seen_ids or not m.get("MatterId"):
            continue
        seen_ids.add(m.get("MatterId"))
        if m.get("MatterRestrictViewViaWeb"):
            continue            # no public page to link
        text = matter_text(m)
        entity, reason, details = classify(text)
        if not entity:
            continue
        key = (entity, _title_key(text))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((m, reason, details, text))
    out = []
    for key in order:
        items = sorted(groups[key], key=lambda it: (_passed(it[0]), _date(it[0].get("MatterIntroDate")),
                                                    it[0].get("MatterId") or 0), reverse=True)
        m, reason, details, text = items[0]
        out.append(lead(m, client, cfg, key[0], reason, details, text, [it[0] for it in items[1:]]))
    return out


def explain(raw_path: Path) -> list[tuple[dict, str, str]]:
    """(matter, entity_type or '', reason) for every matter in a raw file: a
    triage aid for tuning the rules; extract() is what parse.py calls."""
    payload = json.loads(read_raw(Path(raw_path)).decode("utf-8"))
    out = []
    for m in payload if isinstance(payload, list) else []:
        entity, reason, _ = classify(matter_text(m))
        out.append((m, entity, reason))
    return out
