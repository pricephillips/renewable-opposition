"""Packets between research agents (scripts/review_packets.py, docs/AGENTS.md):
cards, blind cards, packet checks and the reconciliation of two readings."""
import csv
import io
import json
from datetime import date

import pytest
import review_packets as rp

TODAY = date(2026, 10, 16)
DRAFTER = "agent:instrument-reader-1 (Claude Code, 2026-10-16)"
REVIEWER = "agent:blind-reviewer-1 (Claude Code, 2026-10-16)"
URL = "https://www.townofglenville.org/local-law-7-2025.pdf"

RECORDS = [
    {"instrument_id": "mn:ny-x", "state": "NY", "jurisdiction": "Glenville", "technology": "battery_storage",
     "status": "extended", "restriction_type": "moratorium", "description": "BESS moratorium."},
    {"instrument_id": "mn:ny-x", "state": "NY", "jurisdiction": "Glenville", "technology": "solar",
     "status": "extended", "restriction_type": "moratorium", "description": "BESS moratorium."},
]
WORK = [{"instrument_id": "mn:ny-x", "tier": "compiled_record", "located_url": "https://found.example.org/a",
         "search_query": "Glenville moratorium"}]
PRIOR = [{"instrument_id": "mn:ny-x", "primary_source_url": "https://x.example.org/o.pdf", "access": "snippet",
          "note": "2026-10-01: HTTP 403 from the town site"}]


def card():
    return rp.build_card("restriction", "mn:ny-x", RECORDS, WORK, PRIOR,
                         [{"date": "2026-10-01", "queue": "restriction", "key": "mn:ny-x", "outcome": "not_read"}])


def reading(packet="draft", agent=DRAFTER, **kw):
    p = {"packet": packet, "queue": "restriction", "key": "mn:ny-x", "agent": agent, "date": "2026-10-16",
         "result": "read", "source_url": URL, "access": "opened", "archived_url": "", "source_kind": "instrument",
         "document": "Local Law 7 of 2025, Town of Glenville, adopted 2025-06-18", "relation": "is",
         "quote": "No application for a battery energy storage system shall be accepted for 120 days.",
         "fields": [{"field": "status", "record": "extended", "document": "in force", "agrees": True},
                    {"field": "technology", "record": "battery_storage; solar", "document": "battery storage only",
                     "agrees": False}],
         "verdict": "contradicts", "note": "The law covers battery storage only; solar is not named.",
         "attempts": []}
    p.update(kw)
    return p


def test_card_joins_technology_rows_and_carries_earlier_attempts():
    c = card()
    assert c["record"]["technology"] == "battery_storage; solar" and c["rows"] == 2
    assert c["worklist"]["located_url"] == "https://found.example.org/a"
    assert c["prior"]["review_rows"][0]["access"] == "snippet" and c["prior"]["log"][0]["outcome"] == "not_read"
    assert c["review_file"] == "data/review/restriction_sources.csv"
    assert c["slug"] == "mn_ny-x"
    with pytest.raises(ValueError, match="no published or quarantined restriction"):
        rp.build_card("restriction", "nope", RECORDS, WORK, PRIOR, [])


def test_blind_card_carries_the_document_and_nothing_the_drafter_concluded():
    blind = rp.blind_card(card(), reading())
    text = json.dumps(blind)
    assert blind["source_url"] == URL and blind["record"]["jurisdiction"] == "Glenville"
    for leaked in ("contradicts", "solar is not named", "120 days", "snippet", "HTTP 403", "prior",
                   "found.example.org"):
        assert leaked not in text, leaked
    with pytest.raises(ValueError, match="nothing to read a second time"):
        rp.blind_card(card(), reading(result="not_read", attempts=[{"url": URL, "result": "HTTP 403"}]))


