"""The county report contract (config/county_report.json), adapted from
pricephillips/data-center-map's location report: sections in the configured
order, terms defined on first use and bare afterwards, no digit in a
definition or notice, every file read named with its hash, and no section
for local reports."""
import csv
import re

import pytest
import site_profile as sp

NO_DIGIT = re.compile(r"\d")


@pytest.fixture(scope="module")
def data():
    return sp.Data(local=False)


@pytest.fixture(scope="module")
def text(data):
    return sp.render(sp.profile(data, "20021", "Cherokee", "KS", radius=40))


def headings(text: str, level: int = 2) -> list[str]:
    mark = "#" * level + " "
    return [line[len(mark):] for line in text.splitlines() if line.startswith(mark)]


def test_sections_follow_the_configured_order(text):
    cfg = sp.load_report_config()
    assert [s["id"] for s in cfg["sections"]] == list(sp.SECTIONS)
    expected = [s["heading"] for s in cfg["sections"]]
    got = headings(text)
    assert [h for h in expected if h in got] == got
    assert all(h in got for s, h in zip(cfg["sections"], expected) if not s.get("optional"))
    assert "Within the radius" in got            # optional, present because --radius was given
    assert "Local knowledge" not in text and "Local reports" not in "\n".join(got)


def test_definitions_carry_no_digit_and_print_once(text):
    cfg = sp.load_report_config()
    for key, t in cfg["terms"].items():
        assert not NO_DIGIT.search(t["term"]) and not NO_DIGIT.search(t["definition"]), key
    for key, notice in cfg["notices"].items():
        assert not NO_DIGIT.search(notice), key
    for key in ("restriction_instrument", "contested_project", "severity", "verification"):
        t = cfg["terms"][key]
        assert text.count(f"({t['definition']})") == 1, key
        assert text.count(t["term"]) > 1, key
    d = sp.Definer(cfg)
    assert d("restriction_instrument", 2).startswith("restriction instruments (")
    assert d("restriction_instrument", 1) == "restriction instrument"
    assert d("restriction_instrument") == "restriction instrument"


def test_the_config_refuses_a_digit_in_a_definition(tmp_path):
    cfg = sp.load_report_config()
    cfg["terms"]["severity"]["definition"] = "a score from 1 to 4"
    bad = tmp_path / "county_report.json"
    bad.write_text(__import__("json").dumps(cfg), encoding="utf-8")
    with pytest.raises(SystemExit, match="severity carries a digit"):
        sp.load_report_config(bad)


def test_title_block_commit_and_sources(text, data):
    lines = text.splitlines()
    assert lines[0] == "# Cherokee, Kansas: county report"
    assert lines[2].startswith("Cherokee, Kansas (FIPS 20021). Data as of ") and ". Commit " in lines[2]
    assert "Every figure in this report was read from the files below at commit " in text
    for rel in ("data/processed/restrictions.csv", "data/processed/contested_projects.csv",
                "data/review/queue.csv", "data/geo/counties_2024.topojson"):
        assert re.search(rf"^\| {re.escape(rel)} \| [0-9a-f]{{12}} \|$", text, re.M), rel
    assert "local_knowledge" not in text
    assert {f["path"] for f in sp.source_files(data)} >= {"data/processed/restrictions.csv"}


def test_every_record_row_carries_its_source_and_verification(text):
    body = text.split("## Restrictions on record\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in body.splitlines() if line.startswith("| ") and not line.startswith("| Date")]
    assert rows
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split(" | ")]
        assert len(cells) == len(sp.RESTRICTION_HEADERS), row
        assert cells[-1] and ("(opened)" in cells[-1] or "Compiled from" in cells[-1] or "http" in cells[-1])
        assert "verified" in cells[6]


def test_a_batch_has_an_overview_and_one_report_per_site(tmp_path):
    sites = tmp_path / "sites.csv"
    with sites.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "state", "county", "fips", "lat", "lon", "notes"])
        w.writeheader()
        w.writerow({"name": "Site A", "state": "KS", "county": "Cherokee", "notes": "two parcels"})
        w.writerow({"name": "Site B", "fips": "21181"})
    out = tmp_path / "reports.md"
    assert sp.main(["--sites", str(sites), "--out", str(out), "--no-local"]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# County reports\n")
    assert "| Site | County | Restriction instruments |" in text
    assert headings(text) == ["Site A: county report", "Site B: county report"]
    assert "### Summary" in text and "Notes supplied with the request: two parcels" in text
    assert "—" not in text


def test_no_em_dash_anywhere(text):
    assert "—" not in text
    assert "—" not in sp.REPORT_CONFIG.read_text(encoding="utf-8")
