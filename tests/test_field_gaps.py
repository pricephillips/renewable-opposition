"""The field gaps check (scripts/field_gaps.py): its selftest, and the
repository's own config. The data itself is not tested here, so a gap opens
the field-gaps issue (.github/workflows/field-gaps.yml) instead of failing
unrelated pull requests."""
import field_gaps as fg


def test_selftest_passes():
    assert fg.selftest() == 0


def test_the_repository_config_is_valid_and_lists_each_file_once():
    cfg = fg.load_config(fg.CONFIG)
    paths = [f["path"] for f in cfg["files"]]
    assert len(paths) == len(set(paths))
    assert all(f["columns"] for f in cfg["files"])
