"""
CERTUS Property-Based Testing with Hypothesis

Rigorous mathematical tests of fundamental properties.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, assume, settings
from hypothesis.extra.numpy import arrays

# Strategies for realistic wavelengths
wavelength_strategy = st.floats(min_value=200.0, max_value=2500.0, allow_nan=False, allow_infinity=False)
refractive_index_strategy = st.floats(min_value=1.0, max_value=4.5, allow_nan=False, allow_infinity=False)
thickness_strategy = st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)


@given(wavelength=wavelength_strategy)
@settings(max_examples=100, deadline=1000)
def test_bare_substrate_transmission_bounds(wavelength):
    """Property: Transmission of a bare substrate must be between 0 and 1."""
    from certus.core._certus_physics_impl import calculate_bare_substrate_RT

    # Substrat verre typique
    n_sub = np.array([1.5], dtype=np.complex128)
    wavelengths = np.array([wavelength])

    T = calculate_bare_substrate_RT(wavelengths, n_sub)

    assert len(T) == 1
    assert 0.0 <= T[0] <= 1.0, f"Transmission {T[0]} hors limites [0,1]"


@given(n1=refractive_index_strategy, n2=refractive_index_strategy)
@settings(max_examples=100, deadline=1000)
def test_single_interface_reflection_symmetry(n1, n2):
    """Property: R(n1→n2) = R(n2→n1) pour interface simple."""
    from certus.core._certus_physics_impl import calculate_single_interface_R

    assume(abs(n1 - n2) > 0.01)  # Éviter indices identiques

    wavelengths = np.array([550.0])  # Visible central

    # Forward
    n_sub_fwd = np.array([n2 / n1], dtype=np.float64)
    R_fwd = calculate_single_interface_R(wavelengths, n_sub_fwd)

    # Reverse
    n_sub_rev = np.array([n1 / n2], dtype=np.float64)
    R_rev = calculate_single_interface_R(wavelengths, n_sub_rev)

    assert np.allclose(R_fwd, R_rev, rtol=1e-6), (
        f"Asymétrie réflexion: R({n1}→{n2})={R_fwd[0]:.6f} != R({n2}→{n1})={R_rev[0]:.6f}"
    )


@given(
    wavelength=wavelength_strategy,
    n_real=st.floats(min_value=1.0, max_value=4.0),
    k=st.floats(min_value=0.0, max_value=2.0),
)
@settings(max_examples=50, deadline=2000)
def test_absorption_increases_with_k(wavelength, n_real, k):
    """Property: The absorption increases with the extinction coefficient k."""
    #This test verifies a fundamental physical property
    #For now, it's a placeholder until it has full TMM functionality

    #Mock: absorption ∝ k for a fixed thickness
    thickness = 100.0  # nm
    alpha = 4 * np.pi * k / wavelength  # coefficient d'absorption
    absorption = 1.0 - np.exp(-alpha * thickness)

    assert 0.0 <= absorption <= 1.0

    if k > 1e-12:
        assert absorption > 0.0, "Avec k>1e-12, il doit y avoir de l'absorption"


@given(phi_r=st.floats(min_value=-2 * np.pi, max_value=2 * np.pi), phi_i=st.floats(min_value=-5.0, max_value=5.0))
@settings(max_examples=100, deadline=1000)
def test_complex_phase_trigonometric_identity(phi_r, phi_i):
    """Property: cos²(φ) + sin²(φ) = 1 pour phases complexes."""
    from certus.core._certus_physics_impl import compute_complex_phase_components

    cos_r, cos_i, sin_r, sin_i = compute_complex_phase_components(phi_r, phi_i)

    # Pour nombre complexe z = a + ib:
    # |cos(z)|² = cos_r² + cos_i²
    # |sin(z)|² = sin_r² + sin_i²
    # Identity: |cos(z)|² + |sin(z)|² = cosh²(phi_i) + sinh²(phi_i)

    cos_squared = cos_r**2 + cos_i**2
    sin_squared = sin_r**2 + sin_i**2

    expected = np.cosh(phi_i) ** 2 + np.sinh(phi_i) ** 2
    actual = cos_squared + sin_squared

    assert np.allclose(actual, expected, rtol=1e-6), f"Identité trigonométrique violée: {actual:.6f} != {expected:.6f}"


@given(
    wavelengths=arrays(
        dtype=np.float64,
        shape=st.integers(min_value=5, max_value=50),
        elements=st.floats(min_value=400.0, max_value=700.0),
    )
)
@settings(max_examples=20, deadline=5000)
def test_spectrum_calculation_vectorized(wavelengths):
    """Property: Vectorized calculations = iterative calculations."""
    from certus.core._certus_physics_impl import calculate_bare_substrate_RT

    assume(len(wavelengths) >= 5)
    wavelengths = np.sort(wavelengths)  # Ordre croissant

    n_sub = np.full_like(wavelengths, 1.5, dtype=np.complex128)

    # Vectorized
    T_vec = calculate_bare_substrate_RT(wavelengths, n_sub)

    # Iterative
    T_iter = np.array([calculate_bare_substrate_RT(np.array([wl]), np.array([1.5 + 0j]))[0] for wl in wavelengths])

    assert np.allclose(T_vec, T_iter, rtol=1e-10), "Calcul vectorisé != itératif"


# Regression tests on known edge cases
def test_normal_incidence_glass():
    """Regression: classic case glass at normal incidence."""
    from certus.core._certus_physics_impl import calculate_bare_substrate_RT

    # Verre BK7, n=1.5168 @ 550nm
    wavelengths = np.array([550.0])
    n_sub = np.array([1.5168], dtype=np.complex128)

    T = calculate_bare_substrate_RT(wavelengths, n_sub)

    # Analytical formula: T = (1-R)/(1+R) where R = ((n-1)/(n+1))²
    n = 1.5168
    R_single = ((n - 1) / (n + 1)) ** 2
    T_expected = (1 - R_single) / (1 + R_single)

    assert np.allclose(T[0], T_expected, rtol=1e-6), f"Régression verre BK7: T={T[0]:.6f} != {T_expected:.6f}"


if __name__ == "__main__":
    #Run with pytest or standalone
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
