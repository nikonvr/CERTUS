"""`_apply_the_admissibility_rule` is the part of Phase A that forbids the unsafe control wavelengths (audit v2, plan S5.2).

It was 85 lines in the middle of `_validate_candidates_phase_a` (378 lines). For each candidate wavelength the Monte-Carlo kernel returned four figures (RMSE, spread, rate of
unfinishable depositions, compensation gain); the rule keeps the ones whose crash rate is under the per-layer tolerance and whose gain is measurable, prices each survivor, writes
the census of the layer into `params`, and - when nobody survives - falls back on the least crashing wavelengths and says so. Pinned here on synthetic kernel output.
"""

from __future__ import annotations

import inspect
import logging
import math

import numpy as np
import pytest

from certus.utils import certus_strat_service as service
from certus.utils.certus_strat_service import _apply_the_admissibility_rule

EXT_KEYS = ("ext_prev_start", "dynamics")


class Recorder:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def rule(rows, *, candidates=None, err_prev_nm=0.0, gain_weight=1.0, crash_tol=0.1, i_layer=2, params=None, survivors=None):
    """Run the rule on kernel rows (rmse, std, crash_rate, gain); return (survivors, params, recorder)."""
    results_fast = np.array(rows, dtype=np.float64).reshape(-1, 4)
    wls = [1000.0 + 10.0 * k for k in range(len(results_fast))]
    candidates = [{"wl": w} for w in wls] if candidates is None else candidates
    recorder = Recorder()
    params = {"logger": recorder} if params is None else params
    out = _apply_the_admissibility_rule(
        candidates,
        i_layer,
        params,
        wls,
        results_fast,
        [] if survivors is None else survivors,
        EXT_KEYS,
        crash_tol,
        gain_weight,
        err_prev_nm,
    )
    return out, params, recorder


def costs(survivors):
    return [round(entry["cost"], 12) for entry in survivors]


# --- what an entry carries ---------------------------------------------------------------------------------------------------------------


def test_an_entry_carries_the_four_kernel_figures_and_its_wavelength():
    out, *_ = rule([(0.5, 0.1, 0.0, 0.2)])
    assert out == [{"wl": 1000.0, "cost": 0.5, "std_dev": 0.1, "crash_rate": 0.0, "compensation_gain": 0.2, "cost_local": 0.5}]


def test_the_inherited_error_is_added_to_the_cost_weighted_by_the_gain_and_the_weight_but_not_to_the_local_cost():
    out, *_ = rule([(0.5, 0.1, 0.0, 0.2)], err_prev_nm=3.0, gain_weight=2.0)
    assert out[0]["cost"] == pytest.approx(0.5 + 2.0 * 0.2 * 3.0)
    assert out[0]["cost_local"] == 0.5


def test_a_negative_gain_does_not_lower_the_cost_even_when_the_entry_is_kept_by_the_fallback():
    out, *_ = rule([(0.5, 0.1, 0.0, -0.4)], err_prev_nm=3.0, gain_weight=2.0)
    assert out[0]["cost"] == 0.5  # eliminated for its negative gain, then rescued by the fallback: priced on its RMSE alone


def test_the_extrema_metadata_of_the_candidate_is_carried_over_for_the_listed_keys_only():
    candidates = [{"wl": 1000.0, "ext_prev_start": 3, "dynamics": 0.7, "other": "x"}, {"wl": 1010.0}]
    out, *_ = rule([(0.5, 0.1, 0.0, 0.2), (0.6, 0.1, 0.0, 0.2)], candidates=candidates)
    assert out[0]["ext_prev_start"] == 3
    assert out[0]["dynamics"] == 0.7
    assert "other" not in out[0]
    assert "ext_prev_start" not in out[1]
    assert "dynamics" not in out[1]


# --- who is forbidden ---------------------------------------------------------------------------------------------------------------------


