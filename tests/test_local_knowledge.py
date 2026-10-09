"""The local-knowledge file: what local contacts, meetings and documents report
about a county. Hand-edited and unverified, kept outside this public repository
($RO_LOCAL_KNOWLEDGE), so the build never reads or publishes it; only
site_profile.py prints it, and --no-local leaves it out."""
import copy
import sys
from pathlib import Path

import build_seed_outputs as bso
import site_profile as sp
from common import read_csv

ROOT = Path(__file__).resolve().parent.parent
_opened: list[str] = []
_watching = False


def _hook(event, args):
    if _watching and event == "open" and args and isinstance(args[0], (str, bytes, Path)):
        _opened.append(str(args[0]))


sys.addaudithook(_hook)  # cannot be removed; it records only while _watching


def test_the_build_never_opens_or_publishes_local_knowledge(monkeypatch, tmp_path):
    global _watching
    monkeypatch.setattr(bso, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(bso, "FIPS_MISSES", tmp_path / "fips_misses.csv")
    _opened.clear()
    _watching = True
    try:
        assert bso.main() == 0
    finally:
        _watching = False
    assert any(p.endswith("restrictions_seed.csv") for p in _opened)   # the hook did see the build
    assert not [p for p in _opened if "local_knowledge" in p]
    assert not [p for p in tmp_path.rglob("*") if "local_knowledge" in p.name]
    # Nor does any module the build imports name the file.
    scripts = ROOT / "scripts"
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None) or ""
        if f and Path(f).parent == scripts and Path(f).name != "site_profile.py":
            assert "local_knowledge" not in Path(f).read_text(encoding="utf-8"), f


def test_the_file_lives_outside_the_repository(monkeypatch, tmp_path):
    """Reports from local contacts never sit in this public repository."""
    assert not (ROOT / "data" / "review" / "local_knowledge.csv").exists()
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/review/local_knowledge.csv" in ignored and "local_knowledge*" in ignored
    monkeypatch.delenv(sp.LOCAL_KNOWLEDGE_ENV, raising=False)
    default = sp.local_knowledge_path()
    assert default == Path("~/.renewable-opposition/local_knowledge.csv").expanduser()
    assert ROOT not in default.parents
    custom = tmp_path / "lk.csv"
    monkeypatch.setenv(sp.LOCAL_KNOWLEDGE_ENV, str(custom))
    assert sp.local_knowledge_path() == custom


def test_the_precommit_gate_refuses_a_staged_local_knowledge_file():
    import precommit_gates as pg
    assert pg.private(["data/review/" + "local_knowledge.csv"]) == 1
    assert pg.private(["notes/Local_Knowledge_copy.csv"]) == 1
    assert pg.private(["data/review/queue.csv"]) == 0


def test_rows_from_the_env_path_print_and_use_the_vocabulary(monkeypatch, tmp_path):
    path = tmp_path / "lk.csv"
    from common import write_csv
    write_csv(path, [ROW], sp.LOCAL_FIELDS)
    monkeypatch.setenv(sp.LOCAL_KNOWLEDGE_ENV, str(path))
    d = sp.Data()
    assert d.local == [ROW]
    for r in read_csv(path):
        assert r["source_type"] in sp.LOCAL_SOURCE_TYPES, r
        assert r["topic"] in sp.LOCAL_TOPICS, r


ROW = {"county_fips": "20021", "state": "KS", "county": "Cherokee", "topic": "restriction",
       "claim": "Commissioners discussed extending the wind rules to solar.", "source_type": "local_contact",
       "source_note": "county clerk, by phone", "date_reported": "2026-10-01", "reporter": "PP"}


def local_data(rows):
    d = sp.Data(local=False)
    d.local = rows
    return d


def test_a_profile_lists_the_county_rows_as_they_are_marked_unverified():
    elsewhere = {**ROW, "county_fips": "21181", "claim": "Nicholas County claim"}
    named_only = {**ROW, "county_fips": "", "claim": "names Cherokee but has no FIPS"}
    d = local_data([ROW, elsewhere, named_only])
    p = sp.profile(d, "20021", "Cherokee", "KS")
    assert p["local_knowledge"] == [ROW]          # matched on county_fips only, no other logic
    text = sp.render(p)
    head = text.index("### Local knowledge on file: 1 item(s)")
    assert text.index("### In the county") < head < text.index("### Adjacent counties")
    assert "Reported, not verified (restriction): Commissioners discussed" in text
    assert "Nicholas County claim" not in text and "has no FIPS" not in text
    assert "—" not in text


def test_an_empty_county_says_so_and_no_local_omits_the_section(tmp_path):
    p = sp.profile(local_data([]), "20021", "Cherokee", "KS")
    assert "- Nothing on file for this county." in sp.render(p)
    d = copy.copy(local_data([ROW]))
    d.local = None
    text = sp.render(sp.profile(d, "20021", "Cherokee", "KS"))
    assert "Local knowledge on file" not in text and "Commissioners discussed" not in text


def test_no_local_does_not_read_the_file(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "nope" / "local_knowledge.csv"
    monkeypatch.setenv(sp.LOCAL_KNOWLEDGE_ENV, str(missing))
    calls = []
    real = sp._csv
    monkeypatch.setattr(sp, "_csv", lambda path: calls.append(path) or real(path))
    assert sp.main(["--state", "KS", "--county", "Cherokee", "--no-local"]) == 0
    assert missing not in calls
    assert "Local knowledge on file" not in capsys.readouterr().out
    assert sp.main(["--state", "KS", "--county", "Cherokee"]) == 0
    assert missing in calls and "Local knowledge on file: 0 item(s)" in capsys.readouterr().out
