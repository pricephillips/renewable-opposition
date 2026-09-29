import source_archive


def test_selftest_mocked_cdx_and_save_page_now():
    """The module's own selftest: mocked HTTP, no network (passoff B2)."""
    assert source_archive.selftest() == 0


import datetime as dt  # noqa: E402
import json  # noqa: E402


def _run(tmp_path, http):
    feed = tmp_path / "sources.csv"
    feed.write_text("source_id,url\ns1,https://a.org/x\ns2,https://b.org/y\n", encoding="utf-8")
    cfg = dict(source_archive.DEFAULTS, cdx_sleep_s=0, save_sleep_s=0, backoff_s=[])
    res = source_archive.run(http=http, feed_csv=str(feed), out_csv=str(tmp_path / "a.csv"),
                             manifest=str(tmp_path / "m.json"), cfg=cfg, sleep=lambda s: None,
                             env={}, today=dt.date(2026, 9, 29), now="t")
    return res, source_archive.load_rows(str(tmp_path / "a.csv"))


def test_cdx_timeout_falls_back_to_the_availability_api(tmp_path):
    def http(method, url, data=None, headers=None, timeout=None):
        if url.startswith(source_archive.CDX_URL):
            return 0, "TimeoutError"
        if url.startswith(source_archive.AVAILABLE_URL):
            if "a.org" in url:
                return 200, json.dumps({"archived_snapshots": {"closest": {
                    "available": True, "status": "200", "timestamp": "20250101120000",
                    "url": "http://web.archive.org/web/20250101120000/https://a.org/x"}}})
            return 200, json.dumps({"archived_snapshots": {}})
        return 200, "{}"  # save

    res, rows = _run(tmp_path, http)
    a, b = rows["https://a.org/x"], rows["https://b.org/y"]
    assert a["status"] == "archived" and a["method"] == "available"
    assert a["archived_url"].startswith("https://web.archive.org/web/20250101120000/")
    assert b["status"] == "requested" and b["last_error"] == ""  # no capture: saved
    assert res["archived"] == 1 and res["saves"] == 1


def test_when_nothing_answers_the_reason_is_recorded(tmp_path):
    def http(method, url, data=None, headers=None, timeout=None):
        if url.startswith(source_archive.CDX_URL):
            return 0, "TimeoutError"
        return 403, "Forbidden"

    res, rows = _run(tmp_path, http)
    assert rows["https://a.org/x"]["last_error"] == "cdx TimeoutError; available 403"
    assert rows["https://a.org/x"]["status"] == "not_archived" and res["saves"] == 0
    assert res["errors"] == {"available 403": 2, "cdx TimeoutError": 2}


def test_parse_available_rejects_non_200_captures():
    body = json.dumps({"archived_snapshots": {"closest": {
        "available": True, "status": "404", "timestamp": "20250101120000", "url": "http://x"}}})
    assert source_archive.parse_available(body) is None
    assert source_archive.parse_available("<html>") is None
