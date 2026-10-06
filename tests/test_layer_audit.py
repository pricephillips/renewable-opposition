import ast
import copy
import json

import layer_audit as la

CONFIG = json.loads(la.CONFIG.read_text(encoding="utf-8"))


def run(config=None, writes=None, unresolved=None, rows=None):
    w, u = la.scan()
    w = {m: t for m, t in w.items() if m not in CONFIG["exempt"]}
    u = {m: s for m, s in u.items() if m not in CONFIG["exempt"]}
    return la.audit(config or CONFIG, writes if writes is not None else w,
                    unresolved if unresolved is not None else u,
                    read_rows=(lambda rel: rows.get(rel, [])) if rows is not None else None)


def test_repository_is_clean():
    assert run() == []


def test_an_undeclared_writer_is_found():
    w, _ = la.scan()
    w = {**w, "scripts/new_scraper.py": {"data/seed/restrictions_seed.csv"}}
    assert any("undeclared writer: scripts/new_scraper.py" in f for f in run(writes=w))


def test_a_stale_declaration_is_found():
    cfg = copy.deepcopy(CONFIG)
    cfg["files"]["data/review/sabin_restrictions_review.csv"]["writers"].append("scripts/coverage_audit.py")
    found = run(config=cfg)
    assert any("stale declaration: scripts/coverage_audit.py" in f for f in found)


def test_a_shared_file_needs_a_reason():
    cfg = copy.deepcopy(CONFIG)
    del cfg["files"]["data/review/queue.csv"]["reason"]
    assert any("data/review/queue.csv: 2 writers and no reason" in f for f in run(config=cfg))


def test_a_reference_file_names_its_source_and_has_no_writer_here():
    cfg = copy.deepcopy(CONFIG)
    del cfg["files"]["data/geo/*"]["copied_from"]
    assert any(f.startswith("data/geo/*: a reference file") for f in run(config=cfg))
    cfg = copy.deepcopy(CONFIG)
    cfg["files"]["data/review/fips_misses.csv"]["writers"] = []
    found = run(config=cfg)
    assert any("data/review/fips_misses.csv: no writer declared" in f for f in found)


def test_an_undeclared_crossing_is_found():
    cfg = copy.deepcopy(CONFIG)
    del cfg["crossings"]["scripts/parse.py"]
    assert any("undeclared crossing: scripts/parse.py" in f for f in run(config=cfg))


def test_a_row_no_writer_owns_is_found():
    rows = {"data/seed/restrictions_seed.csv": [{"source": "Sabin Center, x"},
                                                {"source": "hand-typed"}]}
    found = run(rows=rows)
    assert found == ["data/seed/restrictions_seed.csv row 3: source='hand-typed' matches 0 writers"]


def test_an_unresolved_write_must_be_declared():
    found = run(unresolved={"scripts/new.py": ["scripts/new.py:9: some_path"]})
    assert any("unresolved write" in f and "scripts/new.py:9" in f for f in found)


def test_resolver_follows_constants_fstrings_and_helpers(tmp_path):
    src = (
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parent.parent\n"
        "OUT = ROOT / 'data' / 'processed'\n"
        "def save(rows, path):\n"
        "    path.write_text('x')\n"
        "def main(entity):\n"
        "    save([], OUT / f'{entity}.csv')\n"
        "    (ROOT / 'docs' / 'a.md').open('w')\n"
        "    (ROOT / 'docs' / 'b.md').open()\n"
    )
    res = la.Resolver("scripts/x.py", {})
    res.assign(ast.parse(src))
    assert res.env["OUT"] == "data/processed"
    mod = tmp_path / "x.py"
    mod.write_text(src, encoding="utf-8")
    targets, unresolved = la.module_writes(mod, {}, rel="scripts/x.py")
    assert targets == {"data/processed/*.csv", "docs/a.md"}  # a read-mode open is not a write
    assert unresolved == []


def test_a_hand_edited_file_has_no_writer():
    cfg = copy.deepcopy(CONFIG)
    assert cfg["files"]["data/review/place_overrides.csv"]["hand_edited"] is True
    cfg["files"]["data/review/place_overrides.csv"]["writers"] = ["scripts/resolutions.py"]
    found = run(config=cfg)
    assert any("data/review/place_overrides.csv: a hand-edited file is a review file" in f for f in found)


def test_only_declared_readers_may_name_a_private_file():
    found = run(writes=None)
    assert not any("undeclared reader" in f for f in found)
    mentions = {"local_knowledge.csv": {"scripts/site_profile.py", "scripts/build_seed_outputs.py"}}
    w, u = la.scan()
    w = {m: t for m, t in w.items() if m not in CONFIG["exempt"]}
    u = {m: s for m, s in u.items() if m not in CONFIG["exempt"]}
    found = la.audit(CONFIG, w, u, mentions=lambda name: mentions.get(name, set()))
    assert found == ["undeclared reader: scripts/build_seed_outputs.py names data/review/local_knowledge.csv"]