@pytest.mark.parametrize("change, error", [
    ({"access": "snippet"}, "not a reading"),
    ({"access": "archived"}, "archived_url"),
    ({"source_kind": "news"}, "never verifies"),
    ({"quote": "short"}, "quote is required"),
    ({"verdict": "confirmed"}, "that is contradicts"),
    ({"fields": []}, "at least one"),
    ({"note": "covers storage — not solar"}, "em dash"),
    ({"agent": "agent:Reader One"}, "agent:<role>-<n>"),
    ({"date": "2026-10-17"}, "after today"),
    ({"source_url": "town site"}, "source_url"),
    ({"relation": ""}, "relation"),
    ({"relation": "other"}, "neither confirms nor contradicts"),
])
def test_a_read_packet_must_show_its_reading(change, error):
    errors, _ = rp.check_packet(reading(**change), TODAY)
    assert any(error in e for e in errors), errors


def test_a_clean_reading_passes_and_a_failed_one_lists_its_attempts():
    assert rp.check_packet(reading(), TODAY) == ([], [])
    failed = reading(result="not_read", verdict="", access="", note="Town site and archive both refused.")
    assert any("attempts" in e for e in rp.check_packet(failed, TODAY)[0])
    failed["attempts"] = [{"url": URL, "result": "HTTP 403"},
                          {"url": "https://web.archive.org/web/2025/" + URL, "result": "no snapshot"}]
    assert rp.check_packet(failed, TODAY) == ([], [])
    assert any("conclusion needs a reading" in e
               for e in rp.check_packet({**failed, "verdict": "confirmed"}, TODAY)[0])


def test_outcome_packets_need_the_event_date_and_a_ladder_value():
    p = reading(queue="outcome", key="S26P-1", verdict="", relation="", source_kind="news",
                outcome="blocked_confirmed",
                evidence_date="2024-05", fields=[{"field": "outcome", "record": "blocked_unverified",
                                                  "document": "permit denied", "agrees": False}])
    assert rp.check_packet(p, TODAY) == ([], [])
    assert any("evidence_date" in e for e in rp.check_packet({**p, "evidence_date": "May 2024"}, TODAY)[0])
    assert any("outcome" in e for e in rp.check_packet({**p, "outcome": "cancelled"}, TODAY)[0])
    assert any("_confirmed" in w for w in rp.check_packet({**p, "outcome": "blocked_unverified"}, TODAY)[1])
    assert any("source_kind" in e for e in rp.check_packet({**p, "source_kind": "tracker"}, TODAY)[0])


def test_two_agreeing_readings_make_one_signed_row():
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER, note="Only storage is named."),
                       [], TODAY)
    assert res["result"] == "written" and res["differences"] == []
    row = res["row"]
    assert list(row) == rp.RESTRICTION_FIELDS
    assert row["verdict"] == "contradicts" and row["access"] == "opened" and row["primary_source_url"] == URL
    assert row["reviewer"] == f"{DRAFTER} + {REVIEWER}"
    assert "120 days" in row["note"] and "Only storage is named." in row["note"]
    assert res["log"]["outcome"] == "written" and res["log"]["date"] == "2026-10-16"
    line = rp.csv_line(row, rp.RESTRICTION_FIELDS)
    assert line.endswith("\n") and next(csv.reader(io.StringIO(line)))[0] == "mn:ny-x"


def test_readings_that_differ_are_disputed_and_write_nothing():
    review = reading("review", REVIEWER, verdict="confirmed",
                     fields=[{"field": "technology", "record": "battery_storage; solar",
                              "document": "storage and solar", "agrees": True}])
    res = rp.reconcile(card(), reading(), review, [], TODAY)
    assert res["result"] == "disputed" and res["row"] is None
    assert any(d.startswith("verdict") for d in res["differences"])
    other = rp.reconcile(card(), reading(), reading("review", REVIEWER, relation="amends"), [], TODAY)
    assert other["result"] == "disputed" and other["differences"] == ["relation: draft is, review amends"]
    assert any(d.startswith("technology") for d in res["differences"])
    assert res["log"]["outcome"] == "disputed" and REVIEWER in res["log"]["note"]


