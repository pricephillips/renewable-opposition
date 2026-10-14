"""news_place.py: place a news headline in one county or state, or refuse.

A conservative headline geotagger for the news extractors
(scripts/extractors/gdelt_renewable_news.py). Copied and adapted from
pricephillips/data-center-map, not imported (that repository is not a
dependency): signal_harvest.py locate() (the county pass, the refusals of
bare county names, the roundup rule), gazetteer.py (STOP_PLACES,
COMMON_WORD_PLACES, NAME_PREFIX_PARTICLES, GIVEN_NAMES, ENTITY_SUFFIX_WORDS
and the longer-name test, _in_longer_name) and qc/schema_adapter.py
states_in_text (the state-name rule). It reads this repository's own
reference files, read only, once a process:

  data/county_fips_lookup.json    '<county>|<state name>' -> county FIPS
                                  (build_seed_outputs.load_fips_lookup)
  data/place_county_index.json    '<place_key>|<ST>' -> [county FIPS]
                                  (classify.place_key, build_place_index.py)
  geo.name(fips)                  the Census spelling of the county name

A wrong county is worse than none: it moves a lead into a county that had no
record, and a reviewer reading "Linn County" has no reason to doubt it. So
every rule refuses rather than guesses.

  States    Full state names, longest first with the matched span masked,
            so "West Virginia" is not also Virginia. A name followed by a
            capitalized County, Parish, City, Township, Borough, Avenue,
            Street, Road, River, Valley or Roadhouse, or by a masthead word
            (Tribune, Gazette, Democrat ...), or preceded by Port, Fort, Lake,
            Mount or Sierra, is a place, a company or a newspaper, not the
            state ("Texas County", "Kansas City", "Ohio River", "Tennessee
            Valley Authority", "Lake Michigan", "Arkansas Democrat-Gazette");
            "a West Virginia county" is West Virginia. "Washington" alone is
            the federal government or Washington County as often as the
            state, so it is the state only as "Washington state", "eastern
            Washington" and the like, or after a county or a Washington town
            and a comma ("Benton County, Washington"; not ", Washington says").
  Counties  Only the literal "<Name> County" (or "<Name> Parish" in
            Louisiana), capitalized as a name. A bare county name never
            counts: "Minnesota Power" is not Power County, "Texas" is not
            Texas County, "Cedar Rapids" is not Cedar County. With a state
            named, the county must be in it (high); a county named but not in
            the named state is a contradiction and places nothing. With no
            state named, a county name found in one state only is medium, and
            one found in several places nothing, not even a state.
            Connecticut's eight former counties (no 2024 county code) place
            the state only.
  Towns     Only with a state named, and only when the place index gives the
            name exactly one county in that state (high; several counties
            give the state). Guards: names shorter than four letters, state
            names, ordinary words (STOP_PLACES, COMMON_WORD_PLACES and
            DOMAIN_WORDS, the words renewable headlines are made of), a name
            that is part of a longer one (after a particle such as San, Fort
            or New, after a given name, or before a masthead word such as
            News), a name in lower case, and a name that is also a county of
            that state in a different county. A one-word name must also be
            framed as a place: "Coggon, Iowa", "Coggon Township", "Coggon
            council", or "town of Coggon", "in Coggon" when no capitalized
            word follows ("from Hurricane Isaias" is a storm, not Hurricane,
            North Carolina). A town after "outside" or "outside of" is where
            the story is not, so it places nothing.
  Roundups  Three or more distinct counties or towns, or "<A> and <B>
            counties", are a list, not a dateline: state only. So is a town
            named beside places in the plural, in lower case ("Arkansas
            counties and cities").
  Several states and no county or town pinning one: nothing.

locate(text) returns a Place: state (two-letter code or ''), county ('<Name>
County' or '<Name> Parish', the Census spelling, or ''), county_fips,
municipality (the town that placed it, high only), confidence (high | medium |
state_only | none) and reason, one phrase a reviewer can check. Nothing here
writes a file.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import geo
from common import STATE_ABBREV

ROOT = Path(__file__).resolve().parent.parent
FIPS_LOOKUP = ROOT / "data" / "county_fips_lookup.json"
PLACE_INDEX = ROOT / "data" / "place_county_index.json"

CONFIDENCE_RANK = {"none": 0, "state_only": 1, "medium": 2, "high": 3}
# This many distinct counties or towns in one headline make it a list.
LIST_OF_COUNTIES = 3
MIN_PLACE_LEN = 4
MAX_NAME_TOKENS = 4
# Connecticut's former counties: no polygon in the 2024 county boundaries
# (classify.NOT_2024_COUNTY); naming one places the state only.
NOT_2024_COUNTY = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}

STATE_CODE = {name: code for name, code in STATE_ABBREV.items()}
STATE_PRINTED = {code: name.title().replace(" Of ", " of ") for name, code in STATE_ABBREV.items()}

# After qc/schema_adapter.states_in_text, with river, valley, road and Sierra
# added (multi-state rivers, the Tennessee Valley Authority, Sierra Nevada).
# The word after must be capitalized, as a name is: "Texas County" is a
# county, "a West Virginia county" is in West Virginia.
_STATE_AFTER = re.compile(
    r"\s+(county|parish|city|township|twp|borough|avenue|ave|street|st|road|rd|"
    r"roadhouse|river|valley|basin|"
    # A masthead: "Texas Tribune", "Arkansas Democrat-Gazette", "Iowa Capital Dispatch".
    r"democrat|gazette|times|post|tribune|herald|journal|register|republic|mercury|reformer|"
    r"reflector|examiner|observer|sentinel|courier|chronicle|dispatch|capital\s+(?:journal|dispatch)|"
    r"public\s+(?:radio|media))\b")
_STATE_BEFORE = re.compile(r"\b(?:port|fort|ft\.?|lake|mount|mt\.?|sierra)\s+$")
_WASHINGTON_STATE = re.compile(
    r"\bwashington\s+state\b"
    r"|\b(?:eastern|western|central|southeast(?:ern)?|southwest(?:ern)?|northeast(?:ern)?|"
    r"northwest(?:ern)?|southern|northern|rural)\s+washington\b")
# ", Washington" is the state after a county or a Washington town ("Benton
# County, Washington", "Kennewick, Washington"), not after anything else
# ("halts offshore wind work, Washington says").
_COMMA_WASHINGTON = re.compile(r"([a-z][a-z' .-]{0,40}?)\s*,\s*washington\b(?!\s*,?\s*d\.?\s*c\b)")

# gazetteer.py STOP_PLACES: never distinctive enough to carry a county.
STOP_PLACES = {
    "washington", "york", "union", "center", "centre", "liberty", "franklin",
    "jackson", "jefferson", "madison", "monroe", "clay", "grant", "lincoln",
    "marion", "clinton", "greene", "troy", "salem", "springfield", "fairview",
    "riverside", "oak", "hill", "hills", "lake", "lakes", "river", "valley",
    "summit", "eagle", "aurora", "florida", "nevada", "oregon", "wyoming",
    "delaware", "indiana", "louisiana", "michigan", "ohio", "utah", "kansas",
    "california", "colorado", "texas", "virginia", "georgia", "montana",
    "north", "south", "east", "west", "middle", "new", "old", "mount",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "energy", "power", "water", "school", "district", "county", "state",
    "united states", "america", "national", "federal", "capital", "city",
    "industry", "rapid", "commerce", "enterprise", "normal", "surprise",
    "hope", "home", "blue", "gold", "silver", "sun", "star", "general",
    "standard", "superior", "sterling", "service", "security", "advance",
    "progress", "reliance", "hazard", "boring", "protection", "economy",
    "bland", "climax", "index", "loyal", "rich", "sharp", "speed", "peace",
}

# gazetteer.py COMMON_WORD_PLACES: ordinary English words that are also places.
COMMON_WORD_PLACES = frozenset("""
    agency agenda airport alliance battle bond brownfield cable call carbon case
    cash central chambers chance chief coal commercial compromise conservation
    corner council courthouse cross current daily date deal divide eastern fair
    faith falls farmer farmers farming fell fifth fine first forward fossil fourth
    government grants green grow hall headquarters hire holding independent
    industrial lack land laws lead loud lower main marathon media miles military
    mill mobile model northeast northern northwest pace page park parks pilot
    point post powers preemption president price prior read reading recovery
    reform relief rolling rose roundup rule rural rush second shell signal
    southeast southern southwest sparks spring spur steel stock strong sunset
    third victory view village wells western will winter worth zero
