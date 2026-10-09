"""Opposition groups: canonical names, sources required to publish, no
per-group outcome. Synthetic rows only."""
import group_registry as gr
import site_profile as sp


def test_case_punctuation_inc_and_citizens_for_variants_match():
    k = gr.key("Citizens for Responsible Solar")
    assert gr.key("citizens for responsible solar, Inc.") == k
    assert gr.key("The Responsible Solar") == k
    assert gr.key("Concerned Citizens for Responsible Solar LLC") == k
    assert gr.key("Stop Responsible Solar") != k        # "Stop" names the cause and is kept
    assert gr.key("Save Our Farms") != gr.key("Our Farms")


def proj(**kw):
    return {"id": "con_x", "instrument_id": "sabin:R1", "state": "KS", "description": "Synthetic project.",
            "event_date_text": "August 2014", **kw}


def test_a_group_publishes_only_with_a_source_and_never_with_an_outcome():
    projects = [
        proj(opposition_groups="Citizens for Responsible Solar; Local residents",
             group_sources="https://news.example.com/a"),
        proj(id="con_y", instrument_id="sabin:R2", state="MO", event_date_text="2019-03-02",
             opposition_groups="Responsible Solar, Inc.", group_sources="https://news.example.com/b"),
        proj(id="con_z", instrument_id="sabin:R3", opposition_groups="Unsourced Alliance", group_sources=""),
    ]
    candidates = [{"source_record_id": "R9", "state": "KS", "group_name": "Read Coalition",
                   "group_source_url": "https://news.example.com/c", "access": "opened"},
                  {"source_record_id": "R8", "state": "KS", "group_name": "Snippet Coalition",
                   "group_source_url": "https://news.example.com/d", "access": "snippet"}]
    registry, review = gr.build(gr.occurrences(projects, candidates, []))
    by_name = {r["canonical_name"]: r for r in registry}
    assert set(by_name) == {"Citizens for Responsible Solar", "Read Coalition"}
    g = by_name["Citizens for Responsible Solar"]
    assert (g["n_projects"], g["states"], g["first_seen"], g["last_seen"]) == (2, "KS;MO", "2014-08", "2019-03-02")
    assert g["source_urls"] == "https://news.example.com/a; https://news.example.com/b"
    assert g["variants"] == "Citizens for Responsible Solar; Responsible Solar, Inc."
    assert list(g) == gr.REGISTRY_FIELDS          # no outcome or success-rate column
    assert {r["group_name"] for r in review} == {"Unsourced Alliance", "Snippet Coalition"}
    assert gr.hold_unsourced(projects) == 1 and projects[2]["opposition_groups"] is None
    assert projects[0]["opposition_groups"]       # sourced groups stay published


def test_profiles_show_groups_with_their_sources_and_a_nearby_line():
    d = sp.Data(local=False)
    row = {k: "" for k in ("capacity_mw", "county", "has_litigation", "event_date_text", "finality_evidence",
                           "resolution_url", "source_url", "instrument_id")}
    row.update(id="con_g", project_name="Synthetic Wind", technology="wind", outcome="pending", severity_score="2",
               evidence_level="report_citation", description="Synthetic.", state="KS", county_fips_all="20037",
               opposition_groups="Synthetic Neighbors Alliance", group_sources="https://news.example.com/g")
    d.restrictions, d.projects, d.cases, d.queue = [], [row], [], []
    d.held, d.gaps, d.candidates, d.quarantine, d.checks = [], [], [], [], {}
    text = sp.render(sp.profile(d, "20021", "Cherokee", "KS"))
    assert "Groups: Synthetic Neighbors Alliance (sources: https://news.example.com/g)" in text
    assert ("Groups active nearby: Synthetic Neighbors Alliance (Crawford, KS; sources: "
            "https://news.example.com/g)") in text
    d.projects = []
    assert "Groups active nearby: none with a source" in sp.render(sp.profile(d, "20021", "Cherokee", "KS"))


def test_the_backfill_file_holds_every_group_until_a_read_source_is_added():
    from common import read_csv
    rows = read_csv(gr.CANDIDATES_PATH)
    assert rows and list(rows[0]) == gr.CANDIDATE_FIELDS
    registry, review = gr.build(gr.occurrences([], rows, []))
    unread = [r for r in rows if r["access"] not in gr.READ_ACCESS]
    assert len(review) == len(unread)
