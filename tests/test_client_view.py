"""The client-view audit (scripts/client_view_audit.py) and its question bank."""
import json

import client_view_audit as cva
from common import ROOT


def test_selftest():
    assert cva._selftest() == 0


def test_every_question_names_a_known_check_or_none():
    q = json.loads((ROOT / "config" / "reader_questions.json").read_text(encoding="utf-8"))
    ids = [x["id"] for x in q["questions"]]
    assert len(ids) == len(set(ids))
    for x in q["questions"]:
        assert x["ask"].strip()
        assert x["check"] == "" or x["check"] in cva.ROUTES or x["check"] in (
            "HEADLINE_RECORD_MISMATCH", "STATE_RULES_NOT_SHOWN")
