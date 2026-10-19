"""Review-queue restriction candidates: every mechanism, scored by the rules
published Sabin rows use, and never promoted from search-index text alone.
Synthetic rows only."""
import common
import parse
import promote_reviewed as pr
import pytest

BASE = {"source_id": "web_research_test", "entity_type": "restriction", "review_status": "confirmed",
        "state": "KS", "county": "Example County", "jurisdiction_type": "County",
        "technology": "wind", "description": "Example County adopted wind siting rules.",
        "source_url": "https://example.gov/ordinance.pdf", "access": "opened", "status": "active"}


def row(**kw):
    return {**BASE, **kw}


@pytest.fixture
def queue(monkeypatch, tmp_path):
    review, seed = tmp_path / "review", tmp_path / "seed"
    review.mkdir()
    seed.mkdir()
    monkeypatch.setattr(pr, "QUEUE_PATH", review / "queue.csv")
    monkeypatch.setattr(pr, "CANDIDATES_PATH", review / "cases_candidates.csv")
    monkeypatch.setattr(pr, "SEED_FOR", {
        "restriction": ("restrictions", seed / "restrictions_seed.csv"),
        "contested_project": ("contested_projects", seed / "contested_projects_seed.csv"),
        "case": ("cases", seed / "cases_seed.csv"),
    })
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])

    def run(*rows):
        common.write_csv(review / "queue.csv", list(rows), parse.QUEUE_FIELDS)
        code = pr.main()
        return (code, common.read_csv(seed / "restrictions_seed.csv"),
                [r["review_status"] for r in common.read_csv(review / "queue.csv")])
    return run


def test_every_mechanism_counts_and_the_score_is_computed(queue):
    code, seeds, status = queue(row(mechanisms="height limit; setback; noise limit",
                                    mechanism_detail="Turbines 3,000 feet from any property line; "
                                                     "height 450 ft; 40 dBA at night."))
    assert code == 0 and status == ["promoted"]
    (s,) = seeds
    # A 3,000 ft wind setback sets the score and so names the type, as for Sabin rows.
    assert (s["severity_score"], s["restriction_type"]) == ("3", "setback")
    assert s["severity_basis"] == "wind setback 3000 ft"
    assert s["mechanisms"] == "height limit, setback, noise limit"
    assert "3,000 feet" in s["long_description"]     # the seed's own column, none added


def test_a_matching_typed_score_is_accepted(queue):
    code, seeds, _ = queue(row(mechanisms="setback", mechanism_detail="500 ft from dwellings",
                               technology="solar", severity_score="2"))
    assert code == 0 and seeds[0]["severity_score"] == "2"
    assert seeds[0]["severity_basis"] == "restricting mechanism (default)"


def test_a_typed_score_that_disagrees_is_a_conflict_and_not_promoted(queue, capsys):
    code, seeds, status = queue(row(mechanisms="setback", mechanism_detail="500 ft from dwellings",
                                    technology="solar", severity_score="3"))
    assert code == 0 and seeds == [] and status == ["confirmed"]
    out = capsys.readouterr().out
    assert "typed severity_score 3 conflicts with the computed 2 for solar" in out


def test_each_technology_is_its_own_row_scored_on_its_own_sentences(queue):
    code, seeds, _ = queue(row(technology="solar;wind", mechanisms="setback",
                               mechanism_detail="Wind turbines 2,640 feet from homes. Solar arrays 200 feet "
                                                "from homes."))
    by_tech = {s["technology"]: s["severity_score"] for s in seeds}
    assert code == 0 and by_tech == {"solar": "2", "wind": "3"}


def test_a_ban_or_an_in_force_moratorium_scores_4_and_pending_is_capped(queue):
    _, seeds, _ = queue(row(mechanisms="moratorium", status="active"),
                        row(mechanisms="ban/prohibition", technology="solar",
                            description="Example County bans commercial solar."),
                        row(mechanisms="setback", status="pending",
                            mechanism_detail="Turbines one mile from homes.",
                            description="Example County proposes wind setbacks."))
    got = sorted((s["restriction_type"], s["severity_score"]) for s in seeds)
    assert got == [("ban", "4"), ("moratorium", "4"), ("setback", "2")]


def test_an_unknown_mechanism_stops_the_promotion(queue, capsys):
    code, seeds, status = queue(row(mechanisms="setback"),
                                row(mechanisms="setback; vibes"))
    assert code == 1 and seeds == [] and status == ["confirmed", "confirmed"]
    assert "unknown mechanism(s) ['vibes']" in capsys.readouterr().err


