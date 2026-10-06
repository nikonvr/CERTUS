"""The objective of the METAL SINGLE window is the error it says it is (audit v2, plan S3.2).

`certus/metal/certus_metal_single_physics.py` holds what the window minimises: a metal film (n and k as natural cubic splines of knots, a thickness) on a transparent substrate, compared
with a measured reflectance, and optionally with a transmittance and a reflectance seen from the back (`global_objective_function`), the same with the thickness fixed for the beam analysis
(`objective_function_fixed_eM`) and the analytic gradient of that one (`gradient_function_fixed_eM`). It was covered at 7.6 % by the headless tests, which look at the window and not at the
number; the kernel under it (`calculate_RTRback_incoherent_vectorized`) is compared with the oracle in `tests/oracle/test_normal_plate_absorbing_substrate.py`.

What is pinned here, against `tests/oracle/tmm_reference.py` (the film on the front, then on the back, of an incoherent plate: R, T, Rback) and scipy's natural cubic spline:

    the three curves of the oracle are the ones the objective compares (a metal film on glass)
    the reflectance-only value: mean square error + the smoothness penalty (1e-2 times the sum of the squared second differences of n and k)
    the three-curve value: the mean of the three mean square errors, a curve with nothing finite left out of the mean, the penalty when nothing is left
    the guards: a negative thickness, internal knots that are too close or in the wrong order, non-finite values
    the fixed-thickness objective: the same value, with the knots only in x and the internal knot positions given aside
    the analytic gradient of the beam analysis is the gradient of the whole objective, smoothness penalty included, at smooth and at rough knots (it left the penalty out
    until 2026-10-06, a gap of 1.7e-3 and 1.9e-2: D76)
    the bounds and the substrate label
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from certus.core.certus_substrate_db import substrate_sellmeier_id
from certus.metal.certus_metal_defaults import DEFAULT_NK_MAX, DEFAULT_NK_MIN
from certus.metal.certus_metal_single_physics import (
    _build_single_bounds,
    _resolve_single_substrate_id,
    _single_RTRback_mse,
    global_objective_function,
    gradient_function_fixed_eM,
    objective_function_fixed_eM,
)
from certus_physics import calculate_RTRback_incoherent_vectorized

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

WAVELENGTHS = np.linspace(400.0, 1000.0, 61)
NUM_KNOTS = 5
INTERNAL_KNOTS = np.array([550.0, 700.0, 850.0])
KNOTS = np.concatenate(([400.0], INTERNAL_KNOTS, [1000.0]))
N_KNOTS = np.array([1.2, 1.0, 0.9, 1.1, 1.3])
K_KNOTS = np.array([2.5, 3.0, 3.5, 3.2, 2.8])
THICKNESS = 30.0
SUBSTRATE_INDEX = 1.52
MIN_KNOT_DISTANCE = 10.0
R_TARGET = 0.6 + 0.05 * np.sin(WAVELENGTHS / 80.0)
T_TARGET = 0.1 + 0.02 * np.cos(WAVELENGTHS / 60.0)
RBACK_TARGET = 0.5 + 0.04 * np.sin(WAVELENGTHS / 70.0)
PRECOMPUTED = {"min_lambda": 400.0, "max_lambda": 1000.0, "nSub_complex_array": np.full(len(WAVELENGTHS), SUBSTRATE_INDEX + 0.0j)}


def global_x(thickness=THICKNESS, n=N_KNOTS, k=K_KNOTS, internal=INTERNAL_KNOTS):
    return np.concatenate(([thickness], n, k, internal))


def nk_curves(n_knots=N_KNOTS, k_knots=K_KNOTS):
    """n and k at the wavelengths: natural cubic splines of the knots, kept within [0, 10] (what `get_nk_from_spline` does)."""
    n = np.clip(CubicSpline(KNOTS, n_knots, bc_type="natural")(WAVELENGTHS), 0.0, 10.0)
    k = np.clip(CubicSpline(KNOTS, k_knots, bc_type="natural")(WAVELENGTHS), 0.0, 10.0)
    return n, k


def smoothness_penalty(n, k):
    return 1e-2 * (np.sum(np.diff(n, n=2) ** 2) + np.sum(np.diff(k, n=2) ** 2))


def oracle_curves(thickness, n, k):
    """R and T of film | glass plate | air, and Rback (the film on the back of the plate, seen from the bare side), at normal incidence, by the oracle."""
    r = np.zeros(len(WAVELENGTHS))
    t = np.zeros(len(WAVELENGTHS))
    r_back = np.zeros(len(WAVELENGTHS))
    for i, wavelength in enumerate(WAVELENGTHS):
        film = [complex(n[i], -k[i])]
        r[i], t[i] = oracle.rt_plate_incoherent(wavelength, film, [thickness], [], [], complex(SUBSTRATE_INDEX, 0.0), 0.0, True, 1.0e6)
        r_back[i] = oracle.rt_plate_incoherent(wavelength, [], [], film, [thickness], complex(SUBSTRATE_INDEX, 0.0), 0.0, True, 1.0e6)[0]
    return r, t, r_back


def objective(x, t_target=None, rback_target=None, r_target=R_TARGET, min_knot_distance=MIN_KNOT_DISTANCE):
    return global_objective_function(x, NUM_KNOTS, WAVELENGTHS, r_target, t_target, rback_target, min_knot_distance, PRECOMPUTED["nSub_complex_array"], PRECOMPUTED)


# --- the curves the objective compares -------------------------------------------------------------------------------------------------------


def test_the_curves_of_the_kernel_are_the_oracles_for_a_metal_film_on_glass():
    n, k = nk_curves()
    r, t, r_back = calculate_RTRback_incoherent_vectorized(
        np.array([THICKNESS]), (n - 1j * k).reshape(-1, 1), PRECOMPUTED["nSub_complex_array"], WAVELENGTHS
    )
    expected = oracle_curves(THICKNESS, n, k)
    np.testing.assert_allclose(r, expected[0], rtol=0.0, atol=1e-11)
    np.testing.assert_allclose(t, expected[1], rtol=0.0, atol=1e-11)
    np.testing.assert_allclose(r_back, expected[2], rtol=0.0, atol=1e-11)


# --- the value ---------------------------------------------------------------------------------------------------------------------------------


def test_the_reflectance_only_value_is_the_mean_square_error_plus_the_smoothness_penalty():
    n, k = nk_curves()
    r, _t, _r_back = oracle_curves(THICKNESS, n, k)
    expected = np.mean((r - R_TARGET) ** 2) + smoothness_penalty(n, k)
    assert objective(global_x()) == pytest.approx(expected, rel=1e-9, abs=0.0)


def test_the_smoothness_penalty_grows_with_the_roughness_of_the_knots():
    rough_n = np.array([1.2, 2.4, 0.6, 2.2, 1.0])
    n, k = nk_curves(rough_n, K_KNOTS)
    r, _t, _r_back = oracle_curves(THICKNESS, n, k)
    expected = np.mean((r - R_TARGET) ** 2) + smoothness_penalty(n, k)
    assert objective(global_x(n=rough_n)) == pytest.approx(expected, rel=1e-9, abs=0.0)
    assert smoothness_penalty(n, k) > 10.0 * smoothness_penalty(*nk_curves())


def test_the_three_curve_value_is_the_mean_of_the_three_mean_square_errors_plus_the_penalty():
    n, k = nk_curves()
    r, t, r_back = oracle_curves(THICKNESS, n, k)
    errors = [np.mean((r - R_TARGET) ** 2), np.mean((t - T_TARGET) ** 2), np.mean((r_back - RBACK_TARGET) ** 2)]
    expected = sum(errors) / 3.0 + smoothness_penalty(n, k)
    assert objective(global_x(), T_TARGET, RBACK_TARGET) == pytest.approx(expected, rel=1e-9, abs=0.0)


def test_a_point_without_a_target_is_left_out_of_the_mean_of_its_curve():
    n, k = nk_curves()
    r, t, r_back = oracle_curves(THICKNESS, n, k)
    t_holes = T_TARGET.copy()
    t_holes[[3, 10, 40]] = np.nan
    finite = np.isfinite(t_holes)
    errors = [np.mean((r - R_TARGET) ** 2), np.mean((t[finite] - t_holes[finite]) ** 2), np.mean((r_back - RBACK_TARGET) ** 2)]
    assert objective(global_x(), t_holes, RBACK_TARGET) == pytest.approx(sum(errors) / 3.0 + smoothness_penalty(n, k), rel=1e-9, abs=0.0)


@pytest.mark.filterwarnings("ignore:Mean of empty slice:RuntimeWarning")
def test_a_curve_with_no_finite_target_is_left_out_of_the_mean_of_the_curves():
    n, k = nk_curves()
    r, _t, r_back = oracle_curves(THICKNESS, n, k)
    all_missing = np.full(len(WAVELENGTHS), np.nan)
    expected = (np.mean((r - R_TARGET) ** 2) + np.mean((r_back - RBACK_TARGET) ** 2)) / 2.0 + smoothness_penalty(n, k)
    assert objective(global_x(), all_missing, RBACK_TARGET) == pytest.approx(expected, rel=1e-9, abs=0.0)


@pytest.mark.filterwarnings("ignore:Mean of empty slice:RuntimeWarning")
def test_when_no_curve_has_a_finite_error_the_value_is_the_penalty_of_the_search():
    all_missing = np.full(len(WAVELENGTHS), np.nan)
    assert objective(global_x(), all_missing, all_missing, r_target=all_missing) == 1e12


def test_the_value_does_not_depend_on_the_order_the_internal_knots_are_given_in():
    shuffled = global_x(internal=INTERNAL_KNOTS[::-1])
    assert objective(shuffled) == pytest.approx(objective(global_x()), rel=0.0, abs=1e-15)


# --- the guards -------------------------------------------------------------------------------------------------------------------------------


def test_a_negative_thickness_is_refused_with_the_penalty_of_the_search():
    assert objective(global_x(thickness=-1.0)) == 1e12
    assert objective(global_x(thickness=0.0)) < 1e12  # zero is a bare substrate, not a violation


def test_internal_knots_closer_than_the_minimum_distance_are_refused():
    assert objective(global_x(internal=np.array([550.0, 556.0, 850.0]))) == 1e12
    assert objective(global_x(internal=np.array([550.0, 561.0, 850.0]))) < 1e12


def test_a_knot_as_close_as_the_minimum_to_the_end_is_refused_too():
    assert objective(global_x(internal=np.array([405.0, 700.0, 850.0]))) == 1e12
    assert objective(global_x(internal=np.array([550.0, 700.0, 995.0]))) == 1e12


def test_a_distance_of_zero_lets_close_knots_through_but_the_fixed_thickness_objective_still_refuses_equal_ones():
    close = np.array([550.0, 550.000001, 850.0])
    assert objective(global_x(internal=close), min_knot_distance=0.0) < 1e12
    x_knots_only = np.concatenate((N_KNOTS, K_KNOTS))
    value = objective_function_fixed_eM(x_knots_only, THICKNESS, NUM_KNOTS, WAVELENGTHS, R_TARGET, 0.0, PRECOMPUTED, lambda_internes_fixed=close)
    assert value == 1e12  # the beam analysis asks 1e-5 nm at least between knots


# --- the objective with the thickness fixed --------------------------------------------------------------------------------------------------


def fixed_thickness(x_knots, internal=INTERNAL_KNOTS, precomputed=PRECOMPUTED):
    return objective_function_fixed_eM(x_knots, THICKNESS, NUM_KNOTS, WAVELENGTHS, R_TARGET, MIN_KNOT_DISTANCE, precomputed, lambda_internes_fixed=internal)


def test_the_fixed_thickness_value_is_the_reflectance_only_value_with_the_knots_alone_in_x():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    assert fixed_thickness(x_knots) == pytest.approx(objective(global_x()), rel=1e-12, abs=0.0)


def test_the_fixed_thickness_value_reads_the_thickness_it_is_given():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    other = objective_function_fixed_eM(x_knots, 60.0, NUM_KNOTS, WAVELENGTHS, R_TARGET, MIN_KNOT_DISTANCE, PRECOMPUTED, lambda_internes_fixed=INTERNAL_KNOTS)
    assert other == pytest.approx(objective(global_x(thickness=60.0)), rel=1e-12, abs=0.0)
    assert other != fixed_thickness(x_knots)


def test_the_fixed_thickness_objective_refuses_non_finite_knot_values_with_infinity():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    x_knots[2] = np.nan
    assert fixed_thickness(x_knots) == np.inf


def test_the_fixed_thickness_objective_can_work_in_a_buffer_that_already_holds_the_internal_knots():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    buffer = np.concatenate((np.zeros(len(x_knots)), INTERNAL_KNOTS))
    with_buffer = dict(PRECOMPUTED, x_full_buffer=buffer)
    assert fixed_thickness(x_knots, precomputed=with_buffer) == pytest.approx(fixed_thickness(x_knots), rel=1e-12, abs=0.0)
    np.testing.assert_array_equal(buffer[: len(x_knots)], x_knots)  # the knots were written into it


def test_the_error_function_takes_the_thickness_from_x_unless_it_is_fixed():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS, INTERNAL_KNOTS))
    fixed = _single_RTRback_mse(x_knots, WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, PRECOMPUTED["nSub_complex_array"], PRECOMPUTED, eM_fixed=THICKNESS)
    free = _single_RTRback_mse(global_x(), WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, PRECOMPUTED["nSub_complex_array"], PRECOMPUTED)
    assert fixed == pytest.approx(free, rel=1e-12, abs=0.0)


# --- the analytic gradient of the beam analysis -----------------------------------------------------------------------------------------------


def central_differences(function, x, relative_step=1e-6):
    gradient = np.zeros_like(x)
    for i in range(len(x)):
        step = relative_step * max(1.0, abs(x[i]))
        up, down = x.copy(), x.copy()
        up[i] += step
        down[i] -= step
        gradient[i] = (function(up) - function(down)) / (2.0 * step)
    return gradient


def data_term(x_knots):
    """The mean square error of the reflectance alone, by the oracle: what the gradient claims to be the gradient of."""
    n, k = nk_curves(x_knots[:NUM_KNOTS], x_knots[NUM_KNOTS:])
    r, _t, _rb = oracle_curves(THICKNESS, n, k)
    return float(np.mean((r - R_TARGET) ** 2))


def analytic_gradient(x_knots):
    return gradient_function_fixed_eM(x_knots, THICKNESS, NUM_KNOTS, WAVELENGTHS, R_TARGET, MIN_KNOT_DISTANCE, PRECOMPUTED, lambda_internes_fixed=INTERNAL_KNOTS)


def test_the_analytic_gradient_is_the_gradient_of_the_whole_objective_at_smooth_knots():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    numeric = central_differences(fixed_thickness, x_knots)
    assert np.max(np.abs(numeric)) > 1e-3
    np.testing.assert_allclose(analytic_gradient(x_knots), numeric, rtol=0.0, atol=1e-6 * np.max(np.abs(numeric)))


def test_the_analytic_gradient_is_the_gradient_of_the_whole_objective_at_rough_knots():
    # D76: the gradient left out the derivative of the smoothness penalty that the objective adds (relative gap 1.9e-2
    # at these rough knots, 1.7e-3 at smooth ones). Decided by the owner on 2026-10-06: add it.
    rough_n = np.array([1.2, 2.4, 0.6, 2.2, 1.0])
    x_knots = np.concatenate((rough_n, K_KNOTS))
    numeric = central_differences(fixed_thickness, x_knots)
    np.testing.assert_allclose(analytic_gradient(x_knots), numeric, rtol=0.0, atol=5e-3 * np.max(np.abs(numeric)))


def test_the_analytic_gradient_has_one_component_per_knot_value():
    assert analytic_gradient(np.concatenate((N_KNOTS, K_KNOTS))).shape == (2 * NUM_KNOTS,)


def test_the_analytic_gradient_is_zero_where_the_search_cannot_go():
    x_knots = np.concatenate((N_KNOTS, K_KNOTS))
    nan_knots = x_knots.copy()
    nan_knots[1] = np.nan
    np.testing.assert_array_equal(analytic_gradient(nan_knots), np.zeros(2 * NUM_KNOTS))
    close = gradient_function_fixed_eM(
        x_knots, THICKNESS, NUM_KNOTS, WAVELENGTHS, R_TARGET, MIN_KNOT_DISTANCE, PRECOMPUTED, lambda_internes_fixed=np.array([550.0, 553.0, 850.0])
    )
    np.testing.assert_array_equal(close, np.zeros(2 * NUM_KNOTS))


# --- the bounds and the substrate label ------------------------------------------------------------------------------------------------------


def test_the_bounds_hold_the_thickness_the_values_of_the_knots_and_the_internal_positions():
    params = {"eM_min": 5.0, "eM_max": 80.0, "num_knots": 4}
    bounds = _build_single_bounds(params, WAVELENGTHS)
    assert bounds == [(5.0, 80.0)] + [(DEFAULT_NK_MIN, DEFAULT_NK_MAX)] * 8 + [(400.0, 1000.0)] * 2
    assert _build_single_bounds(params, WAVELENGTHS, include_eM=False) == bounds[1:]


def test_the_bounds_follow_the_limits_given_for_n_and_k():
    params = {"eM_min": 5.0, "eM_max": 80.0, "num_knots": 3, "nk_min": 0.1, "nk_max": 6.0}
    assert _build_single_bounds(params, WAVELENGTHS)[1:7] == [(0.1, 6.0)] * 6


def test_without_a_wavelength_grid_only_the_values_of_the_knots_are_bounded():
    # the beam analysis keeps the internal knots where the global search put them and asks for the bounds of n and k alone (`certus_metal_single_app.py`)
    params = {"eM_min": 5.0, "eM_max": 80.0, "num_knots": 4}
    assert _build_single_bounds(params, l_array=None, include_eM=False) == [(DEFAULT_NK_MIN, DEFAULT_NK_MAX)] * 8


def test_two_knots_have_no_internal_position_to_bound():
    assert _build_single_bounds({"eM_min": 5.0, "eM_max": 80.0, "num_knots": 2}, WAVELENGTHS) == [(5.0, 80.0)] + [(DEFAULT_NK_MIN, DEFAULT_NK_MAX)] * 4


def test_a_known_substrate_label_gives_its_catalogue_number():
    assert _resolve_single_substrate_id("N-BK7") == 1
    assert _resolve_single_substrate_id("fused silica") == 0
    assert _resolve_single_substrate_id("Sapphire") == 3


def test_an_unknown_substrate_label_falls_back_on_bk7():
    assert _resolve_single_substrate_id("nothing of the kind") == substrate_sellmeier_id("BK7") == 1
    assert _resolve_single_substrate_id("") == 1
