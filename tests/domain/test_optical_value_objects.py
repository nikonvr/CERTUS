"""
Property-Based Tests for Optical Domain Value Objects

Tests exhaustifs des invariants avec Hypothesis.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, assume, settings

from certus.domain.optical.value_objects import (
    Wavelength,
    WavelengthRange,
    Thickness,
    RefractiveIndex,
)


# ============================================================================
# Wavelength Tests
# ============================================================================


@given(nm=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=200, deadline=1000)
def test_wavelength_invariants(nm):
    """Property: Wavelength must respect physical bounds."""
    wl = Wavelength(nm)
    assert 100.0 <= wl.nm <= 10000.0
    assert np.isfinite(wl.nm)


@given(nm=st.floats(min_value=100.0, max_value=10000.0))
@settings(max_examples=100, deadline=1000)
def test_wavelength_unit_conversions_roundtrip(nm):
    """Property: Unit conversions must roundtrip exactly."""
    wl = Wavelength(nm)

    # nm → m → nm
    assert np.isclose(Wavelength.from_meters(wl.to_meters()).nm, nm, rtol=1e-10)

    # nm → µm → nm
    assert np.isclose(Wavelength.from_micrometers(wl.to_micrometers()).nm, nm, rtol=1e-10)

    # nm → Å → nm (via multiplication)
    angstroms = wl.to_angstroms()
    assert np.isclose(angstroms / 10.0, nm, rtol=1e-10)


@given(nm=st.floats(min_value=100.0, max_value=10000.0))
@settings(max_examples=100, deadline=1000)
def test_wavelength_energy_frequency_relation(nm):
    """Property: E = hν must hold (E·λ = hc)."""
    wl = Wavelength(nm)

    energy_ev = wl.energy_ev()
    frequency_hz = wl.frequency_hz()

    # E = hν where h = 4.135667696e-15 eV·s
    h_ev_s = 4.135667696e-15
    expected_energy = h_ev_s * frequency_hz

    assert np.isclose(energy_ev, expected_energy, rtol=1e-6), (
        f"Energy-frequency relation violated: {energy_ev} != {expected_energy}"
    )


@given(nm=st.floats(min_value=-1e6, max_value=-1.0) | st.floats(min_value=10001.0, max_value=1e6))
@settings(max_examples=50, deadline=1000)
def test_wavelength_rejects_invalid(nm):
    """Property: Invalid wavelengths must raise ValueError."""
    with pytest.raises(ValueError):
        Wavelength(nm)


def test_wavelength_rejects_nan_inf():
    """Property: NaN and Inf must be rejected."""
    with pytest.raises(ValueError):
        Wavelength(float("nan"))

    with pytest.raises(ValueError):
        Wavelength(float("inf"))


# ============================================================================
# WavelengthRange Tests
# ============================================================================


@given(min_nm=st.floats(min_value=100.0, max_value=5000.0), max_nm=st.floats(min_value=5001.0, max_value=10000.0))
@settings(max_examples=100, deadline=1000)
def test_wavelength_range_invariants(min_nm, max_nm):
    """Property: Range must have min < max."""
    wl_range = WavelengthRange(Wavelength(min_nm), Wavelength(max_nm))

    assert wl_range.min_wl.nm < wl_range.max_wl.nm
    assert wl_range.span_nm() > 0


@given(
    min_nm=st.floats(min_value=100.0, max_value=5000.0),
    max_nm=st.floats(min_value=5001.0, max_value=10000.0),
    test_nm=st.floats(min_value=100.0, max_value=10000.0),
)
@settings(max_examples=100, deadline=1000)
def test_wavelength_range_contains(min_nm, max_nm, test_nm):
    """Property: contains() must be consistent with bounds."""
    wl_range = WavelengthRange(Wavelength(min_nm), Wavelength(max_nm))
    test_wl = Wavelength(test_nm)

    expected = min_nm <= test_nm <= max_nm
    assert wl_range.contains(test_wl) == expected


@given(
    min_nm=st.floats(min_value=100.0, max_value=5000.0),
    max_nm=st.floats(min_value=5001.0, max_value=10000.0),
    num_points=st.integers(min_value=2, max_value=100),
)
@settings(max_examples=50, deadline=2000)
def test_wavelength_range_linspace(min_nm, max_nm, num_points):
    """Property: linspace must generate correct number of points."""
    wl_range = WavelengthRange(Wavelength(min_nm), Wavelength(max_nm))
    points = wl_range.linspace(num_points)

    assert len(points) == num_points
    assert points[0].nm == pytest.approx(min_nm, rel=1e-10)
    assert points[-1].nm == pytest.approx(max_nm, rel=1e-10)

    # Points must be monotonically increasing
    for i in range(len(points) - 1):
        assert points[i].nm < points[i + 1].nm


# ============================================================================
# Thickness Tests
# ============================================================================


@given(nm=st.floats(min_value=0.1, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=200, deadline=1000)
def test_thickness_invariants(nm):
    """Property: Thickness must be positive and bounded."""
    t = Thickness(nm)
    assert 0.0 < t.nm <= 100000.0
    assert np.isfinite(t.nm)


@given(nm=st.floats(min_value=0.1, max_value=100000.0))
@settings(max_examples=100, deadline=1000)
def test_thickness_unit_conversions_roundtrip(nm):
    """Property: Unit conversions must roundtrip."""
    t = Thickness(nm)

    # nm → m → nm
    assert np.isclose(Thickness.from_meters(t.to_meters()).nm, nm, rtol=1e-10)

    # nm → µm → nm
    assert np.isclose(Thickness.from_micrometers(t.to_micrometers()).nm, nm, rtol=1e-10)


@given(
    thickness_nm=st.floats(min_value=1.0, max_value=1000.0),
    n=st.floats(min_value=1.0, max_value=4.0),
    wavelength_nm=st.floats(min_value=400.0, max_value=700.0),
)
@settings(max_examples=100, deadline=1000)
def test_thickness_qwot_positive(thickness_nm, n, wavelength_nm):
    """Property: QWOT must always be positive."""
    t = Thickness(thickness_nm)
    qwot = t.qwot_at_wavelength(wavelength_nm, n)

    assert qwot > 0.0


@given(nm=st.floats(min_value=-1000.0, max_value=0.0))
@settings(max_examples=50, deadline=1000)
def test_thickness_rejects_non_positive(nm):
    """Property: Zero or negative thickness must be rejected."""
    with pytest.raises(ValueError):
        Thickness(nm)


# ============================================================================
# RefractiveIndex Tests
# ============================================================================


@given(
    n=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    k=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=1000)
def test_refractive_index_invariants(n, k):
    """Property: RI must satisfy n >= 1, k >= 0."""
    ri = RefractiveIndex(n, k)
    assert ri.n >= 1.0
    assert ri.k >= 0.0
    assert np.isfinite(ri.n)
    assert np.isfinite(ri.k)


@given(n=st.floats(min_value=1.0, max_value=4.0), k=st.floats(min_value=0.0, max_value=2.0))
@settings(max_examples=100, deadline=1000)
def test_refractive_index_to_complex_correct(n, k):
    """Propriete : to_complex() doit produire n - ik (convention Macleod du projet).

    L'assertion exigeait auparavant n + ik, verrouillant une convention opposee a
    that used throughout the rest of CERTUS (see CLAUDE.md §3). A value in
    n + ik injectee dans le TMM produit un milieu a gain, avec R + T > 1.
    """
    ri = RefractiveIndex(n, k)
    c = ri.to_complex()

    assert np.isclose(c.real, n, rtol=1e-15)
    assert np.isclose(c.imag, -k, rtol=1e-15)


@given(
    n=st.floats(min_value=1.0, max_value=4.0),
    k=st.floats(min_value=0.0, max_value=2.0),
    wavelength_nm=st.floats(min_value=400.0, max_value=700.0),
)
@settings(max_examples=100, deadline=1000)
def test_absorption_penetration_inverse(n, k, wavelength_nm):
    """Property: penetration depth = 1 / absorption coefficient."""
    assume(k > 1e-10)  # Avoid division by zero

    ri = RefractiveIndex(n, k)
    alpha = ri.absorption_coefficient(wavelength_nm)
    delta = ri.penetration_depth_nm(wavelength_nm)

    assert np.isclose(alpha * delta, 1.0, rtol=1e-10), f"α·δ = {alpha * delta} != 1.0"


@given(n=st.floats(min_value=1.0, max_value=4.0))
@settings(max_examples=100, deadline=1000)
def test_transparent_material_properties(n):
    """Property: Transparent materials (k=0) have infinite penetration depth."""
    ri = RefractiveIndex(n, 0.0)

    assert ri.is_transparent()
    assert not ri.is_absorbing()
    assert ri.penetration_depth_nm(550.0) == float("inf")


@given(n=st.floats(min_value=1.0, max_value=4.0), k=st.floats(min_value=0.0, max_value=2.0))
@settings(max_examples=100, deadline=1000)
def test_reflectance_bounds(n, k):
    """Property: Reflectance at normal incidence must be in [0, 1]."""
    ri = RefractiveIndex(n, k)
    R = ri.reflectance_normal_incidence()

    assert 0.0 <= R <= 1.0, f"Reflectance {R} out of bounds"


@given(n=st.floats(min_value=0.5, max_value=0.99))
@settings(max_examples=50, deadline=1000)
def test_refractive_index_rejects_n_less_than_1(n):
    """Property: n < 1.0 violates physics and must be rejected."""
    with pytest.raises(ValueError, match="violates physics"):
        RefractiveIndex(n, 0.0)


@given(k=st.floats(min_value=-10.0, max_value=-0.001))
@settings(max_examples=50, deadline=1000)
def test_refractive_index_rejects_negative_k(k):
    """Property: k < 0 must be rejected."""
    with pytest.raises(ValueError, match="must be >= 0"):
        RefractiveIndex(1.5, k)


# ============================================================================
# Integration Tests (Value Objects Interaction)
# ============================================================================


@given(
    thickness_nm=st.floats(min_value=10.0, max_value=500.0),
    n=st.floats(min_value=1.5, max_value=3.0),
    wavelength_nm=st.floats(min_value=400.0, max_value=700.0),
)
@settings(max_examples=50, deadline=2000)
def test_quarter_wave_stack_property(thickness_nm, n, wavelength_nm):
    """
    Property: A layer λ/4 at λ₀ has QWOT = 1.0.

    QWOT thickness: d = λ₀/(4n)
    """
    #Calculate thickness λ/4
    qwot_thickness_nm = wavelength_nm / (4 * n)

    #If we ask QWOT = 1, must give this thickness
    t = Thickness(qwot_thickness_nm)
    qwot_calculated = t.qwot_at_wavelength(wavelength_nm, n)

    assert np.isclose(qwot_calculated, 1.0, rtol=1e-10), f"λ/4 stack QWOT={qwot_calculated} != 1.0"


@given(
    n_real=st.floats(min_value=1.5, max_value=2.5),
    k=st.floats(min_value=0.001, max_value=0.5),
    thickness_nm=st.floats(min_value=10.0, max_value=500.0),
    wavelength_nm=st.floats(min_value=400.0, max_value=700.0),
)
@settings(max_examples=50, deadline=2000)
def test_absorption_reduces_transmission(n_real, k, thickness_nm, wavelength_nm):
    """
    Property: Plus k est grand, plus l'absorption est forte.

    Transmission through absorbing layer: T ∝ exp(-αd)
    where α = 4πk/λ
    """
    ri = RefractiveIndex(n_real, k)
    t = Thickness(thickness_nm)

    alpha = ri.absorption_coefficient(wavelength_nm)
    transmission_factor = np.exp(-alpha * thickness_nm)

    assert 0.0 < transmission_factor < 1.0, f"Transmission factor {transmission_factor} out of (0,1)"

    # Plus k grand → alpha grand → transmission faible
    if k > 0.1 and thickness_nm >= 150:  # k=0.25 needs >133nm for T<0.9
        assert transmission_factor < 0.9, f"High k={k} should give low transmission, got {transmission_factor}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
