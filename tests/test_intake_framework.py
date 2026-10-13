"""Live intake framework, offline: fetch.py requests, guards, retries and
storage; parse.py dedupe, queue ids and failed extractors; promote_reviewed.py
holding leads."""
import csv
import json

import common
import fetch
import parse
import promote_reviewed
import pytest


class FakeResponse:
    def __init__(self, status=200, body=b"{}", ctype="application/json", headers=None):
        self.status_code = status
        self.content = body
        self.headers = {"Content-Type": ctype, **(headers or {})}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} error", response=self)


@pytest.fixture
def raw_store(monkeypatch, tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    monkeypatch.setattr(fetch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW_DIR", raw)
    return raw


def queue_responses(monkeypatch, responses):
    calls = []

    def get(url, timeout=None, allow_redirects=True, headers=None):
        calls.append({"url": url, "headers": headers or {}})
        return responses.pop(0)
    monkeypatch.setattr(fetch.SESSION, "get", get)
    return calls


def test_build_requests_from_requests_params_and_expand(tmp_path):
    src = {"source_id": "g", "url": "https://api.example.org/doc",
           "requests": [{"label": "a", "params": {"query": '"solar farm" moratorium', "maxrecords": 250}},
                        {"url": "https://other.example.org/x"}]}
    reqs = fetch.build_requests(src)
    assert reqs[0] == ("a", "https://api.example.org/doc?query=%22solar+farm%22+moratorium&maxrecords=250")
    assert reqs[1] == ("g#2", "https://other.example.org/x")

    (tmp_path / "clients.json").write_text(json.dumps({"clients": [
        {"client": "kingco"}, {"client": "offco", "active": False}]}))
    src = {"source_id": "l", "url": "https://webapi.example.com/v1/{client}/matters",
           "expand_from": "clients.json", "params": {"$top": 5}}
    assert fetch.build_requests(src, root=tmp_path) == [
        ("kingco", "https://webapi.example.com/v1/kingco/matters?%24top=5")]
    assert fetch.build_requests({"source_id": "s", "url": "https://x.example.org/p?a=1"}) == [
        ("s", "https://x.example.org/p?a=1")]


def test_the_sources_registry_builds_every_intake_request():
    sources = fetch.load_sources(fetch.CONFIG_PATH)
    for s in fetch.active_sources(sources, intake=True):
        reqs = fetch.build_requests(s)
        assert reqs and all(u.startswith("https://") for _, u in reqs), s["source_id"]
        assert s.get("fetch_method", "static") in fetch.RUNNABLE_METHODS


def test_intake_selects_sources_with_an_extractor_or_a_watch():
    sources = [
        {"source_id": "courtlistener_renewables", "active": True, "url": "https://a.example.org"},
        {"source_id": "no_extractor_here", "active": True, "url": "https://b.example.org"},
        {"source_id": "upstream", "active": True, "watch": True, "url": "https://c.example.org"},
        {"source_id": "rendered", "active": True, "watch": True, "fetch_method": "js_render", "url": "https://d"},
        {"source_id": "off", "active": False, "watch": True, "url": "https://e.example.org"},
    ]
    assert [s["source_id"] for s in fetch.active_sources(sources, intake=True)] == [
        "courtlistener_renewables", "upstream"]
    assert [s["source_id"] for s in fetch.active_sources(sources, source_id=["upstream", "off"])] == ["upstream"]


@pytest.mark.parametrize("expect,body,ok", [
    ("json", b'{"articles": []}', True),
    ("json", b"The specified phrase is too short.", False),
    ("xml", b"<rss><channel/></rss>", True),
    ("xml", b"<html><body>Sorry", False),
    ("html", b"<!DOCTYPE html><html><body>x</body></html>", True),
    ("html", b'{"a": 1}', False),
    ("csv", b"ID,Title\n1,x\n", True),
    ("csv", b"<html>", False),
    (None, b"anything", True),
])
def test_looks_like(expect, body, ok):
    assert (fetch.looks_like(body, expect) is None) is ok


def test_looks_like_requires_the_marker_text():
    assert fetch.looks_like(b"<html>Permit Application</html>", "html", "Permit Application") is None
    assert "does not contain" in fetch.looks_like(b"<html>Moved</html>", "html", "Permit Application")


def test_a_throttled_request_is_retried_then_stored_compressed(monkeypatch, raw_store):
    body = b'{"articles": [{"url": "https://news.example.org/a"}]}'
    calls = queue_responses(monkeypatch, [
        FakeResponse(429, b"Please limit requests to one every 5 seconds", "text/plain"),
        FakeResponse(200, body, "application/json; charset=utf-8"),
    ])
    pauses = []
    src = {"source_id": "gdelt", "expect": "json", "compress": True,
           "retry": {"statuses": [429], "backoff_s": [20, 60]}}
    rec = fetch.fetch_request(src, "https://api.example.org/doc?q=1", [], sleep=pauses.append)
    assert pauses == [20] and len(calls) == 2
    assert rec["error"] == "" and rec["status_code"] == "200"
    assert rec["content_hash"] == fetch.content_hash(body)
    assert rec["local_path"] == f"data/raw/gdelt/{rec['content_hash']}.json.gz"
    stored = raw_store.parent.parent / rec["local_path"]
    assert common.read_raw(stored) == body
    # The same content stores the same bytes (gzip mtime is fixed).
    again = fetch.store_raw(body, "gdelt", ".json", compress=True)
    assert again == stored and again.read_bytes() == stored.read_bytes()


def test_throttling_that_outlasts_the_retries_is_recorded_not_raised(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(429, b"slow down", "text/plain") for _ in range(3)])
    src = {"source_id": "gdelt", "retry": {"statuses": [429], "backoff_s": [1, 1]}}
    rec = fetch.fetch_request(src, "https://api.example.org/doc", [], sleep=lambda s: None)
    assert rec["status_code"] == "429" and "429" in rec["error"] and rec["local_path"] == ""


def test_retry_after_is_honoured_and_capped(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(429, b"", headers={"Retry-After": "9999"}),
                                  FakeResponse(200, b"{}")])
    pauses = []
    fetch.fetch_request({"source_id": "x"}, "https://a.example.org", [], sleep=pauses.append)
    assert pauses == [fetch.MAX_RETRY_AFTER_S]


