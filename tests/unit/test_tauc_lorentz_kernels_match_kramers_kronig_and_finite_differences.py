"""The Tauc-Lorentz-Urbach kernels give the dielectric function the model says and the derivatives the fit needs (audit v2, plan S3.2).

`_compute_epsilon1_gradient_kernel` and `_compute_epsilon2_gradient_kernel` (`certus/physics/gradient_analytic.py`, 372 and 119 lines, 56.6 % of the file covered
before this one) return a dielectric function and its derivatives with respect to the parameters of the model (Eg, A, E0, C, Eu, eps_inf); `_compute_tlu_derivatives_kernel`
turns them into n, k and their derivatives. The only tests were of shapes and finiteness. A derivative of 372 lines of closed form that is wrong by a sign still has the
right shape, and a fit built on it converges to the wrong place without a word.

What is pinned here, against truths that do not come from the code:

    EPS1 IS THE KRAMERS-KRONIG TRANSFORM OF EPS2: the closed form of 120 lines of logarithms and arctangents against a numerical principal-value integral (scipy) of the
        Tauc-Lorentz absorption, at nine energies on three materials, below and above the gap, to 1e-3 (the numerical tail is the limit here: 4e-5 measured)
    EVERY DERIVATIVE IS THE DERIVATIVE OF THE VALUE: central finite differences of the same kernel, parameter by parameter, to 1e-6 of the largest derivative (1e-9 measured);
        the two that are zero by construction (eps1 does not depend on Eu, eps2 not on eps_inf) are zero
    n AND k: n^2 - k^2 = eps1 and 2nk = eps2 (to 1e-9, and to 2e-7 on 2nk where eps2 is under 1e-7, because k is a square root of a cancellation there), their derivatives
        satisfy those equations differentiated, and are the finite differences of n and k where eps2 is over 1e-2
    the physics of the model: eps2 is positive above the gap and decays below it, anchored where the model has it; eps1 is above eps_inf at low energy
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from certus.physics.gradient_analytic import (
    _compute_epsilon1_gradient_kernel,
    _compute_epsilon2_gradient_kernel,
    _compute_tlu_derivatives_kernel,
)

pytestmark = pytest.mark.kernels

#: (Eg, A, E0, C, Eu, eps_inf): a wide-gap oxide, an amorphous-silicon-like film, a strongly absorbing film.
MATERIALS = {
    "oxide": (3.0, 120.0, 4.2, 1.1, 0.08, 1.2),
    "a_silicon": (1.4, 80.0, 3.5, 2.0, 0.05, 1.0),
    "absorbing": (2.2, 200.0, 5.0, 0.6, 0.15, 2.0),
}
ENERGIES = np.array([0.6, 1.0, 1.7, 2.6, 3.4, 4.0, 4.7, 5.5, 6.4])
NAMES = ("Eg", "A", "E0", "C", "Eu", "eps_inf")


def eps1_args(p):
    Eg, A, E0, C, _Eu, eps_inf = p
    return Eg, A, E0, C, eps_inf


def eps2_args(p):
    Eg, A, E0, C, Eu, _eps_inf = p
    return Eg, A, E0, C, Eu


def tauc_lorentz_eps2(E, Eg, A, E0, C):
    """The absorption of the Tauc-Lorentz model, from its definition (Jellison and Modine 1996)."""
    if E <= Eg:
        return 0.0
    return A * E0 * C * (E - Eg) ** 2 / ((E * E - E0 * E0) ** 2 + C * C * E * E) / E


def kramers_kronig_eps1(E, Eg, A, E0, C, eps_inf, e_max=200.0):
    """eps1(E) = eps_inf + (2/pi) P int_Eg^inf xi eps2(xi) / (xi^2 - E^2) dxi, truncated at e_max with the exact leading term of the tail."""
    tail = A * E0 * C / (3.0 * e_max**3)
    if E > Eg:
        # the pole at xi = E: the principal value of f(xi) / (xi - E), with f = xi eps2 / (xi + E)
        value, _ = quad(lambda xi: xi * tauc_lorentz_eps2(xi, Eg, A, E0, C) / (xi + E), Eg, e_max, weight="cauchy", wvar=E, limit=500)
    else:
        value, _ = quad(lambda xi: xi * tauc_lorentz_eps2(xi, Eg, A, E0, C) / (xi * xi - E * E), Eg, e_max, limit=500)
    return eps_inf + 2.0 / np.pi * (value + tail)


def central_difference(kernel, args, index, row=0):
    h = 1e-5 * max(abs(args[index]), 1.0)
    up, down = list(args), list(args)
    up[index] += h
    down[index] -= h
    return (kernel(ENERGIES, *up)[row] - kernel(ENERGIES, *down)[row]) / (2.0 * h)


# --- eps1 is the Kramers-Kronig transform of eps2 --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_eps1_is_the_kramers_kronig_transform_of_the_tauc_lorentz_absorption(name):
    p = MATERIALS[name]
    Eg, A, E0, C, _Eu, eps_inf = p
    kernel = _compute_epsilon1_gradient_kernel(ENERGIES, *eps1_args(p))[0]
    numeric = np.array([kramers_kronig_eps1(E, Eg, A, E0, C, eps_inf) for E in ENERGIES])
    np.testing.assert_allclose(kernel, numeric, rtol=0.0, atol=1e-3)


def test_the_numerical_transform_can_tell_a_wrong_closed_form_from_a_right_one():
    """Negative control: a closed form whose A is 5 % off, or whose eps_inf is off by 0.01, is far outside the tolerance of the comparison above."""
    Eg, A, E0, C, _Eu, eps_inf = MATERIALS["oxide"]
    numeric = np.array([kramers_kronig_eps1(E, Eg, A, E0, C, eps_inf) for E in ENERGIES])
    for wrong in (_compute_epsilon1_gradient_kernel(ENERGIES, Eg, 1.05 * A, E0, C, eps_inf)[0], _compute_epsilon1_gradient_kernel(ENERGIES, Eg, A, E0, C, eps_inf + 0.01)[0]):
        assert np.max(np.abs(wrong - numeric)) > 5e-3


# --- every derivative is the derivative of the value -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_derivatives_of_eps1_are_those_of_its_value(name):
    args = list(eps1_args(MATERIALS[name]))
    result = _compute_epsilon1_gradient_kernel(ENERGIES, *args)
    # the rows are [eps1, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]; the arguments are (Eg, A, E0, C, eps_inf)
    parameters = ("Eg", "A", "E0", "C", "eps_inf")
    for row, index in ((1, 0), (2, 1), (3, 2), (4, 3), (6, 4)):
        expected = central_difference(_compute_epsilon1_gradient_kernel, args, index)
        scale = np.max(np.abs(expected))
        np.testing.assert_allclose(result[row], expected, rtol=0.0, atol=1e-6 * scale, err_msg=f"{name}: row {row} (d/d{parameters[index]})")


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_eps1_does_not_depend_on_the_urbach_energy(name):
    result = _compute_epsilon1_gradient_kernel(ENERGIES, *eps1_args(MATERIALS[name]))
    assert np.all(result[5] == 0.0)


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_derivatives_of_eps2_are_those_of_its_value(name):
    args = list(eps2_args(MATERIALS[name]))
    result = _compute_epsilon2_gradient_kernel(ENERGIES, *args)
    # the rows are [eps2, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]; the arguments are (Eg, A, E0, C, Eu)
    for row, index in ((1, 0), (2, 1), (3, 2), (4, 3), (5, 4)):
        expected = central_difference(_compute_epsilon2_gradient_kernel, args, index)
        scale = np.max(np.abs(expected))
        np.testing.assert_allclose(result[row], expected, rtol=0.0, atol=1e-6 * scale, err_msg=f"{name}: row {row} (d/d{NAMES[index]})")


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_eps2_above_the_gap_is_the_tauc_lorentz_absorption(name):
    """The definition of Jellison and Modine, written in the test: A E0 C (E - Eg)^2 / ((E^2 - E0^2)^2 + C^2 E^2) / E, above the gap."""
    Eg, A, E0, C, _Eu, _eps_inf = MATERIALS[name]
    energies = ENERGIES[ENERGIES > Eg + 0.05]
    kernel = _compute_epsilon2_gradient_kernel(energies, *eps2_args(MATERIALS[name]))[0]
    expected = np.array([tauc_lorentz_eps2(E, Eg, A, E0, C) for E in energies])
    np.testing.assert_allclose(kernel, expected, rtol=1e-12, atol=0.0)


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_eps2_does_not_depend_on_eps_inf(name):
    result = _compute_epsilon2_gradient_kernel(ENERGIES, *eps2_args(MATERIALS[name]))
    assert np.all(result[6] == 0.0)


# --- n and k ---------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_n_and_k_are_the_square_roots_of_the_dielectric_function(name):
    p = MATERIALS[name]
    n, k, _, _ = _compute_tlu_derivatives_kernel(ENERGIES, *p)
    eps1 = _compute_epsilon1_gradient_kernel(ENERGIES, *eps1_args(p))[0]
    eps2 = _compute_epsilon2_gradient_kernel(ENERGIES, *eps2_args(p))[0]
    np.testing.assert_allclose(n * n - k * k, eps1, rtol=1e-9, atol=1e-9)
    # k is computed as sqrt((|eps| - eps1) / 2), which cancels where eps2 is far smaller than eps1: under eps2 ~ 1e-7 (deep below the gap) k comes back as 0 or a few per mille
    # off. That is under 2e-7 on 2nk, and k < 1e-7 does nothing to a stack; it is measured here so that a change of the formula is seen.
    np.testing.assert_allclose(2.0 * n * k, eps2, rtol=1e-9, atol=2e-7)
    assert np.all(n > 0.0)
    assert np.all(k >= 0.0)


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_derivatives_of_n_and_k_satisfy_the_defining_equations_of_n_and_k(name):
    """n^2 - k^2 = eps1 and 2nk = eps2, differentiated: n dn - k dk = d(eps1) / 2 and k dn + n dk = d(eps2) / 2, whatever the energy and the parameter."""
    p = MATERIALS[name]
    n, k, dn, dk = _compute_tlu_derivatives_kernel(ENERGIES, *p)
    d_eps1 = _compute_epsilon1_gradient_kernel(ENERGIES, *eps1_args(p))[1:]  # [Eg, A, E0, C, Eu, eps_inf]
    d_eps2 = _compute_epsilon2_gradient_kernel(ENERGIES, *eps2_args(p))[1:]
    assert dn.shape == dk.shape == (6, len(ENERGIES))
    for index in range(6):
        scale = max(np.max(np.abs(d_eps1[index])), np.max(np.abs(d_eps2[index])), 1e-12)
        np.testing.assert_allclose(n * dn[index] - k * dk[index], d_eps1[index] / 2.0, rtol=0.0, atol=1e-9 * scale, err_msg=f"{name}: d{NAMES[index]}, real part")
        np.testing.assert_allclose(k * dn[index] + n * dk[index], d_eps2[index] / 2.0, rtol=0.0, atol=1e-9 * scale, err_msg=f"{name}: d{NAMES[index]}, imaginary part")


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_derivatives_of_n_and_k_are_those_of_n_and_k_where_k_is_accurate(name):
    """Finite differences of n and k, at the energies where eps2 is over 1e-2. Below, k is a square root of a cancellation and it is the finite difference that is wrong."""
    p = list(MATERIALS[name])
    _n, _k, dn, dk = _compute_tlu_derivatives_kernel(ENERGIES, *p)
    eps2 = _compute_epsilon2_gradient_kernel(ENERGIES, *eps2_args(MATERIALS[name]))[0]
    accurate = eps2 > 1e-2
    assert accurate.sum() >= 4  # absorbing energies exist on every material of the set
    for index in range(6):
        h = 1e-5 * max(abs(p[index]), 1.0)
        up, down = list(p), list(p)
        up[index] += h
        down[index] -= h
        n_up, k_up, _, _ = _compute_tlu_derivatives_kernel(ENERGIES, *up)
        n_down, k_down, _, _ = _compute_tlu_derivatives_kernel(ENERGIES, *down)
        for analytic, numeric, what in ((dn[index], (n_up - n_down) / (2 * h), "n"), (dk[index], (k_up - k_down) / (2 * h), "k")):
            scale = max(np.max(np.abs(numeric[accurate])), 1e-12)
            np.testing.assert_allclose(analytic[accurate], numeric[accurate], rtol=0.0, atol=1e-5 * scale + 1e-10, err_msg=f"{name}: d{what}/d{NAMES[index]}")


# --- the physics of the model ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_absorption_is_positive_above_the_gap_and_decays_below_it(name):
    Eg, *_ = MATERIALS[name]
    energies = np.array([Eg - 0.5, Eg - 0.25, Eg + 0.5, Eg + 1.0])
    eps2 = _compute_epsilon2_gradient_kernel(energies, *eps2_args(MATERIALS[name]))[0]
    assert np.all(eps2 > 0.0)
    assert eps2[0] < eps2[1] < eps2[2]  # the Urbach tail rises towards the gap, the band absorption rises above it


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_the_urbach_tail_is_anchored_a_hundredth_of_an_electron_volt_above_the_gap(name):
    """Below the gap eps2 is the absorption of the model at Eg + 0.01 eV, times exp((E - Eg - 0.01) / Eu): the tail leaves the band absorption where the model has it."""
    Eg, A, E0, C, Eu, _eps_inf = MATERIALS[name]
    energies = np.array([Eg - 0.4, Eg - 0.2, Eg - 0.05, Eg - 0.01])
    tail = _compute_epsilon2_gradient_kernel(energies, *eps2_args(MATERIALS[name]))[0]
    anchor = tauc_lorentz_eps2(Eg + 0.01, Eg, A, E0, C)
    np.testing.assert_allclose(tail, anchor * np.exp((energies - Eg - 0.01) / Eu), rtol=1e-12, atol=0.0)


@pytest.mark.parametrize("name", sorted(MATERIALS))
def test_far_below_the_gap_eps1_tends_to_eps_inf_plus_the_static_contribution_and_eps2_to_zero(name):
    p = MATERIALS[name]
    eps1 = _compute_epsilon1_gradient_kernel(np.array([0.05]), *eps1_args(p))[0]
    eps2 = _compute_epsilon2_gradient_kernel(np.array([0.05]), *eps2_args(p))[0]
    assert eps1[0] > p[5]  # the absorption above adds a positive static term to eps_inf
    assert eps2[0] < 1e-3
