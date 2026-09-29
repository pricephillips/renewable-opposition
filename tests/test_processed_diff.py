import processed_diff as pd

HDR = ["id", "state", "project_name", "outcome", "status", "severity_score", "long_description"]
A = [HDR,
     ["con_1", "OH", "Birch Solar", "pending", "active", "3", "long text"],
     ["con_2", "IN", "Mammoth", "", "active", "2", "more text"]]


def test_summary_names_the_row_and_both_outcome_values():
    b = [HDR,
         ["con_1", "OH", "Birch Solar", "cancelled", "active", "3", "long text"],
         ["con_2", "IN", "Mammoth", "", "active", "2", "more text"]]
    md = pd.render({"contested_projects": pd.hilite(A, b)})
    assert "| contested_projects | 0 | 0 | 1 |" in md
    assert "| contested_projects | con_1 (Birch Solar, OH) | outcome | pending | cancelled |" in md
    assert "long text" not in md  # unchanged columns stay out of the detail
    assert "—" not in md and "\r" not in md


def test_keyed_on_id_so_a_reorder_is_not_a_change():
    md = pd.render({"contested_projects": pd.hilite(A, [HDR, A[2], A[1]])})
    assert "No changes." in md


def test_added_and_removed_rows_are_counted():
    b = [HDR, A[1], ["con_3", "IA", "New", "", "", "1", ""]]
    d = pd.hilite(A, b)
    assert pd.counts(d) == {"added": 1, "removed": 1, "modified": 0}


def test_a_repeated_id_column_in_the_base_is_dropped():
    rows = pd.read_rows("id,state,id\r\nres_1,OH,res_1\r\n")
    assert rows == [["id", "state"], ["res_1", "OH"]]


def test_missing_base_says_so():
    assert "No prior revision" in pd.render({"cases": None})


def test_output_path_is_a_module_constant():
    assert pd.OUT_MD == pd.ROOT / "data" / "processed" / "diff_summary.md"


def test_new_columns_are_one_schema_line_not_every_row():
    b = [HDR + ["scope"]] + [r + ["renewables_only"] for r in A[1:]]
    md = pd.render({"contested_projects": pd.hilite(A, b)})
    assert "- contested_projects: added `scope`" in md
    assert "| + |" not in md and "No changes." not in md
