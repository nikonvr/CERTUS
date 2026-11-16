"""STRAT reads its nominal noise by the factor closest to 1, at the level of the run (audit 2026-11-15, L2-m1, L2-m2, L2-m6)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_strat_robustness_diagnostics import (
    _nominal_crash_rate,
    _nominal_noise_amp,
    _nominal_noise_index,
)
from certus.utils.certus_strat_context import _extract_rmse_p95_for_noise


def test_l2_m1_elite_reads_the_run_level_not_the_level_rescaled_by_the_slit() -> None:
    # A 1 nm child: the task multiplied the run levels (0.25, 0.5, 1.0) by 0.5. The nominal of the run is 0.5.
    result = {
        "results_per_noise": [
            {"noise_level": 0.125, "noise_level_run": 0.25, "rmse_p95": 1.0},
            {"noise_level": 0.25, "noise_level_run": 0.5, "rmse_p95": 2.0},
            {"noise_level": 0.5, "noise_level_run": 1.0, "rmse_p95": 3.0},
        ]
    }
    assert _extract_rmse_p95_for_noise(result, 0.5) == 2.0


def test_l2_m1_a_result_without_the_run_level_keeps_the_old_reading() -> None:
    result = {"results_per_noise": [{"noise_level": 0.25, "rmse_p95": 1.0}, {"noise_level": 0.5, "rmse_p95": 2.0}]}
    assert _extract_rmse_p95_for_noise(result, 0.5) == 2.0


@pytest.mark.parametrize(("factors", "index"), [("0.5,1,2", 1), ("1,0.5,2", 0), ([2.0, 0.5, 1.0], 2)])
def test_l2_m2_the_nominal_level_is_the_factor_closest_to_one(factors, index) -> None:
    assert _nominal_noise_index([0.1, 0.2, 0.3], {"robustness_noise_factors": factors}) == index


def test_l2_m2_unsorted_factors_do_not_double_the_margin() -> None:
    params = {"robustness_noise_factors": "1,0.5,2"}
    assert _nominal_noise_amp([0.5, 0.25, 1.0], params) == pytest.approx(0.005)


def test_l2_m2_the_default_factors_keep_the_middle_level_to_the_bit() -> None:
    levels = [0.25, 0.5, 1.0]
    assert _nominal_noise_amp(levels, {}) == float(levels[len(levels) // 2]) / 100.0


def test_l2_m2_a_thickness_noise_is_converted_to_transmission() -> None:
    params = {"thickness_tolerance_nm": 1.0}
    dT_dd = np.array([0.001, -0.002, 0.003])
    assert _nominal_noise_amp([0.5, 1.0, 2.0], params, dT_dd) == pytest.approx(0.002)


@pytest.mark.parametrize("trigger", [0.05, 0.5])
def test_l2_m6_the_nominal_rate_is_the_rate_of_the_factor_one(trigger: float) -> None:
    levels = [trigger * f for f in (0.5, 1.0, 2.0)]
    rates = {f"{lv:g}": r for lv, r in zip(levels, (0.01, 0.02, 0.04), strict=True)}
    assert _nominal_crash_rate(rates, levels, {}) == 0.02
