"""scripts/review_merge.py: review files merged by key, so branches that each
append rows merge over each other."""
import subprocess

import review_merge as rm

HEAD = "instrument_id,jurisdiction,state,primary_source_url,verdict,checked_on,note,reviewer,access,archived_url\n"
LOG_HEAD = "date,queue,key,outcome,note\n"
SOURCES = "data/review/restriction_sources.csv"


def row(i, verdict="confirmed", on="2026-11-08"):
    return f"{i},P,KS,https://example.gov/{i},{verdict},{on},n,a + b,opened,\n"


def log(day, key, outcome="written"):
    return f"{day},restriction,{key},{outcome},x\n"


def test_selftest():
    assert rm.selftest() == 0


def test_branches_that_append_to_the_same_files_merge_in_git(tmp_path, monkeypatch):
    monkeypatch.setattr(rm, "ROOT", tmp_path)

    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *a], cwd=tmp_path, check=True,
                       capture_output=True)

    def commit(msg, sources, logtext):
        (tmp_path / SOURCES).write_text(sources, newline="")
        (tmp_path / rm.LOG).write_text(logtext, newline="")
        git("add", "-A")
        git("commit", "-q", "-m", msg)

    (tmp_path / "data/review").mkdir(parents=True)
    git("init", "-q", "-b", "main")
    git("config", "user.name", "t")
    git("config", "user.email", "t@example.org")
    commit("base", HEAD + row("a"), LOG_HEAD + log("2026-11-07", "a"))
    for name, extra, day in (("one", row("b") + row("c"), "2026-11-08"),
                             ("two", row("b", on="2026-11-09") + row("c", "contradicts", "2026-11-09") + row("d"),
                              "2026-11-09")):
        git("checkout", "-q", "-b", name, "main")
        commit(name, HEAD + row("a") + extra, LOG_HEAD + log("2026-11-07", "a") + log(day, "b") + log(day, "c"))
    git("checkout", "-q", "-b", "all", "main")
    assert rm.merge_ref("one") == 0 and rm.merge_ref("two") == 0
    # b: the earlier of two agreeing readings. c: the readings disagree, so no
    # row and a disputed line. d: read once. Every attempt is in the log.
    assert (tmp_path / SOURCES).read_text() == HEAD + row("a") + row("b") + row("d")
    lines = (tmp_path / rm.LOG).read_text().splitlines()
    assert len(lines) == 7 and lines[-1].startswith("2026-11-09,restriction,c,disputed,")
    assert rm.merge_ref("two") == 0                      # already merged: nothing to do
    # Both branches are now ancestors, so their pull requests close as merged.
    for name in ("one", "two"):
        assert subprocess.run(["git", "merge-base", "--is-ancestor", name, "HEAD"], cwd=tmp_path).returncode == 0


def test_a_row_changed_differently_on_both_sides_stops_the_merge():
    base = HEAD + row("a")
    try:
        rm.merge_rows(SOURCES, base, HEAD + row("a", on="2026-11-09"), HEAD + row("a", "contradicts"))
    except rm.Conflict as e:
        assert "changed differently" in str(e)
    else:
        raise AssertionError("expected a conflict")
