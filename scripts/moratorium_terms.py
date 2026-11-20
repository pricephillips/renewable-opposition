"""Moratorium terms: how long a pause has run, how often it was extended,
whether the government is drafting the rules that would end it, and whether
the instrument is a pause or a ban.

A reader of a county's record asks these first (Hawthorn's renewables pilot
review, 2026-11-19): a moratorium is not a ban; one six months old while the
county drafts a wind ordinance reads differently from one extended three times
and eighteen months in force; and a ban, or an ordinance that works as one,
reads differently from a true pause.

Every field is derived from the record itself (its status, its dates and its
text, which come from the source, plus the note of a status reading two
reviewers agreed on, data/review/status_resolutions.csv). Nothing here reads a web page, and nothing is a new fact: a field
is blank when the record does not support it. The text cues are patterns, so
each field names what it rests on:

term            moratorium, ban and ban_or_moratorium rows only:
                  temporary  a moratorium, or a ban whose text describes a
                             temporary pause (moratorium, temporary, a term in
                             months, an end date)
                  permanent  a ban whose text describes no pause, or a
                             ban_or_moratorium row whose own text (with the
                             source's category label removed) says the use is
                             prohibited or not allowed and describes no pause
                  unclear    a ban_or_moratorium row whose text says neither
ends_on         the date a temporary instrument runs to: current_end_date_iso,
                or the first "through/until/runs to/expires <date>" in the
                text when that field is blank
ends_on_basis   record (current_end_date_iso), text (parsed), term (a stated
                term such as "a one-year moratorium" counted from a full
                enactment date; approximate) or blank
extensions      the number of extensions the record describes: sentences that
                say the instrument was extended or renewed (not "may be
                extended" or "unless extended"), at least 1 when the status is
                extended. A floor, not a full history.
last_extended_on  the latest date in those sentences
months_in_force from date_enacted_iso to the build date, or to ends_on when
                that has passed; one decimal. Blank without an enactment month.
drafting        active    the text says the government is drafting, studying
                          or preparing the rules the pause waits for
                adopted   the text says those rules were adopted
                blank     the text says neither
drafting_note   the sentence the drafting value rests on, quoted from the
                record (at most 240 characters)
"""
from __future__ import annotations

import calendar
import re
from datetime import date

PAUSE_TYPES = ("moratorium", "ban", "ban_or_moratorium")
FIELDS = ("term", "ends_on", "ends_on_basis", "extensions", "last_extended_on", "months_in_force",
          "drafting", "drafting_note")
TEXT_FIELDS = ("description", "long_description", "legal_basis", "date_text", "status_note")

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december")
_MONTH_RE = "|".join(_MONTHS) + r"|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec"
_DATE = (r"(\d{4}-\d{2}-\d{2}"
         rf"|(?:{_MONTH_RE})\.?\s+\d{{1,2}},?\s+\d{{4}})")
_DATE_RE = re.compile(_DATE, re.I)
_END_RE = re.compile(rf"\b(?:through|until|runs? (?:to|through|until)|expires?(?: on)?|expiring(?: on)?|"
                     rf"ends?(?: on)?|to approximately|to about)\s+(?:approximately\s+|about\s+)?{_DATE}", re.I)
_END_MONTH_RE = re.compile(rf"\b(?:through|until|runs? (?:to|through|until)|expires?(?: in)?|expiring(?: in)?)\s+"
                           rf"(?:the end of\s+)?(?:{_MONTH_RE})\.?\s+\d{{4}}\b(?!\s*-)", re.I)
_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "six": 6, "nine": 9, "twelve": 12, "eighteen": 18,
        "twenty-four": 24}
_TERM_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|six|nine|twelve|eighteen|twenty-four)[- ](year|month)s?\b"
                      r"(?=[^.;]{0,40}\bmoratori)|\bmoratori(?:um|a)\b[^.;]{0,30}\bfor (?:a period of )?"
                      r"(\d{1,2}|one|two|three|four|six|nine|twelve|eighteen|twenty-four) (year|month)s?\b", re.I)