def test_blank_mechanisms_are_reported(queue, capsys):
    code, seeds, _ = queue(row(mechanisms=""))
    assert code == 0 and seeds == [] and "mechanisms is blank" in capsys.readouterr().out


@pytest.mark.parametrize("etype", ["restriction", "contested_project", "case"])
def test_a_snippet_row_is_never_promoted(queue, capsys, etype):
    code, seeds, status = queue(row(entity_type=etype, mechanisms="setback", access="snippet",
                                    project_name="Example", court_level="state_trial", severity_score=""))
    assert code == 0 and seeds == [] and status == ["confirmed"]
    assert "has to be opened or archived first" in capsys.readouterr().out


@pytest.mark.parametrize("access,archived,msg", [
    ("", "", "access ''"), ("read", "", "access 'read'"), ("archived", "", "archived_url")])
def test_a_blank_unknown_or_unlinked_access_is_reported(queue, capsys, access, archived, msg):
    _, seeds, _ = queue(row(mechanisms="setback", access=access, archived_url=archived))
    assert seeds == [] and msg in capsys.readouterr().out


def test_an_archived_copy_can_be_promoted(queue):
    code, seeds, _ = queue(row(mechanisms="setback", access="archived",
                               archived_url="https://web.archive.org/web/2024/https://example.gov/ordinance.pdf"))
    assert code == 0 and len(seeds) == 1


def test_a_pending_row_without_access_is_not_promoted(queue):
    code, seeds, status = queue(row(review_status="pending", mechanisms="vibes", access=""))
    assert code == 0 and seeds == [] and status == ["pending"]


def test_a_blank_status_stops_promotion_and_lifted_is_not_published(queue, capsys):
    code, seeds, status = queue(row(mechanisms="setback", status=""),
                                row(mechanisms="moratorium", status="lifted"),
                                row(mechanisms="moratorium", status="in_force"))
    assert code == 0 and seeds == [] and status == ["confirmed"] * 3
    out = capsys.readouterr().out
    assert "a blank status stops promotion" in out
    assert "status lifted: the instrument is no longer in force" in out
    assert "status 'in_force' must be one of active, extended, pending, lifted, expired" in out


def test_an_instrument_that_was_read_publishes_as_primary_source(queue):
    import build_seed_outputs as bso
    import classify
    _, seeds, _ = queue(row(mechanisms="setback", mechanism_detail="Turbines 1,000 ft from homes.",
                            source_kind="minutes"),
                        row(county="Other County", mechanisms="setback", source_kind="news",
                            source_url="https://news.example.com/story"))
    by_county = {s["jurisdiction"]: s for s in seeds}
    minutes, news = by_county["Example County"], by_county["Other County"]
    assert (minutes["primary_source_url"], minutes["primary_source_access"],
            minutes["primary_source_verdict"]) == ("https://example.gov/ordinance.pdf", "opened", "confirmed")
    stamped = classify.stamp("restrictions", bso.normalize_row(minutes))
    assert (stamped["evidence_level"], stamped["verification"]) == ("primary_source", "verified")
    # A news article locates an instrument but does not verify it.
    assert not news.get("primary_source_url")
    assert classify.stamp("restrictions", bso.normalize_row(news))["verification"] == "unverified"


def test_an_unknown_source_kind_is_reported(queue, capsys):
    _, seeds, _ = queue(row(mechanisms="setback", source_kind="blog"))
    assert seeds == [] and "source_kind 'blog' must be one of" in capsys.readouterr().out


