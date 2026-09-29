"""The oblique plate reads an absorbing substrate: its admittance for what enters it, Beer-Lambert for the way through.

The kernels that build an incoherent plate with a back side (`calc_spectrum_full_oblique_exact`, the
backside bundle, and the two places of DESIGN that combine `Rf`, `Tf`, `Rf'`, `Rb'`, `Tb`) read the real
part of the substrate index and dropped its absorption: under a layer of 2.3 x 100 nm an index of
1.7 - 1.11i gave R off by 0.22 at 30 degrees, and a plate of glass with `k = 4.4e-6` (1 cm-1) transmitted
as much as one without loss. The substrate is now a plate of thickness D (`certus_substrate_absorption`,
1 mm unless told): the front stack is read into the COMPLEX substrate, the interfaces seen from inside keep
its real part, and each pass loses `tau = exp(-4 pi k D / (lambda cos theta))`.

Two oracles, and they do not share their assumptions. `rt_plate_incoherent` writes the model above with
`rt_stack_oblique` for every coherent piece: it checks the kernels to 1e-12. `rt_plate_coherent_mean` is the
exact coherent TMM of the whole plate, averaged over one fringe: it checks the model itself.
"""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import numpy as np
import pytest
from tmm_reference import rt_plate_coherent_mean, rt_plate_incoherent

WLS = np.array([480.0, 640.0, 900.0])
KS = [0.0, 1e-7, 4.4e-6, 1e-4, 1e-2, 1.0]
THICKNESS = 1.0e6


def _stacks(n_front: int, n_back: int, seed: int):
    rng = np.random.default_rng(seed)
    front = rng.uniform(1.3, 2.4, (len(WLS), n_front)).astype(np.complex128)
    back = rng.uniform(1.3, 2.4, (len(WLS), n_back)).astype(np.complex128)
    return front, rng.uniform(40.0, 180.0, n_front), back, rng.uniform(40.0, 180.0, n_back)


def _substrate(k: float) -> np.ndarray:
    return np.array([complex(1.52 + 0.02 * i, -k) for i in range(len(WLS))])


# =============================================================================
# The kernels against the model, written independently
# =============================================================================


@pytest.mark.parametrize("n_back", [0, 2])
@pytest.mark.parametrize("n_front", [0, 3])
@pytest.mark.parametrize("is_s", [True, False])
@pytest.mark.parametrize("angle", [0.0, 25.0, 55.0, 75.0])
@pytest.mark.parametrize("k", KS)
def test_the_plate_spectrum_matches_the_model(k, angle, is_s, n_front, n_back) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact

    front, d_front, back, d_back = _stacks(n_front, n_back, seed=11)
    n_sub = _substrate(k)

    r, t = calc_spectrum_full_oblique_exact(WLS, d_front, front, d_back, back, n_sub, angle, is_s)

    for i, wl in enumerate(WLS):
        r_ref, t_ref = rt_plate_incoherent(wl, front[i], d_front, back[i], d_back, n_sub[i], angle, is_s, THICKNESS)
        assert (r[i], t[i]) == pytest.approx((r_ref, t_ref), abs=1e-12)


@pytest.mark.parametrize("is_s", [True, False])
@pytest.mark.parametrize("k", [4.4e-6, 1e-4])
def test_the_thickness_is_the_one_asked_for(k, is_s) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized

    front, d_front, _back, _d_back = _stacks(2, 0, seed=13)
    n_sub = _substrate(k)
    polarization = "s" if is_s else "p"

    thin = calc_spectrum_oblique_backside_vectorized(WLS, front, d_front, n_sub, 40.0, polarization, 2.0e5)
    thick = calc_spectrum_oblique_backside_vectorized(WLS, front, d_front, n_sub, 40.0, polarization, 5.0e6)

    for i, wl in enumerate(WLS):
        for got, thickness in ((thin, 2.0e5), (thick, 5.0e6)):
            expected = rt_plate_incoherent(wl, front[i], d_front, [], [], n_sub[i], 40.0, is_s, thickness)
            assert (got[0][i], got[1][i]) == pytest.approx(expected, abs=1e-12)
    assert np.all(thin[1] > thick[1])  # a thinner plate transmits more


# =============================================================================
# The model against the exact coherent plate, averaged
# =============================================================================