_SENTENCE = re.compile(r"(?<=[.;])\s+")
_EXTENDED = re.compile(r"\b(extended|renewed|extends|renews|extension of|re-?adopted)\b", re.I)
_CONDITIONAL = re.compile(r"\b(may be|can be|could be|unless|if|or it is|would be|to be|if not)\s+"
                          r"(further\s+)?(extended|renewed)\b|\bunless\b[^.]*\bextended\b", re.I)
_TEMPORARY = re.compile(r"\b(moratori(um|a)|temporar(y|ily)|pause|\d+[- ]month|one[- ]year|six[- ]month|"
                        r"twelve[- ]month|expires?|until (the )?(adoption|county|city|town|board))\b", re.I)
_PROHIBITED = re.compile(r"\b(prohibit(s|ed|ing)?|banned|bans|not (be )?(permitted|allowed)|"
                         r"may not be (sited|located|built|constructed)|outright ban)\b", re.I)
# The Sabin Center's category label ("Ban / Moratorium (wind)") names both, so
# it is removed before the text is read for cues.
_LABEL = re.compile(r"ban\s*/\s*moratorium(\s*\([^)]*\))?|rules?:[^;]*", re.I)
_DRAFT_ACTIVE = re.compile(
    r"\b(draft(s|ed|ing)?|develop(s|ing)?|prepar(e|es|ing)|stud(y|ies|ying)|consider(s|ing)?|reviewing|review and update|"
    r"writ(e|es|ing)|work(s|ing)? on|time to (study|draft|develop|adopt|prepare|review|consider|write|update|weigh))"
    r"\b[^.;]{0,80}\b(ordinance|regulations?|standards|zoning( code)?|code|amendments?|rules)\b"
    r"|\bpending (regulatory review|(the )?(adoption|completion) of)\b"
    r"|\b(need|needs) to draft\b", re.I)
_DRAFT_DONE = re.compile(
    r"\b(adopted|enacted|approved|passed)\b[^.;]{0,60}\b(new |its |the )?(regulations?|ordinance|zoning|code|"
    r"standards)\b[^.;]{0,80}\b(end(ing|ed|s)?|lift(ed|ing)?|replac(ed|ing)|superseding|official(ly)?)\b"
    r"|\b(moratorium|it) (was|were) (lifted|repealed|rescinded|replaced)\b", re.I)


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _text(row: dict) -> str:
    return " ".join(_s(row.get(f)) for f in TEXT_FIELDS if _s(row.get(f)))


def _iso(token: str) -> str:
    """'2026-10-14' or 'October 14, 2026' -> '2026-10-14'; '' when it does not parse."""
    token = token.strip().rstrip(".,")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        return token
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", token)
    if not m:
        return ""
    name = m.group(1).lower()
    month = next((i + 1 for i, mm in enumerate(_MONTHS) if mm.startswith(name[:3])), 0)
    day, year = int(m.group(2)), int(m.group(3))
    if not month or not 1 <= day <= calendar.monthrange(year, month)[1]:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _start(v: str) -> date | None:
    v = _s(v)
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", v)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))


def _end(v: str) -> date | None:
    v = _s(v)
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", v)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return date(y, mo, int(m.group(3) or calendar.monthrange(y, mo)[1]))


_MONTH_YEAR = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{4}})\b(?!\s*-)", re.I)


def _text_start(text: str) -> str:
    """The first month and year the text names ("In September 2023, the county
    enacted a 6-month moratorium") as 'YYYY-MM', for a row with no enactment
    date; '' when the text names none."""
    m = _MONTH_YEAR.search(text)
    if not m:
        return ""
    month = next((i + 1 for i, mm in enumerate(_MONTHS) if mm.startswith(m.group(1).lower()[:3])), 0)
    return f"{int(m.group(2)):04d}-{month:02d}" if month else ""


