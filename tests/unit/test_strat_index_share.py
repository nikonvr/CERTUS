"""A11: the index share of a strategy (`certus/core/certus_strat_index_share.py`, `strat_index_share_top_k`, off by default)."""

import numpy as np

from certus.core.certus_strat_index_share import index_share, top_k


def _levels(rmse, stopped):
    return [(np.asarray(rmse, dtype=float), np.asarray(stopped, dtype=bool))] * 3


def test_off_by_default():
    assert top_k({}) == 0
    assert top_k({"strat_index_share_top_k": 10}) == 10


def test_the_share_is_one_minus_the_ratio_of_mean_squared_errors_on_the_draws_both_complete():
    on = _levels([2.0, 2.0, 9.0, 2.0], [False, False, True, False])
    off = _levels([1.0, 1.0, 1.0, 5.0], [False, False, False, True])
    out = index_share(on, off, 1)
    assert out["rmse2_index_on"] == 4.0  # draws 0 and 1 only: 2 and 3 stopped on one side
    assert out["rmse2_index_off"] == 1.0
    assert out["index_share"] == 0.75


def test_no_common_completed_draw_gives_no_share():
    assert index_share(_levels([1.0], [True]), _levels([1.0], [False]), 1)["index_share"] is None
