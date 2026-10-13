"""The codebook is rendered from the code's own constants and the committed
copy matches it, so a rule change ships with its description."""
import codebook
import qc_gate


def test_codebook_is_rendered_from_the_rules_and_is_deterministic():
    text = codebook.render()
    assert text == codebook.render()
    for code, severity, _ in qc_gate.CHECKS:
        assert f"`{code}` | {severity} |" in text
    assert "| Moratorium, pending | solar | pending | 2 |" in text
    assert "| Wind setback of half a mile | wind | active | 3 |" in text
    assert "`blocked_confirmed` | 4 | 4 |" in text
    assert "`lapsed_unconfirmed`" in text and "| `A` |" in text


def test_committed_codebook_is_current():
    assert codebook.CODEBOOK_PATH.read_text(encoding="utf-8") == codebook.render(), \
        "docs/codebook.md is out of date: run python scripts/codebook.py and commit it"