@pytest.mark.parametrize("k", [0.0, 1e-7, 4.4e-6, 1e-5, 1e-4])
def test_the_model_agrees_with_the_exact_coherent_plate_averaged_over_a_fringe(k) -> None:
    # The interfaces seen from inside read the real part of the index: an error of the order of k, measured
    # at 4e-5 at most for k = 1e-4 and 5e-13 for k = 0.
    rng = np.random.default_rng(17)
    worst = 0.0
    for _ in range(12):
        n_front = rng.uniform(1.3, 2.6, rng.integers(0, 4)).astype(np.complex128)
        n_back = rng.uniform(1.3, 2.6, rng.integers(0, 3)).astype(np.complex128)
        d_front = rng.uniform(40.0, 200.0, len(n_front))
        d_back = rng.uniform(40.0, 200.0, len(n_back))
        n_sub = complex(rng.uniform(1.45, 3.0), -k)
        angle = float(rng.choice([0.0, 20.0, 45.0, 65.0]))
        is_s = bool(rng.integers(0, 2))
        wl = float(rng.uniform(450.0, 900.0))

        model = rt_plate_incoherent(wl, n_front, d_front, n_back, d_back, n_sub, angle, is_s, THICKNESS)
        truth = rt_plate_coherent_mean(wl, n_front, d_front, n_back, d_back, n_sub, angle, is_s, THICKNESS)
        worst = max(worst, abs(model[0] - truth[0]), abs(model[1] - truth[1]))

    assert worst < 1e-4


# =============================================================================
# Limits and continuity
# =============================================================================


def test_the_plate_of_a_glass_that_barely_absorbs_is_not_a_black_absorber() -> None:
    # The audit's glass: k = 4.4e-6 (1 cm-1). Read as a lossless plate it transmits about 0.92 at normal
    # incidence for a bare plate; through one millimetre of it a tenth is lost, not all.
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized

    no_layers = np.zeros((len(WLS), 0), dtype=np.complex128)
    lossless = calc_spectrum_oblique_backside_vectorized(WLS, no_layers, np.zeros(0), _substrate(0.0), 30.0, "s")
    glass = calc_spectrum_oblique_backside_vectorized(WLS, no_layers, np.zeros(0), _substrate(4.4e-6), 30.0, "s")

    assert np.all(glass[1] > 0.7 * lossless[1])
    assert np.all(glass[1] < lossless[1])


def test_a_plate_that_absorbs_everything_is_the_front_stack_on_a_semi_infinite_substrate() -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact, calc_spectrum_oblique_vectorized

    front, d_front, back, d_back = _stacks(2, 1, seed=19)
    n_sub = _substrate(1.0)

    plate = calc_spectrum_full_oblique_exact(WLS, d_front, front, d_back, back, n_sub, 40.0, True)
    semi_infinite = calc_spectrum_oblique_vectorized(WLS, front, d_front, n_sub, 40.0, "s")

    assert plate[0] == pytest.approx(semi_infinite[0], abs=1e-12)
    assert np.all(plate[1] < 1e-12)


def test_the_answer_is_continuous_when_the_absorption_vanishes() -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact

    front, d_front, back, d_back = _stacks(2, 1, seed=23)

    plain = calc_spectrum_full_oblique_exact(WLS, d_front, front, d_back, back, _substrate(0.0), 40.0, False)
    barely = calc_spectrum_full_oblique_exact(WLS, d_front, front, d_back, back, _substrate(1e-14), 40.0, False)

    assert barely[0] == pytest.approx(plain[0], abs=1e-9)
    assert barely[1] == pytest.approx(plain[1], abs=1e-9)


def test_without_absorption_the_plate_loss_changes_nothing_bit_for_bit() -> None:
    from certus.physics.certus_substrate_absorption import apply_plate_loss

    rng = np.random.default_rng(29)
    rb, tb = rng.random(len(WLS)), rng.random(len(WLS))

    rb_eff, tb_eff = apply_plate_loss(rb, tb, _substrate(0.0), WLS, 45.0)

    assert np.array_equal(rb_eff, rb)
    assert np.array_equal(tb_eff, tb)


def test_the_plate_loss_is_tau_squared_on_the_reflection_and_tau_on_the_transmission() -> None:
    from certus.physics.certus_substrate_absorption import apply_plate_loss, plate_internal_transmittance

    rb, tb = np.full(len(WLS), 0.3), np.full(len(WLS), 0.6)
    n_sub = _substrate(1e-5)

    tau = plate_internal_transmittance(n_sub, WLS, 45.0, THICKNESS)
    rb_eff, tb_eff = apply_plate_loss(rb, tb, n_sub, WLS, 45.0)

    assert np.all((tau > 0.0) & (tau < 1.0))
    assert rb_eff == pytest.approx(rb * tau**2)
    assert tb_eff == pytest.approx(tb * tau)


# =============================================================================
# The bundle and the two places of DESIGN that combine the plate
# =============================================================================


