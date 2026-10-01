"""The reflectance of an Air | Metal | SiO2 | Si stack is the one of the independent oracle (audit v2, plan S3.2).

`calculate_reflectance_bilayer_vectorized` (`certus/physics/certus_opt_tmm.py`) is the kernel behind the METAL bilayer window: a scalarized 2 x 2 transfer matrix of two layers on a substrate seen
from the front only (an opaque or rough wafer: no back surface, no second pass). It had no test of its own - the window that calls it was the only reader. A kernel that is wrong by a sign of k, a
swapped layer or a missing clamp still draws a smooth curve.

What is pinned here, against `tests/oracle/tmm_reference.py` (written from Macleod, sharing no code with `certus.physics`), over metals, dielectrics and absorbing substrates:

    the reflectance of the two-layer stack on a semi-infinite substrate, at 1e-12, over a spectrum, for several metals and thicknesses
    the order of the layers (the metal is on the air side, the SiO2 on the substrate side) and the convention n - ik: an index given with the sign of k reversed gives the same answer
    zero thickness is the other stack: no metal is the SiO2 alone, no SiO2 is the metal alone, neither is the bare substrate
    the physics: R is within [0, 1], a thick metal tends to the reflectance of the bulk metal, a lossless stack has a periodic response
    the clamp to [0, 1] and the guard of a vanishing denominator
    `clip_to_bounds`, the one-line kernel INDEX uses to keep a start inside its box
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from certus.physics.certus_opt_tmm import calculate_reflectance_bilayer_vectorized, clip_to_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

pytestmark = pytest.mark.kernels

WAVELENGTHS = np.linspace(400.0, 1100.0, 36)
SILICON = 3.9 - 0.02j
SILICA = 1.46 + 0.0j

#: metals as (n, k) with the Macleod convention n - ik: an aluminium-like, a gold-like and a titanium-like film
METALS = {"aluminium": 1.0 - 6.5j, "gold": 0.4 - 2.6j, "titanium": 3.0 - 3.4j}


def reflectance(metal, eM, eL, n_substrate=SILICON, wl=WAVELENGTHS, n_silica=SILICA):
    n_metal = np.full(len(wl), metal, dtype=np.complex128)
    n_oxide = np.full(len(wl), n_silica, dtype=np.complex128)
    n_sub = np.full(len(wl), n_substrate, dtype=np.complex128)
    return calculate_reflectance_bilayer_vectorized(np.asarray(wl, dtype=np.float64), n_metal, float(eM), float(eL), n_oxide, n_sub)


def oracle_reflectance(metal, eM, eL, n_substrate=SILICON, wl=WAVELENGTHS, n_silica=SILICA):
    """R of Air | metal | SiO2 | substrate by the oracle (index 0 = substrate side): a stack of two layers on a semi-infinite substrate."""
    return np.array([oracle.rt_stack(float(w), [n_silica, metal], [eL, eM], 1.0 + 0.0j, n_substrate)[0] for w in wl])


# --- the oracle ----------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("metal", sorted(METALS))
@pytest.mark.parametrize(("eM", "eL"), [(10.0, 100.0), (25.0, 300.0), (60.0, 90.0), (3.0, 20.0)])
def test_the_reflectance_is_the_oracles(metal, eM, eL):
    np.testing.assert_allclose(reflectance(METALS[metal], eM, eL), oracle_reflectance(METALS[metal], eM, eL), rtol=0.0, atol=1e-12)


@pytest.mark.parametrize("substrate", [1.52 + 0.0j, 3.9 - 0.02j, 4.2 - 1.1j])
def test_the_reflectance_is_the_oracles_on_a_dielectric_and_on_an_absorbing_substrate(substrate):
    np.testing.assert_allclose(reflectance(METALS["gold"], 15.0, 120.0, substrate), oracle_reflectance(METALS["gold"], 15.0, 120.0, substrate), rtol=0.0, atol=1e-12)


def test_the_metal_is_on_the_air_side_and_the_oxide_on_the_substrate_side():
    swapped = oracle.rt_stack(600.0, [METALS["gold"], SILICA], [15.0, 120.0], 1.0 + 0.0j, SILICON)[0]  # the opposite order
    right = float(reflectance(METALS["gold"], 15.0, 120.0, wl=[600.0])[0])
    assert right == pytest.approx(oracle_reflectance(METALS["gold"], 15.0, 120.0, wl=[600.0])[0], abs=1e-12)
    assert abs(right - swapped) > 1e-3  # and the two orders are not the same stack, so the test above can tell them apart


# --- the convention n - ik ------------------------------------------------------------------------------------------------------------------


def test_an_index_given_with_the_wrong_sign_of_k_is_the_same_index():
    right = reflectance(METALS["gold"], 15.0, 120.0)
    wrong_metal = reflectance(METALS["gold"].conjugate(), 15.0, 120.0)
    wrong_substrate = reflectance(METALS["gold"], 15.0, 120.0, SILICON.conjugate())
    wrong_oxide = reflectance(METALS["gold"], 15.0, 120.0, n_silica=SILICA + 0.01j)
    np.testing.assert_allclose(wrong_metal, right, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(wrong_substrate, right, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(wrong_oxide, reflectance(METALS["gold"], 15.0, 120.0, n_silica=SILICA - 0.01j), rtol=0.0, atol=1e-12)


# --- zero thickness ---------------------------------------------------------------------------------------------------------------------------


def test_no_metal_is_the_oxide_alone():
    np.testing.assert_allclose(reflectance(METALS["gold"], 0.0, 120.0), oracle_reflectance(METALS["gold"], 0.0, 120.0), rtol=0.0, atol=1e-12)
    alone = np.array([oracle.rt_stack(float(w), [SILICA], [120.0], 1.0 + 0.0j, SILICON)[0] for w in WAVELENGTHS])
    np.testing.assert_allclose(reflectance(METALS["gold"], 0.0, 120.0), alone, rtol=0.0, atol=1e-12)


def test_no_oxide_is_the_metal_alone():
    alone = np.array([oracle.rt_stack(float(w), [METALS["gold"]], [15.0], 1.0 + 0.0j, SILICON)[0] for w in WAVELENGTHS])
    np.testing.assert_allclose(reflectance(METALS["gold"], 15.0, 0.0), alone, rtol=0.0, atol=1e-12)


def test_neither_layer_is_the_bare_substrate():
    bare = abs((1.0 - SILICON) / (1.0 + SILICON)) ** 2
    np.testing.assert_allclose(reflectance(METALS["gold"], 0.0, 0.0), bare, rtol=0.0, atol=1e-12)


# --- the physics ------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("metal", sorted(METALS))
def test_the_reflectance_is_a_fraction(metal):
    for eM, eL in [(1.0, 10.0), (10.0, 100.0), (200.0, 500.0)]:
        r = reflectance(METALS[metal], eM, eL)
        assert np.all(r >= 0.0)
        assert np.all(r <= 1.0)


def test_a_thick_metal_tends_to_the_reflectance_of_the_bulk_metal():
    bulk = abs((1.0 - METALS["aluminium"]) / (1.0 + METALS["aluminium"])) ** 2
    np.testing.assert_allclose(reflectance(METALS["aluminium"], 500.0, 100.0), bulk, rtol=0.0, atol=1e-9)


def test_a_lossless_stack_repeats_with_the_thickness_of_the_oxide_by_half_a_wave():
    # a lossless oxide on a lossless substrate: R is periodic in the optical thickness of the oxide, with period lambda / 2
    wl = np.array([600.0])
    glass = 1.52 + 0.0j
    period = 600.0 / (2.0 * SILICA.real)
    first = reflectance(0.0 + 0.0j, 0.0, 80.0, glass, wl, SILICA)
    second = reflectance(0.0 + 0.0j, 0.0, 80.0 + period, glass, wl, SILICA)
    np.testing.assert_allclose(first, second, rtol=0.0, atol=1e-12)


def test_a_vanishing_denominator_gives_a_zero_reflectance_and_not_a_nan():
    # zero thicknesses make the matrix the identity: term1 = n0 = 1 and term2 = n_substrate, so a substrate of index -1 makes the denominator exactly zero; the guard answers 0
    r = calculate_reflectance_bilayer_vectorized(np.array([600.0]), np.array([1.0 + 0j]), 0.0, 0.0, np.array([1.0 + 0j]), np.array([-1.0 + 0j]))
    assert r[0] == 0.0
    assert np.isfinite(r[0])


def test_the_result_is_clamped_to_zero_one():
    # a substrate of negative index is not a physical medium; |r|^2 = ((1 - n) / (1 + n))^2 = 9 for n = -2: the clamp, the last guard, answers 1
    r = reflectance(METALS["gold"], 0.0, 0.0, -2.0 + 0.0j)
    np.testing.assert_array_equal(r, np.ones_like(r))
    assert np.all(reflectance(-0.5 - 8.0j, 30.0, 50.0) <= 1.0)


# --- clip_to_bounds ---------------------------------------------------------------------------------------------------------------------------


def test_clip_to_bounds_clips_each_coordinate_to_its_own_interval():
    x = np.array([-5.0, 0.5, 7.0, 2.0])
    lb = np.array([-1.0, 0.0, 0.0, 3.0])
    ub = np.array([1.0, 1.0, 5.0, 4.0])
    np.testing.assert_array_equal(clip_to_bounds(x, lb, ub), [-1.0, 0.5, 5.0, 3.0])


def test_clip_to_bounds_does_not_touch_its_input():
    x = np.array([-5.0, 7.0])
    clip_to_bounds(x, np.array([0.0, 0.0]), np.array([1.0, 1.0]))
    np.testing.assert_array_equal(x, [-5.0, 7.0])


def test_clip_to_bounds_leaves_a_point_on_a_bound_where_it_is():
    x = np.array([0.0, 1.0])
    np.testing.assert_array_equal(clip_to_bounds(x, np.array([0.0, 0.0]), np.array([1.0, 1.0])), x)
