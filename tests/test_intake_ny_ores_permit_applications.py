"""ORES permit applications extractor (scripts/extractors/ny_ores_permit_applications.py),
offline, on a trimmed copy of the real page (tests/fixtures/intake/
ny_ores_permit_applications.html, fetched 2026-10-13; the Permitted table cut to
11 of its 36 rows, every other row verbatim).

The seed rows the extractor matches against are written to a temp file in each
test: real rows from data/seed/contested_projects_seed.csv where noted, and
hypothetical ones (marked) to reach rows the real seed does not name."""
import csv
import gzip
from dataclasses import asdict
from pathlib import Path

import classify
import common
import fetch
import parse
import pytest
from build_sabin_seeds import OUTCOME

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "intake" / "ny_ores_permit_applications.html"
PAGE = "https://dps.ny.gov/ores-permit-applications"
SOURCE = {"source_id": "ny_ores_permit_applications", "url": PAGE, "fetch_date": "2026-10-13T21:08:00+00:00",
          "content_type": "text/html; charset=UTF-8", "status_code": "200", "content_hash": "f" * 64,
          "local_path": "data/raw/ny_ores_permit_applications/x.html.gz", "error": ""}
SEED_FIELDS = ["state", "project_name", "technology", "county", "municipality", "outcome", "status", "pinned_id"]
# Real New York rows of data/seed/contested_projects_seed.csv (2026-10-13).
REAL_SEEDS = [
    ["NY", "Shepherd's Run Solar Project", "solar", "Columbia County", "Town of Copake", "pending", "pending",
     "S26P-4194"],
    ["NY", "Riverside Solar Project", "solar", "Jefferson County", "Towns of Lyme and Brownville", "pending",
     "pending", "S26P-4370"],
    ["NY", "Bear Ridge Solar Project", "solar", "Niagara County", "Towns of Cambria and Pendleton", "pending",
     "pending", "S26P-4159"],
    ["NY", "Rich Road Solar Project", "solar;battery_storage", "St. Lawrence County", "Town of Canton", "pending",
     "pending", "S26P-4192"],
    ["NY", "Mill Point Solar I", "solar", "Montgomery County", "Town of Glen", "pending", "pending", "S26P-4183"],
    ["NY", "Bliss Solar 1 Project", "solar", "Schoharie County", "Village of Schoharie", "pending", "pending",
     "S26P-4161"],
    ["NY", "Columbia Solar", "solar", "Herkimer County", "Town of Columbia", "pending", "pending", "S26P-4166"],
    ["NY", "Garnet Energy Center", "solar", "Cayuga County", "Town of Conquest", "pending", "pending", "S26P-4174"],
]
DASHES = ("—", "–")


@pytest.fixture
def ores():
    mod = parse.load_extractor("ny_ores_permit_applications")
    assert mod is not None
    return mod


def write_seed(path: Path, rows) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SEED_FIELDS)
        w.writerows(rows)
    return path


def raw_copy(tmp_path: Path, html: str | None = None) -> Path:
    """The page as fetch.py stores it: gzipped, <sha256>.html.gz."""
    body = (FIXTURE.read_text(encoding="utf-8") if html is None else html).encode("utf-8")
    path = tmp_path / "raw" / "ny_ores_permit_applications" / "0123abcd.html.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(body))
    return path


def run(ores, tmp_path, monkeypatch, seeds=REAL_SEEDS, html=None):
    monkeypatch.setattr(ores, "SEED_PATH", write_seed(tmp_path / "seed.csv", seeds))
    return ores.extract(raw_copy(tmp_path, html), SOURCE)


def case_of(row: dict) -> str:
    return row["reviewer_notes"].split(", case ", 1)[1].split(";", 1)[0]


def by_case(rows):
    return {case_of(r): r for r in rows}


# ── Reading the page ───────────────────────────────────────────────────────────

def test_every_section_and_row_is_read(ores):
    apps = ores.applications(FIXTURE.read_text(encoding="utf-8"))
    counts = {}
    for a in apps:
        counts[a["section"]] = counts.get(a["section"], 0) + 1
    assert counts == {"notice_of_intent": 1, "pending_completeness": 1, "incomplete": 4, "under_review": 5,
                      "permitted": 11, "withdrawn": 2, "denied": 1, "declaratory": 2}
    assert all(a["case_link"].startswith("https://documents.dps.ny.gov/public/MatterManagement/CaseMaster.aspx?")
               for a in apps)
    denied = next(a for a in apps if a["section"] == "denied")
    assert denied["case"] == "21-02553" and "&amp;" not in denied["case_link"]
    assert any("ViewDoc.aspx" in u for u in denied["links"])


def test_a_page_with_no_tables_raises(ores, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="changed shape"):
        run(ores, tmp_path, monkeypatch, html="<html><body><h2>Denied Applications</h2><p>None.</p></body></html>")