""".split())

# Added here: words renewable-siting headlines are made of that the Census
# index also holds as places ("Prairie, IA", "Farmland, IN", "Energy, IL"),
# and the words of project names ("Big Sky", "Prairie Wolf").
DOMAIN_WORDS = frozenset("""
    solar wind farm farms farmland battery storage project projects turbine turbines
    panel panels array arrays plant plants facility site sites grid lines transmission
    utility utilities electric electricity renewable renewables clean climate
    acres acre field fields prairie ridge creek creeks springs spring meadow meadows
    grove groves orchard garden gardens woods forest pines oaks crossing crossings
    junction plains plain harbor bay beach island mountain mountains heights
    sunrise sky big bright harmony unity freedom independence friendship concord
    hurricane storm tropical tornado flood
    opposition residents neighbors landowners opponents critics supporters voters
    commissioners supervisors trustees council board commission planning zoning
    township town village city court judge hearing meeting petition lawsuit appeal
    moratorium ban ordinance setback setbacks rules vote votes plan plans
    proposal developer developers company companies community local group groups
""".split())

# gazetteer.py NAME_PREFIX_PARTICLES: a match after one of these is part of a
# longer name ("El Reno" is not Reno).
NAME_PREFIX_PARTICLES = {
    "el", "la", "las", "los", "san", "santa", "sao", "ste", "st", "saint",
    "new", "north", "south", "east", "west", "upper", "lower", "old", "big",
    "little", "fort", "ft", "mount", "mt", "port", "lake", "cape", "bay",
    "great", "grand", "green", "white", "black", "red", "blue", "long",
}

# gazetteer.py GIVEN_NAMES: a match after one of these is a surname.
GIVEN_NAMES = {
    "mike", "michael", "john", "jim", "james", "bob", "robert", "bill", "william",
    "tom", "thomas", "joe", "joseph", "dave", "david", "dan", "daniel", "steve",
    "steven", "stephen", "chris", "christopher", "mark", "matt", "matthew", "paul",
    "peter", "rick", "richard", "ron", "ronald", "greg", "gregory", "jeff",
    "jeffrey", "scott", "brian", "kevin", "gary", "larry", "tim", "timothy", "ken",
    "kenneth", "doug", "douglas", "don", "donald", "ed", "edward", "frank",
    "george", "jack", "jerry", "andy", "andrew", "tony", "anthony", "ryan", "eric",
    "josh", "joshua", "jason", "justin", "brandon", "kyle", "adam", "nick",
    "nicholas", "sam", "samuel", "ben", "benjamin", "pete", "phil", "patrick",
    "sean", "shawn", "todd", "chuck", "charles", "randy", "terry", "keith",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan",
    "jessica", "sarah", "karen", "nancy", "lisa", "betty", "sandra", "ashley",
    "kimberly", "donna", "emily", "michelle", "carol", "amanda", "melissa",
    "deborah", "stephanie", "rebecca", "laura", "sharon", "cynthia", "kathy",
    "amy", "angela", "anna", "julie", "heather", "nicole", "rachel", "katie",
    "kate", "kelly", "maria", "pam", "debbie", "tammy", "wendy", "gretchen",
    "kristi", "beth", "jane", "janet", "joan", "judy", "ann", "anne",
}

# gazetteer.py ENTITY_SUFFIX_WORDS: a match before one of these is part of an
# organization or masthead ("Buckeye Country 105.5").
ENTITY_SUFFIX_WORDS = {
    "country", "radio", "news", "times", "herald", "gazette", "journal",
    "tribune", "post", "press", "magazine", "network", "media", "broadcasting",
    "tv", "fm", "am", "channel", "podcast", "review", "report", "digest",
    "bank", "insurance", "airlines", "motors", "brands", "holdings",
    # Added: a project or company name, "Coggon Solar", "Prairie Wind Energy".
    "solar", "wind", "energy", "power", "renewables", "renewable", "storage",
    "battery", "electric", "utilities", "llc", "inc", "corp",
}

# A one-word town must be framed as a place: preceded by one of these...
# ('outside' is not one: "Outside of Little Rock, Arkansas counties and cities
# move ahead on data center moratoriums" is about everywhere but Little Rock.)
_PLACE_LEAD = {"in", "near", "of", "from", "at", "around"}
# Places in the plural, in lower case: the headline is about several of them,
# so a town it also names is not where the story is.
_PLURAL_PLACES = re.compile(r"\b(?:counties|parishes|cities|towns|townships|villages|boroughs|municipalities)\b")
# ...or followed by one of these.
_PLACE_TAIL = {
    "township", "twp", "town", "city", "village", "borough", "council", "councilors",
    "councilmembers", "aldermen", "selectboard", "selectmen", "trustees", "board", "mayor",
    "officials", "leaders", "residents", "neighbors", "voters", "landowners", "farmers",
    "planning", "zoning", "plan", "commission", "commissioners", "supervisors", "area",
}
_MUNICIPAL_PREFIX = re.compile(r"^(?:town|city|village|township|borough)$")
_SUFFIX = {"county": "County", "parish": "Parish"}


@dataclass(frozen=True)
class Place:
    state: str = ""
    county: str = ""
    county_fips: str = ""
    municipality: str = ""
    confidence: str = "none"
    reason: str = ""


# ── normalization ────────────────────────────────────────────────────────────

def _fold(text: str) -> str:
    """Accents folded ("Cañon" -> "Canon"), curly quotes straightened."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace("’", "'").replace("‘", "'").replace("`", "'")


def _clean(text: str) -> str:
    """The form names are compared in, for the text and the reference files
    alike: possessive 's dropped, then periods and apostrophes ("St. Mary's"
    -> "St Mary", "O'Brien" -> "OBrien"), "Saint" -> "St", every other
    non-alphanumeric a space."""
    t = _fold(text)
    t = re.sub(r"\s*'\s*s\b", "", t)
    t = re.sub(r"['.]", "", t)
    t = re.sub(r"(?i)\bsaint\b", "St", t)
    return t


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _clean(text).lower()))


def _tokens(text: str) -> list[str]:
    """Words and the punctuation that frames them (commas, colons), in order.
    Case is kept; comparison lowercases."""
    return re.findall(r"[A-Za-z0-9]+|[,;:|()]", _clean(text))


def _is_word(tok: str) -> bool:
    return tok[:1].isalnum()


def _capitalized(tok: str) -> bool:
    return tok[:1].isupper() or tok[:1].isdigit()


# ── reference data, loaded once ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _counties() -> dict[str, dict[str, dict[str, str]]]:
    """suffix ('county' | 'parish') -> normalized name -> {ST: fips}."""
    data = json.loads(FIPS_LOOKUP.read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict[str, str]]] = {"county": {}, "parish": {}}
    for key, fips in data.items():
        if key.startswith("_"):
            continue
        name, _, state = key.strip().lower().rpartition("|")
        code = STATE_CODE.get(state)
        m = re.match(r"(.+) (county|parish)$", name)
        if not code or not m:
            continue
        if m.group(2) == "parish" and code != "LA":
            continue
        out[m.group(2)].setdefault(norm(m.group(1)), {})[code] = str(fips)
    return out


@lru_cache(maxsize=1)
def _county_squash() -> dict[str, dict[str, str]]:
    """'dekalb' -> 'de kalb' style keys: spacing-insensitive names per suffix."""
    out: dict[str, dict[str, str]] = {}
    for suffix, names in _counties().items():
        out[suffix] = {n.replace(" ", ""): n for n in names}
    return out


@lru_cache(maxsize=1)
def _places() -> dict[str, dict[str, frozenset[str]]]:
    """normalized place name -> {ST: county FIPS set}. Census county divisions
    ('<name> ccd') are left out: no headline names one."""
    data = json.loads(PLACE_INDEX.read_text(encoding="utf-8"))
    out: dict[str, dict[str, set[str]]] = {}
    for key, fips in data.items():
        if key.startswith("_"):
            continue
        name, _, st = key.rpartition("|")
        n = norm(name)
        if not n or n.endswith(" ccd") or len(n) < MIN_PLACE_LEN:
            continue
        out.setdefault(n, {}).setdefault(st.upper(), set()).update(str(f) for f in fips)
    return {n: {st: frozenset(f) for st, f in by.items()} for n, by in out.items()}


def county_display(fips: str, suffix: str) -> str:
    name = geo.name(fips)
    return f"{name} {_SUFFIX[suffix]}" if name else ""


# ── states ───────────────────────────────────────────────────────────────────

def named_states(text: str) -> list[str]:
    """Two-letter codes of the states the text names, in order of first
    appearance (qc/schema_adapter.states_in_text, adapted; see the module
    docstring)."""
    orig = re.sub(r"\s+", " ", _fold(text))
    low = orig.lower()
    if len(low) != len(orig):          # a character whose lower case is longer
        orig = low.upper()
    washington = [(w.start(), w.end()) for w in _WASHINGTON_STATE.finditer(low)]
    washington += [(w.start(), w.end()) for w in _COMMA_WASHINGTON.finditer(low) if _wa_before(w.group(1))]
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, str]] = []
    for name in sorted(STATE_ABBREV, key=len, reverse=True):
        pattern = r"\b" + r"\s+".join(map(re.escape, name.split())) + r"\b"
        for m in re.finditer(pattern, low):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            after = _STATE_AFTER.match(low, m.end())
            if (after and orig[after.start(1)].isupper()) or _STATE_BEFORE.search(low, 0, m.start()):
                continue
            if name == "washington" and not any(a <= m.start() < b for a, b in washington):
                continue
            found.append((m.start(), STATE_ABBREV[name]))
    out: list[str] = []
    for _, code in sorted(found):
        if code not in out:
            out.append(code)
    return out


def _wa_before(before: str) -> bool:
    """Whether the words before ', Washington' are a county or a Washington town."""
    words = norm(before).split()
    if words[-1:] in (["county"], ["parish"]):
        return True
    places = _places()
    return any("WA" in places.get(" ".join(words[-k:]), {}) for k in range(1, min(3, len(words)) + 1))


def _state_spans(words: list[str]) -> set[int]:
    """Word positions taken by a state name, so no town is read inside one."""
    low = [w.lower() for w in words]
    taken: set[int] = set()
    for name in sorted(STATE_ABBREV, key=len, reverse=True):
        parts = norm(name).split()
        for i in range(len(low) - len(parts) + 1):
            if low[i:i + len(parts)] == parts and not taken & set(range(i, i + len(parts))):
                taken.update(range(i, i + len(parts)))
    return taken


# ── counties ─────────────────────────────────────────────────────────────────

@dataclass
class _CountyHit:
    name: str                 # normalized
    suffix: str               # county | parish
    start: int                # word index of the name
    end: int                  # word index after the suffix
    options: dict             # {ST: fips}
    printed: str              # as the text prints it


def _literal_counties(words: list[str]) -> tuple[list[_CountyHit], list[str], set[int]]:
    """Every literal '<Name> County' / '<Name> Parish' the text names, the
    names in an '<A> and <B> counties' list, and the word positions they take."""
    low = [w.lower() for w in words]
    hits: list[_CountyHit] = []
    plural: list[str] = []
    taken: set[int] = set()
    counties, squash = _counties(), _county_squash()
    for i, w in enumerate(low):
        if w in ("county", "parish") and _capitalized(words[i]):
            for k in range(min(MAX_NAME_TOKENS, i), 0, -1):
                span = words[i - k:i]
                if not all(_capitalized(t) for t in span) or taken & set(range(i - k, i)):
                    continue
                key = " ".join(low[i - k:i])
                name = key if key in counties[w] else squash[w].get(key.replace(" ", ""))
                if name:
                    hits.append(_CountyHit(name, w, i - k, i + 1, counties[w][name],
                                           " ".join(span) + " " + words[i]))
                    taken.update(range(i - k, i + 1))
                    break
        elif w in ("counties", "parishes"):
            # "Linn and Benton counties": each name before the plural.
            j = i - 1
            names = []
            while j >= 0 and _capitalized(words[j]) and low[j] not in ("and", "or"):
                names.append(words[j])
                j -= 1
                if j >= 0 and low[j] in ("and", "or", ","):
                    names.append("|")
                    j -= 1
            if "|" in names:
                group = " ".join(reversed(names)).split("|")
                plural += [g.strip() for g in group if g.strip()]
                taken.update(range(j + 1, i + 1))
    return hits, plural, taken


# ── towns ────────────────────────────────────────────────────────────────────

def _framed(tokens: list[str], idx: list[int], start: int, end: int, states: list[str]) -> bool:
    """A one-word town is framed as a place: 'Coggon, Iowa', 'town of Coggon',
    'in Coggon', 'Coggon Township', 'Coggon council'."""
    before = tokens[idx[start] - 1].lower() if idx[start] > 0 else ""
    after_pos = idx[end - 1] + 1
    after_tok = tokens[after_pos] if after_pos < len(tokens) else ""
    after = after_tok.lower()
    if after in _PLACE_TAIL:
        return True
    if after == ",":
        rest = " ".join(t.lower() for t in tokens[after_pos + 1:after_pos + 4] if _is_word(t))
        return any(rest.startswith(norm(STATE_PRINTED[s])) for s in states)
    # 'in Coggon', unless the next word goes on with the name ('from
    # Hurricane Isaias' is a storm, not Hurricane, NC).
    if before in _PLACE_LEAD:
        return not (_is_word(after_tok) and _capitalized(after_tok)
                    and not any(after == norm(STATE_PRINTED[s]).split()[0] for s in states))
    return False


def _towns(tokens: list[str], states: list[str], masked: set[int],
           county_names: dict[str, dict[str, str]]):
    """[(printed name, ST, county fips set)] for every town in a named state,
    longest name first, with the guards in the module docstring."""
    idx = [i for i, t in enumerate(tokens) if _is_word(t)]
    words = [tokens[i] for i in idx]
    low = [w.lower() for w in words]
    places = _places()
    taken = set(masked)
    found = []
    for n in range(min(MAX_NAME_TOKENS, len(words)), 0, -1):
        for s in range(len(words) - n + 1):
            span = set(range(s, s + n))
            if span & taken:
                continue
            name = " ".join(low[s:s + n])
            if name not in places or len(name) < MIN_PLACE_LEN:
                continue
            parts = name.split()
            if (name in STOP_PLACES or name in COMMON_WORD_PLACES or name in DOMAIN_WORDS
                    or all(p in STOP_PLACES or p in COMMON_WORD_PLACES or p in DOMAIN_WORDS for p in parts)
                    or name in STATE_CODE):
                continue
            if not all(_capitalized(w) for w in words[s:s + n]):
                continue
            before = low[s - 1] if s > 0 else ""
            after = low[s + n] if s + n < len(low) else ""
            if before in NAME_PREFIX_PARTICLES or before in GIVEN_NAMES or after in ENTITY_SUFFIX_WORDS:
                continue
            if before == "outside" or (before == "of" and s > 1 and low[s - 2] == "outside"):
                continue          # outside a town is not in it
            if n == 1 and not _framed(tokens, idx, s, s + n, states):
                continue
            for st in states:
                fipses = places[name].get(st)
                if not fipses:
                    continue
                county_fips = county_names.get(name, {}).get(st)
                if county_fips and fipses != {county_fips}:
                    continue          # also a county of that state, elsewhere
                found.append((" ".join(words[s:s + n]), st, fipses))
                taken |= span
                break
    return found


# ── the locator ──────────────────────────────────────────────────────────────

def locate(text: str) -> Place:
    """Best county or state for a headline, or none, with the reason."""
    tokens = _tokens(text)
    words = [t for t in tokens if _is_word(t)]
    states = named_states(text)
    hits, plural, county_taken = _literal_counties(words)

    # Literal counties: resolve each against the named states.
    resolved: list[tuple[int, int, Place]] = []   # (rank, -position, place)
    contradictions, ambiguous = [], []
    for h in hits:
        if states:
            match = [st for st in h.options if st in states]
            if len(match) != 1:
                (ambiguous if match else contradictions).append(h)
                continue
            st, conf = match[0], "high"
            fips = h.options[st]
            why = f"{county_display(fips, h.suffix) or h.printed} in {STATE_PRINTED[st]}, the state named"
        elif len(h.options) == 1:
            st, conf = next(iter(h.options)), "medium"
            fips = h.options[st]
            why = (f"{county_display(fips, h.suffix) or h.printed} named, no state named; "
                   f"the only one is in {STATE_PRINTED[st]}")
        else:
            ambiguous.append(h)
            continue
        if fips in NOT_2024_COUNTY:
            resolved.append((CONFIDENCE_RANK["state_only"], -h.start,
                             Place(st, "", "", "", "state_only",
                                   f"{h.printed} is a former Connecticut county, no 2024 county code")))
            continue
        resolved.append((CONFIDENCE_RANK[conf], -h.start,
                         Place(st, county_display(fips, h.suffix), fips, "", conf, why)))

    # Towns: only with a state named.
    towns = []
    if states:
        masked = county_taken | _state_spans(words)
        bare = {n: by for n, by in _counties()["county"].items()}
        towns = _towns(tokens, states, masked, bare)

    distinct = ({p.county_fips or p.reason for _, _, p in resolved}
                | {h.name for h in ambiguous + contradictions}
                | {next(iter(f)) if len(f) == 1 else f"town:{t}" for t, _, f in towns}
                | {f"plural:{p}" for p in plural})
    single_state = states[0] if len(states) == 1 else ""
    if plural or len(distinct) >= LIST_OF_COUNTIES:
        listed = [h.printed for h in hits] + [t for t, _, _ in towns] + plural
        why = (f"several counties or towns named ({', '.join(listed)}): a roundup")
        if single_state:
            return Place(single_state, confidence="state_only", reason=why + ", state only")
        return Place(reason=why + (", several states named" if states else ", no state named"))

    if contradictions and not resolved:
        h = contradictions[0]
        named = ", ".join(STATE_PRINTED[s] for s in states)
        return Place(reason=f"{h.printed} is not in {named}, the state named; nothing placed")

    if resolved:
        resolved.sort(key=lambda r: (r[0], r[1]), reverse=True)
        best = resolved[0][2]
        others = [p.county for _, _, p in resolved[1:] if p.county and p.county != best.county]
        if others:
            best = Place(best.state, best.county, best.county_fips, "", best.confidence,
                         best.reason + f"; also names {', '.join(others)}")
        return best

    if ambiguous and not states:
        h = ambiguous[0]
        return Place(reason=f"{h.printed} is in {len(h.options)} states and no state is named")

    many = _PLURAL_PLACES.search(_fold(text))
    if towns and many:
        t, st, _ = towns[0]
        return Place(st, "", "", "", "state_only",
                     f"town {t} named beside {many.group(0)} in the plural: a roundup, state only")

    one_county = [(t, st, f) for t, st, f in towns if len(f) == 1]
    if one_county:
        t, st, f = one_county[0]
        fips = next(iter(f))
        county = county_display(fips, "parish" if st == "LA" else "county")
        return Place(st, county, fips, t, "high",
                     f"town {t} in {STATE_PRINTED[st]}, the state named, sits in one county ({county})")

    if towns:
        t, st, f = towns[0]
        return Place(st, "", "", "", "state_only",
                     f"town {t} in {STATE_PRINTED[st]} sits in {len(f)} counties; state only")

    if ambiguous:
        h = ambiguous[0]
        named = ", ".join(STATE_PRINTED[s] for s in states)
        why = f"{h.printed} is in more than one of the states named ({named})"
        return Place(reason=why) if not single_state else Place(single_state, confidence="state_only",
                                                                  reason=why + "; state only")
    if single_state:
        return Place(single_state, confidence="state_only",
                     reason=f"{STATE_PRINTED[single_state]} named, no county or town")
    if states:
        named = ", ".join(STATE_PRINTED[s] for s in states)
        return Place(reason=f"several states named ({named}) and no county or town")
    return Place(reason="no state, county or town named")
