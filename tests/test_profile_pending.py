"""site_profile: pending review-queue candidates, primary sources and how they
were seen. Built on a synthetic data/ tree in a temp dir, never the real seeds;
only the 2024 county geometry (reference data) is real."""
import csv
import json

import pytest
import site_profile as sp

# A county and one of its neighbours, by geometry; the records are invented.
HOME, NEXT, FAR = "20001", "20011", "20021"
LOOKUP = {"allen county|kansas": HOME, "allen|kansas": HOME, "bourbon county|kansas": NEXT,
          "bourbon|kansas": NEXT, "cherokee county|kansas": FAR}
PLACES = {"sampleton|KS": [HOME], "twinville|KS": [HOME, NEXT]}

RESTRICTION = {"id": "res_a", "instrument_id": "sabin:SYN-1", "state": "KS", "technology": "wind",
               "jurisdiction": "Allen", "jurisdiction_type": "County", "restriction_type": "setback",
               "severity_score": "3", "severity_basis": "wind setback 3000 ft", "status": "active",
               "description": "Synthetic wind setback.", "evidence_level": "report_citation",
               "scope": "renewables_only", "source": "Sabin Center, synthetic",
               "source_url": "https://report.example.org/r.pdf", "county_fips_all": HOME,
               "county_fips_method": "name", "primary_source_url": "https://allen.example.gov/o.pdf",
               "primary_source_verdict": "confirmed", "primary_source_access": "snippet"}
READ = {**RESTRICTION, "id": "res_b", "instrument_id": "sabin:SYN-2", "technology": "solar",
        "primary_source_url": "https://allen.example.gov/solar.pdf", "primary_source_access": "opened",
        "evidence_level": "primary_source"}
PLACED = {**RESTRICTION, "id": "res_c", "instrument_id": "mn:syn-3", "jurisdiction": "Twinville",
          "jurisdiction_type": "Municipality", "primary_source_url": "", "primary_source_access": "",
          "primary_source_verdict": "", "county_fips_method": "override", "placement_access": "snippet",
          "placement_url": "https://news.example.org/twinville", "source_url": "https://mn.example.org/inv.csv"}
PROJECT = {"id": "con_a", "instrument_id": "sabin:SYN-9", "source_record_id": "SYN-9", "state": "KS",
           "project_name": "Synthetic Wind", "technology": "wind", "county": "Bourbon",
           "outcome": "blocked_unverified", "severity_score": "4", "has_litigation": "no",
           "finality_evidence": "lead: https://news.example.org/syn", "evidence_level": "report_citation",
           "description": "Synthetic project.", "source_url": "https://report.example.org/r.pdf",
           "county_fips_all": NEXT, "county_fips_method": "name",
           "resolution_url": "https://news.example.org/syn", "resolution_access": "snippet"}

QUEUE_FIELDS = ["entity_type", "review_status", "state", "county", "municipality", "project_name",
                "technology", "description", "source_url", "mechanisms", "mechanism_detail",
                "adopted_date", "first_event_date", "filing_date", "access", "archived_url"]
Q = {"entity_type": "restriction", "review_status": "pending", "state": "KS", "technology": "solar",
     "source_url": "https://allen.example.gov/minutes", "access": "snippet"}
QUEUE = [
    {**Q, "county": "Allen County", "mechanisms": "setback; noise limit",
     "mechanism_detail": "500 ft from dwellings; 50 dBA at night", "adopted_date": "2025-03-01",
     "description": "Synthetic solar rules."},
    {**Q, "entity_type": "contested_project", "municipality": "Sampleton", "project_name": "Sampleton Solar",
     "first_event_date": "2025-06", "access": "opened", "description": "Synthetic hearing."},
    {**Q, "entity_type": "case", "project_name": "Residents v. Board", "filing_date": "2024-01-02",
     "description": "Suit over a solar permit in Allen County.", "technology": "wind"},
    {**Q, "county": "Bourbon", "mechanisms": "moratorium", "adopted_date": "2025-09",
     "description": "Synthetic moratorium."},
    # Not this county: a decided row, a town shared by two counties, and another state.
    {**Q, "county": "Allen County", "review_status": "confirmed", "description": "Decided already."},
    {**Q, "municipality": "Twinville", "description": "Shared town name."},
    {**Q, "state": "OH", "county": "Allen County", "description": "Same name, other state."},
]


