"""The two last stages of the FIELD optimization are methods of their own (audit v2, plan S5.2).

`FieldWorkerThread._run_optimize` is 347 lines: the cost function, the global or local search, and then two stages that come out here, each pinned on a namespace in place of the worker's
parameters, a recorder in place of the signal and fakes in place of the field calculation:

    _clean_the_thin_layers_of_the_solutions   the layers thinner than `dmin` are removed from the best solution and from every other solution found, each one re-optimized
    _field_of_the_best_solution               the electric field of the best solution at every calculation wavelength, the final metrics at the first
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.utils.certus_progress_tracker import StepState
from certus.workers import certus_field_workers as module
from certus.workers.certus_field_workers import FieldWorkerThread

# --- _clean_the_thin_layers_of_the_solutions ---------------------------------------------------------------------------------------------


class Signal:
    def __init__(self) -> None:
        self.emitted: list = []

    def emit(self, snapshot) -> None:
        self.emitted.append(snapshot)


class Logger:
    def __init__(self) -> None:
        self.infos: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)


class Cleaner:
    """Stands in for `_clean_and_reoptimize`: records its calls and answers from a script keyed on the first vector."""

    def __init__(self, script: dict | None = None) -> None:
        self.script = script or {}
        self.calls: list[tuple] = []

    def __call__(self, x, types, dmin, params):
        self.calls.append((tuple(x), tuple(types), dmin, params))
        return self.script.get(tuple(x), (list(x), list(types), False, None))


def clean(*, cleaner, params, best_x=(1.0, 2.0, 3.0), best_cost=0.5, solutions=(), logger=None):
    signal = Signal()
    worker = SimpleNamespace(signals=SimpleNamespace(progress_snapshot=signal), _clean_and_reoptimize=cleaner)
    logger = Logger() if logger is None else logger
    out = FieldWorkerThread._clean_the_thin_layers_of_the_solutions(worker, params, logger, best_cost, list(best_x), list(solutions))
    return out, signal, logger


def thin_params(**changes):
    base = {"dmin": 5.0, "layer_types": [0, 1, 0]}
    base.update(changes)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("dmin", [0.0, -1.0], ids=["zero", "negative"])
def test_without_a_minimum_thickness_nothing_is_cleaned_emitted_or_changed(dmin):
    cleaner = Cleaner()
    solutions = [{"cost": 0.4, "emp_factors": [1.0], "layer_types": [0]}]
    (all_solutions, best_cost, best_x), signal, logger = clean(cleaner=cleaner, params=thin_params(dmin=dmin), solutions=solutions)
    assert cleaner.calls == []
    assert signal.emitted == []
    assert logger.infos == []
    assert (best_cost, best_x) == (0.5, [1.0, 2.0, 3.0])
    assert all_solutions == solutions


def test_a_worker_without_a_minimum_thickness_cleans_at_five_nanometres():
    params = SimpleNamespace(layer_types=[0, 1, 0])
    cleaner = Cleaner()
    clean(cleaner=cleaner, params=params)
    assert [call[2] for call in cleaner.calls] == [5.0]


def test_the_cleaning_is_announced_twice_under_the_two_phases_it_has_always_used():
    _out, signal, _logger = clean(cleaner=Cleaner(), params=thin_params(dmin=7.5))
    first, second = signal.emitted
    for snapshot in (first, second):
        assert snapshot.message == "Auto-cleaning layers thinner than 7.5 nm..."
        assert (snapshot.display_ratio, snapshot.progress_ratio) == (0.85, 0.85)
        assert snapshot.state is StepState.RUNNING
        assert snapshot.module == "FIELD"
        assert snapshot.confidence == 0.25
        assert snapshot.eta_seconds is None
    assert (first.phase, first.metadata) == ("OPTIMIZATION", {"mode": "CLEANUP", "dmin": 7.5})
    assert (second.phase, second.metadata) == ("AUTO_CLEAN", None)


def test_the_best_solution_is_cleaned_with_its_own_layer_types_and_the_minimum_thickness():
    params = thin_params()
    cleaner = Cleaner()
    clean(cleaner=cleaner, params=params, best_x=(1.0, 2.0, 3.0))
    assert cleaner.calls[0] == ((1.0, 2.0, 3.0), (0, 1, 0), 5.0, params)


def test_a_cleaned_best_solution_replaces_the_best_one_its_cost_and_the_layer_types(monkeypatch):
    params = thin_params()
    cleaner = Cleaner({(1.0, 2.0, 3.0): ([4.0, 5.0], [1, 0], True, 0.25)})
    (_solutions, best_cost, best_x), _signal, logger = clean(cleaner=cleaner, params=params)
    assert best_x == [4.0, 5.0]
    assert best_cost == 0.25
    assert params.layer_types == [1, 0]
    assert logger.infos == ["Auto-cleaned best solution: reduced layers from 3 to 2, cost: 0.250000"]


def test_a_best_solution_that_nothing_was_removed_from_stays_as_it_was():
    params = thin_params()
    (_solutions, best_cost, best_x), _signal, logger = clean(cleaner=Cleaner(), params=params)
    assert (best_x, best_cost, params.layer_types) == ([1.0, 2.0, 3.0], 0.5, [0, 1, 0])
    assert logger.infos == []


def test_every_other_solution_is_cleaned_and_a_cleaned_one_is_rebuilt_with_its_qwot_sum():
    params = thin_params()
    solutions = [
        {"cost": 0.4, "emp_factors": [1.0, 1.0], "layer_types": [1, 1], "qwot_sum": 2.0},
        {"cost": 0.6, "emp_factors": [2.0, 2.0], "layer_types": [0, 0], "qwot_sum": 4.0},
    ]
    cleaner = Cleaner({(1.0, 1.0): ([3.0, 0.5], [1, 0], True, 0.3)})
    (all_solutions, _cost, _x), _signal, _logger = clean(cleaner=cleaner, params=params, solutions=solutions)
    assert all_solutions[0] == {"cost": 0.3, "qwot_sum": 3.5, "emp_factors": [3.0, 0.5], "layer_types": [1, 0]}
    assert all_solutions[1] is solutions[1]
    assert [call[0] for call in cleaner.calls[1:]] == [(1.0, 1.0), (2.0, 2.0)]


def test_a_solution_that_was_cleaned_without_a_cost_is_kept_as_it_was():
    solutions = [{"cost": 0.4, "emp_factors": [1.0, 1.0], "layer_types": [1, 1]}]
    cleaner = Cleaner({(1.0, 1.0): ([3.0], [1], True, None)})
    (all_solutions, _cost, _x), _signal, _logger = clean(cleaner=cleaner, params=thin_params(), solutions=solutions)
    assert all_solutions == [solutions[0]]
    assert all_solutions[0] is solutions[0]


def test_a_solution_without_layer_types_is_read_with_the_types_of_the_best_solution_as_it_was_just_cleaned():
    params = thin_params()
    solutions = [{"cost": 0.4, "emp_factors": [1.0, 1.0]}, {"cost": 0.4, "emp_factors": [2.0, 2.0], "layer_types": [1, 1]}]
    cleaner = Cleaner({(1.0, 2.0, 3.0): ([4.0, 5.0], [1, 0], True, 0.25)})
    clean(cleaner=cleaner, params=params, solutions=solutions)
    assert cleaner.calls[1][1] == (1, 0)
    assert cleaner.calls[2][1] == (1, 1)


def test_the_other_solutions_are_handed_the_same_minimum_and_parameters():
    params = thin_params(dmin=9.0)
    cleaner = Cleaner()
    clean(cleaner=cleaner, params=params, solutions=[{"cost": 0.4, "emp_factors": [1.0], "layer_types": [0]}])
    assert [call[2] for call in cleaner.calls] == [9.0, 9.0]
    assert all(call[3] is params for call in cleaner.calls)


def test_without_any_other_solution_the_list_stays_empty():
    (all_solutions, _cost, _x), _signal, _logger = clean(cleaner=Cleaner(), params=thin_params())
    assert all_solutions == []


# --- _field_of_the_best_solution ---------------------------------------------------------------------------------------------------------


def field_params(wavelengths=(500.0, 600.0, 700.0)):
    n = len(wavelengths)
    return SimpleNamespace(
        lambda_calcs=list(wavelengths),
        n1_rs=[1.5 + 0.01 * k for k in range(n)],
        n2_rs=[2.0 + 0.01 * k for k in range(n)],
        nSub_rs=[1.45 + 0.01 * k for k in range(n)],
        n_supers=[1.0 + 0.001 * k for k in range(n)],
        l0=550.0,
        layer_types=[0, 1],
        integral_points=33,
        theta_inc=0.1,
        pol_flag=2,
    )


@pytest.fixture
def fakes(monkeypatch):
    seen = SimpleNamespace(fields=[], metrics=[])

    def electric_field(**kwargs):
        k = len(seen.fields)
        seen.fields.append(kwargs)
        return np.array([0.0, 1.0, 2.0]) + 10 * k, np.array([1.0, 2.0, 3.0]) * (k + 1), f"ep{k}", None, None

    def opt_metrics(*args):
        seen.metrics.append(args)
        return "the final metrics"

    monkeypatch.setattr(module, "calculate_electric_field", electric_field)
    monkeypatch.setattr(module, "calculate_opt_metrics", opt_metrics)
    return seen


def field(params=None, best_x=(1.0, 2.0)):
    return FieldWorkerThread._field_of_the_best_solution(SimpleNamespace(), params or field_params(), list(best_x))


def test_the_field_is_computed_once_per_wavelength_with_the_index_of_that_wavelength(fakes):
    params = field_params()
    field(params, best_x=(1.5, 2.5))
    assert len(fakes.fields) == 3
    for k, kwargs in enumerate(fakes.fields):
        assert kwargs == {
            "n1_r": params.n1_rs[k],
            "n2_r": params.n2_rs[k],
            "nSub_r": params.nSub_rs[k],
            "l0": 550.0,
            "lambda_calc": params.lambda_calcs[k],
            "emp_factors": [1.5, 2.5],
            "layer_types": [0, 1],
            "n_superstrate_real": params.n_supers[k],
            "integral_points": 33,
            "theta_inc": 0.1,
            "pol_flag": 2,
        }


def test_the_squared_fields_come_back_as_lists_in_the_order_of_the_wavelengths(fakes):
    e2_values, _ep, _metrics, _z = field()
    assert e2_values == [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [3.0, 6.0, 9.0]]
    assert all(isinstance(values, list) for values in e2_values)


def test_the_coordinates_and_the_layer_field_are_those_of_the_first_wavelength(fakes):
    _e2, ep_c, _metrics, z_coords = field()
    assert z_coords == [0.0, 1.0, 2.0]
    assert isinstance(z_coords, list)
    assert ep_c == "ep0"


def test_the_final_metrics_are_computed_once_at_the_first_wavelength_in_the_order_the_function_expects(fakes):
    params = field_params()
    _e2, _ep, metrics, _z = field(params, best_x=(1.5, 2.5))
    assert metrics == "the final metrics"
    assert fakes.metrics == [(params.n1_rs[0], params.n2_rs[0], params.nSub_rs[0], 550.0, [1.5, 2.5], [0, 1], params.n_supers[0], 33, 0.1, 2, 500.0)]


def test_a_single_wavelength_is_enough(fakes):
    e2_values, ep_c, _metrics, z_coords = field(field_params((520.0,)))
    assert len(e2_values) == 1
    assert (z_coords, ep_c) == ([0.0, 1.0, 2.0], "ep0")


def test_the_values_come_back_in_the_order_the_optimization_unpacks_them(fakes):
    out = field()
    assert out[0] == [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [3.0, 6.0, 9.0]]
    assert out[1] == "ep0"
    assert out[2] == "the final metrics"
    assert out[3] == [0.0, 1.0, 2.0]


# --- the optimization hands them their work ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        "all_solutions, best_cost, best_x = self._clean_the_thin_layers_of_the_solutions(params, logger, best_cost, best_x, all_solutions)",
        "E2_values_list, ep_c_final, final_metrics, z_coords_final = self._field_of_the_best_solution(params, best_x)",
    ],
)
def test_the_optimization_calls_each_stage_with_the_values_it_computed(call):
    assert call in inspect.getsource(FieldWorkerThread._run_optimize)


def test_the_stages_come_after_the_search_in_this_order_and_the_solutions_are_sorted_between_them():
    source = inspect.getsource(FieldWorkerThread._run_optimize)
    order = [
        source.index('raise RuntimeError("No usable optimization solution found.")'),
        source.index("self._clean_the_thin_layers_of_the_solutions("),
        source.index("all_solutions.sort("),
        source.index("self._field_of_the_best_solution("),
        source.index("self.signals.finished.emit("),
    ]
    assert order == sorted(order)