# A field both readings can fault, so a "contradicts" verdict names a disagreeing field.
ADOPTED = {"field": "restriction_type", "record": "moratorium", "document": "siting law", "agrees": False}


@pytest.mark.parametrize("a, b, field", [
    ("297", "297", "capacity_mw"),
    ("297 MW nameplate", "297", "capacity_mw"),
    ("1,200 acres", "1200 Acres.", "acreage"),
    ("2.5 MW", "2.5 MW (nameplate)", "capacity_mw"),
    ("Jacumba Valley Ranch (JVR) Energy Park",
     "Jacumba Valley Ranch (JVR) Energy Park, BayWa r.e., 127 MW solar and 70 MW storage in Jacumba",
     "project_name"),
    ("Stony Creek Wind Farm NY (EIA plant 58088)", "Stony Creek Wind Farm NY (EIA plant 58088), Wyoming County",
     "project_name"),
    ("Big Sky Solar", "Big Sky Solar (Lightsource bp)", "name"),
    ("", "", "status"),
    ("§", " § ", "status"),
])
def test_values_that_differ_only_in_formatting_are_the_same(a, b, field):
    assert rp._same_value(a, b, field) and rp._same_value(b, a, field)


@pytest.mark.parametrize("a, b, field", [
    ("297", "300", "capacity_mw"), ("not 300", "300", "capacity_mw"), ("2970", "297", "capacity_mw"),
    ("297", "", "capacity_mw"), ("storage and solar", "battery storage only", "technology"),
    # Added words that change what the value says.
    ("in force", "in force until 2025-03-01, since lapsed", "status"), ("moratorium", "moratorium lifted", "status"),
    ("adopted", "adopted, later repealed", "status"), ("solar", "solar excluded", "technology"),
    ("300", "300 not", "capacity_mw"), ("battery storage", "battery storage not covered", "technology"),
    ("yes", "yes, but repealed in 2025", "status"), ("in force", "in force through 2025-03-01", "status"),
    ("moratorium", "moratorium, sunset June 2025", "status"), ("approved", "approved conditionally", "status"),
    ("approved", "approved, vacated by the court", "status"), ("solar", "solar and wind", "technology"),
    ("$1.5", "$1.5 million", "cost"), ("297 MW", "297 MW nameplate, 250 MW AC", "capacity_mw"),
    ("500 ft", "500 ft maximum", "setback"), ("500 ft", "500 ft or less", "setback"), ("50", "50%", "share"),
    # A name followed by words that change what it refers to, or by anything in a field that is not a name.
    ("Stony Creek Wind Farm NY (EIA plant 58088)",
     "Stony Creek Wind Farm NY (EIA plant 58088); no EIA-860M plant is named Orangeville", "project_name"),
    ("Jacumba Valley Ranch", "Jacumba Valley Ranch, BayWa r.e.", "status"),
    # Decimals, signs, comparisons and digit groups are part of the value.
    ("2", "2.5 MW", "capacity_mw"), ("297", "297.5", "capacity_mw"), ("0", "0.5 mile", "setback"),
    ("1", "1 000", "setback"), (">= 300 ft", "<= 300 ft", "setback"), ("<500", ">500", "setback"),
    ("-5", "5", "change"), ("\u22125", "5", "change"), ("≥ 1,000 ft", "≤ 1,000 ft", "setback"),
    (".5 mile", "5 mile", "setback"), ("1/2", "1-2", "setback"), ("~300", "300", "setback"),
    # A value of symbols alone is not empty.
    ("§", "", "status"), ("§", "—", "status"),
    # Only exact name fields get the looser rule, and a name's suffix may name another project or phase.
    ("297", "297 MW, later reduced to 250", "nameplate_mw"), ("297", "297 then 150", "nameplate_capacity"),
    ("Stony Creek Wind Farm", "Stony Creek Wind Farm Phase 2", "project_name"),
    ("Stony Creek Wind Farm", "Stony Creek Wind Farm II", "project_name"),
    ("Stony Creek Wind Farm", "Stony Creek Wind Farm, Phase 2", "project_name"),
    ("Big Sky Solar", "Big Sky Solar Storage", "project_name"), ("Jacumba Solar", "Jacumba Solar East", "name"),
    # A unit of another size, or two units, is a different value.
    ("297", "297 kW", "capacity"), ("297", "297 GW", "capacity"), ("297", "297 MWh", "capacity"),
    ("500", "500 m", "setback"), ("500 ft", "500 ft m", "setback"), ("1 mile", "1 mile ft", "setback"),
    ("\u20135", "5", "change"),
])
def test_values_that_say_different_things_are_not_the_same(a, b, field):
    assert not rp._same_value(a, b, field) and not rp._same_value(b, a, field)


