"""The live intake registry and its output hold their rules: every GDELT query
is one GDELT accepts, every extractor ships with its own offline test, the
committed queue keeps parse.py's columns, and every lead in it already meets
the lead contract (the intake workflow runs this file on the fresh queue
before it commits)."""
import dataclasses
import re
from pathlib import Path

import common
import fetch
import parse

ROOT = Path(__file__).resolve().parent.parent
# GDELT answered a 246-character query and refused a 303-character one with
# HTTP 200 and a line of text (probed 2026-10-13); stay well under.
GDELT_MAX_QUERY = 240


def _gdelt_queries():
    for s in fetch.load_sources(fetch.CONFIG_PATH):
        if "gdeltproject.org" in s.get("url", ""):
            for req in s.get("requests", []):
                yield req.get("label", ""), req["params"]["query"]


def test_every_gdelt_query_is_one_gdelt_accepts():
    queries = list(_gdelt_queries())
    assert queries
    for label, q in queries:
        assert len(q) <= GDELT_MAX_QUERY, (label, len(q))
        assert "sourcecountry:US" in q, label
        depth, outside = 0, []
        for tok in re.findall(r'"[^"]*"|\(|\)|[^\s()"]+', q):
            if tok == "(":
                depth += 1
                assert depth == 1, f"{label}: GDELT refuses nested parentheses"
            elif tok == ")":
                depth -= 1
            elif depth == 0:
                outside.append(tok)
        assert depth == 0, f"{label}: unbalanced parentheses"
        assert "OR" not in outside, f"{label}: GDELT requires every OR inside parentheses"
        for word in re.findall(r'"([^"]*)"|\b(\w+)\b', q):
            term = word[0] or word[1]
            assert len(term) >= 3 or term in ("OR", "US"), f"{label}: term {term!r} is too short for GDELT"


def test_every_extractor_ships_with_an_offline_test():
    for path in sorted((ROOT / "scripts" / "extractors").glob("*.py")):
        sid = path.stem
        tested = (ROOT / "tests" / f"test_intake_{sid}.py").exists() or sid == "courtlistener_renewables"
        assert tested, f"scripts/extractors/{sid}.py has no tests/test_intake_{sid}.py"


def test_every_intake_source_says_what_its_body_must_be():
    for s in fetch.active_sources(fetch.load_sources(fetch.CONFIG_PATH), intake=True):
        assert s.get("expect") in ("json", "xml", "html", "csv"), s["source_id"]


def test_the_committed_queue_keeps_parse_columns():
    header = (ROOT / "data" / "review" / "queue.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == parse.QUEUE_FIELDS


def test_every_committed_lead_meets_the_lead_contract():
    for i, row in enumerate(common.read_csv(ROOT / "data" / "review" / "queue.csv"), start=2):
        if row.get("review_status") != parse.LEAD:
            continue
        c = parse.CandidateRecord(**{k: row.get(k, "") for k in parse.QUEUE_FIELDS})
        before = dataclasses.asdict(c)
        assert parse.sanitize(c), f"queue.csv row {i}: entity_type {row.get('entity_type')!r}"
        after = dataclasses.asdict(c)
        changed = {k: (before[k], after[k]) for k in before if before[k] != after[k] and k != "reviewer_notes"}
        assert not changed, f"queue.csv row {i}: {changed}"
        assert row["queue_id"].startswith("q_") and row["source_id"], f"queue.csv row {i}"
