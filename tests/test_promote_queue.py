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
        "source_url": "https://example.gov/ordinance.pdf", "access": "opened"}


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
    assert "3,000 feet" in s["mechanism_detail"]


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
    _, seeds, _ = queue(row(mechanisms="moratorium", status="in_force"),
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


def test_pending_rows_are_left_alone(queue):
    code, seeds, status = queue(row(review_status="pending", mechanisms="vibes", access=""))
    assert code == 0 and seeds == [] and status == ["pending"]