def test_the_same_value_judged_differently_is_noted_not_disputed():
    draft = reading(fields=reading()["fields"] + [ADOPTED])
    fields = [{"field": "status", "record": "extended", "document": "In force.", "agrees": True},
              {"field": "technology", "record": "battery_storage; solar",
               "document": "Battery-storage only.", "agrees": True}, ADOPTED]
    res = rp.reconcile(card(), draft, reading("review", REVIEWER, fields=fields), [], TODAY)
    assert res["result"] == "written" and res["differences"] == []
    assert res["judgment_differences"] == [
        "technology (draft read 'battery storage only', review read 'Battery-storage only.'; "
        "draft says it differs from the record, review says it matches the record)"]
    assert "judged differently against the record: technology (draft read" in res["row"]["note"]
    assert "judged differently against the record: technology (draft read" in res["log"]["note"]
    same = [{**fields[1], "document": "Battery storage ONLY"}, ADOPTED]
    res = rp.reconcile(card(), draft, reading("review", REVIEWER, fields=same), [], TODAY)
    assert res["result"] == "written" and res["judgment_differences"][0].startswith(
        "technology (both read 'battery storage only';")
    plain = rp.reconcile(card(), reading(), reading("review", REVIEWER), [], TODAY)
    assert "judgment_differences" not in plain and "judged differently" not in plain["row"]["note"]


def test_a_contradiction_needs_a_field_both_readings_fault():
    fields = [{"field": "technology", "record": "battery_storage; solar", "document": "battery storage only",
               "agrees": True}, ADOPTED]
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER, fields=fields), [], TODAY)
    assert res["result"] == "disputed" and res["row"] is None
    assert res["differences"] == ["verdict contradicts: no field both readings mark as disagreeing"]


def test_a_value_extended_with_words_that_change_it_is_disputed():
    fields = [{"field": "status", "record": "extended", "document": "in force until 2025-03-01, since lapsed",
               "agrees": False}, reading()["fields"][1]]
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER, fields=fields), [], TODAY)
    assert res["result"] == "disputed" and res["differences"] == [
        "status: draft reads 'in force' and says it matches the record, review reads "
        "'in force until 2025-03-01, since lapsed' and says it differs from the record"]


def test_a_dispute_names_both_values_and_both_judgments():
    fields = [{"field": "technology", "record": "battery_storage; solar", "document": "storage and solar",
               "agrees": True}, ADOPTED]
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER, fields=fields), [], TODAY)
    assert res["result"] == "disputed" and res["differences"] == [
        "technology: draft reads 'battery storage only' and says it differs from the record, "
        "review reads 'storage and solar' and says it matches the record"]


def test_no_self_review_and_no_mixed_items():
    res = rp.reconcile(card(), reading(), reading("review", DRAFTER), [], TODAY)
    assert res["result"] == "invalid" and any("own reading" in e for e in res["errors"])
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER, key="mn:ny-y"), [], TODAY)
    assert res["result"] == "invalid"


def test_a_second_reader_who_cannot_open_the_source_writes_nothing():
    review = reading("review", REVIEWER, result="not_read", verdict="", access="", note="Blocked.",
                     attempts=[{"url": URL, "result": "HTTP 403"}])
    res = rp.reconcile(card(), reading(), review, [], TODAY)
    assert res["result"] == "not_read" and res["row"] is None and "HTTP 403" in res["log"]["note"]