def test_a_row_corrected_after_promotion_resyncs_its_seed_rows_and_keeps_the_id(queue, monkeypatch, tmp_path,
                                                                                capsys):
    """A row promoted earlier (no queue_id yet, the old description, unknown
    status, no severity_basis, report_citation evidence) is corrected in the
    queue; the next run brings the seed row up to date under the same id."""
    import build_seed_outputs as bso
    seed_path = pr.SEED_FOR["restriction"][1]
    stale = {"state": "KS", "technology": "wind", "restriction_type": "setback", "severity_score": "2",
             "description": "Old text from search snippets.", "status": "unknown",
             "jurisdiction": "Example County", "jurisdiction_type": "County", "date_enacted_iso": "2024-01-02",
             "mechanisms": "", "severity_basis": "", "long_description": "", "moratorium_id": "",
             "source_record_id": "", "source": "review queue: web_research_test",
             "source_url": "https://example.gov/minutes-not-read",
             "notes": "old notes; promoted automatically from data/review/queue.csv on 2026-01-05: "
                      "required fields complete, not reviewed by hand"}
    common.write_csv(seed_path, [stale])
    old_id = bso.record_id("restrictions", bso.normalize_row(stale))
    corrected = row(review_status="promoted", technology="wind;battery_storage", mechanisms="setback; noise limit",
                    mechanism_detail="Turbines 2,640 ft from homes; 45 dBA. Battery storage 500 ft from homes.",
                    description="Corrected against the ordinance.", adopted_date="2024-01-02",
                    source_kind="instrument", reviewer_notes="corrected notes")
    code, seeds, status = queue(corrected)
    assert code == 0 and status == ["promoted"]
    by_tech = {s["technology"]: s for s in seeds}
    wind = by_tech["wind"]
    assert wind["pinned_id"] == old_id
    assert (wind["description"], wind["status"], wind["severity_score"], wind["severity_basis"]) == (
        "Corrected against the ordinance.", "active", "3", "wind setback 2640 ft")
    assert wind["mechanisms"] == "setback, noise limit" and "45 dBA" in wind["long_description"]
    assert wind["source_url"] == "https://example.gov/ordinance.pdf"
    assert wind["primary_source_verdict"] == "confirmed" and wind["queue_id"].startswith("q_")
    # The original automatic-promotion date is kept, so notes do not churn.
    assert wind["notes"] == ("corrected notes; promoted automatically from data/review/queue.csv on "
                             "2026-01-05: required fields complete, not reviewed by hand")
    assert by_tech["battery_storage"]["queue_id"] == wind["queue_id"]
    import classify
    # One ordinance, two technology rows: one instrument.
    assert {classify.instrument_id("restrictions", r) for r in seeds} == {f"queue:{wind['queue_id']}"}
    out = capsys.readouterr().out
    for field in ("description", "status", "severity_basis", "source_url", "primary_source_url"):
        assert f"({'wind'}): {field} changed" in out, field
    assert "added a row for battery_storage" in out
    # The build publishes the pinned id, and a second run changes nothing.
    monkeypatch.setattr(bso, "SEED_DIR", seed_path.parent)
    built, _ = bso.build_entity("restrictions", seed_path.name)
    assert {r["technology"]: r["id"] for r in built}["wind"] == old_id   # errors: the real review files
    code, again, _ = queue(dict(corrected, queue_id=wind["queue_id"]))
    assert again == seeds and "0 field change(s)" in capsys.readouterr().out


def test_a_contested_project_is_scored_by_the_sabin_rule(monkeypatch, tmp_path):
    seed = pr.queue_to_seed({**BASE, "entity_type": "contested_project", "project_name": "Example Solar",
                             "status": "approved_after_opposition", "severity_score": ""})
    assert (seed["outcome"], seed["severity_score"]) == ("advanced_unverified", 1)
    seed = pr.queue_to_seed({**BASE, "entity_type": "contested_project", "project_name": "Example Solar",
                             "status": "proposed", "severity_score": ""})
    assert (seed["outcome"], seed["severity_score"]) == ("pending", 2)


def test_rows_from_one_article_are_separate_instruments(queue):
    import classify
    _, seeds, _ = queue(row(technology="solar", mechanisms="setback", mechanism_detail="250 ft"),
                        row(technology="wind", mechanisms="setback", mechanism_detail="1,500 ft"),
                        row(technology="wind", mechanisms="moratorium", description="A second wind instrument."))
    ids = [classify.instrument_id("restrictions", s) for s in seeds]
    assert len(set(ids)) == 3 and ids[2].endswith("-2")


def test_a_row_awaiting_review_is_held_until_someone_else_confirms_it(queue, capsys):
    code, seed, statuses = queue(row(review_status="awaiting_review", mechanisms="setback",
                                     mechanism_detail="setback 1,000 feet"))
    assert code == 0 and seed == [] and statuses == ["awaiting_review"]
    assert "awaiting review by someone other than its drafter" in capsys.readouterr().out


