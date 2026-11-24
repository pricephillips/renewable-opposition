"""
brief_core.py

The shared core of the county brief (plain-English county summaries): the
format of a county's fact sheet and of the brief drafted from it, and the
check every brief must pass before a page shows it.

A brief has two parts. The headline is 3 to 5 bullets for the top of a county
page. Each section line is one or two sentences that open a page section
(a reader folds it open or closed). Every bullet and line names the facts it
rests on, and every fact is a published record with its id and source. The
check refuses a brief when:

- its fact sheet has changed since it was drafted (the digest differs), so a
  brief never outlives the records it describes;
- it cites a fact the sheet does not hold, or a bullet cites a section the
  page does not show;
- a number in the text is not in a fact it cites (dates, sizes, distances,
  counts and vote tallies all count as numbers);
- it uses a causal, predictive or scorekeeping word, first person, an em or
  en dash, or a term the product keeps internal;
- it is too long (bullets, sentences, words).

This file is copied byte for byte into renewable-opposition
(scripts/brief_core.py) from data-centers (brief_core.py) and pinned in both
repositories by brief_format.lock, as variable_core.py is. Keep it standard
library only, with no repository paths and no import from either repository.
What a product's facts are, which sections it has and which terms it keeps
internal belong in that repository's own brief script and config.

Changing anything here changes the format: bump the lock in both
repositories in the same week.

Usage
  python brief_core.py --selftest
  python brief_core.py --check BRIEF.json FACTS.json [--refused TERM ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

FORMAT_VERSION = 1
FACTS_FORMAT = "county_brief_facts"
BRIEF_FORMAT = "county_brief"

HEADLINE_MIN, HEADLINE_MAX = 3, 5
SECTION_MAX_SENTENCES = 2
MAX_WORDS = 60  # per bullet, and per section line

# Words that claim a cause, forecast an outcome or keep score. The record
# says what public bodies did; it never says why, or what comes next.
BANNED = [
    r"because", r"caus\w*", r"led to", r"lead to", r"leads to", r"due to", r"as a result",
    r"result(?:ed|s)? in", r"driv(?:e|es|en|ing) by", r"thanks to", r"in response to",
    r"prompt(?:ed|s)?", r"spark(?:ed|s)?", r"trigger(?:ed|s)?", r"fuel(?:ed|led|s)?",
    r"will", r"would", r"likely", r"unlikely", r"probabl\w*", r"expect\w*", r"predict\w*",
    r"forecast\w*", r"chance", r"risk\w*", r"poised", r"set to", r"bound to", r"threat\w*",
    r"win", r"wins", r"won", r"victory", r"victories", r"defeat\w*", r"loss", r"losses", r"lost",
    r"beat", r"backlash", r"crackdown", r"hostile", r"anti-\w+",
    r"we", r"our", r"us", r"i", r"ours",
]
_BANNED = re.compile(r"(?<![\w-])(?:" + "|".join(BANNED) + r")(?![\w-])", re.IGNORECASE)
_DASH = re.compile("[–—]|(?<=\\w) -- ?(?=\\w)")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_NUMBER_WORD = re.compile(r"(?<![\w-])(" + "|".join(_WORDS) + r")(?![\w-])", re.IGNORECASE)
_SENTENCE = re.compile(r"[.!?](?:\s|$)")


def canonical(obj) -> str:
    """The one JSON spelling a digest is taken over: sorted keys, no spaces."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def facts_digest(sheet: dict) -> str:
    """SHA-256 of what a brief may say: the sections' facts and the rules.
    The sheet's made_by, as_of and digest fields are left out, so a rebuild
    with the same records keeps the same digest."""
    body = {"fips": sheet.get("fips"), "product": sheet.get("product"),
            "sections": sheet.get("sections", {}), "rules": sheet.get("rules", {})}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def numbers(text: str) -> set[str]:
    """Every number in a text, normalised: commas and leading zeros dropped,
    so 2,000 and 2000 match and the 08 of 2026-08-14 matches an August 8."""
    out = set()
    for m in _NUMBER.findall(str(text)):
        v = m.replace(",", "").rstrip(".")
        if "." in v:
            v = v.rstrip("0").rstrip(".")
        out.add(v.lstrip("0") or "0")
    for part in re.split(r"[-/]", str(text)):  # ISO dates: 2026-08-14 also gives 2026, 8, 14
        if part.isdigit():
            out.add(part.lstrip("0") or "0")
    return out


def fact_numbers(fact: dict) -> set[str]:
    vals = [fact.get("text", "")] + [str(v) for v in (fact.get("values") or {}).values()]
    out = set()
    for v in vals:
        out |= numbers(v)
    return out


def _fact_index(sheet: dict) -> dict[str, tuple[str, dict]]:
    idx = {}
    for sid, sec in (sheet.get("sections") or {}).items():
        for f in sec.get("facts", []):
            idx[f["id"]] = (sid, f)
    return idx


