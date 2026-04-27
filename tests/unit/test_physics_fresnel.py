"""Track B (P1-12): minimal Fresnel-oriented coverage on physics core.

Roadmap wording mentions ``fresnel_equations``; in the current codebase the
equivalent low-level entry point is ``calculate_reflection_single``.
"""

from __future__ import annotations

import numpy as np
import pytest


def test_b2_import_physics_core_fresnel_entrypoint():
    """B.2: smoke import of the low-level Fresnel computation entry point."""
    from _certus_physics_impl import calculate_reflection_single

    assert callable(calculate_reflection_single)


def test_b3_normal_incidence_interface_reflectance():
    """B.3: numeric check against Fresnel closed-form for n0=1, n1=1.5.

    For a zero-thickness layer, the stack reduces to a single interface and
    reflectance should be ((n0-n1)/(n0+n1))^2 = 0.04.
    """
    from _certus_physics_impl import calculate_reflection_single

    wl_nm = 550.0
    n = 1.5
    r = calculate_reflection_single(
        wl_nm,
        n_film_real=n,
        n_film_imag=0.0,
        thickness_nm=0.0,
        n_sub=n,
    )

    assert r == pytest.approx(0.04, abs=1e-12)


def test_b3_infinite_substrate_zero_thickness_matches_single_interface():
    """Infinite-substrate path should reduce to Fresnel at zero film thickness."""
    from _certus_physics_impl import calculate_reflection_infinite_substrate_single

    r = calculate_reflection_infinite_substrate_single(
        wavelength=550.0,
        n_film_real=1.5,
        n_film_imag=0.0,
        thickness_nm=0.0,
        n_sub=1.5 + 0.0j,
    )

    assert r == pytest.approx(0.04, abs=1e-12)


def test_b3_infinite_substrate_array_matches_single_kernel():
    """Vectorized infinite-substrate reflection should match pointwise evaluation."""
    from _certus_physics_impl import (
        calculate_reflection_infinite_substrate_array,
        calculate_reflection_infinite_substrate_single,
    )

    wavelengths = np.array([450.0, 550.0, 650.0], dtype=np.float64)
    n_array = np.array([1.45, 1.5, 1.55], dtype=np.float64)
    k_array = np.zeros(3, dtype=np.float64)
    n_substrate = np.array([1.52 + 0.0j, 1.52 + 0.0j, 1.52 + 0.0j], dtype=np.complex128)

    batch = calculate_reflection_infinite_substrate_array(
        wavelengths,
        n_array,
        k_array,
        thickness=120.0,
        n_substrate=n_substrate,
    )
    pointwise = np.array(
        [
            calculate_reflection_infinite_substrate_single(wl, n, k, 120.0, ns)
            for wl, n, k, ns in zip(wavelengths, n_array, k_array, n_substrate, strict=False)
        ],
        dtype=np.float64,
    )

    assert np.allclose(batch, pointwise, atol=1e-12, rtol=0.0)


def test_b3_reflection_array_matches_single_kernel():
    """Vectorized single-layer reflection should match pointwise evaluation."""
    from _certus_physics_impl import calculate_reflection_array, calculate_reflection_single

    wavelengths = np.array([450.0, 550.0, 650.0], dtype=np.float64)
    n_array = np.array([1.45, 1.5, 1.55], dtype=np.float64)
    k_array = np.array([0.0, 0.01, 0.02], dtype=np.float64)
    n_substrate = np.array([1.52, 1.52, 1.52], dtype=np.float64)

    batch = calculate_reflection_array(
        wavelengths,
        n_array,
        k_array,
        thickness=120.0,
        n_substrate=n_substrate,
    )
    pointwise = np.array(
        [
            calculate_reflection_single(wl, n, k, 120.0, ns)
            for wl, n, k, ns in zip(wavelengths, n_array, k_array, n_substrate, strict=False)
        ],
        dtype=np.float64,
    )

    assert np.allclose(batch, pointwise, atol=1e-12, rtol=0.0)