def test_the_trail_records_each_decision_once_and_every_change(queue, tmp_path):
    from common import read_csv
    trail = tmp_path / "promotion_trail.csv"   # conftest points pr.TRAIL_PATH here
    held = row(mechanisms="setback", mechanism_detail="500 ft", access="snippet", source_id="held_src")
    code, _, status = queue(held, row(mechanisms="setback", mechanism_detail="500 ft", source_id="ok_src"))
    assert code == 0 and status == ["confirmed", "promoted"]
    rows = read_csv(trail)
    assert [(r["file"], r["action"]) for r in rows] == [("queue.csv", "held"), ("queue.csv", "promoted")]
    assert "snippet" in rows[0]["reason"] and rows[0]["place"] == "Example County" and rows[0]["state"] == "KS"
    # The same run again: the promoted row re-syncs, the held row is held again; nothing new is recorded.
    code, _, _ = queue(held, row(mechanisms="setback", mechanism_detail="500 ft", source_id="ok_src",
                                 review_status="promoted"))
    assert code == 0 and len(read_csv(trail)) == 2
    # The hold is lifted: that is an event, and the trail now has three rows.
    code, _, status = queue({**held, "access": "opened"})
    assert code == 0 and status == ["promoted"]
    rows = read_csv(trail)
    assert len(rows) == 3 and rows[-1]["action"] == "promoted" and rows[-1]["key"] == rows[0]["key"]


def test_a_dry_run_leaves_no_trail(queue, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py", "--dry-run"])
    code, seeds, _ = queue(row(mechanisms="setback", mechanism_detail="500 ft"))
    assert code == 0 and seeds == [] and not (tmp_path / "promotion_trail.csv").exists()


def test_a_promoted_row_found_lifted_leaves_the_seed_and_the_trail_says_so(queue, tmp_path, capsys):
    """A repeal read after promotion: the seed rows go (a first promotion would
    not publish a lifted instrument), the queue row stays promoted, and the
    trail records the change once."""
    from common import read_csv
    code, seeds, _ = queue(row(mechanisms="setback", mechanism_detail="500 ft", technology="solar;wind"))
    assert code == 0 and len(seeds) == 2
    qid = seeds[0]["queue_id"]
    lifted = row(mechanisms="setback", mechanism_detail="500 ft", technology="solar;wind",
                 review_status="promoted", queue_id=qid, status="lifted")
    code, seeds, status = queue(lifted)
    assert code == 0 and seeds == [] and status == ["promoted"]
    out = capsys.readouterr().out
    assert out.count("status lifted: the instrument is no longer in force") == 2
    trail = read_csv(tmp_path / "promotion_trail.csv")
    assert [r["action"] for r in trail] == ["promoted", "unpublished"]
    # Already removed: a second run changes nothing and reports no problem.
    code, seeds, _ = queue(lifted)
    out = capsys.readouterr().out
    assert code == 0 and seeds == [] and "0 field change(s)" in out and "no seed row is linked" not in out
    assert len(read_csv(tmp_path / "promotion_trail.csv")) == 2
    # Back in force but still marked promoted: reported, with the way to republish.
    code, seeds, _ = queue(dict(lifted, status="active"))
    assert seeds == [] and "set review_status to pending" in capsys.readouterr().out


def test_an_end_date_reaches_the_seed_and_a_malformed_one_holds_the_row(queue, capsys):
    import build_seed_outputs as bso
    import classify
    from datetime import date
    code, seeds, status = queue(row(mechanisms="moratorium", end_date="2027-03-31"),
                                row(county="Other County", mechanisms="moratorium", end_date="March 2027"))
    assert code == 0 and status == ["promoted", "confirmed"]
    (s,) = seeds
    assert s["current_end_date_iso"] == "2027-03-31"
    assert "end_date 'March 2027' must be YYYY-MM or YYYY-MM-DD" in capsys.readouterr().out
    _, _, status = queue(row(mechanisms="moratorium", end_date="2027"))
    assert status == ["confirmed"]     # a bare year never lapses, so it is not accepted
    # Past its end date with no confirmation since, the moratorium reads as lapsed.
    stamped = classify.stamp("restrictions", bso.normalize_row(s))
    assert classify.currency(stamped, today=date(2027, 4, 1)) == "lapsed_unconfirmed"


def test_appending_to_a_queue_written_before_a_field_existed_realigns_it(tmp_path):
    import csv
    path = tmp_path / "queue.csv"
    old_fields = [f for f in parse.QUEUE_FIELDS if f != "end_date"]
    common.write_csv(path, [{**dict.fromkeys(old_fields, ""), "source_id": "old", "status": "active"}], old_fields)
    parse.append_queue(path, [parse.CandidateRecord(source_id="new", entity_type="restriction", end_date="2027")])
    with open(path, newline="", encoding="utf-8") as f:
        header, *rows = list(csv.reader(f))
    assert header == parse.QUEUE_FIELDS and all(len(r) == len(header) for r in rows)
    got = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    assert [(r["source_id"], r["status"], r["end_date"]) for r in got] == [("old", "active", ""), ("new", "", "2027")]