def test_survivors_keep_the_order_of_the_candidates():
    out, *_ = rule([(0.9, 0, 0.0, 0.1), (0.1, 0, 0.0, 0.1), (0.5, 0, 0.0, 0.1)])
    assert [entry["wl"] for entry in out] == [1000.0, 1010.0, 1020.0]


def test_a_crash_rate_at_the_tolerance_is_forbidden_and_just_under_it_is_not():
    out, *_ = rule([(0.1, 0, 0.1, 0.1), (0.2, 0, 0.0999, 0.1)], crash_tol=0.1)
    assert [entry["wl"] for entry in out] == [1010.0]


def test_a_gain_that_is_not_measurable_is_forbidden_and_a_zero_gain_is_not():
    out, *_ = rule([(0.1, 0, 0.0, -0.001), (0.2, 0, 0.0, 0.0)])
    assert [entry["wl"] for entry in out] == [1010.0]


def test_the_census_counts_each_forbidden_candidate_once_and_a_crash_wins_over_a_negative_gain():
    _out, params, _ = rule([(0.1, 0, 0.5, -1.0), (0.1, 0, 0.5, 0.1), (0.1, 0, 0.0, -1.0), (0.1, 0, 0.0, 0.1)])
    (stats,) = params["phase_a_admissibility_stats"]
    assert stats["forbidden_crash"] == 2
    assert stats["forbidden_gain_negative"] == 1
    assert stats["survivors"] == 1


def test_a_negative_gain_is_also_counted_when_the_crash_gate_already_forbade_the_candidate():
    """D17: the exclusive count never showed the gain rule at work, since a crash wins; the overlap is counted on its own."""
    _out, params, _ = rule([(0.1, 0, 0.5, -1.0), (0.1, 0, 0.0, -1.0), (0.1, 0, 0.0, 0.1)])
    (stats,) = params["phase_a_admissibility_stats"]
    assert stats["forbidden_crash"] == 1
    assert stats["forbidden_gain_negative"] == 1
    assert stats["gain_negative_any"] == 2


# --- the census ------------------------------------------------------------------------------------------------------------------------


def test_the_census_describes_the_layer():
    _out, params, _ = rule([(0.1, 0, 0.5, 0.1), (0.1, 0, 0.02, 0.1), (0.1, 0, 0.04, 0.1)], crash_tol=0.1, i_layer=4)
    (stats,) = params["phase_a_admissibility_stats"]
    assert stats == {
        "layer": 5,
        "offered": 3,
        "forbidden_crash": 1,
        "forbidden_gain_negative": 0,
        "gain_negative_any": 0,
        "survivors": 2,
        "crash_rate_min_observed": 0.02,
        "crash_tolerance": 0.1,
    }


def test_the_minimum_crash_rate_looks_at_every_candidate_not_only_the_survivors():
    _out, params, _ = rule([(0.1, 0, 0.5, 0.1), (0.1, 0, 0.3, 0.1)], crash_tol=0.1)
    assert params["phase_a_admissibility_stats"][0]["crash_rate_min_observed"] == 0.3


def test_without_candidates_the_minimum_crash_rate_is_nan_and_nothing_is_returned():
    out, params, _ = rule([])
    assert out == []
    assert math.isnan(params["phase_a_admissibility_stats"][0]["crash_rate_min_observed"])
    assert params["phase_a_admissibility_stats"][0]["offered"] == 0


def test_the_census_is_appended_to_the_list_that_params_already_holds():
    existing = ["an earlier layer"]
    _out, params, _ = rule([(0.1, 0, 0.0, 0.1)], params={"phase_a_admissibility_stats": existing, "logger": Recorder()})
    assert params["phase_a_admissibility_stats"] is existing
    assert len(existing) == 2
    assert existing[0] == "an earlier layer"
    assert existing[1]["layer"] == 3


def test_the_list_is_created_in_params_when_it_is_missing():
    _out, params, _ = rule([(0.1, 0, 0.0, 0.1)])
    assert isinstance(params["phase_a_admissibility_stats"], list)
    assert len(params["phase_a_admissibility_stats"]) == 1


