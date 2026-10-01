"""The bare-substrate references INDEX divides by are the oracle's plate (audit v2, plan S3.2).

INDEX normalises a measured spectrum by the bare substrate seen the same way (`T / Tsub`, `R / Tsub`), and the frosted-glass mode compares with the one interface: five kernels of
`certus/physics/certus_tmm_substrate.py`. A reference that is wrong by a factor rescales every spectrum fitted against it, and the fit still converges - to the wrong index. Two of them,
`calculate_bare_substrate_R_absorbing` and `calculate_bare_substrate_T_absorbing` (an absorbing substrate), and the guards of two others, had no test at all.

What is pinned here, against `tests/oracle/tmm_reference.py` (`rt_plate_incoherent`, written from Macleod, sharing no code with `certus.physics`):

    the transparent plate: R with the back face (2 R1 / (1 + R1)) and T ((1 - R1) / (1 + R1)), over indices from 1 to silicon, and R + T = 1
    the single interface (the frosted glass of INDEX: no back face)
    the absorbing plate (Beer-Lambert per pass, a thickness in nm): R and T at the oracle's values, the pure absorption law when the interface does not reflect (n = 1), the energy
    bookkeeping (R + T + A = 1 with A summed pass by pass), the limits (no absorption, an opaque plate), the guard of a vanishing denominator
    the guards of the negative index that `calculate_bare_substrate_R` and `calculate_single_interface_R` carry

The interface of the absorbing kernels is read with the real part of the index only (the extinction enters through the bulk), where the oracle reads the complex index: the two differ by
`k**2` times a number below one, which the tolerance of the absorbing tests allows for and nothing else.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

from certus.physics.certus_tmm_substrate import (
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_single_interface_R,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

pytestmark = pytest.mark.kernels

WAVELENGTHS = np.array([300.0, 450.0, 550.0, 700.0, 1000.0, 1600.0, 2400.0])
INDICES = [1.0, 1.33, 1.45, 1.52, 1.77, 2.4, 3.42]  # air-matched, water, silica, glass, sapphire, diamond, silicon


def plate(wavelength, n, k=0.0, thickness=1.0e6):
    """(R, T) of a bare plate in air by the oracle, at normal incidence: no stack on either face."""
    empty = np.zeros(0, dtype=np.complex128)
    return oracle.rt_plate_incoherent(float(wavelength), empty, np.zeros(0), empty, np.zeros(0), complex(n, -k), 0.0, True, thickness)


def constant(value):
    return np.full(len(WAVELENGTHS), value, dtype=np.float64)


def interface_reflectance(n):
    return ((1.0 - n) / (1.0 + n)) ** 2


# --- the transparent plate ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", INDICES)
def test_the_reflectance_with_the_back_face_is_the_oracles(n):
    expected = [plate(wl, n)[0] for wl in WAVELENGTHS]
    np.testing.assert_allclose(calculate_bare_substrate_R(WAVELENGTHS, constant(n)), expected, rtol=0.0, atol=1e-12)


@pytest.mark.parametrize("n", INDICES)
def test_the_transmittance_of_the_plate_is_the_oracles(n):
    expected = [plate(wl, n)[1] for wl in WAVELENGTHS]
    np.testing.assert_allclose(calculate_bare_substrate_RT(WAVELENGTHS, constant(n)), expected, rtol=0.0, atol=1e-12)


@pytest.mark.parametrize("n", INDICES)
def test_a_transparent_plate_reflects_and_transmits_everything(n):
    total = calculate_bare_substrate_R(WAVELENGTHS, constant(n)) + calculate_bare_substrate_RT(WAVELENGTHS, constant(n))
    np.testing.assert_allclose(total, 1.0, rtol=0.0, atol=1e-12)


def test_a_complex_index_array_gives_the_same_reflectance_as_a_real_one():
    # the kernel reads `.real` and `.imag` of each index; an array that carries a zero imaginary part is the same substrate
    real = calculate_bare_substrate_R(WAVELENGTHS, constant(1.52))
    complex_array = calculate_bare_substrate_R(WAVELENGTHS, np.full(len(WAVELENGTHS), 1.52 + 0.0j))
    np.testing.assert_allclose(complex_array, real, rtol=0.0, atol=1e-14)


def test_the_reflectance_of_a_plate_follows_the_index_it_is_given_point_by_point():
    n = np.array([1.45, 1.52, 1.77, 2.4, 3.42, 1.33, 1.0])
    expected = [plate(wl, n_i)[0] for wl, n_i in zip(WAVELENGTHS, n, strict=True)]
    np.testing.assert_allclose(calculate_bare_substrate_R(WAVELENGTHS, n), expected, rtol=0.0, atol=1e-12)


# --- the single interface (frosted glass) ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", INDICES)
def test_the_single_interface_is_the_front_reflectance_of_the_oracle(n):
    expected = [oracle.rt_stack(float(wl), [], [], 1.0 + 0.0j, complex(n, 0.0))[0] for wl in WAVELENGTHS]
    np.testing.assert_allclose(calculate_single_interface_R(WAVELENGTHS, constant(n)), expected, rtol=0.0, atol=1e-12)


def test_the_single_interface_has_no_back_face():
    one_face = calculate_single_interface_R(WAVELENGTHS, constant(1.52))
    two_faces = calculate_bare_substrate_R(WAVELENGTHS, constant(1.52))
    np.testing.assert_allclose(one_face, interface_reflectance(1.52), rtol=0.0, atol=1e-14)
    assert np.all(two_faces > one_face)  # 2 R / (1 + R) > R for R in (0, 1)


# --- the guards of the negative index -------------------------------------------------------------------------------------------------------
#
# A negative real index is not a medium; `calculate_bare_substrate_R` and `calculate_single_interface_R` read it as 1.5 (a glass), `calculate_bare_substrate_RT` has no such guard
# and is not pinned here (the audit's PHY-05 is about the guards of the substrate and is the owner's).


def test_a_negative_index_is_read_as_a_glass_by_the_reflectance_with_the_back_face():
    np.testing.assert_allclose(
        calculate_bare_substrate_R(WAVELENGTHS, constant(-2.0)), calculate_bare_substrate_R(WAVELENGTHS, constant(1.5)), rtol=0.0, atol=1e-14
    )


def test_a_negative_index_is_read_as_a_glass_by_the_single_interface():
    np.testing.assert_allclose(
        calculate_single_interface_R(WAVELENGTHS, constant(-2.0)), calculate_single_interface_R(WAVELENGTHS, constant(1.5)), rtol=0.0, atol=1e-14
    )


# --- the absorbing plate ----------------------------------------------------------------------------------------------------------------------

EXTINCTIONS = [0.0, 1e-7, 1e-6, 1e-5, 1e-4, 5e-4]
THICKNESSES_NM = [2.0e5, 1.0e6, 2.5e6]


def tolerance(k):
    """The kernel reads the first interface with the real index; the oracle with the complex one: `k**2` times a factor below 0.2."""
    return 1e-12 + 2.0 * k * k


@pytest.mark.parametrize("k", EXTINCTIONS)
@pytest.mark.parametrize("thickness", THICKNESSES_NM)
@pytest.mark.parametrize("n", [1.45, 1.77, 3.42])
def test_the_absorbing_plate_is_the_oracles(n, k, thickness):
    expected = np.array([plate(wl, n, k, thickness) for wl in WAVELENGTHS])
    reflectance = calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(n), constant(k), thickness)
    transmittance = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(n), constant(k), thickness)
    np.testing.assert_allclose(reflectance, expected[:, 0], rtol=0.0, atol=tolerance(k))
    np.testing.assert_allclose(transmittance, expected[:, 1], rtol=0.0, atol=tolerance(k))


def test_the_absorption_law_is_exact_when_the_interface_does_not_reflect():
    # n = 1: R1 = 0, T1 = 1, nothing bounces: T = exp(-4 pi k D / lambda), R = 0 - the wave number, the factor 4 pi, nm and nm
    for k, thickness in [(1e-6, 1.0e6), (1e-5, 1.0e6), (2e-5, 3.0e5), (1e-4, 5.0e4)]:
        expected = np.exp(-4.0 * math.pi * k * thickness / WAVELENGTHS)
        np.testing.assert_allclose(
            calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(1.0), constant(k), thickness), expected, rtol=1e-12, atol=0.0
        )
        np.testing.assert_allclose(calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(1.0), constant(k), thickness), 0.0, rtol=0.0, atol=1e-15)


@pytest.mark.parametrize("n", [1.33, 1.52, 2.4])
@pytest.mark.parametrize(("k", "thickness"), [(1e-5, 1.0e6), (2e-4, 1.0e6), (1e-3, 1.0e5)])
def test_the_energy_is_booked_pass_by_pass(n, k, thickness):
    # the flux absorbed in the bulk, summed over the passes: the first pass absorbs (1 - R1)(1 - tau), every later pass is R1 * tau times the previous one
    r1 = interface_reflectance(n)
    tau = np.exp(-4.0 * math.pi * k * thickness / WAVELENGTHS)
    absorbed = (1.0 - r1) * (1.0 - tau) / (1.0 - r1 * tau)
    reflectance = calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(n), constant(k), thickness)
    transmittance = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(n), constant(k), thickness)
    np.testing.assert_allclose(reflectance + transmittance + absorbed, 1.0, rtol=0.0, atol=1e-12)
    assert np.all(absorbed >= 0.0)


@pytest.mark.parametrize("n", INDICES)
def test_without_absorption_the_plate_is_the_transparent_one(n):
    np.testing.assert_allclose(
        calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(n), constant(0.0), 1.0e6), calculate_bare_substrate_R(WAVELENGTHS, constant(n)), rtol=0.0, atol=1e-12
    )
    np.testing.assert_allclose(
        calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(n), constant(0.0), 1.0e6), calculate_bare_substrate_RT(WAVELENGTHS, constant(n)), rtol=0.0, atol=1e-12
    )


def test_a_plate_of_no_thickness_is_the_transparent_one_whatever_its_extinction():
    np.testing.assert_allclose(
        calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(1.52), constant(0.05), 0.0), calculate_bare_substrate_R(WAVELENGTHS, constant(1.52)), rtol=0.0, atol=1e-12
    )


def test_an_opaque_plate_reflects_its_first_face_and_transmits_nothing():
    # k = 0.1 over a millimetre: exp(-4 pi k D / lambda) is 1e-228 at 2.4 um and underflows to zero below
    reflectance = calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(1.52), constant(0.1), 1.0e6)
    transmittance = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(1.52), constant(0.1), 1.0e6)
    np.testing.assert_allclose(reflectance, interface_reflectance(1.52), rtol=0.0, atol=1e-12)
    assert np.all(transmittance < 1e-50)


def test_the_plate_absorbs_more_the_thicker_it_is():
    thin = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(1.52), constant(1e-5), 1.0e5)
    thick = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(1.52), constant(1e-5), 1.0e6)
    assert np.all(thick < thin)


def test_each_wavelength_is_read_with_its_own_index_and_extinction():
    n = np.array([1.45, 1.52, 1.77, 2.4, 3.42, 1.33, 1.0])
    k = np.array([0.0, 1e-6, 1e-5, 1e-4, 5e-5, 2e-6, 3e-5])
    expected = np.array([plate(wl, n_i, k_i) for wl, n_i, k_i in zip(WAVELENGTHS, n, k, strict=True)])
    np.testing.assert_allclose(calculate_bare_substrate_R_absorbing(WAVELENGTHS, n, k, 1.0e6), expected[:, 0], rtol=0.0, atol=1e-8)
    np.testing.assert_allclose(calculate_bare_substrate_T_absorbing(WAVELENGTHS, n, k, 1.0e6), expected[:, 1], rtol=0.0, atol=1e-8)


def test_a_vanishing_denominator_gives_a_finite_answer():
    # an index of 0 reflects everything (R1 = 1) and a plate without absorption keeps it all: 1 - R1**2 * 1 = 0, the guard answers instead of a NaN
    reflectance = calculate_bare_substrate_R_absorbing(WAVELENGTHS, constant(0.0), constant(0.0), 1.0e6)
    transmittance = calculate_bare_substrate_T_absorbing(WAVELENGTHS, constant(0.0), constant(0.0), 1.0e6)
    assert np.all(np.isfinite(reflectance))
    assert np.all(np.isfinite(transmittance))
    np.testing.assert_allclose(reflectance, 1.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(transmittance, 0.0, rtol=0.0, atol=1e-12)