def _term_end(enacted: str, text: str) -> str:
    """A stated term ("a one-year moratorium", "a moratorium for 6 months")
    counted from the enactment date; '' without both. A full date gives a full
    end date. With only a month (the enactment month, or the first month and
    year the text names), the end is that many months on, as 'YYYY-MM', read
    as the end of that month. The date is approximate (an ordinance may run
    from its effective date)."""
    m = _TERM_RE.search(text)
    if not m:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", enacted):
        enacted = _text_start(text)
        if not enacted:
            return ""
    n, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    n = int(n) if n.isdigit() else _NUM[n.lower()]
    months = n * 12 if unit.lower() == "year" else n
    start = _start(enacted)
    y, mo = divmod(start.month - 1 + months, 12)
    y, mo = start.year + y, mo + 1
    if len(enacted) == 7:
        return f"{y:04d}-{mo:02d}"
    return date(y, mo, min(start.day, calendar.monthrange(y, mo)[1])).isoformat()


def term(row: dict, text: str) -> str:
    kind = _s(row.get("restriction_type"))
    if kind == "moratorium":
        return "temporary"
    cues = _LABEL.sub(" ", text)
    temporary = bool(_TEMPORARY.search(cues) or _s(row.get("current_end_date_iso")))
    if kind == "ban":
        return "temporary" if temporary else "permanent"
    if temporary:
        return "temporary"
    return "permanent" if _PROHIBITED.search(cues) else "unclear"


def extensions(row: dict, text: str) -> tuple[int, str]:
    """(count, latest date) of the extensions the text describes. The count
    is the number of distinct dates on which an extension was made, or 1 when
    an extension is described without a date (or the status is extended)."""
    enacted = _s(row.get("date_enacted_iso"))
    dates: set[str] = set()
    described = False
    for sentence in _SENTENCE.split(text):
        if not _EXTENDED.search(sentence) or _CONDITIONAL.search(sentence) and not re.search(
                r"\b(was|were|has been|have been) (further )?(extended|renewed)\b", sentence, re.I):
            continue
        described = True
        # Dates the extension runs to are end dates, and the enactment date
        # is the original adoption, so neither is a date an extension was made.
        acted = re.sub(rf"\b(?:to|through|until|from|as of)\s+(?:approximately\s+|about\s+|its\s+)?{_DATE}", " ",
                       _END_RE.sub(" ", sentence), flags=re.I)
        for d in _DATE_RE.findall(acted):
            iso = _iso(d)
            if iso and iso != enacted:
                dates.add(iso)
    count = len(dates) or (1 if described else 0)
    if _s(row.get("status")) == "extended":
        count = max(count, 1)
    return count, max(dates) if dates else ""


def drafting(text: str) -> tuple[str, str]:
    sentences = _SENTENCE.split(text)
    for s in sentences:
        if _DRAFT_DONE.search(s):
            return "adopted", s.strip()[:240]
    for s in sentences:
        if _DRAFT_ACTIVE.search(s):
            return "active", s.strip()[:240]
    return "", ""