def test_gzipped_and_plain_raw_files_read_the_same(ores, tmp_path, monkeypatch):
    rows_gz = run(ores, tmp_path, monkeypatch)
    plain = tmp_path / "page.html"
    plain.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    assert ores.extract(plain, SOURCE) == rows_gz


# ── Relevance ──────────────────────────────────────────────────────────────────

def test_denied_withdrawn_and_seed_matches_only(ores, tmp_path, monkeypatch):
    rows = run(ores, tmp_path, monkeypatch)
    assert sorted(by_case(rows)) == ["21-00752", "21-02104", "21-02553", "22-02969", "23-02972", "23-02992",
                                     "24-03041", "24-03042"]
    names = {case_of(r): r["project_name"] for r in rows}
    assert names["23-02992"] == "Flat Creek Solar" and names["24-03042"] == "Moss Ridge Solar"
    assert names["21-02553"] == names["24-03041"] == "Shepherd's Run Solar"
    seeds = {case_of(r): r["reviewer_notes"].split("matches seed ")[1].split(" ")[0]
             for r in rows if "matches seed" in r["reviewer_notes"]}
    assert seeds == {"21-00752": "S26P-4370", "21-02104": "S26P-4159", "22-02969": "S26P-4192",
                     "23-02972": "S26P-4183", "21-02553": "S26P-4194", "24-03041": "S26P-4194"}
    # Without the seeds only the denied and withdrawn applications remain.
    rows = run(ores, tmp_path, monkeypatch, seeds=[])
    assert sorted(by_case(rows)) == ["21-02553", "23-02992", "24-03042"]


def test_a_shared_name_word_needs_the_technology_and_county_too(ores, tmp_path, monkeypatch):
    # Real seed: Bliss Solar 1 Project (solar, Schoharie County). The page's
    # Bliss Wind (wind, Wyoming County) has the same distinctive word and is
    # not matched; nor is Columbia Solar (Herkimer) by Hecate Energy Columbia
    # County, nor Garnet Energy Center (Cayuga County) by Cayuga Solar.
    rows = run(ores, tmp_path, monkeypatch)
    assert "23-03030" not in by_case(rows) and "23-03014" not in by_case(rows)
    # Hypothetical seeds: the same name in its own county matches; the same
    # name and technology in another county does not.
    rows = run(ores, tmp_path, monkeypatch, seeds=[
        ["NY", "Bliss Wind Project", "wind", "Wyoming County", "", "pending", "pending", "HYPO-1"],
        ["NY", "Heritage Wind", "wind", "Erie County", "", "pending", "pending", "HYPO-2"],
    ])
    found = by_case(rows)
    assert "HYPO-1" in found["23-03030"]["reviewer_notes"] and found["23-03030"]["status"] == "pending"
    assert "21-00026" not in found


def test_a_seed_with_no_county_matches_on_name_and_technology(ores, tmp_path, monkeypatch):
    # Hypothetical seed with no county, against a declaratory-ruling row that names none either.
    rows = run(ores, tmp_path, monkeypatch, seeds=[
        ["NY", "Howard Wind Farm", "wind", "", "", "operational", "operational", "HYPO-3"]])
    row = by_case(rows)["24-03058"]
    assert "county not compared" in row["reviewer_notes"]
    assert row["status"] == "" and row["county"] == "" and row["municipality"] == ""
    assert "no 'located in' clause" in row["reviewer_notes"]


# ── Status ─────────────────────────────────────────────────────────────────────

def test_status_only_where_the_section_states_it(ores, tmp_path, monkeypatch):
    found = by_case(run(ores, tmp_path, monkeypatch))
    assert found["21-00752"]["status"] == "approved"           # Permitted, seed match
    assert found["24-03041"]["status"] == "pending"            # Complete Applications Under Review
    assert found["23-02992"]["status"] == "" and found["24-03042"]["status"] == ""   # Withdrawn / Relinquished
    assert "not a stated cancellation" in found["23-02992"]["reviewer_notes"]
    # Denied, but refiled: the same project is under review again.
    denied = found["21-02553"]
    assert denied["status"] == ""
    assert "listed again under Complete Applications Under Review (case 24-03041)" in denied["reviewer_notes"]
    assert "denied without prejudice" in denied["description"]
    assert "ViewDoc.aspx?DocRefId=" in denied["reviewer_notes"]


