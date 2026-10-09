"""data-center-map events: filtered, placed with this repository's county
logic, shown in site profiles and fed to the group registry. A synthetic
master_opposition.csv only."""
import csv

import group_registry as gr
import site_profile as sp
import sync_data_center_map as dcm

HEADER = ["Incident", "City", "Date", "Opposition Type", "State", "County", "Status", "Summary", "Source URL",
          "Sources", "Opposition Groups", "Objective", "data_source", "lat", "lon"]


def row(**kw):
    base = {k: "" for k in HEADER}
    base.update({"Incident": "Synthetic County data center moratorium", "Date": "2026-07-01",
                 "Opposition Type": "moratorium", "State": "KS", "County": "Cherokee County", "Status": "passed",
                 "Summary": "Commissioners paused data center permits — for a year. Second sentence.",
                 "Source URL": "https://news.example.com/a",
                 "Sources": "{'url': 'https://news.example.com/b', 'title': 'B'}; https://news.example.com/a",
                 "Opposition Groups": "Synthetic Neighbors Alliance; Cherokee County residents",
                 "data_source": "datacentertracker.org"})
    base.update(kw)
    return base


def write(tmp_path, rows):
    path = tmp_path / "master_opposition.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    return path


def test_off_topic_harvest_rows_are_left_out_and_the_rest_are_placed(tmp_path, monkeypatch):
    rows = [
        row(),
        row(Incident="Man arrested by immigration agents in Cedar Rapids", Summary="An arrest.",
            County="Cedar", State="IA", data_source="signal_harvest_auto", **{"Opposition Type": "other"}),
        row(Incident="Data centers", data_source="signal_harvest_auto"),                      # generic
        row(State="", data_source="signal_harvest_auto"),                                     # no state
        row(data_source="signal_harvest_auto", **{"Opposition Type": ""}),                    # no type
        row(Incident="Energy loan to restart a nuclear plant", Summary="A loan.", **{"Opposition Type": ""},
            data_source="manual_correction"),
        row(County="", City="", lat="37.17", lon="-94.85", Incident="Data center hearing at a farm"),
        row(County="Nowhere County", Incident="Data center rezoning"),
    ]
    monkeypatch.setattr(dcm, "OUT", tmp_path / "data_center_events.csv")
    assert dcm.main(["--dc-map", str(write(tmp_path, rows))]) == 0
    events = list(csv.DictReader(open(tmp_path / "data_center_events.csv", encoding="utf-8")))
    assert [e["county_fips"] for e in events] == ["20021", "20021"]      # by name, then by coordinates
    e = events[0] if events[0]["dc_row_ref"].startswith("master_opposition.csv row 2:") else events[1]
    assert list(e) == dcm.FIELDS
    assert e["summary"] == "Commissioners paused data center permits, for a year."
    assert e["source_urls"] == "https://news.example.com/a; https://news.example.com/b"
    assert e["opposition_groups"] == "Synthetic Neighbors Alliance"        # "residents" is not a group
    _, dropped = dcm.transform(rows, {}, {}, None)
    assert dropped["signal_harvest_auto: unrelated headline"] == 1
    assert dropped["signal_harvest_auto: generic headline"] == 1
    assert dropped["no type and the text names no data center"] == 1


def test_the_path_comes_from_the_flag_then_the_environment(monkeypatch, tmp_path):
    monkeypatch.delenv(dcm.DC_MAP_ENV, raising=False)
    assert dcm.dc_map_path(None) == dcm.ROOT.parent / "data-center-map" / "master_opposition.csv"
    monkeypatch.setenv(dcm.DC_MAP_ENV, str(tmp_path / "x.csv"))
    assert dcm.dc_map_path(None) == tmp_path / "x.csv"
    assert dcm.dc_map_path("/y.csv").as_posix() == "/y.csv"


def test_only_an_official_record_is_verified():
    assert dcm.evidence_label(["https://www.example.gov/AgendaCenter/ViewFile/Minutes/_0101"]) == "verified"
    assert dcm.evidence_label(["https://county.example.us/files/ordinance_12.pdf"]) == "verified"
    assert dcm.evidence_label(["https://public.destinyhosted.com/x/doc.pdf"]) == "verified"
    assert dcm.evidence_label(["https://www.example.gov/news/county-passes-pause"]) == "reported"
    assert dcm.evidence_label(["https://news.example.com/minutes.pdf"]) == "reported"


def test_profiles_list_data_center_activity_and_its_groups():
    d = sp.Data(local=False)
    d.restrictions, d.projects, d.cases, d.queue = [], [], [], []
    d.held, d.gaps, d.candidates, d.quarantine, d.checks = [], [], [], [], {}
    d.dc_events = [
        {"county_fips": "20021", "date": "2026-07-01", "event_type": "moratorium", "status": "passed",
         "summary": "Here.", "source_urls": "https://www.example.gov/minutes/1.pdf",
         "opposition_groups": "Synthetic Neighbors Alliance", "dc_row_ref": "master_opposition.csv row 2: A"},
        {"county_fips": "20037", "date": "2026-08-01", "event_type": "lawsuit", "status": "filed",
         "summary": "Next door.", "source_urls": "https://news.example.com/n", "opposition_groups": "",
         "dc_row_ref": "master_opposition.csv row 3: B"},
        {"county_fips": "19113", "date": "2026-08-01", "summary": "Far away.", "source_urls": "",
         "dc_row_ref": "row 4"}]
    text = sp.render(sp.profile(d, "20021", "Cherokee", "KS"))
    assert "### Data center activity (data-center-map): 2 event(s)" in text
    assert ("- 2026-07-01, moratorium, status passed (verified: a source is the instrument or official "
            "minutes): Here.") in text
    assert "- Crawford (20037):" in text and "(reported): Next door." in text and "Far away" not in text
    assert "Synthetic Neighbors Alliance (in the county, data center activity; sources: " \
           "https://www.example.gov/minutes/1.pdf)" in text
    assert "—" not in text


def test_data_center_groups_feed_the_registry_with_their_sources():
    events = [{"state": "KS", "date": "2026-07-01", "opposition_groups": "Synthetic Neighbors Alliance",
               "source_urls": "https://news.example.com/a", "dc_row_ref": "row 2", "summary": "x"},
              {"state": "MO", "date": "2026-09-01", "opposition_groups": "Unsourced Group", "source_urls": "",
               "dc_row_ref": "row 3", "summary": "y"}]
    registry, review = gr.build(gr.occurrences([], [], events))
    assert [(r["canonical_name"], r["source_urls"]) for r in registry] == [
        ("Synthetic Neighbors Alliance", "https://news.example.com/a")]
    assert [r["group_name"] for r in review] == ["Unsourced Group"]