def test_a_200_that_is_not_the_promised_format_is_refused(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(200, b"Your search contained too many keywords.", "text/html")])
    rec = fetch.fetch_request({"source_id": "gdelt", "expect": "json"}, "https://a.example.org", [])
    assert rec["error"].startswith("refused: expected json") and rec["local_path"] == ""
    assert not list(raw_store.rglob("*"))


def test_unchanged_is_judged_per_request_url(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(200, b"[1]"), FakeResponse(200, b"[1]"), FakeResponse(200, b"[1]")])
    manifest = []
    src = {"source_id": "legistar"}
    a = fetch.fetch_request(src, "https://w.example.com/v1/a/matters", manifest)
    manifest.append(a)
    b = fetch.fetch_request(src, "https://w.example.com/v1/b/matters", manifest)
    manifest.append(b)
    a2 = fetch.fetch_request(src, "https://w.example.com/v1/a/matters", manifest)
    assert a["local_path"].endswith(".json") and b["local_path"] == a["local_path"]
    assert a2["local_path"] == "unchanged"
    # Callers that pass no URL keep the old per-source behaviour.
    assert fetch.last_hash_for_source(manifest, "legistar") == a["content_hash"]


def test_an_api_token_is_sent_only_when_its_variable_is_set(monkeypatch, raw_store):
    src = {"source_id": "cl", "auth_env": "TEST_INTAKE_TOKEN", "auth_prefix": "Token "}
    monkeypatch.delenv("TEST_INTAKE_TOKEN", raising=False)
    assert fetch.auth_headers(src) == {}
    monkeypatch.setenv("TEST_INTAKE_TOKEN", "abc")
    calls = queue_responses(monkeypatch, [FakeResponse(200, b"{}")])
    fetch.fetch_request(src, "https://a.example.org", [])
    assert calls[0]["headers"] == {"Authorization": "Token abc"}


def test_process_source_paces_requests_and_summarizes(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(200, b'{"a":1}'), FakeResponse(503, b"down")])
    pauses = []
    src = {"source_id": "g", "url": "https://a.example.org", "min_interval_s": 6, "retry": {"statuses": []},
           "watch": True, "on_change": "upstream changed: rerun",
           "requests": [{"label": "one", "params": {"q": 1}}, {"label": "two", "params": {"q": 2}}]}
    rows = fetch.process_source(src, [], sleep=pauses.append)
    assert pauses == [6] and [bool(r["error"]) for r in rows] == [False, True]
    lines = fetch.summarize(rows, {"g": src})
    assert lines == ["g: 2 request(s), 1 stored, 0 unchanged, 1 failed", "  upstream changed: rerun"]
    assert fetch.process_source({"source_id": "r", "fetch_method": "js_render", "url": "u"}, [])[0]["error"]