def test_an_existing_row_is_reported_so_it_is_edited_not_duplicated():
    res = rp.reconcile(card(), reading(), reading("review", REVIEWER), PRIOR, TODAY)
    assert res["result"] == "written" and res["existing"][0]["access"] == "snippet"


def test_cli_row_refuses_a_disputed_item(tmp_path, capsys):
    paths = {}
    review = reading("review", REVIEWER, verdict="confirmed",
                     fields=[{"field": "status", "record": "extended", "document": "in force", "agrees": True}])
    for name, obj in (("card", card()), ("draft", reading()), ("review", review)):
        paths[name] = tmp_path / f"x.{name}.json"
        paths[name].write_text(json.dumps(obj))
    args = ["reconcile", str(paths["card"]), str(paths["draft"]), str(paths["review"]), "--today", "2026-10-16"]
    assert rp.main(args + ["--row"]) == 1
    assert "disputed" in capsys.readouterr().err
    assert rp.main(args + ["--log"]) == 0
    assert capsys.readouterr().out.startswith("2026-10-16,restriction,mn:ny-x,disputed,")
    assert rp.main(["check", str(paths["draft"]), "--today", "2026-10-16"]) == 0


QUEUE = [
    {"queue_id": "q_lead", "review_status": "lead", "source_url": "https://news.example.org/a", "state": "IA",
     "reviewer_notes": "Found by GDELT; placed by the headline.", "raw_path": "data/raw/x.gz"},
    {"queue_id": "q_draft", "review_status": "awaiting_review", "source_url": "https://county.gov/o.pdf",
     "mechanisms": "setback", "mechanism_detail": "1,000 ft", "access": "opened",
     "reviewer_notes": "Drafted by agent:county-examiner-1 (Claude Code, 2026-10-16). Read section 4."},
]
NEGATIVE = [
    {"county_fips": "19113", "scope": "both", "checked_on": "2025-01-02", "drafted_by": "a", "reviewer": "b",
     "note": "old", "sources_checked": "code: x"},
    {"county_fips": "19113", "scope": "restrictions", "checked_on": "2026-10-16", "result": "none_found",
     "drafted_by": "agent:county-examiner-1 (Claude Code, 2026-10-16)", "reviewer": "",
     "note": "Codes set road setbacks only.", "sources_checked": "code: Linn County Code (https://x.gov)"},
]
CANDIDATES = [{"source_record_id": "REC-9", "state": "IN", "project_name": "Grandview Solar",
               "litigation_context": "Landowners sued.", "reviewer_notes": "earlier try", "case_name": ""}]


def test_blind_rows_carry_claims_and_never_a_note_or_signer():
    lead = rp.blind_row("lead", "q_lead", QUEUE, [], [])
    assert lead["record"]["reviewer_notes"].startswith("Found by GDELT") and "raw_path" not in lead["record"]
    assert lead["expect"]["queue"] == "lead" and lead["source_url"] == "https://news.example.org/a"
    with pytest.raises(ValueError, match="not an untriaged lead"):
        rp.blind_row("lead", "q_draft", QUEUE, [], [])

    row = rp.blind_row("queue_row", "q_draft", QUEUE, [], [])
    text = json.dumps(row)
    assert row["claim"]["mechanism_detail"] == "1,000 ft" and row["archived_url"] == ""
    assert "county-examiner" not in text and "section 4" not in text and "awaiting_review" not in text

    check = rp.blind_row("negative_check", "19113", [], [], NEGATIVE)
    assert check["claim"]["checked_on"] == "2026-10-16"
    assert "road setbacks" not in json.dumps(check) and "drafted_by" not in check["claim"]
    with pytest.raises(ValueError, match="no held negative check"):
        rp.blind_row("negative_check", "19001", [], [], NEGATIVE)