def test_a_denial_with_no_later_application_is_rejected(ores, tmp_path, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    start = html.index('<tr><td><a href="https://documents.dps.ny.gov/public/MatterManagement/CaseMaster.aspx?'
                       'MatterSeq=85385&amp;MNO=24-03041"')
    html = html[:start] + html[html.index("</tr>", start) + len("</tr>"):]
    found = by_case(run(ores, tmp_path, monkeypatch, html=html))
    assert "24-03041" not in found
    assert found["21-02553"]["status"] == "rejected"
    assert "denied without prejudice, so the applicant may refile" in found["21-02553"]["reviewer_notes"]


def test_vocabulary_and_field_rules(ores, tmp_path, monkeypatch):
    rows = run(ores, tmp_path, monkeypatch)
    assert rows
    for r in rows:
        assert set(r) <= set(parse.QUEUE_FIELDS) and not set(r) & set(parse.OWN_FIELDS)
        assert r["entity_type"] == "contested_project" and r["state"] == "NY"
        assert common.technology_tokens(r["technology"]) == r["technology"].split(";")
        assert set(r["technology"].split(";")) <= {"solar", "wind", "battery_storage"}
        assert r["status"] in OUTCOME or r["status"] == ""
        assert r.get("mechanisms", "") == "" and r.get("severity_score", "") == ""
        assert r.get("first_event_date", "") == "" and r.get("adopted_date", "") == ""
        assert r["access"] == "snippet"
        assert r["source_kind"] == "other" and r["source_kind"] in classify.SOURCE_KINDS
        assert r["source_url"].startswith("https://") and r["source_url"] == common.strip_tracking(r["source_url"])
        assert 0 < len(r["evidence_text"]) <= 1000
        assert r["reviewer_notes"].startswith("ORES ") and "opposition is not shown on this page" in r["reviewer_notes"]
        for k, v in r.items():
            assert not any(d in v for d in DASHES), (k, v)
            assert "<" not in v and "&amp;" not in v and "&nbsp;" not in v, (k, v)
        one_sentence = r["description"].replace("St. ", "St ")
        assert one_sentence.count(". ") == 0 and one_sentence.endswith(".")


# ── Placement ──────────────────────────────────────────────────────────────────

def test_county_and_towns_from_the_row(ores, tmp_path, monkeypatch):
    found = by_case(run(ores, tmp_path, monkeypatch))
    lookup = ores.load_lookup()
    assert (found["23-02992"]["county"], found["23-02992"]["municipality"]) == (
        "Montgomery County", "Towns of Root and Canajoharie")
    assert (found["24-03042"]["county"], found["24-03042"]["municipality"]) == (
        "St. Lawrence County", "Town of De Kalb")
    for r in found.values():
        name = r["county"].removesuffix(" County")
        assert classify.lookup_county(name, "new york", lookup), r["county"]
        assert "towns confirmed in that county by the Census place index" in r["reviewer_notes"]
    assert found["24-03042"]["description"] == (
        "Moss Ridge Solar, a 60 MW solar facility in the Town of De Kalb, St. Lawrence County, is listed by "
        "ORES under Withdrawn Applications / Relinquished Permits, case 24-03042 (withdrawn effective May 7, 2025).")


def test_several_counties_take_the_first_and_list_all(ores, tmp_path, monkeypatch):
    # Hypothetical seeds, to reach multi-county rows the real seed does not name.
    rows = run(ores, tmp_path, monkeypatch, seeds=[
        ["NY", "Horseshoe Solar", "solar", "Monroe County", "", "pending", "pending", "HYPO-4"],
        ["NY", "Sugar Maple Solar", "solar", "", "", "pending", "pending", "HYPO-5"]])
    found = by_case(rows)
    horseshoe = found["21-02480"]
    assert (horseshoe["county"], horseshoe["municipality"]) == ("Livingston County", "Town of Caledonia")
    assert ("counties named: Livingston County (Town of Caledonia); Monroe County (Town of Rush); "
            "county set to the first valid one") in horseshoe["reviewer_notes"]
    maple = found["23-03027"]
    assert (maple["county"], maple["municipality"]) == ("Jefferson County", "Town of Wilna")
    assert maple["technology"] == "solar;battery_storage"
    assert "a 125 MW solar facility with battery storage in the Town of Wilna, Jefferson County and the Town " \
           "of Croghan, Lewis County" in maple["description"]


def test_placement_refusals(ores, tmp_path, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    # A county the lookup does not know is not set.
    html = html.replace("Towns of ROOT and CANAJOHARIE, MONTGOMERY COUNTY", "Towns of ROOT and CANAJOHARIE, NARNIA COUNTY")
    # A town the place index puts in another county is noted; the county named stays.
    html = html.replace("Town of DE KALB, ST. LAWRENCE COUNTY", "Town of COPAKE, ST. LAWRENCE COUNTY")
    found = by_case(run(ores, tmp_path, monkeypatch, html=html))
    flat = found["23-02992"]
    assert flat["county"] == "" and flat["municipality"] == ""
    assert "Narnia County not a New York county" in flat["reviewer_notes"]
    moss = found["24-03042"]
    assert moss["county"] == "St. Lawrence County"
    assert "Copake not in St. Lawrence County per the Census place index" in moss["reviewer_notes"]


def test_places_parse_the_page_forms(ores):
    lookup = ores.load_lookup()
    apps = {a["case"]: a for a in ores.applications(FIXTURE.read_text(encoding="utf-8"))}

    def read(case):
        return [(p["county"], p["fips"], ores.municipality(p["towns"])) for p in ores.places(apps[case]["desc"], lookup)]
    assert read("23-02973") == [("Franklin County", "36033", "Towns of Bellmont, Burke and Chateaugay"),
                                ("Clinton County", "36019", "Town of Clinton")]
    assert read("23-02984") == [("Fulton County", "36035", "Town of Mayfield and Village of Mayfield")]
    assert read("24-03035") == [("Sullivan County", "36105", "Towns of Thompson and Forestburgh")]
    assert read("23-03031") == [("Franklin County", "36033", "Town of Chateaugay"),
                                ("Clinton County", "36019", "Town of Clinton")]
    assert read("21-02553") == [("Columbia County", "36021", "Town of Copake")]
    assert read("22-02970") == []


def test_a_name_and_description_that_disagree_keep_both_and_say_so(ores, tmp_path, monkeypatch):
    # The page's own Bull Run Wind row describes "a 449-Megawatt (MW) Solar
    # Energy Facility". Hypothetical seed, to bring the row out.
    rows = run(ores, tmp_path, monkeypatch, seeds=[
        ["NY", "Bull Run Wind Energy Center", "wind", "Clinton County", "", "pending", "pending", "HYPO-6"]])
    row = by_case(rows)["23-02975"]
    assert row["technology"] == "solar;wind" and row["status"] == "proposed"
    assert "technology conflict: the name says wind, the description says solar" in row["reviewer_notes"]
    assert "a 449 MW facility in the Towns of Altona, Clinton, Ellenburg and Mooers" in row["description"]


def test_a_row_with_no_case_link_cites_the_page(ores, tmp_path, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<a href="https://documents.dps.ny.gov/public/MatterManagement/CaseMaster.aspx?MatterSeq=85415&amp;'
        'MNO=24-03042" target="_blank">24-03042</a>', "24-03042")
    row = by_case(run(ores, tmp_path, monkeypatch, html=html))["24-03042"]
    assert row["source_url"] == PAGE
    assert "the row links no case page" in row["reviewer_notes"]


# ── Through parse.py ───────────────────────────────────────────────────────────

def test_round_trip_through_parse_dedupe(ores, tmp_path, monkeypatch):
    monkeypatch.setattr(ores, "SEED_PATH", write_seed(tmp_path / "seed.csv", REAL_SEEDS))
    raw = raw_copy(tmp_path)
    candidates = parse.run_extractor(ores, raw, SOURCE, rel_path=SOURCE["local_path"])
    assert len(candidates) == 8 and all(c.review_status == "lead" for c in candidates)
    assert all(c.source_id == "ny_ores_permit_applications" and c.raw_path == SOURCE["local_path"]
               for c in candidates)

    # Against the real seeds and review files: nothing is already held.
    known = parse.load_known(tmp_path / "no_queue.csv", parse.SEED_PATHS, parse.CITED_PATHS)
    kept, dropped = parse.dedupe(candidates, known)
    assert len(kept) == 8 and dropped == []
    # The two Shepherd's Run cases share a name: the second is kept and noted.
    shepherd = [c for c in kept if c.project_name == "Shepherd's Run Solar"]
    assert len(shepherd) == 2 and "possible duplicate of" in shepherd[1].reviewer_notes
    parse.assign_queue_ids(kept, set())
    assert len({c.queue_id for c in kept}) == 8

    # The next run of the same page queues nothing new.
    again = parse.run_extractor(ores, raw, SOURCE, rel_path=SOURCE["local_path"])
    known = parse.Known([asdict(c) for c in kept], {}, [])
    kept2, dropped2 = parse.dedupe(again, known)
    assert kept2 == [] and len(dropped2) == 8 and all("same source document" in d for d in dropped2)


def test_the_registry_entry_and_the_page(ores):
    sources = {s["source_id"]: s for s in fetch.load_sources(fetch.CONFIG_PATH)}
    entry = sources["ny_ores_permit_applications"]
    assert entry["url"] == PAGE and entry["expect"] == "html" and entry.get("compress")
    assert entry["expect_contains"] in FIXTURE.read_text(encoding="utf-8")
    intake = [s["source_id"] for s in fetch.active_sources(list(sources.values()), intake=True)]
    assert "ny_ores_permit_applications" in intake
    assert FIXTURE.stat().st_size <= 40_000