def test_strip_tracking():
    assert common.strip_tracking("https://news.example.org/a?utm_source=x&id=7&fbclid=y#top") == \
        "https://news.example.org/a?id=7"
    assert common.strip_tracking("https://county.example.gov/ViewFile/Item/12?fileID=3") == \
        "https://county.example.gov/ViewFile/Item/12?fileID=3"


def test_read_raw_reads_plain_and_gzipped(tmp_path):
    (tmp_path / "a.json").write_bytes(b"[1]")
    import gzip
    (tmp_path / "b.json.gz").write_bytes(gzip.compress(b"[2]"))
    assert common.read_raw(tmp_path / "a.json") == b"[1]"
    assert common.read_raw(tmp_path / "b.json.gz") == b"[2]"


def _cand(**kw):
    base = dict(source_id="gdelt_renewable_news", entity_type="restriction", state="IA", county="Linn County",
                source_url="https://news.example.org/linn-solar", source_kind="news",
                evidence_text="Linn County supervisors extend solar moratorium")
    return parse.CandidateRecord(**{**base, **kw})


def test_dedupe_drops_documents_cited_anywhere_and_syndicated_headlines():
    queue = [{"entity_type": "contested_project", "source_kind": "news", "source_id": "gdelt_renewable_news",
              "source_url": "https://paper-a.example.org/story",
              "evidence_text": "Neighbors sue over Rainbow Springs solar farm"}]
    seeds = {"restriction": [{"state": "IA", "jurisdiction": "Story County", "pinned_id": "res_9",
                              "source_url": "https://report.example.org/",
                              "primary_source_url": "https://story.example.gov/ord.pdf"}],
             "contested_project": [{"state": "KS", "project_name": "X", "source_url": "https://k.example.org",
                                    "group_sources": "https://g1.example.org/a; https://g2.example.org/b",
                                    "pinned_id": "con_2"}],
             "case": []}
    known = parse.Known(queue, seeds, [("https://res.example.org/evidence?utm_campaign=z", "outcome_resolutions.csv row 4")])
    kept, dropped = parse.dedupe([
        _cand(source_url="https://story.example.gov/ord.pdf"),                       # a seed's primary source
        _cand(entity_type="contested_project", source_url="https://g2.example.org/b"),  # a group source
        _cand(source_url="https://res.example.org/evidence"),                        # a resolution's evidence
        _cand(entity_type="contested_project", source_url="https://paper-b.example.org/syndicated",
              evidence_text="Neighbors sue over Rainbow Springs solar farm!"),        # same headline
        _cand(source_url="https://paper-c.example.org/new?utm_source=feed"),          # new
        _cand(source_url="https://paper-c.example.org/new"),                          # same, tracking removed
    ], known)
    assert [c.source_url for c in kept] == ["https://paper-c.example.org/new?utm_source=feed"]
    assert "primary_source_url of seed res_9" in dropped[0]
    assert "group_sources of seed con_2" in dropped[1]
    assert "outcome_resolutions.csv row 4" in dropped[2]
    assert "same headline as queue row from gdelt_renewable_news" in dropped[3]
    assert "same source document as queue row from gdelt_renewable_news" in dropped[4]


def test_queue_ids_are_distinct_for_leads_from_one_raw_file():
    leads = [_cand(source_url=f"https://news.example.org/{i}") for i in range(3)] + [_cand(queue_id="q_kept")]
    taken = {"q_existing"}
    parse.assign_queue_ids(leads, taken)
    ids = [c.queue_id for c in leads]
    assert len(set(ids)) == 4 and ids[3] == "q_kept" and taken >= set(ids)
    twins = [_cand(), _cand()]
    parse.assign_queue_ids(twins, set())
    assert twins[1].queue_id == twins[0].queue_id + "-2"


