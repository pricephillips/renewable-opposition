import source_archive


def test_selftest_mocked_cdx_and_save_page_now():
    """The module's own selftest: mocked HTTP, no network (passoff B2)."""
    assert source_archive.selftest() == 0
