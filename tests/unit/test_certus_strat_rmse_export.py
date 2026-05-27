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


def test_extract_best_rmse_from_final_results():
    from CERTUS_STRAT import extract_best_rmse
    
    # Valide que extract_best_rmse extrait correctement le meilleur résultat fini
    final_results = {
        "all_strategies_results": [
            {"strategy_id": "strat_1", "rmse": 0.005},
            {"strategy_id": "strat_2", "rmse": 0.010},
        ]
    }
    rmse = extract_best_rmse(final_results.get("all_strategies_results", []))
    assert rmse == pytest.approx(0.005)


def test_extract_best_rmse_raises_on_null_rmse():
    from CERTUS_STRAT import extract_best_rmse
    from certus.utils.errors import PhysicsConvergenceError
    
    # Une RMSE de 0.0 est physiquement impossible pour un signal de dépôt réel bruité
    final_results = {
        "all_strategies_results": [
            {"strategy_id": "strat_1", "rmse": 0.0},
        ]
    }
    with pytest.raises(PhysicsConvergenceError, match="abnormally low/null value"):
        extract_best_rmse(final_results.get("all_strategies_results", []))