def _intake_tree(monkeypatch, tmp_path, extractor_src):
    raw, review = tmp_path / "data" / "raw", tmp_path / "data" / "review"
    (raw / "broken_src").mkdir(parents=True)
    review.mkdir(parents=True)
    (raw / "broken_src" / "abc.json").write_text("[]")
    with (raw / "manifest.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fetch.MANIFEST_FIELDS)
        w.writeheader()
        w.writerow({"source_id": "broken_src", "url": "u", "content_hash": "abc",
                    "local_path": "data/raw/broken_src/abc.json", "error": ""})
    ext = tmp_path / "extractors"
    ext.mkdir()
    (ext / "broken_src.py").write_text(extractor_src)
    monkeypatch.setattr(parse, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(parse, "MANIFEST_PATH", raw / "manifest.csv")
    monkeypatch.setattr(parse, "PARSE_STATE_PATH", raw / "parse_state.csv")
    monkeypatch.setattr(parse, "QUEUE_PATH", review / "queue.csv")
    monkeypatch.setattr(parse, "EXTRACTORS_DIR", ext)
    monkeypatch.setattr(parse, "SEED_PATHS", {})
    monkeypatch.setattr(parse, "CITED_PATHS", [])
    monkeypatch.setattr("sys.argv", ["parse.py"])
    return raw, review


def test_a_raw_file_whose_extractor_raised_is_retried_then_skipped(monkeypatch, tmp_path):
    raw, review = _intake_tree(monkeypatch, tmp_path, "def extract(raw_path, source):\n    raise ValueError('bad')\n")
    for _ in range(parse.MAX_ATTEMPTS):
        assert parse.main() == 1          # each failure is recorded and reported
    assert parse.load_parse_state(raw / "parse_state.csv") == set()
    assert parse.load_parse_failures(raw / "parse_state.csv") == {("broken_src", "abc"): parse.MAX_ATTEMPTS}
    assert parse.main() == 0              # then skipped, so the weekly run is not red forever
    assert not (review / "queue.csv").exists()
    # Fixed and re-parsed on purpose, it is parsed and marked done.
    (tmp_path / "extractors" / "broken_src.py").write_text(
        "def extract(raw_path, source):\n    return [{'entity_type': 'case', 'source_url': 'https://a.example.org/c'}]\n")
    monkeypatch.setattr("sys.argv", ["parse.py", "--reparse", "broken_src"])
    assert parse.main() == 0
    assert parse.load_parse_state(raw / "parse_state.csv") == {("broken_src", "abc")}
    assert len(common.read_csv(review / "queue.csv")) == 1


def test_sanitize_holds_every_machine_row_to_the_lead_contract():
    c = _cand(review_status="pending", access="opened", archived_url="https://web.archive.org/x",
              state="iowa", technology="solar;offshore_wind;hydro", status="adopted",
              mechanisms="moratorium;solar ban", severity_score="4", source_kind="press release",
              description="Board \u2014 votes 3\u20132", source_url="not a url")
    assert parse.sanitize(c)
    assert (c.review_status, c.access, c.archived_url) == ("lead", "snippet", "")
    assert c.state == "" and c.technology == "solar;wind" and c.status == "" and c.mechanisms == ""
    assert c.severity_score == "" and c.source_kind == "" and c.source_url == ""
    assert c.description == "Board, votes 3-2"
    assert "intake blanked values outside the vocabulary" in c.reviewer_notes
    for field in ("state 'iowa'", "technology 'solar;offshore_wind;hydro'", "status 'adopted'", "mechanisms",
                  "severity_score", "source_kind", "source_url"):
        assert field in c.reviewer_notes, field
    ok = _cand(state="ia", technology="Solar", mechanisms="moratorium", status="pending")
    assert parse.sanitize(ok) and ok.state == "IA" and ok.technology == "solar" and ok.mechanisms == "moratorium"
    assert "intake blanked" not in ok.reviewer_notes
    assert not parse.sanitize(_cand(entity_type="unknown"))
    project = _cand(entity_type="contested_project", status="rejected", technology="battery")
    assert parse.sanitize(project) and project.status == "rejected" and project.technology == "battery_storage"


def test_parse_keeps_the_promotion_vocabulary():
    assert parse.RESTRICTION_STATUS == promote_reviewed.QUEUE_RESTRICTION_STATUS


def test_url_key_folds_scheme_www_and_tracking():
    assert parse.url_key("http://www.News.example.org/a/?utm_source=x") == parse.url_key("https://news.example.org/a")
    assert parse.url_key("https://county.example.gov/doc?id=1") != parse.url_key("https://county.example.gov/doc?id=2")


def test_a_seed_source_url_is_cited_for_every_entity():
    known = parse.Known([], {"restriction": [{"state": "IA", "jurisdiction": "Linn County", "pinned_id": "res_1",
                                              "source_url": "https://paper.example.org/linn"}],
                             "contested_project": [], "case": []})
    kept, dropped = parse.dedupe([_cand(entity_type="contested_project",
                                        source_url="http://www.paper.example.org/linn/")], known)
    assert not kept and "source_url of seed res_1" in dropped[0]


def test_extractor_keys_parse_sets_itself_are_ignored_not_fatal(monkeypatch, tmp_path):
    raw, review = _intake_tree(monkeypatch, tmp_path, (
        "def extract(raw_path, source):\n"
        "    return [{'entity_type': 'restriction', 'source_id': 'spoofed', 'raw_path': '/abs',\n"
        "             'source_url': 'https://a.example.org/x', 'access': 'snippet'}]\n"))
    assert parse.main() == 0
    rows = common.read_csv(review / "queue.csv")
    assert len(rows) == 1 and rows[0]["source_id"] == "broken_src"
    assert rows[0]["raw_path"] == "data/raw/broken_src/abc.json" and rows[0]["review_status"] == "lead"


def test_promote_holds_leads_and_leaves_no_trail(monkeypatch, tmp_path, capsys):
    review, seed = tmp_path / "review", tmp_path / "seed"
    review.mkdir()
    seed.mkdir()
    monkeypatch.setattr(promote_reviewed, "QUEUE_PATH", review / "queue.csv")
    monkeypatch.setattr(promote_reviewed, "CANDIDATES_PATH", review / "cases_candidates.csv")
    monkeypatch.setattr(promote_reviewed, "TRAIL_PATH", review / "promotion_trail.csv")
    monkeypatch.setattr(promote_reviewed, "SEED_FOR", {
        "restriction": ("restrictions", seed / "restrictions_seed.csv"),
        "contested_project": ("contested_projects", seed / "contested_projects_seed.csv"),
        "case": ("cases", seed / "cases_seed.csv"),
    })
    complete = {"source_id": "courtlistener_renewables", "entity_type": "case", "review_status": "lead",
                "state": "IA", "project_name": "A v. B", "technology": "wind", "court_level": "state_appellate",
                "severity_score": "3", "description": "d", "source_url": "https://www.courtlistener.com/o/1/",
                "access": "opened", "source_kind": "court_record", "queue_id": "q_1"}
    common.write_csv(review / "queue.csv", [complete, {**complete, "queue_id": "q_2", "source_id": "gdelt"}])
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    assert promote_reviewed.main() == 0
    out = capsys.readouterr().out
    assert "2 live-intake lead(s) await triage" in out and "courtlistener_renewables 1" in out
    assert not common.read_csv(seed / "cases_seed.csv")
    assert not common.read_csv(review / "promotion_trail.csv")


def test_the_run_budget_stops_new_requests_and_records_each_one_skipped(monkeypatch, raw_store):
    queue_responses(monkeypatch, [FakeResponse(200, b'{"a":1}')])
    ticks = iter([0, 100])                      # the second request starts after the deadline
    src = {"source_id": "l", "url": "https://w.example.com/v1/{client}/m", "min_interval_s": 0,
           "requests": [{"label": "a", "url": "https://w.example.com/v1/a/m"},
                        {"label": "b", "url": "https://w.example.com/v1/b/m"}]}
    rows = fetch.process_source(src, [], sleep=lambda s: None, deadline=50, clock=lambda: next(ticks))
    assert rows[0]["error"] == "" and rows[1]["error"] == "skipped: run time budget reached"
    assert rows[1]["url"] == "https://w.example.com/v1/b/m"


def test_a_watched_sources_first_copy_is_a_baseline_not_a_change():
    src = {"w": {"source_id": "w", "on_change": "upstream changed: rerun"}}
    stored = [{"source_id": "w", "url": "https://u.example.org", "local_path": "data/raw/w/x.json", "error": ""}]
    assert fetch.summarize(stored, src, prior=set())[1] == "  first copy stored: the baseline for change detection"
    assert fetch.summarize(stored, src, prior={("w", "https://u.example.org")})[1] == "  upstream changed: rerun"
    unchanged = [{**stored[0], "local_path": "unchanged"}]
    assert fetch.summarize(unchanged, src, prior={("w", "https://u.example.org")}) == [
        "w: 1 request(s), 0 stored, 1 unchanged, 0 failed"]


def test_run_pipeline_streams_a_summary_stage(tmp_path, capsys):
    import run_pipeline
    script = tmp_path / "stage.py"
    script.write_text("print('one')\nprint('two')\nraise SystemExit(3)\n")
    summary = tmp_path / "summary.md"
    code = run_pipeline.run(("s", [str(script)], "a stage", True), summary, False)
    assert code == 3 and summary.read_text() == "one\ntwo\n" and "one\ntwo\n" in capsys.readouterr().out
