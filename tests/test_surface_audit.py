"""Every published output is read by a page, a download, or internal with a
reason; the declaration matches the page code."""
import json

import surface_audit as sa


def test_the_repository_is_fully_classified():
    config = json.loads(sa.CONFIG.read_text(encoding="utf-8"))
    outputs = sa.tracked_outputs()
    texts = {page: sa.page_paths(sa.ROOT / page) for page in config["pages"]}
    matrix, findings = sa.audit(config, outputs, texts)
    assert findings == []
    assert matrix["data/processed/headline_metrics.json"] == ["national-dashboard.js", "processed-data.js"]
    assert any(r.startswith("internal:") for r in matrix["data/processed/qc_report.md"])
    assert all(r == "national-dashboard.js" for r in matrix["data/db/state/IA.json"])


def test_each_finding_kind_is_raised():
    config = {"pages": {"p.js": {"reads": ["data/processed/a.json", "data/processed/missing.json"],
                                 "prefixes": {"data/db/state/": "per state"}}},
              "downloads": {"_what": "x", "data/processed/gone.csv": "r"},
              "internal": {"data/processed/b.md": "notes"}}
    outputs = ["data/processed/a.json", "data/processed/b.md", "data/processed/c.csv", "data/db/state/IA.json"]
    matrix, findings = sa.audit(config, outputs, {"p.js": {"data/processed/a.json"}})
    assert sa.names("data/db/parquet/x.parquet", {"data/db/"}) and not sa.names("data/db/x.json", {"data/processed/"})
    # The prefix attributes the state file even though the code never names it: that is the stale entry.
    assert matrix["data/processed/a.json"] == ["p.js"] and matrix["data/db/state/IA.json"] == ["p.js"]
    kinds = sorted(f.split(":")[0] for f in findings)
    # missing.json: never named (stale) and not published (wrong layer); the prefix: stale; gone.csv: stale.
    assert kinds == ["stale entry", "stale entry", "stale entry", "unclassified", "wrong layer"]
    assert any("missing.json" in f and "never names it" in f for f in findings)
    assert any("gone.csv" in f for f in findings) and any("c.csv" in f for f in findings)
    text = sa.render(matrix, findings, config)
    assert "UNCLASSIFIED" in text and "5 finding(s)" in text
