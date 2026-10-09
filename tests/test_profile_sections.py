"""The site profile's State framework and Local siting standards sections, and
the new headline metrics. Synthetic data in a temporary tree."""
import csv

import geo
import headline_metrics as hm
import site_profile as sp
import siting_standards
import state_policies

FIPS = "20021"  # Cherokee County, KS


def write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def tree(tmp_path):
    import shutil
    root = tmp_path
    (root / "data").mkdir()
    for name in ("county_fips_lookup.json",):
        shutil.copy(sp.FIPS_LOOKUP, root / "data" / name)
    proc, rev = root / "data" / "processed", root / "data" / "review"
    write(proc / "restrictions.csv", [], ["id", "state"])
    write(proc / "contested_projects.csv", [], ["id", "state"])
    write(proc / "cases.csv", [], ["id", "state"])
    policy = {"id": "KS-siting_authority-1", "state": "KS", "technology": "solar;wind",
              "policy_type": "siting_authority", "who_decides": "local_government", "summary": "Counties decide.",
              "statute_citation": "K.S.A. 12-741", "source_url": "https://example.org/ksa", "reviewer": "agent:r",
              "reviewed_on": "2026-10-09", "review_access": "opened", "verification": "verified",
              "evidence_level": "primary_source"}
    write(proc / "state_policies.csv", [policy], list(policy))
    write(proc / "state_policies_held.csv", [{"policy_id": "KS-other-1", "state": "KS", "policy_type": "other",
                                            "technology": "wind", "statute_citation": "K.S.A. 66-1,177",
                                            "reason": "no recorded review"}], state_policies.HELD_FIELDS)
    base = {k: "" for k in siting_standards.OUT_FIELDS}
    rows = [
        {**base, "id": "s1", "state": "KS", "jurisdiction": "Cherokee County", "jurisdiction_type": "County",
         "technology": "wind", "feature": "Structures (Non-Participating)", "value": "5250", "units": "feet",
         "county_fips_all": FIPS, "restricting": "yes", "verification": "unverified"},
        {**base, "id": "s2", "state": "KS", "jurisdiction": "Cherokee County", "jurisdiction_type": "County",
         "technology": "wind", "feature": "Noise", "value": "39", "units": "dBA", "county_fips_all": FIPS,
         "restricting": "yes", "verification": "verified"},
        {**base, "id": "s3", "state": "KS", "jurisdiction": "Labette County", "jurisdiction_type": "County",
         "technology": "wind", "feature": "Maximum Height", "value": "430", "units": "feet",
         "county_fips_all": "20099", "restricting": "yes", "verification": "unverified"},
    ]
    write(proc / "siting_standards.csv", rows, siting_standards.OUT_FIELDS)
    return root


def test_profile_shows_the_state_framework_and_local_standards(tmp_path):
    d = sp.Data(local=False, root=tree(tmp_path))
    p = sp.profile(d, FIPS, "Cherokee", "KS")
    text = sp.render(p)
    assert text.index("### State framework (KS)") < text.index("### In the county")
    assert "**Who decides** (solar, wind): local government." in text and "verified against the statute" in text
    assert "Not verified, held for review: Other state rule (K.S.A. 66-1,177): no recorded review" in text
    assert "### Local siting standards (NREL): 2 feature(s) in the county, 1 in adjacent counties" in text
    assert "1 verified against the ordinance, 1 unverified" in text
    assert "all unverified: NREL's reading" in text and "CC BY 4.0" in text


def test_verified_only_applies_to_the_new_sections(tmp_path):
    d = sp.Data(local=False, root=tree(tmp_path))
    p = sp.profile(d, FIPS, "Cherokee", "KS", verified_only=True)
    text = sp.render(p)
    assert "held for review" not in text.split("### In the county")[0].replace("1 row(s) still held for review", "")
    assert "1 row(s) still held for review were left out" in text
    assert [r["id"] for g in p["local_standards"].values() for r in g] == ["s2"]
    assert "2 unverified feature(s) were left out" in text


def test_headline_metrics_by_source_and_county_coverage():
    rows = [{"instrument_id": "sabin:REC-1", "sabin_edition": "2026-09", "severity_score": 4, "verification": "verified",
             "scope": "renewables_only", "county_fips_all": FIPS},
            {"instrument_id": "nrel:wind:20099", "severity_score": 2, "verification": "unverified",
             "scope": "renewables_only", "county_fips_all": "20099"},
            {"instrument_id": "sabin:REC-2", "sabin_edition": "2025-06", "severity_score": 3,
             "verification": "unverified", "scope": "renewables_only"}]
    m = hm.compute({"restrictions": rows}, standards=[{"county_fips_all": "20037", "verification": "unverified"}],
                   checks=[{"county_fips": "20021"}, {"county_fips": "20001"}], all_counties=geo.all_counties())
    src = m["restrictions"]["by_source"]
    assert src["Sabin 2026"]["by_verification"] == {"verified": 1}
    assert src["NREL"]["instruments"] == 1 and src["Sabin 2025 (not in 2026 edition)"]["severe_instruments"] == 1
    cc = m["county_coverage"]
    assert cc["with_any_record"] == 3 and cc["with_negative_check"] == 2
    assert cc["with_negative_check_and_no_record"] == 1
    assert cc["with_neither"] == cc["counties"] - 4
    assert "## County coverage" in hm.render(m)