def test_a_case_blind_card_carries_the_court_records_and_not_the_reading():
    draft = {"queue": "case", "key": "REC-9", "cases": [
        {"case_name": "Wike v. Grandview Solar", "case_source_url": "https://www.courtlistener.com/opinion/1/"}]}
    card = rp.blind_row("case", "REC-9", [], CANDIDATES, [], draft)
    assert card["source_urls"] == ["https://www.courtlistener.com/opinion/1/"]
    assert "Wike" not in json.dumps(card) and "earlier try" not in json.dumps(card)
    with pytest.raises(ValueError, match="--draft"):
        rp.blind_row("case", "REC-9", [], CANDIDATES, [], None)


STATUS_DRAFTER = "agent:status-checker-1 (Claude Code, 2026-10-16)"
NREL = [{"instrument_id": "nrel:wind:31065", "state": "NE", "jurisdiction": "Furnas County", "technology": "wind",
         "status": "unknown", "restriction_type": "setback", "currency": "unknown"}]


def status_reading(packet="draft", agent=STATUS_DRAFTER, **kw):
    p = {"packet": packet, "queue": "status", "key": "nrel:wind:31065", "agent": agent, "date": "2026-10-16",
         "result": "read", "source_url": "https://furnascounty.ne.gov/zoning.pdf", "access": "opened",
         "archived_url": "", "source_kind": "official_copy",
         "document": "Furnas County Zoning Regulations, Article 7, current through 2026-02-10", "relation": "is",
         "quote": "No wind turbine shall be located within 2,000 feet of a non-participating dwelling.",
         "fields": [{"field": "status", "record": "unknown", "document": "in the current code", "agrees": False}],
         "status": "active", "end_date": "", "evidence_date": "2026-02-10",
         "note": "The current zoning code holds the wind setbacks NREL compiled.", "attempts": []}
    p.update(kw)
    return p


def test_a_status_card_points_at_status_resolutions():
    c = rp.build_card("status", "nrel:wind:31065", NREL, [], [], [])
    assert c["review_file"] == "data/review/status_resolutions.csv" and c["record"]["currency"] == "unknown"
    assert "instrument" in c["source_kinds"] and "news" not in c["source_kinds"]


@pytest.mark.parametrize("change, error", [
    ({"status": "repealed"}, "status 'repealed'"),
    ({"status": "lifted"}, "needs end_date"),
    ({"status": "expired", "end_date": "June 2026"}, "end_date"),
    ({"relation": "repeals"}, "a repealed instrument is lifted"),
    ({"evidence_date": ""}, "evidence_date"),
    ({"source_kind": "news"}, "never verifies"),
    ({"relation": "other"}, "neither confirms nor contradicts"),
    ({"status": "extended", "relation": "extends", "end_date": "2027-01"}, "full YYYY-MM-DD"),
    ({"status": "lifted", "relation": "repeals", "end_date": "2026-12-01"}, "after the reading"),
])
def test_a_status_packet_must_settle_the_status_from_a_reading(change, error):
    errors, _ = rp.check_packet(status_reading(**change), TODAY)
    assert any(error in e for e in errors), errors


def test_a_clean_status_reading_passes_and_lifted_needs_its_date():
    assert rp.check_packet(status_reading(), TODAY) == ([], [])
    lifted = status_reading(status="lifted", relation="repeals", end_date="2025-11-04")
    assert rp.check_packet(lifted, TODAY) == ([], [])
    failed = status_reading(result="not_read", status="", access="", note="Site and archive refused.",
                            attempts=[{"url": "https://furnascounty.ne.gov/zoning.pdf", "result": "HTTP 403"}])
    assert rp.check_packet(failed, TODAY) == ([], [])
    assert any("status is set" in e for e in rp.check_packet({**failed, "status": "active"}, TODAY)[0])


