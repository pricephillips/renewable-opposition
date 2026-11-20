"""The Renewable Headwind Model's wide variable search (scripts/headwind_search.py)."""
import headwind_search as hs


def test_search_selftest():
    assert hs._selftest() == 0


def test_bar_is_corrected_for_the_searches_run():
    assert hs.MAX_P == 0.05 / hs.SEARCHES
    assert hs.SEARCHES == len(hs.OUTER) * 2, "two learners per label"


def test_outer_folds_run_forward():
    for folds in hs.OUTER.values():
        for train_to, (t0, _t1) in folds:
            assert t0 > train_to, "test years come after every training year"
