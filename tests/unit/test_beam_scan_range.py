"""The scan of the beam analysis is a method of its own, fed by a context (decision D64, audit v2 plan S5.2).

`BeamAnalysisWorker.run` scanned the metal thickness outward from the optimum with a function nested in it (198 lines), which rebound two of its variables by `nonlocal`
(`processed_steps`, `last_beam_emit_t`) and closed over eighteen others. The owner left the choice to the most logical: the scan is `_scan_the_thickness_range(scan, eM_list, start_x0,
label)`, a method, and what it closed over lives in `scan`, a namespace that `run` builds once and hands to both scans (UP, then DOWN) - the two counters stay shared between them.

Pinned here without a fit: `scipy.optimize.minimize` is a scripted fake that records what it is asked and also probes the objective it is given, the gradient kernel and the spline
evaluation are fakes too, the clock is a counter. The real example is run by tests/unit/test_metal_bilayer_beam.py.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.metal import certus_metal_bilayer_app as module
from certus.metal.certus_metal_bilayer_app import BeamAnalysisWorker

K = 3  # knots per spline family: x = [eL, n_inf, A, n x 3, k x 3, one inner lambda]
X_RESULT = np.arange(1.0, 11.0)  # eL 1, n_inf 2, A 3, n 4 5 6, k 7 8 9, lambda 10
X_START = np.linspace(0.5, 5.0, 10)
X_REDUCED = np.linspace(-1.0, -2.0, 10)  # the optimum the scan falls back on
THRESHOLD = 1e-3
OPTIMAL_MSE = 1e-4


class Recorder:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, bool]] = []

    def debug(self, message, **kwargs) -> None:
        self.records.append(("debug", message, bool(kwargs.get("exc_info"))))

    def info(self, message, **kwargs) -> None:
        self.records.append(("info", message, bool(kwargs.get("exc_info"))))

    def error(self, message, **kwargs) -> None:
        self.records.append(("error", message, bool(kwargs.get("exc_info"))))

    def of(self, level: str) -> list[str]:
        return [message for lvl, message, _ in self.records if lvl == level]


class Signal:
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, *args) -> None:
        self.emitted.append(args)


def result(fun, x=None, success=True):
    return SimpleNamespace(fun=fun, x=np.array(X_RESULT if x is None else x, dtype=float), success=success)


class Minimizer:
    """Stands in for `scipy.optimize.minimize`: answers from a script (a good result when it runs out) and probes the objective it is given."""

    def __init__(self, script) -> None:
        self.script = list(script)
        self.calls: list[SimpleNamespace] = []

    def __call__(self, fun, x0, **kwargs):
        probe = np.array(x0, dtype=float)
        value, gradient = fun(probe)
        self.calls.append(SimpleNamespace(fun=fun, x0_object=x0, x0=probe, kwargs=kwargs, value=value, gradient=gradient))
        return self.script.pop(0) if self.script else result(1e-5)


class Gradient:
    """The gradient kernel: cost 100 * eM, gradient (999, 0 + eM, 1 + eM, ...) whose first slot is the thickness one."""

    def __init__(self, fail_at=None, error=ValueError) -> None:
        self.calls: list[SimpleNamespace] = []
        self.fail_at = fail_at
        self.error = error

    def __call__(self, x_full, num_knots, l_array, r_tgt_array, min_knot_dist, n_sub):
        eM = float(x_full[0])
        self.calls.append(SimpleNamespace(eM=eM, x=np.array(x_full[1:], dtype=float), args=(num_knots, l_array, r_tgt_array, min_knot_dist, n_sub)))
        if self.fail_at is not None and eM == self.fail_at:
            raise self.error("planted")
        return 100.0 * eM, np.concatenate(([999.0], np.arange(x_full.size - 1, dtype=float) + eM))


class Spline:
    def __init__(self) -> None:
        self.calls: list[SimpleNamespace] = []

    def __call__(self, p_spline, knot_l, lam):
        self.calls.append(SimpleNamespace(p=np.array(p_spline), knots=np.array(knot_l), lam=lam))
        return np.full(lam.size, float(p_spline[0])), np.full(lam.size, float(p_spline[len(p_spline) // 2]))


def make_scan(**changes):
    scan = SimpleNamespace(
        num_knots=K,
        l_array=np.linspace(400.0, 800.0, 5),
        r_tgt_array=np.zeros(5),
        min_knot_dist=20.0,
        x0_optimal_reduced=X_REDUCED.copy(),
        total_steps=100,
        bounds=[(-50.0, 50.0)] * 10,
        l_min_val=400.0,
        l_max_val=800.0,
        mse_threshold=THRESHOLD,
        nSub_precomputed=np.ones(5),
        logger=Recorder(),
        all_solutions=[],
        plot_lambda=np.linspace(400.0, 800.0, 7),
        processed_steps=1,
        beam_emit_interval_s=5.0,
        last_beam_emit_t=0.0,
        beam_stall_patience=10,
        beam_fail_patience=6,
        beam_min_rel_gain=2e-4,
    )
    for key, value in changes.items():
        setattr(scan, key, value)
    return scan


def scan_range(eMs, *script, monkeypatch, scan=None, running=True, label="UP", start=None, fail_at=None, error=ValueError, optimal_mse=OPTIMAL_MSE, **scan_changes):
    scan = scan or make_scan(**scan_changes)
    worker = SimpleNamespace(is_running=running, optimal_mse=optimal_mse, progress=Signal())
    minimizer, gradient, spline = Minimizer(script), Gradient(fail_at, error), Spline()
    clock = {"t": 0.0}

    def fake_time():
        clock["t"] += 2.0
        return clock["t"]

    monkeypatch.setattr(module.scipy.optimize, "minimize", minimizer)
    monkeypatch.setattr(module, "compute_metal_bilayer_gradient_analytic", gradient)
    monkeypatch.setattr(module, "get_nk_from_spline", spline)
    monkeypatch.setattr(module, "time", SimpleNamespace(time=fake_time))
    start = np.array(X_START if start is None else start, dtype=float)
    returned = BeamAnalysisWorker._scan_the_thickness_range(worker, scan, list(eMs), start, label)
    return SimpleNamespace(scan=scan, worker=worker, minimizer=minimizer, gradient=gradient, spline=spline, start=start, returned=returned)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


# --- the stop button and the objective ------------------------------------------------------------------------------------------------------


def test_a_stopped_worker_scans_nothing(mp):
    run = scan_range([10.0, 12.0], monkeypatch=mp, running=False)
    assert run.returned is None
    assert run.minimizer.calls == []
    assert run.scan.processed_steps == 1
    assert run.worker.progress.emitted == []


def test_the_worker_stopped_in_the_middle_leaves_the_steps_already_counted(mp):
    scan = make_scan()
    worker = SimpleNamespace(is_running=True, optimal_mse=OPTIMAL_MSE, progress=Signal())
    minimizer = Minimizer([])

    def stop_after_the_first(fun, x0, **kwargs):
        worker.is_running = False
        return minimizer(fun, x0, **kwargs)

    mp.setattr(module.scipy.optimize, "minimize", stop_after_the_first)
    mp.setattr(module, "compute_metal_bilayer_gradient_analytic", Gradient())
    mp.setattr(module, "get_nk_from_spline", Spline())
    mp.setattr(module, "time", SimpleNamespace(time=lambda: 1.0))
    BeamAnalysisWorker._scan_the_thickness_range(worker, scan, [10.0, 12.0, 14.0], X_START.copy(), "UP")
    assert len(minimizer.calls) == 1
    assert scan.processed_steps == 2


def test_each_thickness_is_optimized_with_the_objective_of_that_thickness_and_the_gradient_without_the_thickness_slot(mp):
    run = scan_range([10.0, 12.0], monkeypatch=mp)
    first, second = run.minimizer.calls
    assert (first.value, second.value) == (1000.0, 1200.0)
    np.testing.assert_array_equal(first.gradient, np.arange(10.0) + 10.0)
    np.testing.assert_array_equal(second.gradient, np.arange(10.0) + 12.0)
    assert [call.eM for call in run.gradient.calls[:1]] == [10.0]


def test_the_gradient_kernel_gets_what_the_scan_carries(mp):
    run = scan_range([10.0], monkeypatch=mp)
    num_knots, l_array, r_tgt, min_knot_dist, n_sub = run.gradient.calls[0].args
    assert num_knots == K
    assert l_array is run.scan.l_array
    assert r_tgt is run.scan.r_tgt_array
    assert min_knot_dist == 20.0
    assert n_sub is run.scan.nSub_precomputed


def test_the_objective_stays_bound_to_its_own_thickness_after_the_scan_moved_on(mp):
    run = scan_range([10.0, 12.0], monkeypatch=mp)
    run.minimizer.calls[0].fun(np.zeros(10))
    assert run.gradient.calls[-1].eM == 10.0


def test_the_minimization_is_lbfgsb_with_the_scan_bounds_the_analytic_gradient_and_tight_tolerances(mp):
    run = scan_range([10.0], monkeypatch=mp)
    kwargs = run.minimizer.calls[0].kwargs
    assert kwargs["method"] == "L-BFGS-B"
    assert kwargs["bounds"] is run.scan.bounds
    assert kwargs["jac"] is True
    assert kwargs["options"] == {"ftol": 1e-9, "gtol": 1e-9, "maxiter": 2000}


def test_the_first_minimization_starts_from_a_copy_of_the_point_given(mp):
    run = scan_range([10.0], monkeypatch=mp)
    first = run.minimizer.calls[0]
    np.testing.assert_array_equal(first.x0, X_START)
    assert first.x0_object is not run.start


def test_the_next_thickness_starts_from_the_optimum_of_the_previous_one(mp):
    previous = X_RESULT + 0.5
    run = scan_range([10.0, 12.0], result(1e-5, x=previous), monkeypatch=mp)
    np.testing.assert_array_equal(run.minimizer.calls[1].x0, previous)
    assert run.minimizer.calls[1].x0_object is not run.minimizer.calls[0].x0_object


# --- what is kept -----------------------------------------------------------------------------------------------------------------------


def test_a_good_point_is_kept_with_the_thickness_the_layer_values_and_the_index_curves(mp):
    run = scan_range([10.0], result(5e-4), monkeypatch=mp)
    ((kept),) = run.scan.all_solutions
    assert kept["mse"] == 5e-4
    assert (kept["eM"], kept["eL"], kept["n_infini"], kept["A_diel"]) == (10.0, 1.0, 2.0, 3.0)
    np.testing.assert_array_equal(kept["params"], np.concatenate(([10.0], X_RESULT)))
    np.testing.assert_array_equal(kept["n"], np.full(7, 4.0))  # first n knot, from the spline stand-in
    np.testing.assert_array_equal(kept["k"], np.full(7, 7.0))  # first k knot


def test_the_spline_is_evaluated_on_the_plot_axis_with_sorted_knots_between_the_two_extremes(mp):
    unsorted = X_RESULT.copy()
    unsorted[9] = 650.0
    scan = make_scan()
    run = scan_range([10.0], result(5e-4, x=unsorted), monkeypatch=mp, scan=scan)
    call = run.spline.calls[0]
    np.testing.assert_array_equal(call.p, unsorted[3:9])
    np.testing.assert_array_equal(call.knots, [400.0, 650.0, 800.0])
    assert call.lam is scan.plot_lambda


def test_the_inner_knots_are_sorted_between_the_two_extremes_whatever_their_order(mp):
    # four knots per family: x = [eL, n_inf, A, n x 4, k x 4, two inner lambdas]
    x = np.arange(1.0, 14.0)
    x[11], x[12] = 700.0, 500.0
    scan = make_scan(num_knots=4, bounds=[(-50.0, 50.0)] * 13, x0_optimal_reduced=np.zeros(13))
    run = scan_range([10.0], result(5e-4, x=x), monkeypatch=mp, scan=scan, start=np.zeros(13))
    np.testing.assert_array_equal(run.spline.calls[0].knots, [400.0, 500.0, 700.0, 800.0])
    np.testing.assert_array_equal(run.spline.calls[0].p, x[3:11])


def test_a_point_exactly_at_the_threshold_is_kept_and_one_above_is_followed_but_not_kept(mp):
    run = scan_range([10.0, 12.0], result(THRESHOLD), result(THRESHOLD * 1.0001), monkeypatch=mp)
    assert [kept["eM"] for kept in run.scan.all_solutions] == [10.0]


def test_a_point_within_twice_the_threshold_is_followed(mp):
    followed = X_RESULT + 0.25
    run = scan_range([10.0, 12.0], result(1.5e-3, x=followed), monkeypatch=mp)
    np.testing.assert_array_equal(run.minimizer.calls[1].x0, followed)
    assert [kept["eM"] for kept in run.scan.all_solutions] == [12.0]  # the first is followed but not kept, the second (a good default) is kept


def test_a_minus_infinite_value_is_a_lost_trace_and_is_not_kept(mp):
    run = scan_range([10.0], result(float("-inf")), monkeypatch=mp)
    assert run.scan.logger.of("debug")[0].startswith("Continuity loss at 10.00 nm")
    assert 10.0 not in [kept["eM"] for kept in run.scan.all_solutions]


def test_a_point_that_is_not_finite_is_a_lost_trace(mp):
    found = X_RESULT + 9.0
    run = scan_range([10.0, 12.0], result(float("nan"), x=X_RESULT + 5.0), result(5e-4, x=found), monkeypatch=mp)
    assert run.scan.logger.of("debug") == ["Continuity loss at 10.00 nm (MSE=nan). Resetting."]
    np.testing.assert_array_equal(run.minimizer.calls[1].x0, X_REDUCED)  # the restart goes from the optimum, not from the nan point
    np.testing.assert_array_equal(run.minimizer.calls[2].x0, found)
    assert 10.0 not in [kept["eM"] for kept in run.scan.all_solutions]


# --- retries ------------------------------------------------------------------------------------------------------------------------------


RELAXED = {"ftol": 1e-7, "gtol": 1e-7, "maxiter": 3000}


def test_a_failed_minimization_is_retried_with_relaxed_tolerances_and_the_better_result_is_kept(mp):
    run = scan_range([10.0], result(8e-4, success=False), result(4e-4, x=X_RESULT + 1.0), monkeypatch=mp)
    assert len(run.minimizer.calls) == 2
    assert run.minimizer.calls[1].kwargs["options"] == RELAXED
    np.testing.assert_array_equal(run.minimizer.calls[1].x0, X_START)
    assert run.scan.all_solutions[0]["mse"] == 4e-4


def test_a_retry_that_is_not_better_is_ignored(mp):
    run = scan_range([10.0], result(8e-4, success=False), result(9e-4, x=X_RESULT + 1.0), monkeypatch=mp)
    assert run.scan.all_solutions[0]["mse"] == 8e-4
    np.testing.assert_array_equal(run.scan.all_solutions[0]["params"][1:], X_RESULT)


def test_a_result_just_over_one_and_a_half_times_the_threshold_is_retried_and_one_at_the_limit_is_not(mp):
    over = scan_range([10.0], result(THRESHOLD * 1.5 * 1.0001), monkeypatch=mp)
    assert len(over.minimizer.calls) == 2
    at = scan_range([10.0], result(THRESHOLD * 1.5), monkeypatch=mp)
    assert len(at.minimizer.calls) == 1


def test_a_lost_trace_is_logged_and_retried_from_the_optimum_with_relaxed_tolerances(mp):
    found = X_RESULT + 2.0
    run = scan_range([10.0, 12.0], result(2.5e-3), result(2.6e-3), result(5e-4, x=found), monkeypatch=mp)
    assert run.scan.logger.of("debug") == ["Continuity loss at 10.00 nm (MSE=2.50e-03). Resetting."]
    restart = run.minimizer.calls[2]
    np.testing.assert_array_equal(restart.x0, X_REDUCED)
    assert restart.x0_object is run.scan.x0_optimal_reduced
    assert restart.kwargs["options"] == RELAXED
    assert restart.kwargs["jac"] is True
    np.testing.assert_array_equal(run.minimizer.calls[3].x0, found)  # a valley was found: the next thickness starts there
    assert 10.0 not in [kept["eM"] for kept in run.scan.all_solutions]  # the lost point itself is not kept


def test_the_lost_trace_is_logged_with_the_better_of_the_two_first_results(mp):
    run = scan_range([10.0], result(2.5e-3), result(2.4e-3), monkeypatch=mp)
    assert run.scan.logger.of("debug") == ["Continuity loss at 10.00 nm (MSE=2.40e-03). Resetting."]


def test_a_lost_trace_that_finds_nothing_falls_back_on_the_optimum_and_counts_as_poor(mp):
    run = scan_range([10.0, 12.0], result(2.5e-3), result(2.4e-3), result(THRESHOLD), monkeypatch=mp)
    np.testing.assert_array_equal(run.minimizer.calls[3].x0, X_REDUCED)
    assert run.minimizer.calls[3].x0_object is not run.scan.x0_optimal_reduced  # a copy


def test_a_lost_trace_that_finds_a_valley_just_under_the_threshold_follows_it(mp):
    found = X_RESULT + 3.0
    run = scan_range([10.0, 12.0], result(2.5e-3), result(2.4e-3), result(THRESHOLD * 0.9999, x=found), monkeypatch=mp)
    np.testing.assert_array_equal(run.minimizer.calls[3].x0, found)


# --- errors -------------------------------------------------------------------------------------------------------------------------------


def test_an_error_at_one_thickness_is_logged_with_its_traceback_and_the_scan_goes_on_from_the_optimum(mp):
    run = scan_range([10.0, 12.0, 14.0], monkeypatch=mp, fail_at=12.0)
    assert run.scan.logger.of("error") == ["Error at 12.00: planted"]
    assert [exc_info for level, _msg, exc_info in run.scan.logger.records if level == "error"] == [True]
    third = run.minimizer.calls[-1]
    assert third.value == 1400.0
    np.testing.assert_array_equal(third.x0, X_REDUCED)
    assert third.x0_object is not run.scan.x0_optimal_reduced


@pytest.mark.parametrize("error", [ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError])
def test_these_errors_do_not_stop_the_scan(mp, error):
    run = scan_range([10.0, 12.0], monkeypatch=mp, fail_at=10.0, error=error)
    assert len(run.scan.logger.of("error")) == 1
    assert run.scan.processed_steps == 3


def test_other_errors_are_not_swallowed(mp):
    with pytest.raises(ZeroDivisionError):
        scan_range([10.0], monkeypatch=mp, fail_at=10.0, error=ZeroDivisionError)


def test_a_wrong_spline_state_is_an_error_of_that_step(mp):
    run = scan_range([10.0], result(5e-4, x=X_RESULT[:8]), monkeypatch=mp)
    assert len(run.scan.logger.of("error")) == 1
    assert run.scan.all_solutions == []


def test_inner_knots_that_do_not_match_the_coefficients_are_an_error_of_that_step(mp):
    x = np.arange(1.0, 12.0)  # three knots per family but two inner lambdas
    scan = make_scan(bounds=[(-50.0, 50.0)] * 11, x0_optimal_reduced=np.zeros(11))
    run = scan_range([10.0], result(5e-4, x=x), monkeypatch=mp, scan=scan, start=np.zeros(11))
    assert "Invalid spline state during beam scan" in run.scan.logger.of("error")[0]
    assert run.scan.all_solutions == []


def test_a_wrong_number_of_n_knots_is_named_in_the_error(mp):
    run = scan_range([10.0], result(5e-4, x=X_RESULT[:4]), monkeypatch=mp)
    assert "Invalid beam spline state" in run.scan.logger.of("error")[0]


# --- progress -----------------------------------------------------------------------------------------------------------------------------


def test_every_thickness_counts_one_step_on_the_context(mp):
    run = scan_range([10.0, 12.0, 14.0], monkeypatch=mp)
    assert run.scan.processed_steps == 4  # it started at 1: the optimum itself


def test_progress_is_reported_at_most_every_five_seconds_with_the_step_the_total_and_the_optimum(mp):
    run = scan_range([10.0 + 2 * k for k in range(6)], monkeypatch=mp)
    assert run.worker.progress.emitted == [(4, 100, OPTIMAL_MSE), (7, 100, OPTIMAL_MSE)]
    assert run.scan.last_beam_emit_t == 12.0


def test_progress_is_reported_at_every_step_once_the_total_is_reached(mp):
    run = scan_range([10.0, 12.0, 14.0], monkeypatch=mp, total_steps=3)
    assert run.worker.progress.emitted == [(3, 3, OPTIMAL_MSE), (4, 3, OPTIMAL_MSE)]


def test_the_counters_are_shared_by_the_two_scans_through_the_context(mp):
    scan = make_scan()
    scan_range([10.0, 12.0, 14.0], monkeypatch=mp, scan=scan, label="UP")
    assert scan.processed_steps == 4
    second = scan_range([8.0, 6.0], monkeypatch=mp, scan=scan, label="DOWN")
    assert second.scan.processed_steps == 6
    assert scan.last_beam_emit_t > 0.0


# --- early stop -------------------------------------------------------------------------------------------------------------------------


def test_a_branch_that_stagnates_with_poor_points_stops_and_says_where(mp):
    run = scan_range([10.0, 12.0, 14.0, 16.0], result(1.5e-3), result(1.5e-3), monkeypatch=mp, beam_stall_patience=2, beam_fail_patience=2, label="DOWN")
    assert len(run.minimizer.calls) == 2
    assert run.scan.logger.of("info") == ["Early stop DOWN: stagnation at eM=12.00 nm (no_gain=2, poor=2)"]


def test_stagnation_without_poor_points_does_not_stop_the_branch(mp):
    run = scan_range([10.0, 12.0, 14.0, 16.0], *[result(5e-4)] * 4, monkeypatch=mp, beam_stall_patience=2, beam_fail_patience=2)
    assert len(run.minimizer.calls) == 4
    assert run.scan.logger.of("info") == []


def test_poor_points_that_still_gain_do_not_stop_the_branch(mp):
    # every point is above the threshold (poor) but better than the one before: the stagnation count stays at zero
    run = scan_range(
        [10.0, 12.0, 14.0],
        result(1.2e-3),
        result(1.1e-3),
        result(1.05e-3),
        monkeypatch=mp,
        optimal_mse=5e-3,
        beam_stall_patience=1,
        beam_fail_patience=1,
    )
    assert len(run.minimizer.calls) == 3
    assert run.scan.logger.of("info") == []


def test_a_point_exactly_at_the_threshold_resets_the_poor_count(mp):
    run = scan_range(
        [10.0, 12.0, 14.0],
        result(1.5e-3),
        result(THRESHOLD),
        result(5e-4),
        monkeypatch=mp,
        beam_stall_patience=2,
        beam_fail_patience=2,
    )
    assert len(run.minimizer.calls) == 3
    assert run.scan.logger.of("info") == []


def test_a_lost_trace_that_finds_nothing_counts_twice_as_poor_so_a_single_one_can_stop_the_branch(mp):
    run = scan_range(
        [10.0, 12.0],
        result(2.5e-3),
        result(2.4e-3),
        result(THRESHOLD),
        monkeypatch=mp,
        beam_stall_patience=1,
        beam_fail_patience=2,
    )
    assert len(run.minimizer.calls) == 3
    assert run.scan.logger.of("info") == ["Early stop UP: stagnation at eM=10.00 nm (no_gain=1, poor=2)"]


def test_a_gain_resets_the_stagnation_count(mp):
    run = scan_range(
        [10.0, 12.0, 14.0, 16.0, 18.0],
        result(1e-4),
        result(5e-5),
        result(5e-5),
        result(5e-5),
        monkeypatch=mp,
        beam_stall_patience=2,
        beam_fail_patience=0,
    )
    assert len(run.minimizer.calls) == 4
    assert run.scan.logger.of("info") == ["Early stop UP: stagnation at eM=16.00 nm (no_gain=2, poor=0)"]


def test_a_gain_needs_to_beat_the_best_by_the_relative_margin(mp):
    best = OPTIMAL_MSE * (1.0 - 2e-4)
    run = scan_range([10.0, 12.0], result(best), result(best * 0.9), monkeypatch=mp, beam_stall_patience=2, beam_fail_patience=0)
    # exactly at the margin is no gain (first step), a real improvement is (second step): the count never reaches two
    assert len(run.minimizer.calls) == 2
    assert run.scan.logger.of("info") == []


def test_an_error_counts_as_a_step_without_gain_and_a_poor_one(mp):
    run = scan_range([10.0, 12.0, 14.0], monkeypatch=mp, fail_at=10.0, beam_stall_patience=1, beam_fail_patience=1)
    assert run.scan.logger.of("info") == ["Early stop UP: stagnation at eM=10.00 nm (no_gain=1, poor=1)"]
    assert len(run.gradient.calls) == 1


# --- the analysis hands the scan its context ---------------------------------------------------------------------------------------------


def test_the_analysis_builds_the_context_once_and_scans_up_then_down_with_it():
    source = inspect.getsource(BeamAnalysisWorker.run)
    assert source.count("scan = SimpleNamespace(") == 1
    up = source.index('self._scan_the_thickness_range(scan, eM_range_up, x0_optimal_reduced, "UP")')
    down = source.index('self._scan_the_thickness_range(scan, eM_range_down, x0_optimal_reduced, "DOWN")')
    assert source.index("scan = SimpleNamespace(") < up < down


def test_the_context_carries_exactly_what_the_scan_reads():
    source = inspect.getsource(BeamAnalysisWorker.run)
    block = source[source.index("scan = SimpleNamespace(") : source.index('self._scan_the_thickness_range(scan, eM_range_up')]
    carried = {line.split("=")[0].strip() for line in block.splitlines()[1:] if "=" in line}
    method = inspect.getsource(BeamAnalysisWorker._scan_the_thickness_range)
    read = {name for name in carried if f"scan.{name}" in method}
    assert carried == read
    assert len(carried) == 20