def test_two_agreeing_status_readings_make_one_status_row():
    c = rp.build_card("status", "nrel:wind:31065", NREL, [], [], [])
    draft = status_reading(status="lifted", relation="repeals", end_date="2025-11")
    review = status_reading("review", REVIEWER, status="lifted", relation="repeals", end_date="2025-11-04",
                            note="Ordinance 2025-9 repealed Article 7.")
    res = rp.reconcile(c, draft, review, [], TODAY)
    assert res["result"] == "written"
    row = res["row"]
    assert list(row) == rp.STATUS_FIELDS
    assert row["status"] == "lifted" and row["end_date"] == "2025-11-04"          # the more precise date
    assert row["evidence_date"] == "2026-02-10" and row["reviewer"] == f"{STATUS_DRAFTER} + {REVIEWER}"
    assert row["jurisdiction"] == "Furnas County" and res["log"]["queue"] == "status"
    other = rp.reconcile(c, draft, {**review, "end_date": "2024-03-01"}, [], TODAY)
    assert other["result"] == "disputed" and any(d.startswith("end_date") for d in other["differences"])
    active = rp.reconcile(c, status_reading(), status_reading("review", REVIEWER, status="lifted",
                                                              relation="repeals", end_date="2025-11"), [], TODAY)
    assert active["result"] == "disputed" and any(d.startswith("status") for d in active["differences"])


def test_a_hand_queued_lead_reaches_the_second_reader_without_its_notes():
    hand = {"queue_id": "q_hand", "review_status": "lead", "source_url": "https://city.gov/agenda.pdf",
            "state": "TX", "reviewer_notes": "Both readings of q_1 say Section 1208 is a siting law."}
    card = rp.blind_row("lead", "q_hand", [hand], [], [])
    assert "reviewer_notes" not in card["record"] and "Section 1208" not in json.dumps(card)
    assert card["notes_withheld"].startswith("queued by hand")
    harvested = rp.blind_row("lead", "q_lead", QUEUE, [], [])
    assert "notes_withheld" not in harvested


def claim(**kw):
    p = {"packet": "review", "queue": "queue_row", "key": "q_draft", "agent": REVIEWER, "date": "2026-10-16",
         "result": "read", "verdict": "contradicts", "source_url": "https://county.gov/o.pdf", "access": "opened",
         "archived_url": "", "quote": "No turbine shall stand within 1,500 feet of any dwelling.",
         "fields": [{"field": "mechanism_detail", "claimed": "1,000 ft", "document": "1,500 feet", "agrees": False}],
         "note": "The ordinance sets 1,500 feet, not 1,000.", "attempts": []}
    p.update(kw)
    return p


def test_claim_checks_pass_the_checker_and_must_agree_with_their_fields():
    assert rp.check_packet(claim(), TODAY) == ([], [])
    assert rp.check_packet(claim(queue="negative_check", key="19113"), TODAY) == ([], [])
    agree = [{"field": "mechanism_detail", "claimed": "1,500 ft", "document": "1,500 feet", "agrees": True}]
    assert rp.check_packet(claim(verdict="confirmed", fields=agree), TODAY) == ([], [])
    assert any("that is contradicts" in e for e in rp.check_packet(claim(verdict="confirmed"), TODAY)[0])
    assert any("names no field" in e for e in rp.check_packet(claim(fields=agree), TODAY)[0])
    assert any("snippet" in e for e in rp.check_packet(claim(access="snippet"), TODAY)[0])
    unread = claim(result="not_read", verdict="unverifiable", quote="", fields=[], access="",
                   attempts=[{"url": "https://county.gov/o.pdf", "result": "HTTP 403"}])
    assert rp.check_packet(unread, TODAY) == ([], [])
    assert any("unverifiable" in e for e in rp.check_packet({**unread, "verdict": "confirmed"}, TODAY)[0])
    assert any("attempts" in e for e in rp.check_packet({**unread, "attempts": []}, TODAY)[0])