def _write(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def tree(tmp_path):
    data = tmp_path / "data"
    _write(data / "processed" / "restrictions.csv", [RESTRICTION, READ, PLACED])
    _write(data / "processed" / "contested_projects.csv", [PROJECT])
    _write(data / "processed" / "cases.csv", [], ["id", "state", "source_record_id"])
    (data / "county_fips_lookup.json").write_text(json.dumps(LOOKUP), encoding="utf-8")
    (data / "place_county_index.json").write_text(json.dumps(PLACES), encoding="utf-8")
    _write(data / "review" / "queue.csv", QUEUE, QUEUE_FIELDS)
    return tmp_path


def run(tree, fips=HOME):
    d = sp.Data(local=False, root=tree)
    f, name, st = sp.resolve(d, fips=fips)
    return sp.profile(d, f, name, st)


def test_pending_candidates_of_every_type_that_concern_the_county(tree):
    p = run(tree)
    got = [(r["entity_type"], r.get("county") or r.get("municipality") or r["project_name"])
           for r in p["not_published"]["pending_review"]]
    assert got == [("restriction", "Allen County"), ("contested_project", "Sampleton"),
                   ("case", "Residents v. Board")]
    text = sp.render(p)
    line = next(x for x in text.splitlines() if "Allen County, solar" in x)
    assert line.startswith("- Pending review, not published: restriction")
    assert "adopted 2025-03-01" in line and "(located, not yet read)" in line
    assert "Mechanisms: setback; noise limit. Values: 500 ft from dwellings; 50 dBA at night" in text
    assert "contested_project, Sampleton Solar, solar; adopted 2025-06" in text and "(opened)" in text


def test_pending_candidates_next_door_are_one_line_each(tree):
    p = run(tree)
    (pending,) = p["adjacent"][NEXT]["pending"]
    assert pending["description"] == "Synthetic moratorium."
    lines = [x for x in sp.render(p).splitlines() if "Synthetic" not in x and "Bourbon, solar" in x]
    assert lines == ["  - Pending review, not published: restriction, Bourbon, solar; moratorium; 2025-09; "
                     "source located, not yet read"]


def test_source_lines_show_the_primary_source_and_how_it_was_seen(tree):
    text = sp.render(run(tree))
    assert ("Source: https://allen.example.gov/o.pdf (located, not yet read). "
            "Compiled from Sabin Center report, https://report.example.org/r.pdf") in text
    assert "Source: https://allen.example.gov/solar.pdf (opened). Compiled from Sabin Center report" in text
    assert "Source: no primary source attached. Compiled from Moratorium Nation, https://mn.example.org/inv.csv" \
        in text
    assert "placed by override (located, not yet read)" in text
    assert "Outcome source: https://news.example.org/syn (located, not yet read)" in text


def test_one_flag_counts_the_evidence_still_to_read(tree):
    flags = [f for f in run(tree)["flags"] if f.startswith("Evidence still to read")]
    # primary source, placement, outcome source next door, and the snippet candidates
    # here (restriction, case) and next door (moratorium); the opened one is not counted.
    assert len(flags) == 1 and flags[0].startswith("Evidence still to read: 6 item(s)")
    assert "Sampleton" not in flags[0]


def test_no_flag_when_everything_shown_was_read(tree):
    for name in ("restrictions.csv", "contested_projects.csv"):
        (tree / "data" / "processed" / name).unlink()
    _write(tree / "data" / "processed" / "restrictions.csv", [READ])
    _write(tree / "data" / "review" / "queue.csv", [], QUEUE_FIELDS)
    p = run(tree)
    assert not [f for f in p["flags"] if f.startswith("Evidence still to read")]
    assert p["not_published"]["pending_review"] == []


def test_render_has_no_em_dashes(tree):
    assert "—" not in sp.render(run(tree))
