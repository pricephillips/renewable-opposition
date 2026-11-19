"""config/adopted_tools.json: what renewables-integrator built after Price
approved it (docs/SCOUT_BUILDS.md). Every entry is complete and traceable."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "adopted_tools.json"
REQUIRED = ("id", "name", "kind", "license", "version", "source_url", "target", "approved", "built_on", "proof")
KINDS = {"dataset", "python", "npm", "cli", "action", "service"}
COPYLEFT = re.compile(r"\b(A?GPL|SSPL)", re.I)


def problems(reg):
    out, seen = [], set()
    for i, t in enumerate(reg.get("tools", [])):
        tid = t.get("id") or f"<row {i}>"
        if tid in seen:
            out.append(f"{tid}: duplicate id")
        seen.add(tid)
        out += [f"{tid}: missing {k}" for k in REQUIRED if not t.get(k)]
        if t.get("kind") and t["kind"] not in KINDS:
            out.append(f"{tid}: kind {t['kind']!r} not in {sorted(KINDS)}")
        if COPYLEFT.search(str(t.get("license", ""))) and t.get("kind") != "cli":
            out.append(f"{tid}: copyleft code runs only as a separate command-line program")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t.get("built_on", ""))):
            out.append(f"{tid}: built_on is not YYYY-MM-DD")
        if not str(t.get("source_url", "")).startswith(("https://", "http://")):
            out.append(f"{tid}: source_url is not a link")
        if not isinstance(t.get("target"), list):
            out.append(f"{tid}: target lists the files changed")
    return out


def test_the_committed_file_is_sound():
    assert problems(json.loads(REGISTRY.read_text(encoding="utf-8"))) == []


def test_a_bad_entry_is_caught():
    good = {"id": "a", "name": "A", "kind": "python", "license": "MIT", "version": "==1.0",
            "source_url": "https://example.org/a", "target": ["scripts/x.py"], "approved": "#1",
            "built_on": "2026-11-24", "proof": "validate.yml"}
    assert problems({"tools": [good]}) == []
    assert problems({"tools": [good, good]}) == ["a: duplicate id"]
    assert "a: missing proof" in problems({"tools": [dict(good, proof="")]})
    assert any("copyleft" in p for p in problems({"tools": [dict(good, license="GPL-3.0")]}))
    assert problems({"tools": [dict(good, license="GPL-3.0", kind="cli")]}) == []
    assert any("built_on" in p for p in problems({"tools": [dict(good, built_on="Nov 24")]}))
