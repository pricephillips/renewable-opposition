import pytest

from common import jurisdiction_key, normalize_url, source_id_for, state_code, technology_tokens


def test_state_code_accepts_names_and_codes():
    assert state_code("Connecticut") == "CT"
    assert state_code("ny") == "NY"
    with pytest.raises(ValueError):
        state_code("Atlantis")


def test_technology_tokens_normalizes_and_orders():
    assert technology_tokens("wind, solar,storage") == ["solar", "wind", "battery_storage"]
    assert technology_tokens("") == []
    with pytest.raises(ValueError):
        technology_tokens("fusion")


def test_source_id_ignores_fragment_trailing_slash_and_host_case():
    a = source_id_for("https://Example.org/report/#page=3")
    b = source_id_for("https://example.org/report")
    assert a == b
    assert a.startswith("src_") and len(a) == 16
    assert normalize_url("https://x.org/a?b=1") == "https://x.org/a?b=1"


def test_jurisdiction_key_matches_loosely_within_kind_only():
    assert jurisdiction_key("CT", "municipal", "Town of Morris") == jurisdiction_key("Connecticut", "municipal", "Morris")
    assert jurisdiction_key("GA", "county", "Carroll County") == jurisdiction_key("GA", "county", "Carroll")
    assert jurisdiction_key("CT", "county", "Morris") != jurisdiction_key("CT", "municipal", "Morris")
    assert jurisdiction_key("MA", "municipal", "Gill (proposal, not enacted)") == jurisdiction_key("MA", "municipal", "Gill")
