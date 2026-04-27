"""Track B (P1-12): direct numeric coverage for TMM core."""

from __future__ import annotations

import numpy as np
import pytest


def test_b4_tmm_empty_stack_matches_single_interface():
    """Empty multilayer stack should reduce to Air/Sub interface Fresnel values."""
    from _certus_physics_impl import compute_TMM_single_point_k0

    wl_nm = 550.0
    k0 = 2.0 * np.pi / wl_nm
    thicknesses = np.array([], dtype=np.float64)
    n_layers = np.array([], dtype=np.complex128)
    n_sub = 1.5 + 0.0j

    r, t = compute_TMM_single_point_k0(k0, thicknesses, n_layers, n_sub)

    assert r == pytest.approx(0.04, abs=1e-12)
    assert t == pytest.approx(0.96, abs=1e-12)
    assert (r + t) == pytest.approx(1.0, abs=1e-12)


def test_b4_tmm_exact_empty_stack_matches_front_and_back_interface_values():
    """Exact empty-stack TMM should expose the same interface reflectance both ways."""
    from _certus_physics_impl import compute_TMM_single_point_k0_exact

    wl_nm = 550.0
    k0 = 2.0 * np.pi / wl_nm
    thicknesses = np.array([], dtype=np.float64)
    n_layers = np.array([], dtype=np.complex128)
    n_sub = 1.5 + 0.0j

    r_f, t_f, r_b = compute_TMM_single_point_k0_exact(
        k0,
        thicknesses,
        n_layers,
        n_sub,
    )

    assert r_f == pytest.approx(0.04, abs=1e-12)
    assert t_f == pytest.approx(0.96, abs=1e-12)
    assert r_b == pytest.approx(0.04, abs=1e-12)
    assert (r_f + t_f) == pytest.approx(1.0, abs=1e-12)


def test_b4_compute_rt_from_identity_matrix_matches_single_interface():
    """The R/T extractor should reduce to a bare Fresnel interface for M=I."""
    from _certus_physics_impl import compute_RT_from_matrix

    r, t = compute_RT_from_matrix(
        1.0 + 0.0j,
        0.0 + 0.0j,
        0.0 + 0.0j,
        1.0 + 0.0j,
        1.0 + 0.0j,
        1.5 + 0.0j,
    )

    assert r == pytest.approx(0.04, abs=1e-12)
    assert t == pytest.approx(0.96, abs=1e-12)
    assert (r + t) == pytest.approx(1.0, abs=1e-12)


def test_b4_compute_rt_from_matrix_zeroes_transmission_for_near_zero_incident_real_part():
    """The low-level R/T extractor should clamp T to zero when Re(n_inc) is tiny."""
    from _certus_physics_impl import compute_RT_from_matrix

    r, t = compute_RT_from_matrix(
        1.0 + 0.0j,
        0.0 + 0.0j,
        0.0 + 0.0j,
        1.0 + 0.0j,
        1e-12 + 0.5j,
        1.5 + 0.0j,
    )

    assert r == pytest.approx(1.0, abs=5e-12)
    assert t == pytest.approx(0.0, abs=1e-12)


def test_b4_compute_rt_from_matrix_returns_zeros_when_system_admittance_cancels():
    """The low-level R/T extractor should fail safely when the denominator vanishes."""
    from _certus_physics_impl import compute_RT_from_matrix

    r, t = compute_RT_from_matrix(
        1.0 + 0.0j,
        0.0 + 0.0j,
        0.0 + 0.0j,
        1.0 + 0.0j,
        1.0 + 0.0j,
        -1.0 + 0.0j,
    )

    assert r == pytest.approx(0.0, abs=1e-12)
    assert t == pytest.approx(0.0, abs=1e-12)
