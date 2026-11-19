"""Internal layer at exact critical angle (cos_theta_layer == 0) is continuous with neighboring angles (m4)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_tmm_oblique import (
    _calc_spectrum_oblique_parallel,
    _oblique_stack_rt_single,
    oblique_front_char_matrix_single,
)


@pytest.mark.parametrize("is_s_pol", [True, False])
def test_calc_spectrum_oblique_parallel_is_continuous_at_internal_layer_critical_angle(is_s_pol: bool) -> None:
    wls = np.array([550.0], dtype=np.float64)
    d = np.array([50.0], dtype=np.float64)
    n_sub = np.array([1.52 + 0.0j], dtype=np.complex128)
    angle_deg = 45.0
    n_crit = np.sin(np.deg2rad(angle_deg))

    r_crit, t_crit = _calc_spectrum_oblique_parallel(
        wls, np.array([[n_crit + 0.0j]], dtype=np.complex128), d, n_sub, angle_deg, is_s_pol
    )
    r_plus, t_plus = _calc_spectrum_oblique_parallel(
        wls, np.array([[n_crit + 1e-6 + 0.0j]], dtype=np.complex128), d, n_sub, angle_deg, is_s_pol
    )
    r_minus, t_minus = _calc_spectrum_oblique_parallel(
        wls, np.array([[n_crit - 1e-6 + 0.0j]], dtype=np.complex128), d, n_sub, angle_deg, is_s_pol
    )

    assert t_crit[0] > 0.1
    assert abs(r_crit[0] + t_crit[0] - 1.0) < 1e-12
    assert abs(r_crit[0] - r_plus[0]) < 1e-4
    assert abs(t_crit[0] - t_plus[0]) < 1e-4
    assert abs(r_crit[0] - r_minus[0]) < 1e-4
    assert abs(t_crit[0] - t_minus[0]) < 1e-4


@pytest.mark.parametrize("is_s_pol", [True, False])
def test_oblique_stack_rt_single_is_continuous_at_internal_layer_critical_angle(is_s_pol: bool) -> None:
    wl = 550.0
    d = np.array([50.0], dtype=np.float64)
    angle_deg = 45.0
    sin_a = float(np.sin(np.deg2rad(angle_deg)))
    cos_a = float(np.cos(np.deg2rad(angle_deg)))

    r_crit, t_crit = _oblique_stack_rt_single(
        wl, np.array([sin_a + 0.0j], dtype=np.complex128), d, sin_a, cos_a, 1.0, 1.52, is_s_pol
    )
    r_plus, t_plus = _oblique_stack_rt_single(
        wl, np.array([sin_a + 1e-6 + 0.0j], dtype=np.complex128), d, sin_a, cos_a, 1.0, 1.52, is_s_pol
    )

    assert t_crit > 0.1
    assert abs(r_crit + t_crit - 1.0) < 1e-12
    assert abs(r_crit - r_plus) < 1e-4
    assert abs(t_crit - t_plus) < 1e-4


@pytest.mark.parametrize("is_s_pol", [True, False])
def test_oblique_front_char_matrix_single_is_continuous_at_internal_layer_critical_angle(is_s_pol: bool) -> None:
    wl = 550.0
    d = np.array([50.0], dtype=np.float64)
    sin_a = 1.38
    cos_a = 0.5

    m_crit = np.array(
        oblique_front_char_matrix_single(
            wl, np.array([1.38 + 0.0j], dtype=np.complex128), d, sin_a, cos_a, is_s_pol
        )
    )
    m_plus = np.array(
        oblique_front_char_matrix_single(
            wl, np.array([1.38 + 1e-6 + 0.0j], dtype=np.complex128), d, sin_a, cos_a, is_s_pol
        )
    )

    assert not np.allclose(m_crit, np.array([1.0, 0.0, 0.0, 1.0]))
    np.testing.assert_allclose(m_crit, m_plus, atol=1e-4, rtol=1e-4)