def lead(**kw):
    item = {"queue_id": "q_lead", "decision": "pending", "on_topic": True, "placed": True, "duplicate_of": "",
            "read": True, "source_url": "https://news.example.org/a", "access": "opened", "archived_url": "",
            "source_kind": "news", "set": {"county": "Linn County"},
            "quote": "The Linn County board adopted a solar moratorium on Monday.",
            "note": "The article names Linn County and the moratorium.", "attempts": []}
    item.update(kw)
    return item


def test_lead_triage_packets_are_checked_item_by_item():
    batch = {"packet": "draft", "queue": "lead", "agent": DRAFTER, "date": "2026-10-16",
             "leads": [lead(), lead(queue_id="q_2", decision="rejected", on_topic=False, set={}, read=False,
                                    access="snippet", quote="")]}
    assert rp.check_packet(batch, TODAY) == ([], [])
    headline = lead(queue_id="q_3", read=False, access="snippet", quote="Linn County OKs solar moratorium")
    assert rp.check_packet({**batch, "leads": [headline]}, TODAY) == ([], [])
    bad = {**batch, "leads": [lead(decision="rejected"),
                              lead(queue_id="", read=False, access="snippet", set={"status": "active"}),
                              lead(decision="duplicate")]}
    errors = rp.check_packet(bad, TODAY)[0]
    assert any("leads[1] q_lead: decision rejected" in e for e in errors)
    assert any("queue_id is required" in e for e in errors)
    assert any("set status from a source that was not read" in e for e in errors)
    assert any("duplicate_of" in e for e in errors)
    # The blind second triage is one lead, keyed like its card.
    review = {"packet": "review", "queue": "lead", "key": "q_lead", "agent": REVIEWER, "date": "2026-10-16",
              **{k: v for k, v in lead(result="read").items() if k not in ("queue_id", "read")}}
    assert rp.check_packet(review, TODAY) == ([], [])


def test_case_packets_need_a_court_record_for_each_case():
    p = {"packet": "draft", "queue": "case", "key": "REC-9", "agent": DRAFTER, "date": "2026-10-16",
         "result": "read", "note": "The opinion names the project and the county.", "attempts": [],
         "cases": [{"case_name": "Wike v. Grandview Solar", "court": "Indiana Court of Appeals",
                    "court_level": "state_appellate", "docket_number": "23A-PL-1", "case_status": "pending",
                    "case_source_url": "https://www.courtlistener.com/opinion/1/", "access": "opened",
                    "archived_url": "", "quote": "Landowners appeal the approval of Grandview Solar."}]}
    assert rp.check_packet(p, TODAY) == ([], [])
    errors = rp.check_packet({**p, "cases": [{**p["cases"][0], "court": "", "access": "snippet"}]}, TODAY)[0]
    assert any("missing court" in e for e in errors) and any("snippet" in e for e in errors)
    assert any("needs cases" in e for e in rp.check_packet({**p, "cases": []}, TODAY)[0])
    assert any("queue 'other'" in e for e in rp.check_packet({**p, "queue": "other"}, TODAY)[0])


def test_a_quarantined_record_gets_a_card_that_says_why_it_is_held():
    held = [{**RECORDS[0], "entity": "restrictions",
             "qc_issues": [{"code": "PRIMARY_SOURCE_CONTRADICTS", "severity": "HIGH"}]},
            {"entity": "contested_projects", "instrument_id": "mn:ny-x"}]
    c = rp.build_card("status", "mn:ny-x", [], [], [], [], held)
    assert c["quarantined"] == ["PRIMARY_SOURCE_CONTRADICTS"] and c["rows"] == 1
    assert c["record"]["jurisdiction"] == "Glenville"
    # A published record is carded from the published rows, with no quarantine line.
    assert "quarantined" not in rp.build_card("status", "mn:ny-x", RECORDS, [], [], [], held)
    # The blind card never says the record is held for a contradiction.
    draft = {"queue": "status", "key": "mn:ny-x", "result": "read", "source_url": URL}
    assert "quarantined" not in rp.blind_card(c, draft) and "CONTRADICTS" not in json.dumps(rp.blind_card(c, draft))
