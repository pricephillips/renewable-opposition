import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_profile_requests(monkeypatch, tmp_path):
    """Profiles run by tests never record a request in the real
    data/review/profile_requests.csv."""
    import site_profile
    monkeypatch.setattr(site_profile, "PROFILE_REQUESTS", tmp_path / "profile_requests.csv")


@pytest.fixture(autouse=True)
def _no_real_worklist(monkeypatch, tmp_path):
    """A build run by a test writes its negative-check worklist to a temp dir."""
    import build_seed_outputs
    monkeypatch.setattr(build_seed_outputs, "NEGATIVE_WORKLIST", tmp_path / "negative_check_worklist.csv")


@pytest.fixture(autouse=True)
def _no_real_group_files(monkeypatch, tmp_path):
    """A build run by a test writes the group registry and review to a temp dir."""
    import group_registry
    monkeypatch.setattr(group_registry, "REGISTRY_PATH", tmp_path / "group_registry.csv")
    monkeypatch.setattr(group_registry, "REVIEW_PATH", tmp_path / "group_review.csv")


@pytest.fixture(autouse=True)
def _no_real_facility_worklist(monkeypatch, tmp_path):
    """A build run by a test writes the facility match worklist to a temp dir."""
    import facility_matches
    monkeypatch.setattr(facility_matches, "WORKLIST_PATH", tmp_path / "facility_matches.csv")


@pytest.fixture(autouse=True)
def _no_real_promotion_trail(monkeypatch, tmp_path):
    """A promotion run by a test records its decisions in a temp dir, never in
    the real data/review/promotion_trail.csv."""
    import promote_reviewed
    monkeypatch.setattr(promote_reviewed, "TRAIL_PATH", tmp_path / "promotion_trail.csv")


@pytest.fixture(autouse=True)
def _no_real_held_policies(monkeypatch, tmp_path):
    """A build run by a test writes state_policies_held.csv to a temp dir, never
    the real data/processed/state_policies_held.csv."""
    import state_policies
    monkeypatch.setattr(state_policies, "HELD_PATH", tmp_path / "state_policies_held.csv")


# ── Nothing under data/ is written by a test ─────────────────────────────────
# One audit hook for the session. It notes every write-like call on a path
# under data/ (so tests can run in parallel, pytest -n, without one worker
# reading a file another is rewriting), and, while seed_build runs, every file
# opened (test_local_knowledge).

DATA = ROOT / "data"
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
# event -> (index of a path it writes, index of that path's dir_fd or None).
# A copy reads its source, so only the destination counts. shutil.rmtree
# removes by name relative to a directory descriptor (os.rmdir("data",
# dir_fd=3) inside a temp dir), so such a name is resolved against that
# directory, never against the working directory.
_WRITE_EVENTS = {
    "os.remove": ((0, 1),), "os.rmdir": ((0, 1),), "os.mkdir": ((0, 2),), "os.truncate": ((0, None),),
    "os.rename": ((0, 2), (1, 3)), "os.link": ((1, 3),), "os.symlink": ((1, 2),),
    "shutil.copyfile": ((1, None),), "shutil.copytree": ((1, None),),
    "shutil.move": ((0, None), (1, None)), "shutil.rmtree": ((0, 1),),
}
_data_writes: list[str] = []
_data_writes_reported = 0
_opened: list[str] = []
_watching = False


def _under_data(path, dir_fd=None) -> str | None:
    if not isinstance(path, (str, bytes, os.PathLike)):
        return None
    try:
        p = os.fsdecode(path)
        if isinstance(dir_fd, int) and dir_fd >= 0 and not os.path.isabs(p):
            p = os.path.join(os.readlink(f"/proc/self/fd/{dir_fd}"), p)
        p = os.path.abspath(p)
    except (OSError, TypeError, ValueError):
        return None
    return p if p == str(DATA) or p.startswith(str(DATA) + os.sep) else None


def _audit(event, args):
    if event == "open" and args:
        if _watching and isinstance(args[0], (str, bytes, Path)):
            _opened.append(str(args[0]))
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        if ((isinstance(mode, str) and any(c in mode for c in "wax+"))
                or (isinstance(flags, int) and flags & _WRITE_FLAGS)):
            hit = _under_data(args[0])
            if hit:
                _data_writes.append(f"{event} {hit}")
    elif event in _WRITE_EVENTS:
        for i, fd in _WRITE_EVENTS[event]:
            if i < len(args):
                hit = _under_data(args[i], args[fd] if fd is not None and fd < len(args) else None)
                if hit:
                    _data_writes.append(f"{event} {hit}")
                    break


sys.addaudithook(_audit)  # cannot be removed; it only appends to two lists


@pytest.fixture(autouse=True)
def _nothing_written_under_data():
    """Fails the test (at teardown) that wrote under data/, itself or through a
    module or session fixture it set up first."""
    global _data_writes_reported
    yield
    new = _data_writes[_data_writes_reported:]
    _data_writes_reported = len(_data_writes)
    if new:
        pytest.fail("wrote under data/: " + "; ".join(sorted(set(new))), pytrace=False)


# ── One seed build, shared ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def seed_build(tmp_path_factory):
    """build_seed_outputs.main(), run once per session (once per xdist worker)
    for the tests that only read what it writes: test_build_outputs,
    test_local_knowledge and test_site_profile. It takes about 30 s.

    Every path it writes is redirected. processed/ holds what each test's own
    build wrote into its tmp_path: PROCESSED_DIR and FIPS_MISSES, which the
    tests patched, and the files the autouse fixtures above redirect (they are
    function-scoped, so they are not active here and are patched again).
    state_policies_held.csv goes to held/: those builds wrote it to the real
    data/processed/, outside PROCESSED_DIR, so datapackage.json and
    site_profile.Data read exactly what they read then.

    opened lists every file the build opened, recorded by the audit hook."""
    global _watching
    import build_seed_outputs as bso
    import facility_matches
    import group_registry
    import promote_reviewed
    import site_profile
    import state_policies
    root = tmp_path_factory.mktemp("seed_build")
    out, held = root / "processed", root / "held"
    out.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bso, "PROCESSED_DIR", out)
        mp.setattr(bso, "FIPS_MISSES", out / "fips_misses.csv")
        mp.setattr(bso, "NEGATIVE_WORKLIST", out / "negative_check_worklist.csv")
        mp.setattr(group_registry, "REGISTRY_PATH", out / "group_registry.csv")
        mp.setattr(group_registry, "REVIEW_PATH", out / "group_review.csv")
        mp.setattr(facility_matches, "WORKLIST_PATH", out / "facility_matches.csv")
        mp.setattr(promote_reviewed, "TRAIL_PATH", out / "promotion_trail.csv")
        mp.setattr(site_profile, "PROFILE_REQUESTS", out / "profile_requests.csv")
        mp.setattr(state_policies, "HELD_PATH", held / "state_policies_held.csv")
        _opened.clear()
        _watching = True
        try:
            returncode = bso.main()
        finally:
            _watching = False
    return SimpleNamespace(returncode=returncode, root=root, processed=out, opened=tuple(_opened))
