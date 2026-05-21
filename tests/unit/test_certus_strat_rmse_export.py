from __future__ import annotations

from pathlib import Path

import pytest

from CERTUS_STRAT import _select_best_strat_result


@pytest.mark.parametrize(
    "items, expected",
    [
        ([{"robustness_score": 0.0}, {"robustness_score": 0.031}], 0.031),
        ([{"rmse_p95": 0.0}, {"rmse_mean": 0.042}], 0.042),
        ([{"rmse": 0.0}, {"final_rmse": 0.055}], 0.055),
        ([{"robustness_score": 0.0}, {"rmse": 0.0}], 0.0),
    ],
)
def test_select_best_strat_result_prefers_first_positive_score(items, expected):
    best = _select_best_strat_result(items)
    assert best is not None

    for key in ("robustness_score", "rmse_p95", "rmse_mean", "rmse", "final_rmse"):
        if key in best and best[key]:
            assert float(best[key]) == pytest.approx(expected)
            return

    assert expected == 0.0


def test_select_best_strat_result_returns_none_for_empty_list():
    assert _select_best_strat_result([]) is None
