"""Plug-in inputs for the Renewable Headwind Model (config/headwind_inputs.json)."""
import json

import headwind_history as hh
import headwind_inputs as hi
from common import ROOT


def test_inputs_selftest():
    assert hi._selftest() == 0


def test_config_is_usable():
    assert hi.problems(hi.config()) == []


def test_every_registered_input_is_configured_and_amended():
    reg = json.loads((ROOT / "config" / "headwind_model_registration.json").read_text(encoding="utf-8"))
    configured = {hi.name_of(e): e for e in hi.config()["inputs"]}
    for name in hi.registered(reg):
        assert name in configured, f"{name} is registered but not in config/headwind_inputs.json"
        eid = configured[name]["id"]
        assert any(eid in a["change"] for a in reg["amendments"]), f"{name} has no amendment naming it"
    # Plug-ins come after the core variables, in config order.
    assert hh.COUNTY_VARS[len(hh.COUNTY_VARS) - len(hi.names(reg=reg)):] == hi.names(reg=reg)


def test_wanted_ids_are_unique():
    ids = [w["id"] for w in hi.config()["wanted"]]
    assert len(ids) == len(set(ids)) and ids
