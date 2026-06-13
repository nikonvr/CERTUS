import pytest
import numpy as np
from certus_physics import calculate_transmission_single

def test_calculate_transmission_single_zero_div_protection():
    """
    Test that calculate_transmission_single does not raise a ZeroDivisionError
    when parameters are chosen such that internal Yp_mag_sq becomes < 1e-25.
    (This tests the speculative execution fix for Numba njit).
    """
    wavelength = 500.0
    # Provide an extreme imaginary part to drive internal admittances to 0/infinity
    n_film_real = 1.5
    n_film_imag = 1e15
    thickness_nm = 100.0
    n_sub = complex(1.5, 0.0)

    # In the unfixed version, if Yp_mag_sq dropped below 1e-25, 
    # the T_prime computation outside the conditional threw ZeroDivisionError.
    # We just want to ensure this executes without raising an exception.
    R, T = calculate_transmission_single(
        wavelength,
        n_film_real,
        n_film_imag,
        thickness_nm,
        n_sub
    )
    
    # It should gracefully return values (possibly nan/0) instead of throwing.
    assert isinstance(R, float)
    assert isinstance(T, float)
