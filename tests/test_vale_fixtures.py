"""Each Vale fixture produces exactly its intended alerts (passoff A7).

Skipped where the vale binary is not installed; validate.yml installs it.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "vale"

EXPECTED = {
    "causal_and_undefined.md": ["Hawthorn.Causal", "Hawthorn.Undefined"],
    "defined_decile.md": [],
    "emdash.md": ["Hawthorn.EmDash"],
}


@pytest.mark.skipif(shutil.which("vale") is None, reason="vale not installed")
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_alerts(name):
    r = subprocess.run(
        # Relative path: .vale.ini globs match paths relative to ROOT.
        ["vale", "--no-wrap", "--output=line", f"tests/fixtures/vale/{name}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    rules = [line.split(":")[3] for line in r.stdout.splitlines() if line.strip()]
    assert rules == EXPECTED[name], r.stdout + r.stderr


def test_every_fixture_has_an_expectation():
    assert sorted(p.name for p in FIXTURES.glob("*.md")) == sorted(EXPECTED)