def sentences(text: str) -> int:
    t = re.sub(r"\b(?:[A-Z]|No|Nos|St|Twp|Co|Inc|Ky|Pa|U\.S)\.", "X", str(text).strip())
    return max(1, len(_SENTENCE.findall(t + " ")))


def _in_name(word: str, names: str) -> bool:
    """A banned word written with a capital, as part of a name a cited fact
    also spells that way (Lost Creek Township, Wills County), is allowed."""
    return word[:1].isupper() and word.lower() not in ("i", "we", "our", "us", "ours") and \
        re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", names) is not None


def text_problems(where: str, text: str, cited: list[dict], refused: list[str],
                  max_sentences: int | None = None) -> list[str]:
    """What is wrong with one bullet or section line, given the facts it cites."""
    out = []
    t = str(text or "").strip()
    if not t:
        return [f"{where}: empty text"]
    words = len(t.split())
    if words > MAX_WORDS:
        out.append(f"{where}: {words} words, more than {MAX_WORDS}")
    if max_sentences and sentences(t) > max_sentences:
        out.append(f"{where}: more than {max_sentences} sentences")
    names = " ".join(str(f.get("text", "")) for f in cited)
    for m in sorted({m.group(0).lower() for m in _BANNED.finditer(t) if not _in_name(m.group(0), names)}):
        out.append(f"{where}: uses '{m}' (causal, predictive, scorekeeping or first person)")
    if _DASH.search(t):
        out.append(f"{where}: em or en dash")
    for term in refused:
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", t, re.IGNORECASE):
            out.append(f"{where}: names '{term}', which the product keeps internal")
    if not cited:
        out.append(f"{where}: cites no fact")
        return out
    allowed = set()
    for f in cited:
        allowed |= fact_numbers(f)
    for n in sorted(numbers(t) - allowed):
        out.append(f"{where}: the number {n} is in no fact it cites")
    for w in sorted({m.group(1).lower() for m in _NUMBER_WORD.finditer(t)}):
        n = _WORDS[w]
        if str(n) not in allowed and n > len(cited):
            out.append(f"{where}: '{w}' is more than the {len(cited)} fact(s) it cites and in none of them")
    return out


def check(brief: dict, sheet: dict, *, refused: list[str] | None = None,
          shown_sections: list[str] | None = None) -> list[str]:
    """Every reason the brief may not be shown. Empty means it passes.
    `refused` lists the terms the product keeps internal. `shown_sections`,
    when given, is the sections the page shows; a bullet citing any other
    section fails (the page cannot show a claim whose section it hides)."""
    refused = list(refused or [])
    out = []
    if brief.get("format") != BRIEF_FORMAT or brief.get("format_version") != FORMAT_VERSION:
        out.append(f"brief is not {BRIEF_FORMAT} version {FORMAT_VERSION}")
    if sheet.get("format") != FACTS_FORMAT or sheet.get("format_version") != FORMAT_VERSION:
        out.append(f"fact sheet is not {FACTS_FORMAT} version {FORMAT_VERSION}")
    for k in ("fips", "product"):
        if brief.get(k) != sheet.get(k):
            out.append(f"{k} {brief.get(k)!r} does not match the fact sheet's {sheet.get(k)!r}")
    if brief.get("facts_digest") != facts_digest(sheet):
        out.append("stale: the fact sheet changed after the brief was drafted")
    made = brief.get("made_by") or {}
    for k in ("drafter", "reviewer"):
        if not made.get(k):
            out.append(f"made_by.{k} is missing")
    if made.get("drafter") and made.get("drafter") == made.get("reviewer"):
        out.append("the drafter and the reviewer are the same")
    idx = _fact_index(sheet)
    with_facts = [s for s, sec in (sheet.get("sections") or {}).items() if sec.get("facts")]

    head = brief.get("headline") or []
    lo = min(HEADLINE_MIN, max(1, len(idx)))
    if not lo <= len(head) <= HEADLINE_MAX:
        out.append(f"headline has {len(head)} bullets; it needs {lo} to {HEADLINE_MAX}")
    for i, b in enumerate(head, 1):
        ids = b.get("facts") or []
        missing = [x for x in ids if x not in idx]
        if missing:
            out.append(f"headline {i}: cites facts not in the sheet: {', '.join(missing)}")
        cited = [idx[x][1] for x in ids if x in idx]
        secs = sorted({idx[x][0] for x in ids if x in idx})
        if shown_sections is not None:
            hidden = [s for s in secs if s not in shown_sections]
            if hidden:
                out.append(f"headline {i}: rests on sections the page does not show: {', '.join(hidden)}")
        out += text_problems(f"headline {i}", b.get("text"), cited, refused)

    for sid, line in (brief.get("sections") or {}).items():
        if sid not in (sheet.get("sections") or {}):
            out.append(f"section {sid}: not a section of the fact sheet")
            continue
        ids = line.get("facts") or []
        wrong = [x for x in ids if idx.get(x, ("",))[0] != sid]
        if wrong:
            out.append(f"section {sid}: cites facts from elsewhere or not in the sheet: {', '.join(wrong)}")
        cited = [idx[x][1] for x in ids if idx.get(x, ("",))[0] == sid]
        out += text_problems(f"section {sid}", line.get("text"), cited, refused, SECTION_MAX_SENTENCES)
    for sid in with_facts:
        if sid not in (brief.get("sections") or {}):
            out.append(f"section {sid}: has facts but no line")
    return out