@pytest.mark.parametrize("is_s", [True, False])
@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4])
def test_the_bundle_is_the_spectrum_and_its_derivatives(k, is_s) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact
    from certus.physics.gradient_oblique import compute_oblique_backside_bundle_analytic

    front, d_front, back, d_back = _stacks(3, 2, seed=31)
    n_sub = _substrate(k)
    var = np.arange(3, dtype=np.int64)

    y_r, dy_r, y_t, dy_t = compute_oblique_backside_bundle_analytic(d_front, front, n_sub, WLS, var, 35.0, is_s, back, d_back)

    r, t = calc_spectrum_full_oblique_exact(WLS, d_front, front, d_back, back, n_sub, 35.0, is_s)
    assert y_r == pytest.approx(r, abs=1e-12)
    assert y_t == pytest.approx(t, abs=1e-12)

    step = 1e-3
    for j in range(3):
        up, down = d_front.copy(), d_front.copy()
        up[j] += step
        down[j] -= step
        r_up, t_up = calc_spectrum_full_oblique_exact(WLS, up, front, d_back, back, n_sub, 35.0, is_s)
        r_down, t_down = calc_spectrum_full_oblique_exact(WLS, down, front, d_back, back, n_sub, 35.0, is_s)
        assert dy_r[:, j] == pytest.approx((r_up - r_down) / (2 * step), rel=1e-5, abs=1e-8)
        assert dy_t[:, j] == pytest.approx((t_up - t_down) / (2 * step), rel=1e-5, abs=1e-8)


def _configuration(front, back, d_back, n_sub, angle, is_s, target_type, seed):
    rng = np.random.default_rng(seed)
    return {
        "wls_config": WLS,
        "n_layers_T_config": front,
        "n_sub_config": n_sub,
        "sw_cfg": np.ones(len(WLS)),
        "angle": angle,
        "pol": "s" if is_s else "p",
        "is_s_pol": is_s,
        "all_clues": np.arange(len(WLS)),
        "targets": [
            {
                "local_positions": np.arange(len(WLS)),
                "tgt_vals": rng.uniform(0.0, 1.0, len(WLS)),
                "weight": 1.0,
                "target_type": target_type,
            }
        ],
    }


@pytest.mark.parametrize("target_type", ["R", "T"])
@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4])
@pytest.mark.parametrize("with_back_stack", [False, True])
def test_the_objective_of_design_and_its_gradient_agree_through_the_plate(with_back_stack, k, target_type) -> None:
    # The gradient combines Rf, Tf, Rf', Rb', Tb itself; the error is the spectrum of the plate kernel. If the
    # loss were applied in one and not the other, the finite differences of the error would not be the gradient.
    from certus.core.certus_design_core import (
        _design_compute_oblique_error_and_grad_analytic_common,
        _design_compute_oblique_error_common,
    )

    front, d_front, back, d_back = _stacks(3, 2 if with_back_stack else 0, seed=37)
    n_sub = _substrate(k)
    config = _configuration(front, back, d_back, n_sub, 40.0, True, target_type, seed=41)
    app = SimpleNamespace(
        _oblique_configs=[config],
        _has_back_calc=True,
        _has_back_stack=with_back_stack,
        _d_back=d_back if with_back_stack else np.zeros(0),
        _n_back_T=back if with_back_stack else np.zeros((len(WLS), 0), dtype=np.complex128),
        _var_idx=np.arange(3, dtype=np.int64),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        error = _design_compute_oblique_error_common(app, d_front)
        error_analytic, gradient = _design_compute_oblique_error_and_grad_analytic_common(app, d_front)

    assert error_analytic == pytest.approx(error, rel=1e-10)
    step = 1e-3
    for j in range(3):
        up, down = d_front.copy(), d_front.copy()
        up[j] += step
        down[j] -= step
        derivative = (
            _design_compute_oblique_error_common(app, up) - _design_compute_oblique_error_common(app, down)
        ) / (2 * step)
        assert gradient[j] == pytest.approx(derivative, rel=1e-5, abs=1e-9)


@pytest.mark.parametrize("target_type", ["R", "T"])
@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4])
def test_the_design_engine_combines_the_plate_like_the_core_does(k, target_type) -> None:
    from certus.core.certus_design_core import _design_compute_oblique_error_and_grad_analytic_common
    from certus.workers.certus_design_engine import DesignPhysicsBridge

    front, d_front, back, d_back = _stacks(3, 2, seed=43)
    n_sub = _substrate(k)
    config = _configuration(front, back, d_back, n_sub, 40.0, False, target_type, seed=47)
    var = np.arange(3, dtype=np.int64)
    app = SimpleNamespace(
        _oblique_configs=[config], _has_back_calc=True, _has_back_stack=True, _d_back=d_back, _n_back_T=back, _var_idx=var
    )
    bridge = DesignPhysicsBridge(
        var_idx=var,
        all_variable=True,
        ep0=d_front,
        oblique_mode=True,
        has_back_calc=True,
        has_back_stack=True,
        d_back=d_back,
        n_back_T=back,
        n_layers_T=front,
        n_sub=n_sub,
        wls=WLS,
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[config],
    )

    from_core = _design_compute_oblique_error_and_grad_analytic_common(app, d_front)
    from_engine = bridge.compute_oblique_error_and_grad_analytic(d_front)

    assert from_engine[0] == pytest.approx(from_core[0], rel=1e-12)
    assert from_engine[1] == pytest.approx(from_core[1], rel=1e-10, abs=1e-14)
