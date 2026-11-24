"""County briefs (scripts/county_briefs.py) on the shared format
(scripts/brief_core.py): the fact sheet holds only what clients may see, a
brief passes only while its records are unchanged, and the drafter's and
reviewer's packets are checked before a brief is kept."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import brief_core  # noqa: E402
import county_briefs  # noqa: E402
import review_packets  # noqa: E402
import site_profile  # noqa: E402

FIPS = "21181"  # Nicholas County, KY: three instruments, one contested project


@pytest.fixture(scope="module")
def data():
    return site_profile.Data(local=False)


@pytest.fixture(scope="module")
def cfg():
    return county_briefs.load_config()


@pytest.fixture(scope="module")
def sheet(data, cfg):
    return county_briefs.facts(data, FIPS, cfg)


def test_the_core_matches_its_lock_and_passes_its_selftest():
    lock = json.loads((ROOT / "config" / "brief_format.lock").read_text(encoding="utf-8"))
    assert hashlib.sha256((ROOT / "scripts" / "brief_core.py").read_bytes()).hexdigest() == lock["core_sha256"]
    assert lock["format_version"] == brief_core.FORMAT_VERSION
    brief_core._selftest()
    assert county_briefs.compare_lock(ROOT / "config" / "brief_format.lock") == []


def test_every_section_is_a_portal_section_with_a_known_table(cfg):
    tables = {"restrictions", "state_policies", "contested_projects", "cases"}
    ids = [s["id"] for s in cfg["sections"]]
    assert len(ids) == len(set(ids)) and {s["facts"] for s in cfg["sections"]} <= tables
    assert set(cfg["township"]) == {"no_zoning_power", "where_county_unzoned", "own_rules_else_county",
                                    "township_primary"}


def test_the_fact_sheet_holds_no_internal_field_and_no_date_that_moves(sheet):
    facts = [f for sec in sheet["sections"].values() for f in sec["facts"]]
    keys = {k for f in facts for k in f["values"]}
    assert not keys & {"severity_score", "severity_basis", "months_in_force", "status_as_of"}, keys
    assert facts and all(f["id"] and f["source_url"].startswith("http") for f in facts)
    assert len(sheet["sections"]["renewables"]["facts"]) == 3  # one fact per instrument, not per technology


def test_the_digest_is_stable_and_follows_the_records(data, cfg, sheet):
    again = county_briefs.facts(data, FIPS, cfg)
    assert again["digest"] == sheet["digest"] == brief_core.facts_digest(sheet)
    changed = json.loads(json.dumps(sheet))
    changed["sections"]["renewables"]["facts"][0]["values"]["status"] = "lifted"
    assert brief_core.facts_digest(changed) != sheet["digest"]


def _packets(sheet):
    r = [f["id"] for f in sheet["sections"]["renewables"]["facts"]]
    s = [f["id"] for f in sheet["sections"]["state_rules"]["facts"]]
    p = [f["id"] for f in sheet["sections"]["renewable_projects"]["facts"]]
    draft = {"packet": "draft", "queue": "brief", "key": FIPS, "facts_digest": sheet["digest"],
             "agent": "agent:brief-drafter-1 (Claude Code, 2026-11-24)", "date": "2026-11-24",
             "headline": [
                 {"text": "Nicholas County has a solar ordinance and two moratoria on record.", "facts": r},
                 {"text": "The state siting board reviews larger plants.", "facts": s},
                 {"text": "South Fork Solar is on record as pending.", "facts": p}],
             "sections": {"renewables": {"text": "Three county rules are on record.", "facts": r},
                          "state_rules": {"text": "Kentucky's siting board reviews larger plants.", "facts": s},
                          "renewable_projects": {"text": "One contested project is on record.", "facts": p}},
             "note": "test draft"}
    review = {"packet": "review", "queue": "brief", "key": FIPS, "facts_digest": sheet["digest"],
              "agent": "agent:blind-reviewer-1 (Claude Code, 2026-11-24)", "date": "2026-11-24",
              "verdict": "confirmed", "note": "each item checked against its facts",
              "items": [{"where": f"headline {i}", "supported": True, "problem": ""} for i in (1, 2, 3)]}
    return draft, review


def test_a_confirmed_draft_is_accepted_and_published(tmp_path, data, cfg, sheet):
    draft, review = _packets(sheet)
    brief, problems = county_briefs.accept(draft, review, sheet, cfg)
    assert problems == []
    assert brief["made_by"]["drafter"] != brief["made_by"]["reviewer"]
    out = tmp_path / "county_briefs.json"
    doc = county_briefs.publish(data, cfg, {FIPS: brief}, out)
    assert [b["fips"] for b in doc["briefs"]] == [FIPS] and doc["held"] == {}
    stale = {**brief, "facts_digest": "0" * 64}
    doc = county_briefs.publish(data, cfg, {FIPS: stale}, out)
    assert doc["briefs"] == [] and any("stale" in p for p in doc["held"][FIPS])


def test_a_draft_is_refused_when_the_review_disagrees_or_the_text_breaks_a_rule(cfg, sheet):
    draft, review = _packets(sheet)
    bad_review = {**review, "verdict": "contradicts",
                  "items": [{"where": "headline 1", "supported": False, "problem": "no moratorium in facts"}]}
    assert any("does not confirm" in p for p in county_briefs.accept(draft, bad_review, sheet, cfg)[1])
    causal = json.loads(json.dumps(draft))
    causal["headline"][0]["text"] = "Residents' objections led to two moratoria."
    assert any("led to" in p for p in county_briefs.accept(causal, review, sheet, cfg)[1])
    scored = json.loads(json.dumps(draft))
    scored["headline"][0]["text"] = "Its Record Score is high."
    assert any("Record Score" in p for p in county_briefs.accept(scored, review, sheet, cfg)[1])


def test_the_packet_checks_know_the_brief_queue(sheet):
    draft, review = _packets(sheet)
    assert review_packets.check_packet(draft)[0] == []
    assert review_packets.check_packet(review)[0] == []
    wrong = {**review, "items": [{"where": "headline 1", "supported": False, "problem": "x"}]}
    assert any("that is contradicts" in e for e in review_packets.check_packet(wrong)[0])


def test_the_township_rule_comes_from_the_zoning_survey():
    zoning = {"states": {"MI": {"township_land_use": {"role": "own_rules_else_county", "basis": "statute",
                                                      "confidence": "high", "citations": []}}}}
    assert county_briefs.township_rule("MI", zoning) == {"role": "own_rules_else_county", "basis": "statute",
                                                         "confidence": "high"}
    assert county_briefs.township_rule("KY", zoning) == {}


def test_the_blind_card_carries_no_drafter_view(cfg, sheet):
    draft, _ = _packets(sheet)
    card = county_briefs.blind(draft, sheet, cfg)
    text = json.dumps(card)
    assert "brief-drafter" not in text and "test draft" not in text
    assert [c["where"] for c in card["claims"]][:3] == ["headline 1", "headline 2", "headline 3"]
