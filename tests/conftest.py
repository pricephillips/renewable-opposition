import sys
from pathlib import Path

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
