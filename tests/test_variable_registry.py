"""Registered variables (scripts/variable_registry.py; spec 033 in pricephillips/data-centers):
the registry's own selftest, the county_summary columns and the database tables."""
import duckdb

import build_database as bdb
import county_summary
import variable_core as vc
import variable_registry as vr


def test_registry_selftest_passes():
    assert vr.selftest() == 0


def test_the_lock_matches_the_shared_files_here():
    assert vr.lock_problems() == []


def test_county_summary_appends_one_column_per_variable_after_fields():
    rows = [{"county_fips": "01001"}, {"county_fips": "01003"}]
    added = county_summary.add_variables(rows, [("pop_x", {"01001": "5"}), ("cls_y", {"01003": "low"})])
    assert added == ["pop_x", "cls_y"]
    assert rows == [{"county_fips": "01001", "pop_x": "5", "cls_y": ""},
                    {"county_fips": "01003", "pop_x": "", "cls_y": "low"}]
    assert not set(added) & set(county_summary.FIELDS)


def _entry():
    return vc.parse_entry({
        "id": "demo_var", "format_version": 1, "file": "data/reference/variables/demo.csv",
        "key": "county_fips", "grain": "county", "audience": "public",
        "definition": "A fixture value.",
        "source": {"type": "none", "title": "Fixture", "url": "https://example.gov",
                   "license": "public domain", "attribution": "Fixture agency", "vintage": "2024"},
        "columns": {"v": {"name": "demo_v", "label": "Demo", "unit": "index", "format": "dec1"},
                    "c": {"name": "demo_c", "label": "Class", "unit": "category", "format": "text"}},
    }, "fixture")


def test_the_database_loads_a_public_variable(monkeypatch):
    e = _entry()
    monkeypatch.setattr(vr, "published", lambda *a, **k: ([e], []))
    monkeypatch.setattr(vr, "county_values", lambda entry, *a, **k: {
        "demo_v": {"01001": "1.5", "01003": ""}, "demo_c": {"01001": "low", "01003": "7"}})
    con = duckdb.connect()
    bdb.build(con)
    assert con.execute("SELECT variable_id, basis, license FROM variable ORDER BY 1").fetchall() == [
        ("demo_c", "county", "public domain"), ("demo_v", "county", "public domain")]
    rows = con.execute("SELECT county_fips, variable_id, value, value_text FROM county_variable "
                       "ORDER BY 1, 2").fetchall()
    # missing is no row (NULL), never zero; a category keeps its text, even "7"
    assert rows == [("01001", "demo_c", None, "low"), ("01001", "demo_v", 1.5, None),
                    ("01003", "demo_c", None, "7")]
    view = con.execute("SELECT county_name, label FROM v_county_variables WHERE variable_id = 'demo_v'").fetchall()
    assert view == [("Autauga", "Demo")]
    con.close()
