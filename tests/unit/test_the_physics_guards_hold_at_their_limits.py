"""The guards of three small physics modules hold at their limits, and say what they refuse.

`certus_inputs` (the door of the kernels), `certus_substrate_absorption` (the plate loss) and `certus_oblique_substrate`
(the exit admittance) were the pilot of the mutation runner (`scripts/mutation_pilot.py`, S3.6). On 2026-10-01 it
planted 124 faults in them, one at a time, and the existing tests saw 98. The 26 that got through were the honest list of
what no test said:

- the overflow limit itself (`PHASE_IMAG_OVERFLOW`, and the `2 pi` in front of it): every test used a layer far beyond it
  or far below it, so the limit could have been 701 or 1 049 and nothing failed;
- the sign of the absorption index (CERTUS writes `n - ik`: the guard takes `abs`, and the tests only ever used `n + ik`);
- the wavelength that counts (the shortest one) and the wavelength where a layer absorbs (only one of several);
- which layer the message names, the shapes the guard does not judge, a stack of one layer and one wavelength;
- the angle limit (90 accepted, 91 accepted by the mutant);
- the error messages, never read word for word;
- an exit medium whose index is below the sine of the incidence (evanescent: a purely imaginary admittance, usable);
- a substrate whose real index cannot carry the ray (nothing crosses it), a wavelength at or below zero.

What stays alive is named in `docs/ETAT.md`: equalities between two floats (`>` against `>=` at exactly 700.0, `<` against
`<=` at exactly 1e-12) that no input reaches, which are equivalent faults in practice.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from certus.physics.certus_inputs import (
    PHASE_IMAG_OVERFLOW,
    check_incidence_angle,
    is_s_polarization,
    require_finite,
    require_layers_below_overflow,
)
from certus.physics.certus_oblique_substrate import oblique_exit_admittance
from certus.physics.certus_substrate_absorption import plate_internal_transmittance, substrate_internal_transmittance

pytestmark = pytest.mark.kernels

WAVELENGTH = 500.0
K = 3.5


def _thickness_at(reach: float, k: float = K, wavelength: float = WAVELENGTH) -> float:
    """The thickness at which `2 pi k d / lambda` equals `reach`."""
    return reach * wavelength / (2.0 * math.pi * k)


def _stack(k: float, thickness: float, sign: float = -1.0):
    """One layer, one wavelength: (thicknesses, n_layers, wavelengths), with the CERTUS convention n - ik by default."""
    return np.array([thickness]), np.array([[1.5 + sign * 1j * k]]), np.array([WAVELENGTH])


# =============================================================================
# The overflow limit


def test_a_layer_just_below_the_overflow_limit_passes_and_just_above_it_is_refused():
    below = _stack(K, _thickness_at(PHASE_IMAG_OVERFLOW * 0.9995))
    above = _stack(K, _thickness_at(PHASE_IMAG_OVERFLOW * 1.0005))
    require_layers_below_overflow(*below)
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(*above)


def test_the_limit_is_the_documented_700():
    assert PHASE_IMAG_OVERFLOW == 700.0


@pytest.mark.parametrize("sign", [-1.0, 1.0])
def test_the_sign_of_the_absorption_index_does_not_matter(sign):
    """CERTUS writes n - ik (Im n < 0); the guard reads |Im n|, so both signs are refused."""
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(*_stack(7.0, 12000.0, sign=sign))


def test_a_negative_thickness_counts_by_its_size():
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(*_stack(7.0, -12000.0))


def test_one_absorbing_wavelength_among_transparent_ones_is_enough():
    n = np.array([[1.5 + 0j], [1.5 - 7j], [1.5 + 0j]])
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(np.array([12000.0]), n, np.array([500.0, 500.0, 500.0]))


def test_the_shortest_wavelength_decides():
    """`2 pi k d / lambda` is largest at the shortest wavelength: a layer opaque at 300 nm but not at 900 nm is opaque."""
    d = 1.5 * _thickness_at(PHASE_IMAG_OVERFLOW, wavelength=300.0)
    n = np.array([[1.5 - 1j * K], [1.5 - 1j * K]])
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(np.array([d]), n, np.array([300.0, 900.0]))
    require_layers_below_overflow(np.array([d]), n, np.array([900.0, 1100.0]))


def test_the_message_names_the_layer_that_absorbs_most_and_says_why():
    n = np.array([[1.5 - 0.1j, 1.5 - 7j, 1.5 - 0.1j]])
    d = np.array([100.0, 12000.0, 100.0])
    expected = (
        r"^layer 1 absorbs too much for a stack calculation \(\|Im phase\| = \d+, beyond 700\): "
        r"it is opaque, and the kernel would answer \(R, T\) = \(0, 0\)$"
    )
    with pytest.raises(ValueError, match=expected):
        require_layers_below_overflow(d, n, np.array([500.0]))


def test_a_stack_of_one_layer_and_one_wavelength_is_judged():
    """The smallest stack that exists is not a shape the guard skips."""
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(*_stack(7.0, 12000.0))


def test_shapes_the_guard_does_not_judge_are_left_to_the_callers():
    huge = np.array([12000.0, 12000.0, 12000.0])
    wls = np.array([500.0])
    assert require_layers_below_overflow(huge, np.array([1.5 - 7j, 1.5 - 7j, 1.5 - 7j]), wls) is None  # one dimension
    assert require_layers_below_overflow(huge, np.array([[1.5 - 7j, 1.5 - 7j]]), wls) is None  # two layers, three thicknesses
    assert require_layers_below_overflow(huge, np.empty((0, 3), dtype=complex), wls) is None  # no wavelength


# =============================================================================
# The error messages, word for word


def test_a_wrong_polarization_is_named_in_the_error():
    with pytest.raises(ValueError, match=r"^polarization must be 's' or 'p' \(TE / TM\), got 'Avg'$"):
        is_s_polarization("Avg")


def test_an_angle_that_is_not_a_number_is_named_in_the_error():
    with pytest.raises(ValueError, match=r"^angle of incidence must be a number of degrees, got 'abc'$"):
        check_incidence_angle("abc")


def test_a_nan_angle_is_named_in_the_error():
    with pytest.raises(ValueError, match=r"^angle of incidence must be finite, got nan$"):
        check_incidence_angle(float("nan"))


@pytest.mark.parametrize("angle", [90.5, -90.5, 95, 180])
def test_an_angle_beyond_grazing_is_refused_and_named(angle):
    with pytest.raises(ValueError, match=rf"^angle of incidence must lie between -90 and 90 degrees, got {angle}$"):
        check_incidence_angle(angle)


@pytest.mark.parametrize("angle", [90.0, -90.0, 0.0, 89.999999])
def test_grazing_itself_is_accepted(angle):
    assert check_incidence_angle(angle) == angle


def test_a_non_finite_array_is_named_in_the_error():
    with pytest.raises(ValueError, match=r"^thicknesses must be finite \(no NaN, no infinity\)$"):
        require_finite(thicknesses=np.array([1.0, np.nan]))


# =============================================================================
# The plate loss


def test_a_wavelength_at_or_below_zero_lets_nothing_through():
    for wavelength in (0.0, -500.0):
        assert substrate_internal_transmittance(1e-6, wavelength, 1.0e6, 1.0) == 0.0


def test_a_very_short_positive_wavelength_follows_the_formula():
    """Below 1 nm there is no physics here, but the guard is `<= 0`, not `<= 1`: the formula answers."""
    expected = math.exp(-4.0 * math.pi * 1e-12 * 1.0e6 / (0.5 * 1.0))
    assert substrate_internal_transmittance(1e-12, 0.5, 1.0e6, 1.0) == pytest.approx(expected, rel=1e-12)


def test_a_substrate_whose_real_index_cannot_carry_the_ray_lets_nothing_through():
    """A real part of 0 (or of the order of the guard): the angle in the substrate does not exist, nothing crosses."""
    n_sub = np.array([0.0 - 1e-7j])
    tau = plate_internal_transmittance(n_sub, np.array([500.0]), 0.0, 1.0e6)
    assert tau[0] == 0.0


# =============================================================================
# The exit admittance at oblique incidence


def test_an_exit_medium_below_the_sine_of_the_incidence_is_evanescent_and_usable():
    """n = 0.5 under 60 degrees: sin theta = 1.73, cos theta = 1.41i, the p admittance n / cos theta = -0.354i, usable."""
    sin_air = math.sin(math.radians(60.0))
    eta, usable = oblique_exit_admittance(0.5 + 0j, sin_air, False)
    assert usable
    cos_t = np.sqrt(1.0 - (sin_air / 0.5) ** 2 + 0j)
    assert eta == pytest.approx(0.5 / cos_t, rel=1e-12)
    assert abs(eta) == pytest.approx(0.5 / math.sqrt((sin_air / 0.5) ** 2 - 1.0), rel=1e-12)


def test_the_s_admittance_of_the_same_medium_is_n_cos_theta():
    sin_air = math.sin(math.radians(60.0))
    eta, usable = oblique_exit_admittance(0.5 + 0j, sin_air, True)
    assert usable
    assert eta == pytest.approx(0.5 * np.sqrt(1.0 - (sin_air / 0.5) ** 2 + 0j), rel=1e-12)