# --- what is said ---------------------------------------------------------------------------------------------------------------------


def test_the_census_is_logged_on_one_line():
    _out, _params, recorder = rule([(0.1, 0, 0.5, 0.1), (0.1, 0, 0.0, -1.0), (0.1, 0, 0.02, 0.1)], crash_tol=0.1, i_layer=2)
    assert recorder.infos == [
        "   [ADMISSIBILITY] Layer 3: 3 offered -> forbidden crash>=10.000%: 1 | forbidden gain<0: 1 of 1 with gain<0 | survivors: 1 | min crash rate observed: 0.000%"
    ]
    assert recorder.warnings == []


def test_without_a_logger_in_params_the_census_goes_to_the_thinfilm_logger(caplog):
    with caplog.at_level(logging.INFO, logger="ThinFilm"):
        rule([(0.1, 0, 0.0, 0.1)], params={})
    assert any("[ADMISSIBILITY] Layer 3: 1 offered" in record.getMessage() for record in caplog.records)


# --- when nobody survives -------------------------------------------------------------------------------------------------------------


def test_when_nobody_survives_the_least_crashing_candidates_are_kept_and_the_layer_is_called_a_hard_point():
    out, params, recorder = rule([(0.3, 0, 0.5, 0.1), (0.1, 0, 0.2, 0.1), (0.2, 0, 0.9, 0.1)], crash_tol=0.1)
    assert [entry["wl"] for entry in out] == [1010.0]
    (stats,) = params["phase_a_admissibility_stats"]
    assert stats["fallback_on_min_crash"] is True
    assert stats["survivors"] == 1
    assert len(recorder.warnings) == 1
    assert "[CRASH] Layer 3: NO wavelength under the threshold of 10.000% unfinishable depositions." in recorder.warnings[0]
    assert "Fallback to the minimum observed rate (20.000%)" in recorder.warnings[0]
    assert "the layer is a hard point" in recorder.warnings[0]


def test_the_fallback_keeps_every_candidate_that_ties_with_the_best_within_a_picometre_and_in_their_order():
    rows = [(0.3, 0, 0.2 + 1e-13, 0.1), (0.1, 0, 0.2 + 1e-11, 0.1), (0.2, 0, 0.2, 0.1)]
    out, params, _ = rule(rows, crash_tol=0.1)
    assert [entry["wl"] for entry in out] == [1000.0, 1020.0]
    assert params["phase_a_admissibility_stats"][0]["survivors"] == 2


def test_the_fallback_is_for_the_empty_case_only():
    out, params, recorder = rule([(0.3, 0, 0.5, 0.1), (0.1, 0, 0.01, 0.1)], crash_tol=0.1)
    assert [entry["wl"] for entry in out] == [1010.0]
    assert "fallback_on_min_crash" not in params["phase_a_admissibility_stats"][0]
    assert recorder.warnings == []


def test_the_fallback_prices_the_rescued_entries_like_the_others():
    out, *_ = rule([(0.3, 0, 0.5, 0.1), (0.1, 0, 0.2, 0.5)], crash_tol=0.1, err_prev_nm=2.0, gain_weight=3.0)
    assert costs(out) == [round(0.1 + 3.0 * 0.5 * 2.0, 12)]


# --- the caller -----------------------------------------------------------------------------------------------------------------------


def test_phase_a_validation_hands_the_rule_its_results_and_takes_the_survivors_back():
    source = inspect.getsource(service._validate_candidates_phase_a)
    assert "results_thickness = _apply_the_admissibility_rule(" in source
    assert "candidates, i_layer, params, candidate_wls, results_fast, results_thickness, _EXT_KEYS, crash_tol, gain_weight, err_prev_nm" in source
    assert source.index("_apply_the_admissibility_rule(") < source.index("results_thickness.sort(")