def test_b3_complex_phase_components_reduce_to_standard_trig_without_absorption():
    """With phi_i=0, the complex-phase helper should reduce to standard trig."""
    from _certus_physics_impl import compute_complex_phase_components

    phi_r = np.pi / 3.0
    cos_real, cos_imag, sin_real, sin_imag = compute_complex_phase_components(phi_r, 0.0)

    assert cos_real == pytest.approx(np.cos(phi_r), abs=1e-12)
    assert cos_imag == pytest.approx(0.0, abs=1e-12)
    assert sin_real == pytest.approx(np.sin(phi_r), abs=1e-12)
    assert sin_imag == pytest.approx(0.0, abs=1e-12)


def test_b3_reflection_array_returns_nan_for_invalid_substrate_entries():
    """Invalid substrate indices should propagate as NaN in the vectorized kernel."""
    from _certus_physics_impl import calculate_reflection_array

    result = calculate_reflection_array(
        np.array([450.0, 550.0], dtype=np.float64),
        np.array([1.45, 1.50], dtype=np.float64),
        np.array([0.0, 0.0], dtype=np.float64),
        thickness=120.0,
        n_substrate=np.array([1.52, 0.95], dtype=np.float64),
    )

    assert np.isfinite(result[0])
    assert np.isnan(result[1])


def test_b3_reflection_single_returns_nan_for_invalid_substrate():
    """The scalar reflection kernel should fail safely on invalid substrate index."""
    from _certus_physics_impl import calculate_reflection_single

    result = calculate_reflection_single(
        wavelength=550.0,
        n_film_real=1.5,
        n_film_imag=0.0,
        thickness_nm=120.0,
        n_sub=0.95,
    )

    assert np.isnan(result)


def test_b3_reflection_single_returns_nan_for_zero_film_index_magnitude():
    """The scalar reflection kernel should fail safely when |n_film| is zero."""
    from _certus_physics_impl import calculate_reflection_single

    result = calculate_reflection_single(
        wavelength=550.0,
        n_film_real=0.0,
        n_film_imag=0.0,
        thickness_nm=120.0,
        n_sub=1.52,
    )

    assert np.isnan(result)


def test_b3_transmission_array_matches_single_kernel():
    """Vectorized transmission should match pointwise scalar transmission."""
    from _certus_physics_impl import calculate_transmission_array, calculate_transmission_single

    wavelengths = np.array([450.0, 550.0, 650.0], dtype=np.float64)
    n_array = np.array([1.45, 1.5, 1.55], dtype=np.float64)
    k_array = np.array([0.0, 0.01, 0.02], dtype=np.float64)
    n_substrate = np.array([1.52, 1.52, 1.52], dtype=np.float64)

    batch = calculate_transmission_array(
        wavelengths,
        n_array,
        k_array,
        thickness=120.0,
        n_substrate=n_substrate,
    )
    pointwise = np.array(
        [
            calculate_transmission_single(wl, n, k, 120.0, ns)
            for wl, n, k, ns in zip(wavelengths, n_array, k_array, n_substrate, strict=False)
        ],
        dtype=np.float64,
    )

    assert np.allclose(batch, pointwise, atol=1e-12, rtol=0.0)


def test_b3_transmission_array_returns_nan_for_invalid_substrate_entries():
    """Invalid substrate indices should propagate as NaN in transmission vector kernel."""
    from _certus_physics_impl import calculate_transmission_array

    result = calculate_transmission_array(
        np.array([450.0, 550.0], dtype=np.float64),
        np.array([1.45, 1.50], dtype=np.float64),
        np.array([0.0, 0.0], dtype=np.float64),
        thickness=120.0,
        n_substrate=np.array([1.52, 0.95], dtype=np.float64),
    )

    assert np.isfinite(result[0])
    assert np.isnan(result[1])


def test_b3_transmission_single_returns_nan_for_invalid_substrate():
    """Scalar transmission kernel should fail safely on invalid substrate index."""
    from _certus_physics_impl import calculate_transmission_single

    result = calculate_transmission_single(
        wavelength=550.0,
        n_film_real=1.5,
        n_film_imag=0.0,
        thickness_nm=120.0,
        n_sub=0.95,
    )

    assert np.isnan(result)
