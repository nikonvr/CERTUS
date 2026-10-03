"""The objective of the METAL BILAYER window is the error it says it is (audit v2, plan S3.2).

`certus/metal/certus_metal_bilayer_physics.py` holds what the window minimises: Air | metal | SiO2 | silicon seen from the front, where n and k of the metal are natural cubic splines of knots, the
SiO2 follows a Cauchy law (`n_inf + A / lambda**2`) and the thickness of both layers is searched (`global_objective_function`) or the metal's is fixed for the beam analysis
(`objective_function_fixed_eM`). The kernel under it (`calculate_reflectance_bilayer_vectorized`) is compared with the oracle in
`test_metal_bilayer_reflectance_kernel_matches_the_oracle.py`; what was never read is the objective around it, covered at 6.0 % by the headless tests, which look at the window and not at the number.

What is pinned here, against `tests/oracle/tmm_reference.py` and scipy's natural cubic spline:

    the value: mean square error of the oracle's reflectance + the smoothness penalty (1e-2 times the squared second differences of n and k), for the free and the fixed thickness
    the layout of x (thickness, SiO2 thickness, n_inf, A, n knots, k knots, internal knot positions) and the Cauchy law of the oxide
    that the substrate is the one given, or silicon when none is
    the guards: a wrong size, a negative thickness, knots that are too close, values that are not finite - infinity inside, the penalty of the search (1e12) outside
    the input validator, the spline-state validator, the bounds, the diagnostic penalty

The spline-state validator returns internal knots consistent with the full knot vector,
including after it repairs an invalid input.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from certus.metal.certus_metal_bilayer_physics import (
    _bilayer_reflectance_mse,
    _build_bilayer_bounds,
    _diagnostic_bilayer_penalty,
    _validate_bilayer_objective_inputs,
    _validate_bilayer_spline_state,
    global_objective_function,
    objective_function_fixed_eM,
)
from certus_physics import get_nk_si

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

WAVELENGTHS = np.linspace(400.0, 880.0, 49)
NUM_KNOTS = 5
INTERNAL_KNOTS = np.array([500.0, 640.0, 760.0])
KNOTS = np.concatenate(([400.0], INTERNAL_KNOTS, [880.0]))
N_KNOTS = np.array([1.0, 0.8, 0.7, 0.9, 1.1])
K_KNOTS = np.array([5.5, 5.0, 4.8, 5.2, 5.6])
THICKNESS_METAL = 25.0
THICKNESS_OXIDE = 300.0
N_INF = 1.43
A_CAUCHY = 3000.0
MIN_KNOT_DISTANCE = 10.0
SUBSTRATE = np.full(len(WAVELENGTHS), 3.9 - 0.02j)
R_TARGET = 0.55 + 0.1 * np.sin(WAVELENGTHS / 50.0)


def x_global(em=THICKNESS_METAL, el=THICKNESS_OXIDE, n_inf=N_INF, a=A_CAUCHY, n=N_KNOTS, k=K_KNOTS, internal=INTERNAL_KNOTS):
    return np.concatenate(([em, el, n_inf, a], n, k, internal))


def x_fixed(el=THICKNESS_OXIDE, n_inf=N_INF, a=A_CAUCHY, n=N_KNOTS, k=K_KNOTS, internal=INTERNAL_KNOTS):
    return np.concatenate(([el, n_inf, a], n, k, internal))


def nk_curves(n_knots=N_KNOTS, k_knots=K_KNOTS):
    n = np.clip(CubicSpline(KNOTS, n_knots, bc_type="natural")(WAVELENGTHS), 0.0, 10.0)
    k = np.clip(CubicSpline(KNOTS, k_knots, bc_type="natural")(WAVELENGTHS), 0.0, 10.0)
    return n, k


def smoothness_penalty(n, k):
    return 1e-2 * (np.sum(np.diff(n, n=2) ** 2) + np.sum(np.diff(k, n=2) ** 2))


def oracle_reflectance(em=THICKNESS_METAL, el=THICKNESS_OXIDE, n_inf=N_INF, a=A_CAUCHY, n_knots=N_KNOTS, k_knots=K_KNOTS, substrate=SUBSTRATE):
    n, k = nk_curves(n_knots, k_knots)
    oxide = n_inf + a / WAVELENGTHS**2
    return np.array(
        [oracle.rt_stack(float(wl), [complex(oxide[i], 0.0), complex(n[i], -k[i])], [el, em], 1.0 + 0.0j, complex(substrate[i]))[0] for i, wl in enumerate(WAVELENGTHS)]
    )


def reference_value(**options):
    n, k = nk_curves(options.get("n_knots", N_KNOTS), options.get("k_knots", K_KNOTS))
    return float(np.mean((oracle_reflectance(**options) - R_TARGET) ** 2) + smoothness_penalty(n, k))


def free(x, nsub=SUBSTRATE, min_distance=MIN_KNOT_DISTANCE):
    return global_objective_function(x, NUM_KNOTS, WAVELENGTHS, R_TARGET, min_distance, nsub)


def fixed(x, em=THICKNESS_METAL, nsub=SUBSTRATE, min_distance=MIN_KNOT_DISTANCE):
    return objective_function_fixed_eM(x, em, NUM_KNOTS, WAVELENGTHS, R_TARGET, min_distance, nsub)


# --- the value ---------------------------------------------------------------------------------------------------------------------------------


def test_the_value_is_the_mean_square_error_of_the_oracle_plus_the_smoothness_penalty():
    assert free(x_global()) == pytest.approx(reference_value(), rel=1e-9, abs=0.0)


@pytest.mark.parametrize(("em", "el"), [(5.0, 100.0), (60.0, 250.0), (12.0, 900.0), (0.0, 300.0), (25.0, 0.0)])
def test_the_value_follows_the_two_thicknesses(em, el):
    assert free(x_global(em=em, el=el)) == pytest.approx(reference_value(em=em, el=el), rel=1e-9, abs=0.0)


@pytest.mark.parametrize(("n_inf", "a"), [(1.42, 0.0), (1.44, 10000.0), (1.46, 2500.0)])
def test_the_oxide_follows_the_cauchy_law_it_is_given(n_inf, a):
    assert free(x_global(n_inf=n_inf, a=a)) == pytest.approx(reference_value(n_inf=n_inf, a=a), rel=1e-9, abs=0.0)


def test_the_penalty_grows_with_the_roughness_of_the_knots():
    rough_n = np.array([1.0, 2.2, 0.4, 1.9, 1.1])
    assert free(x_global(n=rough_n)) == pytest.approx(reference_value(n_knots=rough_n), rel=1e-9, abs=0.0)
    assert smoothness_penalty(*nk_curves(rough_n, K_KNOTS)) > 10.0 * smoothness_penalty(*nk_curves())


def test_the_fixed_thickness_value_is_the_free_value_at_that_thickness():
    assert fixed(x_fixed()) == pytest.approx(free(x_global()), rel=1e-12, abs=0.0)
    assert fixed(x_fixed(), em=50.0) == pytest.approx(reference_value(em=50.0), rel=1e-9, abs=0.0)
    assert fixed(x_fixed(), em=50.0) != fixed(x_fixed(), em=25.0)


def test_the_value_does_not_depend_on_the_order_of_the_internal_knots():
    assert free(x_global(internal=INTERNAL_KNOTS[::-1])) == pytest.approx(free(x_global()), rel=0.0, abs=1e-15)


def test_the_substrate_is_silicon_when_none_is_given():
    silicon = get_nk_si(WAVELENGTHS)
    assert free(x_global(), nsub=None) == pytest.approx(free(x_global(), nsub=silicon), rel=1e-12, abs=0.0)
    assert abs(free(x_global(), nsub=None) - free(x_global())) > 1e-4  # and the substrate given above is not silicon


# --- the guards -------------------------------------------------------------------------------------------------------------------------------


def test_a_vector_of_the_wrong_size_is_refused_inside_with_infinity_and_outside_with_the_penalty():
    too_long = np.append(x_global(), 1.0)
    too_short = x_global()[:-1]
    for x in (too_long, too_short):
        assert _bilayer_reflectance_mse(x, WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, SUBSTRATE) == np.inf
        assert free(x) == 1e12
    assert _bilayer_reflectance_mse(np.array([1.0, 2.0, 3.0]), WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, SUBSTRATE) == np.inf  # less than the four leading values
    assert _bilayer_reflectance_mse(np.array([1.0, 2.0]), WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, SUBSTRATE, eM_fixed=10.0) == np.inf


def test_a_negative_thickness_is_refused():
    assert free(x_global(em=-1.0)) == 1e12
    assert free(x_global(el=-1.0)) == 1e12
    assert fixed(x_fixed(el=-1.0)) == 1e12
    assert fixed(x_fixed(), em=-5.0) == 1e12


def test_internal_knots_closer_than_the_minimum_distance_are_refused():
    assert free(x_global(internal=np.array([500.0, 506.0, 760.0]))) == 1e12
    assert free(x_global(internal=np.array([500.0, 511.0, 760.0]))) < 1e12
    assert free(x_global(internal=np.array([404.0, 640.0, 760.0]))) == 1e12  # too close to the first end
    assert free(x_global(internal=np.array([500.0, 640.0, 876.0]))) == 1e12  # and to the last


@pytest.mark.parametrize("position", [0, 1, 2, 3, 4, 8, 11])
def test_a_value_that_is_not_finite_is_refused_by_the_free_objective(position):
    x = x_global()
    x[position] = np.nan
    assert free(x) == 1e12


@pytest.mark.parametrize("position", [0, 1, 2, 3, 7, 10])
def test_a_value_that_is_not_finite_is_refused_by_the_fixed_thickness_objective(position):
    x = x_fixed()
    x[position] = np.nan
    assert fixed(x) == 1e12


def test_a_non_finite_oxide_is_refused_inside():
    x = x_global(a=np.inf)
    assert _bilayer_reflectance_mse(x, WAVELENGTHS, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, SUBSTRATE) == np.inf


def test_a_wavelength_interval_that_is_empty_is_refused():
    flat = np.full(len(WAVELENGTHS), 600.0)
    assert _bilayer_reflectance_mse(x_global(), flat, R_TARGET, NUM_KNOTS, MIN_KNOT_DISTANCE, SUBSTRATE) == np.inf


# --- the validator of the inputs ---------------------------------------------------------------------------------------------------------------


def context_of(**changes):
    arguments = {"x": x_global(), "num_knots": NUM_KNOTS, "l_array": WAVELENGTHS, "r_tgt_array": R_TARGET, "min_knot_dist": MIN_KNOT_DISTANCE, "eM_fixed": None}
    arguments.update(changes)
    return _validate_bilayer_objective_inputs(**arguments)


def test_valid_inputs_give_a_context_of_their_sizes():
    context = context_of()
    assert context["x_dim"] == len(x_global())
    assert context["num_knots"] == NUM_KNOTS
    assert context["lambda_dim"] == context["target_dim"] == len(WAVELENGTHS)
    assert context["min_knot_dist"] == MIN_KNOT_DISTANCE
    assert "eM_fixed" not in context
    assert context_of(eM_fixed=12.0)["eM_fixed"] == 12.0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"x": np.ones((2, 3))}, "1D"),
        ({"x": np.array([1.0, np.nan, 3.0])}, "Non-finite optimization variables at indices=[1]"),
        ({"num_knots": 1}, "num_knots must be >= 2"),
        ({"l_array": np.ones((2, 3))}, "must be 1D"),
        ({"l_array": np.array([]), "r_tgt_array": np.array([])}, "Empty target arrays"),
        ({"r_tgt_array": R_TARGET[:-1]}, "size mismatch"),
        ({"r_tgt_array": np.append(R_TARGET[:-1], np.nan)}, "non-finite"),
        ({"l_array": np.append(WAVELENGTHS[:-1], np.inf)}, "non-finite"),
        ({"min_knot_dist": np.nan}, "Invalid min_knot_dist"),
        ({"min_knot_dist": -1.0}, "Invalid min_knot_dist"),
        ({"eM_fixed": np.inf}, "Invalid fixed eM"),
    ],
)
def test_inputs_that_cannot_be_an_objective_are_refused_with_the_reason(changes, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        context_of(**changes)


# --- the validator of the spline state ---------------------------------------------------------------------------------------------------------


def test_a_good_spline_state_keeps_its_knots():
    knots, internal = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, INTERNAL_KNOTS, 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_array_equal(knots, KNOTS)
    np.testing.assert_array_equal(internal, INTERNAL_KNOTS)


def test_internal_knots_given_in_disorder_or_twice_are_repaired():
    knots, internal = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, np.array([760.0, 500.0, 640.0, 640.0]), 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_array_equal(internal, INTERNAL_KNOTS)
    np.testing.assert_array_equal(knots, KNOTS)


def test_the_wrong_number_of_internal_knots_gives_equally_spaced_knots():
    knots, _internal = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, np.array([500.0]), 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_allclose(knots, np.linspace(400.0, 880.0, NUM_KNOTS))


@pytest.mark.parametrize("given", [np.array([500.0]), np.array([400.0, 640.0, 760.0])], ids=["wrong_count", "knot_on_an_end"])
def test_the_internal_knots_returned_after_a_repair_are_those_of_the_knots_returned(given):
    knots, internal = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, given, 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_allclose(internal, knots[1:-1])


def test_internal_knots_that_are_not_numbers_are_dropped_before_the_count():
    knots, internal = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, np.array([500.0, np.nan, 640.0, 760.0]), 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_array_equal(internal, INTERNAL_KNOTS)
    assert len(knots) == NUM_KNOTS


def test_internal_knots_on_an_end_fall_back_on_equal_spacing_of_all_the_knots():
    knots, _ = _validate_bilayer_spline_state(N_KNOTS, K_KNOTS, np.array([400.0, 640.0, 760.0]), 400.0, 880.0, NUM_KNOTS)
    np.testing.assert_allclose(knots, np.linspace(400.0, 880.0, NUM_KNOTS))


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"expected_knot_count": 1}, "expected_knot_count must be >= 2"),
        ({"min_l": 500.0, "max_l": 400.0}, "Invalid wavelength interval"),
        ({"min_l": np.nan}, "Invalid wavelength interval"),
        ({"n_knots": N_KNOTS[:-1]}, "Invalid spline coefficient state"),
    ],
)
def test_a_spline_state_that_cannot_be_repaired_is_refused(arguments, message):
    defaults = {"n_knots": N_KNOTS, "k_knots": K_KNOTS, "lambda_internes": INTERNAL_KNOTS, "min_l": 400.0, "max_l": 880.0, "expected_knot_count": NUM_KNOTS}
    defaults.update(arguments)
    with pytest.raises(ValueError, match=re.escape(message)):
        _validate_bilayer_spline_state(**defaults)


# --- the bounds and the diagnostic penalty --------------------------------------------------------------------------------------------------------


def test_the_bounds_hold_the_thickness_of_the_metal_the_oxide_its_law_and_the_knots():
    params = {"eM_min": 5.0, "eM_max": 60.0, "num_knots": 4, "eL_nominal": 300.0, "eL_variation": 25.0}
    bounds = _build_bilayer_bounds(params, WAVELENGTHS)
    assert bounds == [(5.0, 60.0), (275.0, 325.0), (1.42, 1.44), (0, 10000)] + [(0, 10)] * 8 + [(400.0, 880.0)] * 2
    assert _build_bilayer_bounds(params, WAVELENGTHS, include_eM=False) == bounds[1:]


def test_the_oxide_thickness_cannot_be_negative_and_defaults_are_900_plus_or_minus_20():
    assert _build_bilayer_bounds({"eM_min": 1.0, "eM_max": 2.0, "num_knots": 2, "eL_nominal": 10.0, "eL_variation": 50.0})[1] == (0, 60.0)
    assert _build_bilayer_bounds({"eM_min": 1.0, "eM_max": 2.0, "num_knots": 2})[1] == (880, 920)


def test_without_a_wavelength_grid_the_internal_knots_are_bounded_by_the_range_of_the_window():
    bounds = _build_bilayer_bounds({"eM_min": 1.0, "eM_max": 2.0, "num_knots": 4})
    assert bounds[-2:] == [(350.0, 880.0)] * 2


def test_the_bounds_follow_the_limits_given_for_the_oxide_and_for_n_and_k():
    params = {"eM_min": 1.0, "eM_max": 2.0, "num_knots": 2, "n_infini_bounds": (1.3, 1.5), "A_diel_bounds": (1.0, 2.0), "nk_min": 0.1, "nk_max": 6.0}
    assert _build_bilayer_bounds(params, WAVELENGTHS)[2:] == [(1.3, 1.5), (1.0, 2.0)] + [(0.1, 6.0)] * 4


def test_the_diagnostic_penalty_is_the_penalty_of_the_search_whatever_it_is_given():
    assert _diagnostic_bilayer_penalty("a reason") == 1e12
    assert _diagnostic_bilayer_penalty("a reason", x_global()) == 1e12
    assert _diagnostic_bilayer_penalty("a reason", None, context={"anything": 1}) == 1e12
    assert _diagnostic_bilayer_penalty("a reason", np.array(["not a number"])) == 1e12