def _selftest() -> None:
    sheet = {"format": FACTS_FORMAT, "format_version": FORMAT_VERSION, "product": "renewables",
             "fips": "21181", "sections": {
                 "renewables": {"facts": [
                     {"id": "r1", "text": "Nicholas County solar ordinance adopted 2024-06-11",
                      "values": {"setback_ft": "2,000"}, "source_url": "https://example.org/a"},
                     {"id": "r2", "text": "Nicholas County wind moratorium adopted 2026-08-14, one year",
                      "values": {}, "source_url": "https://example.org/b"}]},
                 "state_rules": {"facts": [
                     {"id": "s1", "text": "Kentucky Siting Board decides plants of 10 MW or more",
                      "values": {"threshold_mw": "10"}, "source_url": "https://example.org/c"}]},
                 "empty": {"facts": []}},
             "rules": {"township_role": "none"}}
    good = {"format": BRIEF_FORMAT, "format_version": FORMAT_VERSION, "product": "renewables",
            "fips": "21181", "facts_digest": facts_digest(sheet),
            "made_by": {"drafter": "brief-drafter", "reviewer": "brief-reviewer"},
            "headline": [
                {"text": "The county's 2024 solar ordinance sets a 2,000-foot setback.", "facts": ["r1"]},
                {"text": "A one-year wind moratorium was adopted on August 14, 2026.", "facts": ["r2"]},
                {"text": "The state Siting Board decides plants of 10 MW or more.", "facts": ["s1"]}],
            "sections": {
                "renewables": {"text": "Two county rules are on record, both adopted since 2024.",
                               "facts": ["r1", "r2"]},
                "state_rules": {"text": "Plants of 10 MW or more go to the state Siting Board.",
                                "facts": ["s1"]}}}
    assert check(good, sheet) == [], check(good, sheet)
    assert check(good, sheet, shown_sections=["renewables"]) and \
        "state_rules" in check(good, sheet, shown_sections=["renewables"])[0]

    def bad(edit):
        b = json.loads(json.dumps(good))
        edit(b)
        return check(b, sheet, refused=["Record Score"])

    assert any("number 3,000" in p or "number 3000" in p for p in bad(
        lambda b: b["headline"][0].update(text="It sets a 3,000-foot setback.")))
    assert any("'because'" in p for p in bad(
        lambda b: b["headline"][1].update(text="It paused wind because residents objected.")))
    assert any("'will'" in p for p in bad(
        lambda b: b["headline"][1].update(text="The moratorium will slow wind.")))
    assert any("'our'" in p for p in bad(lambda b: b["headline"][1].update(text="Our reading of 2026.")))
    assert any("dash" in p for p in bad(lambda b: b["headline"][1].update(text="Wind — paused in 2026.")))
    assert any("Record Score" in p for p in bad(
        lambda b: b["headline"][1].update(text="Its Record Score rose in 2026.")))
    assert any("stale" in p for p in bad(lambda b: b.update(facts_digest="0" * 64)))
    assert any("not in the sheet" in p for p in bad(lambda b: b["headline"][0].update(facts=["zz"])))
    assert any("bullets" in p for p in bad(lambda b: b.update(headline=b["headline"][:2])))
    assert any("same" in p for p in bad(lambda b: b["made_by"].update(reviewer="brief-drafter")))
    assert any("sentences" in p for p in bad(lambda b: b["sections"]["renewables"].update(
        text="One rule. Another rule. A third rule.")))
    assert any("elsewhere" in p for p in bad(lambda b: b["sections"]["renewables"].update(facts=["s1"])))
    assert any("no line" in p for p in bad(lambda b: b["sections"].pop("state_rules")))
    assert any("'five'" in p for p in bad(lambda b: b["sections"]["renewables"].update(
        text="Five county rules are on record.")))
    # a rebuild with a new as_of or made_by keeps the digest
    assert facts_digest({**sheet, "as_of": "x", "made_by": {"commit": "y"}}) == facts_digest(sheet)
    assert numbers("On 2026-08-14, 2,000 feet and 4.50 MW") >= {"2026", "8", "14", "2000", "4.5"}
    assert not any("'lost'" in p for p in text_problems(
        "x", "Lost Creek Township adopted a rule in 2026.", [{"text": "Lost Creek Township rule 2026"}], []))
    assert "won" not in {m.group(0) for m in _BANNED.finditer("the Wonder township")}
    print("brief_core selftest: ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check", nargs=2, metavar=("BRIEF", "FACTS"))
    ap.add_argument("--refused", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if a.check:
        with open(a.check[0], encoding="utf-8") as fb, open(a.check[1], encoding="utf-8") as ff:
            problems = check(json.load(fb), json.load(ff), refused=a.refused)
        for p in problems:
            print(p)
        return 1 if problems else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
