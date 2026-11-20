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


def test_fetcher_selftests():
    import fetch_headwind_bea_income
    import fetch_headwind_cbp
    import fetch_headwind_fhfa_hpi
    import fetch_headwind_saipe
    for mod in (fetch_headwind_bea_income, fetch_headwind_fhfa_hpi, fetch_headwind_saipe, fetch_headwind_cbp):
        assert mod._selftest() == 0


def test_every_configured_input_names_its_fetcher():
    for e in hi.config()["inputs"]:
        assert (ROOT / e["fetcher"]).is_file(), f"{e['id']}: fetcher {e['fetcher']} not found"
