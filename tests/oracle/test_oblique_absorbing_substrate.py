"""The oblique kernels that end on a semi-infinite substrate read its absorption.

They kept the real part of the substrate index (`n_sub[i].real`) and dropped the rest: under a layer of
2.3 x 100 nm, a substrate of index 1.7 - 1.11i at 600 nm and 30 degrees gave R off by 0.22 (s) and 0.19
(p) against `tests/oracle/tmm_reference.py`, in the spectrum on screen and in the objective and gradient
that DESIGN optimizes, both wrong in the same way, so nothing looked off. No oracle test had a complex
substrate at oblique incidence.

The exit admittance is now complex (Macleod eq. 2.36 and 2.37, complex angle) and `T` is the flux that
enters the substrate, `4 Re(η_inc) Re(η_exit) / |η_inc B + C|²`. The kernels for a substrate without
absorption are the ones that always ran, bit for bit (C1): the absorbing branch is compiled apart.

Not covered here: the kernels that build an incoherent plate with a back side, which still read the real
part (`test_oblique_transparent_substrate_bound.py`).
"""

from __future__ import annotations

import numpy as np
import pytest
from tmm_reference import rt_stack_oblique

#: (n, k) of substrates: a glass, a doped glass, a semiconductor, a lossy dielectric, a metal.
SUBSTRATES = [
    pytest.param(complex(1.52, -1e-6), id="glass"),
    pytest.param(complex(1.7, -1.11), id="the-case-that-was-off-by-0.2"),
    pytest.param(complex(3.5, -0.5), id="semiconductor"),
    pytest.param(complex(2.0, -0.01), id="lossy-dielectric"),
    pytest.param(complex(0.15, -3.5), id="metal"),
]
ANGLES = [5.0, 30.0, 60.0, 85.0]
POLARIZATIONS = ["s", "p"]
WLS = np.array([450.0, 700.0, 1100.0])


def _stack(n_layers: int, rng: np.random.Generator):
    n = (rng.uniform(1.3, 3.0, (len(WLS), n_layers)) - 1j * 0.01 * rng.random((len(WLS), n_layers))).astype(
        np.complex128
    )
    d = rng.uniform(40.0, 200.0, n_layers)
    return n, d


def _oracle(n_layers_row, d, n_sub, wl, angle, polarization):
    return rt_stack_oblique(float(wl), n_layers_row, d, angle, polarization == "s", n_sub=n_sub)


@pytest.mark.parametrize("n_layers", [0, 1, 5])
@pytest.mark.parametrize("polarization", POLARIZATIONS)
@pytest.mark.parametrize("angle", ANGLES)
@pytest.mark.parametrize("n_sub", SUBSTRATES)
def test_the_spectrum_of_a_front_stack_matches_the_oracle(n_sub, angle, polarization, n_layers) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n, d = _stack(n_layers, np.random.default_rng(3))
    n_sub_arr = np.full(len(WLS), n_sub)

    r, t = calc_spectrum_oblique_vectorized(WLS, n, d, n_sub_arr, angle, polarization)

    for i, wl in enumerate(WLS):
        r_ref, t_ref = _oracle(n[i], d, n_sub, wl, angle, polarization)
        assert r[i] == pytest.approx(r_ref, abs=1e-12)
        assert t[i] == pytest.approx(t_ref, abs=1e-12)


@pytest.mark.parametrize("polarization", POLARIZATIONS)
def test_the_substrate_that_was_off_by_0_2_is_now_exact(polarization) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n_sub = complex(1.7, -1.11)
    layer = np.array([[complex(2.3, 0.0)]])
    thickness = np.array([100.0])

    r, _t = calc_spectrum_oblique_vectorized(np.array([600.0]), layer, thickness, np.array([n_sub]), 30.0, polarization)
    r_ref, _ = rt_stack_oblique(600.0, layer[0], thickness, 30.0, polarization == "s", n_sub=n_sub)

    assert float(r[0]) == pytest.approx(r_ref, abs=1e-12)
    # What the real part alone gave (0.22 in s, 0.19 in p, measured), so that this test cannot pass for
    # the wrong reason.
    r_real_part, _ = rt_stack_oblique(600.0, layer[0], thickness, 30.0, polarization == "s", n_sub=complex(1.7, 0.0))
    assert abs(r_real_part - r_ref) > 0.15


@pytest.mark.parametrize("polarization", POLARIZATIONS)
@pytest.mark.parametrize("n_sub", SUBSTRATES)
def test_lossless_layers_on_an_absorbing_substrate_lose_nothing_but_the_flux_that_enters_it(n_sub, polarization) -> None:
    # T is the flux that enters the substrate, so R + T = 1 when nothing above it absorbs. This does
    # not depend on the oracle: it is energy conservation.
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    rng = np.random.default_rng(5)
    n = rng.uniform(1.3, 3.0, (len(WLS), 4)).astype(np.complex128)
    d = rng.uniform(40.0, 200.0, 4)

    r, t = calc_spectrum_oblique_vectorized(WLS, n, d, np.full(len(WLS), n_sub), 40.0, polarization)

    assert r + t == pytest.approx(np.ones(len(WLS)), abs=1e-12)


