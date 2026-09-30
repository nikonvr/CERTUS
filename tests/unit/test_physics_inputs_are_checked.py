"""The kernels are given what they can compute: a wrong input is an error, never a wave or a zero.

Measured on 2026-09-30, before `certus_inputs.py`:
- any polarization string but `s` was computed as `p`: `'TE'` (which is s), `'S '`, `''`, `'Avg'`;
- an angle of 95 degrees was accepted (`R = 1`), a NaN angle ended in a `SystemError`;
- a non-finite thickness, index, wavelength or substrate gave `(R, T) = (0, 0)`;
- DESIGN's target table offered `Avg` ("unpolarized average") and computed p.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

WLS = np.array([500.0, 600.0, 700.0])
LAYERS = np.full((3, 2), complex(1.9, 0.0))
THICKNESS = np.array([100.0, 120.0])
SUBSTRATE = np.full(3, complex(1.52, 0.0))


# =============================================================================
# The polarization
# =============================================================================


@pytest.mark.parametrize("name", ["s", "S", " s ", "TE", "te"])
def test_the_names_of_the_s_wave_are_s(name) -> None:
    from certus.physics.certus_inputs import is_s_polarization

    assert is_s_polarization(name) is True


@pytest.mark.parametrize("name", ["p", "P", " p ", "TM", "tm"])
def test_the_names_of_the_p_wave_are_p(name) -> None:
    from certus.physics.certus_inputs import is_s_polarization

    assert is_s_polarization(name) is False


@pytest.mark.parametrize("name", ["", "Avg", "avg", "unpolarized", "x", "sp", None, 5])
def test_anything_else_is_refused_and_not_computed_as_p(name) -> None:
    from certus.physics.certus_inputs import is_s_polarization

    with pytest.raises(ValueError, match="polarization"):
        is_s_polarization(name)


@pytest.mark.parametrize("name", ["", "Avg", "TE?"])
def test_the_spectrum_wrappers_refuse_an_unknown_polarization(name) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized

    with pytest.raises(ValueError, match="polarization"):
        calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 30.0, name)
    with pytest.raises(ValueError, match="polarization"):
        calc_spectrum_oblique_backside_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 30.0, name)


def test_te_is_s_in_the_spectrum() -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    te = calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 40.0, "TE")
    s = calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 40.0, "s")
    p = calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 40.0, "p")

    assert np.array_equal(te[0], s[0])
    assert not np.allclose(te[0], p[0])


# =============================================================================
# The angle
# =============================================================================


@pytest.mark.parametrize("angle", [0.0, 45, -30.0, 90.0, -90.0, np.float32(20.0)])
def test_an_angle_between_minus_90_and_90_is_accepted(angle) -> None:
    from certus.physics.certus_inputs import check_incidence_angle

    assert check_incidence_angle(angle) == float(angle)


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), -float("inf"), 95.0, -95.0, 180.0, "abc", None])
def test_no_other_angle_is_one(angle) -> None:
    from certus.physics.certus_inputs import check_incidence_angle

    with pytest.raises(ValueError, match="angle"):
        check_incidence_angle(angle)


@pytest.mark.parametrize("angle", [float("nan"), 95.0])
def test_every_oblique_entry_point_refuses_a_bad_angle(angle) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized
    from certus.physics.gradient_oblique import (
        compute_oblique_backside_bundle_analytic,
        compute_oblique_gradient_contrib_analytic,
        compute_oblique_rt_and_grads_analytic,
        compute_oblique_rt_pair_and_grads_analytic,
    )

    var = np.array([0], dtype=np.int64)
    calls = [
        lambda: calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, angle, "s"),
        lambda: calc_spectrum_oblique_backside_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, angle, "s"),
        lambda: compute_oblique_gradient_contrib_analytic(
            THICKNESS, LAYERS, SUBSTRATE, WLS, np.full(3, 0.5), np.ones(3), angle, True, True, var
        ),
        lambda: compute_oblique_rt_and_grads_analytic(THICKNESS, LAYERS, SUBSTRATE, WLS, var, angle, True, False),
        lambda: compute_oblique_rt_pair_and_grads_analytic(THICKNESS, LAYERS, SUBSTRATE, WLS, var, angle, True),
        lambda: compute_oblique_backside_bundle_analytic(THICKNESS, LAYERS, SUBSTRATE, WLS, var, angle, True),
    ]
    for call in calls:
        with pytest.raises(ValueError, match="angle"):
            call()


def test_a_valid_angle_still_computes_as_before() -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    r, t = calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, SUBSTRATE, 89.9, "p")

    assert np.all(np.isfinite(r)) and np.all(np.isfinite(t))


# =============================================================================
# Non-finite values
# =============================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
@pytest.mark.parametrize("which", ["wls", "thickness", "substrate"])
def test_the_spectrum_wrappers_refuse_a_non_finite_input(which, bad) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized

    wls, thickness, substrate = WLS.copy(), THICKNESS.copy(), SUBSTRATE.copy()
    {"wls": wls, "thickness": thickness, "substrate": substrate}[which][0] = bad

    with pytest.raises(ValueError, match="finite"):
        calc_spectrum_oblique_vectorized(wls, LAYERS, thickness, substrate, 30.0, "s")
    with pytest.raises(ValueError, match="finite"):
        calc_spectrum_oblique_backside_vectorized(wls, LAYERS, thickness, substrate, 30.0, "p")


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
@pytest.mark.parametrize("which", ["wls", "thickness", "index", "substrate"])
def test_the_normal_incidence_entry_refuses_a_non_finite_input_instead_of_answering_zero(which, bad) -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    wls, thickness, index, substrate = WLS.copy(), THICKNESS.copy(), LAYERS.copy(), SUBSTRATE.copy()
    target = {"wls": wls, "thickness": thickness, "index": index, "substrate": substrate}[which]
    target.reshape(-1)[0] = bad

    with pytest.raises(ValueError, match="finite"):
        calculate_RT_vectorized_real(thickness, index, substrate, wls)


def test_a_layer_that_is_opaque_beyond_overflow_is_refused_instead_of_answering_zero() -> None:
    # A metal of k = 7 thicker than 10 um made cos/sin of the phase overflow: (R, T) = (0, 0).
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    metal = np.full((3, 1), complex(0.15, -7.0))
    substrate = np.full(3, complex(1.52, 0.0))

    r_ok, _ = calculate_RT_vectorized_real(np.array([3000.0]), metal, substrate, WLS)
    assert np.all(r_ok > 0.5)  # a mirror
    with pytest.raises(ValueError, match="absorbs too much"):
        calculate_RT_vectorized_real(np.array([20000.0]), metal, substrate, WLS)


def test_a_thin_absorbing_layer_is_not_mistaken_for_an_opaque_one() -> None:
    from certus.physics.certus_inputs import require_layers_below_overflow

    assert require_layers_below_overflow(np.array([50.0]), np.full((3, 1), complex(2.0, -0.1)), WLS) is None


# =============================================================================
# The objective functions receive the optimizer's trial vectors
# =============================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_design_returns_the_penalty_for_a_trial_vector_that_is_not_finite(bad) -> None:
    from certus.core.certus_design_core import _design_gradient_func_pglobal_common, _design_objective_wrapper_common

    app = SimpleNamespace(_var_idx=np.arange(3, dtype=np.int64))
    x = np.array([100.0, bad, 120.0])

    assert _design_objective_wrapper_common(app, x) == 1e30
    cost, gradient = _design_gradient_func_pglobal_common(app, x)
    assert cost == 1e30
    assert np.array_equal(gradient, np.zeros(3))


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_the_design_engine_does_the_same(bad) -> None:
    from certus.workers.certus_design_engine import DesignPhysicsBridge

    bridge = DesignPhysicsBridge(
        var_idx=np.arange(3, dtype=np.int64),
        all_variable=True,
        ep0=np.zeros(3),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0),
        n_back_T=np.zeros((3, 0), dtype=np.complex128),
        n_layers_T=np.zeros((3, 3), dtype=np.complex128),
        n_sub=SUBSTRATE,
        wls=WLS,
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[],
    )
    x = np.array([100.0, bad, 120.0])

    assert bridge.objective(x) == 1e30
    assert bridge.gradient(x)[0] == 1e30