def derive(row: dict, today: date | None = None) -> dict:
    """The fields above for one restrictions row; every field blank for a row
    that is not a moratorium or ban."""
    out = dict.fromkeys(FIELDS, "")
    if _s(row.get("restriction_type")) not in PAUSE_TYPES:
        return out
    today = today or date.today()
    text = _text(row)
    out["term"] = term(row, text)
    if out["term"] == "temporary":
        end = _s(row.get("current_end_date_iso"))
        if end:
            out["ends_on"], out["ends_on_basis"] = end, "record"
        else:
            m = _END_RE.search(text)
            iso = _iso(m.group(1)) if m else ""
            if not iso:
                # "extended ... until September 2024": the latest month-precision
                # end the text names, read as the end of that month.
                ends = [_text_start(x.group(0)) for x in _END_MONTH_RE.finditer(text)]
                iso = max((e for e in ends if e), default="")
            if iso:
                out["ends_on"], out["ends_on_basis"] = iso, "text"
        n, last = extensions(row, text)
        # A stated term says when the first pause ends; once it was extended,
        # that date says nothing about today.
        if not out["ends_on"] and not n and _s(row.get("status")) != "extended":
            iso = _term_end(_s(row.get("date_enacted_iso")), text)
            if iso:
                out["ends_on"], out["ends_on_basis"] = iso, "term"
        out["extensions"] = str(n)
        out["last_extended_on"] = last
        out["drafting"], out["drafting_note"] = drafting(text)
    start = _start(row.get("date_enacted_iso")) or (
        _start(_text_start(text)) if out["ends_on_basis"] == "term" else None)
    if start and start <= today:
        stop = today
        end = _end(out["ends_on"])
        if end and end < today:
            stop = end
        months = (stop.year - start.year) * 12 + (stop.month - start.month) + (stop.day - start.day) / 30.4
        out["months_in_force"] = f"{max(months, 0.0):.1f}"
    return out


def stamp(row: dict, today: date | None = None) -> dict:
    row.update(derive(row, today))
    return row


def _selftest() -> None:
    t = date(2026, 11, 19)
    r = derive({"restriction_type": "moratorium", "status": "extended", "date_enacted_iso": "2025-02-24",
                "description": "The original 12-month moratorium (Ordinance 2806, adopted 2025-02-24) was extended "
                               "12 additional months by Ordinance 2833, adopted March 9, 2026; runs through "
                               "2027-02-24. The city is drafting BESS siting standards."}, t)
    assert r["term"] == "temporary" and r["ends_on"] == "2027-02-24" and r["ends_on_basis"] == "text", r
    assert r["extensions"] == "1" and r["last_extended_on"] == "2026-03-09", r
    assert r["drafting"] == "active" and r["months_in_force"] == "20.8", r
    assert derive({"restriction_type": "setback"}, t) == dict.fromkeys(FIELDS, "")
    sabin = {"restriction_type": "ban_or_moratorium", "description": "Town of X: Ban / Moratorium (solar)"}
    assert derive(sabin, t)["term"] == "unclear"
    assert derive({**sabin, "description": "Large-scale solar is not allowed in any district."}, t)["term"] \
        == "permanent"
    assert derive({"restriction_type": "ban", "description": "Wind energy facilities are prohibited."}, t)["term"] \
        == "permanent"
    lapsed = derive({"restriction_type": "moratorium", "date_enacted_iso": "2026-01-13",
                     "current_end_date_iso": "2026-10-01",
                     "description": "Unless extended, it ends then. The county adopted its new zoning code, "
                                    "officially ending the moratorium."}, t)
    assert lapsed["extensions"] == "0" and lapsed["drafting"] == "adopted" and lapsed["months_in_force"] == "8.6", \
        lapsed
    # A stated term counted from the month and year the text names, and an
    # extension's month-precision end (a reader's review of the pilot, 2026-11-19).
    sabin = derive({"restriction_type": "moratorium", "status": "active",
                    "description": "In September 2023, the county enacted a 6-month moratorium on solar "
                                   "applications."}, date(2026, 11, 19))
    assert (sabin["ends_on"], sabin["ends_on_basis"], sabin["months_in_force"]) == ("2024-03", "term", "7.0"), sabin
    ext = derive({"restriction_type": "moratorium", "status": "active",
                  "description": "In September 2023, the county enacted a 6-month moratorium. In March 2024, the "
                                 "commission extended the moratorium until September 2024. In August 2024, the "
                                 "county adopted new regulations, officially ending the moratorium."},
                 date(2026, 11, 19))
    assert (ext["ends_on"], ext["ends_on_basis"], ext["drafting"]) == ("2024-09", "text", "adopted"), ext
    print("moratorium_terms selftest: ok")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