def test_the_absorption_reaches_the_answer_wavelength_by_wavelength() -> None:
    # One absorbing wavelength is enough to read the band as absorbing; the others are still exact.
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n, d = _stack(3, np.random.default_rng(9))
    n_sub = np.array([complex(1.52, 0.0), complex(1.7, -1.11), complex(1.5, 0.0)])

    r, t = calc_spectrum_oblique_vectorized(WLS, n, d, n_sub, 50.0, "p")

    for i, wl in enumerate(WLS):
        r_ref, t_ref = _oracle(n[i], d, n_sub[i], wl, 50.0, "p")
        assert (r[i], t[i]) == pytest.approx((r_ref, t_ref), abs=1e-12)


def test_the_answer_is_continuous_when_the_absorption_vanishes() -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n, d = _stack(3, np.random.default_rng(13))
    plain = calc_spectrum_oblique_vectorized(WLS, n, d, np.full(len(WLS), complex(1.52, 0.0)), 50.0, "s")
    barely = calc_spectrum_oblique_vectorized(WLS, n, d, np.full(len(WLS), complex(1.52, -1e-12)), 50.0, "s")

    assert barely[0] == pytest.approx(plain[0], abs=1e-9)
    assert barely[1] == pytest.approx(plain[1], abs=1e-9)


# =============================================================================
# The objective of DESIGN and its analytic gradient
# =============================================================================


def _oracle_objective(d, n, n_sub, weights, targets, angle, is_s, is_reflectance) -> float:
    total = 0.0
    for i, wl in enumerate(WLS):
        r, t = rt_stack_oblique(float(wl), n[i], d, angle, is_s, n_sub=n_sub[i])
        y = min(1.0, max(0.0, r if is_reflectance else t))
        total += weights[i] * (y - targets[i]) ** 2
    return total


@pytest.mark.parametrize("is_reflectance", [True, False])
@pytest.mark.parametrize("is_s", [True, False])
@pytest.mark.parametrize("n_sub", SUBSTRATES)
def test_the_objective_and_its_gradient_match_the_oracle(n_sub, is_s, is_reflectance) -> None:
    from certus.physics.gradient_oblique import compute_oblique_gradient_contrib_analytic

    rng = np.random.default_rng(17)
    n_layers = 4
    n, d = _stack(n_layers, rng)
    n_sub_arr = np.full(len(WLS), n_sub)
    targets = rng.uniform(0.0, 1.0, len(WLS))
    weights = rng.uniform(0.3, 1.0, len(WLS))
    angle = 45.0

    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
        d, n, n_sub_arr, WLS, targets, weights, angle, is_s, is_reflectance, np.arange(n_layers, dtype=np.int64)
    )

    expected = _oracle_objective(d, n, n_sub_arr, weights, targets, angle, is_s, is_reflectance)
    assert err_sum == pytest.approx(expected, abs=1e-12)
    assert weight_sum == pytest.approx(weights.sum())

    # err_sum = sum w (y - t)^2, so d(err_sum)/d(d_j) = 2 * grad_raw_j; checked against central
    # differences of the ORACLE objective, which shares no code with the kernel.
    step = 1e-3
    for j in range(n_layers):
        up, down = d.copy(), d.copy()
        up[j] += step
        down[j] -= step
        derivative = (
            _oracle_objective(up, n, n_sub_arr, weights, targets, angle, is_s, is_reflectance)
            - _oracle_objective(down, n, n_sub_arr, weights, targets, angle, is_s, is_reflectance)
        ) / (2.0 * step)
        assert 2.0 * grad_raw[j] == pytest.approx(derivative, rel=1e-5, abs=1e-8)


def test_a_substrate_without_absorption_keeps_the_kernel_that_always_ran(monkeypatch) -> None:
    # C1: the inactive path is the same kernel, not a re-derivation of it. Which kernel runs is the
    # wrapper's choice; that the plain one is bit for bit the old one was measured when it was changed.
    import certus.physics.gradient_oblique as module

    used = []
    monkeypatch.setattr(module, "_compute_oblique_gradient_contrib_kernel", lambda *a: used.append("plain") or (0.0, a[0], 0.0))
    monkeypatch.setattr(
        module, "_compute_oblique_gradient_contrib_kernel_absorbing", lambda *a: used.append("absorbing") or (0.0, a[0], 0.0)
    )
    rng = np.random.default_rng(19)
    n, d = _stack(2, rng)
    args = (d, n, None, WLS, np.full(len(WLS), 0.5), np.ones(len(WLS)), 30.0, True, True)

    module.compute_oblique_gradient_contrib_analytic(*args[:2], np.full(len(WLS), complex(1.52, 0.0)), *args[3:])
    module.compute_oblique_gradient_contrib_analytic(
        *args[:2], np.array([complex(1.52, 0.0), complex(1.52, 0.0), complex(1.52, -1e-9)]), *args[3:]
    )

    assert used == ["plain", "absorbing"]


def test_the_exit_admittance_refuses_a_p_wave_at_grazing_of_a_medium_that_cannot_carry_it() -> None:
    from certus.physics.certus_oblique_substrate import oblique_exit_admittance

    eta, ok = oblique_exit_admittance(complex(1.0, 0.0), 1.0, False)  # cos θ = 0: the admittance is infinite

    assert (eta, ok) == (0j, False)
    eta_s, ok_s = oblique_exit_admittance(complex(1.0, 0.0), 1.0, True)
    assert ok_s and eta_s == 0j  # s at grazing: admittance 0, usable, and the caller sees it
