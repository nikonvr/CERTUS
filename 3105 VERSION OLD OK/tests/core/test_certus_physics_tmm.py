import pytest
import numpy as np
from certus.core._certus_physics_impl import (
    calculate_bare_substrate_RT,
    calculate_single_interface_R,
    compute_complex_phase_components,
)

def test_calculate_bare_substrate_RT():
    wavelengths = np.array([400.0, 500.0])
    
    # Substrate index n=1.5
    # r = (1 - 1.5) / (1 + 1.5) = -0.5 / 2.5 = -0.2
    # R_single = 0.04
    # T = (1 - 0.04) / (1 + 0.04) = 0.96 / 1.04 = 0.9230769
    
    n_sub = np.array([1.5, 1.5], dtype=np.complex128)
    T = calculate_bare_substrate_RT(wavelengths, n_sub)
    
    assert len(T) == 2
    assert np.allclose(T, 0.9230769230769231)

def test_calculate_single_interface_R():
    wavelengths = np.array([400.0, 500.0])
    
    # Frosted glass, n=1.5
    # R_single = 0.04
    n_sub = np.array([1.5, 1.5], dtype=np.float64)
    R = calculate_single_interface_R(wavelengths, n_sub)
    
    assert len(R) == 2
    assert np.allclose(R, 0.04)

def test_compute_complex_phase_components():
    phi_r = np.pi / 2  # 90 degrees
    phi_i = 0.0        # No absorption
    
    cos_phi_r, cos_phi_i, sin_phi_r, sin_phi_i = compute_complex_phase_components(phi_r, phi_i)
    
    assert np.isclose(cos_phi_r, 0.0, atol=1e-10)
    assert np.isclose(cos_phi_i, 0.0, atol=1e-10)
    assert np.isclose(sin_phi_r, 1.0)
    assert np.isclose(sin_phi_i, 0.0, atol=1e-10)
    
    # With absorption
    phi_i_abs = 1.0
    cos2_r, cos2_i, sin2_r, sin2_i = compute_complex_phase_components(phi_r, phi_i_abs)
    
    # exp(1) = 2.718, exp(-1) = 0.367
    # cos_phi_real = cos(pi/2) * ... = 0
    # cos_phi_imag = sin(pi/2) * (exp(-1) - exp(1)) / 2 = (0.367 - 2.718)/2 = -1.175
    # sin_phi_real = sin(pi/2) * (exp(-1) + exp(1)) / 2 = (0.367 + 2.718)/2 = 1.543
    # sin_phi_imag = cos(pi/2) * ... = 0
    
    assert np.isclose(cos2_r, 0.0, atol=1e-10)
    assert cos2_i < 0.0 # Negative imaginary part for Macleod convention
    assert sin2_r > 1.0 # Hyperbolic cosine factor
    assert np.isclose(sin2_i, 0.0, atol=1e-10)
