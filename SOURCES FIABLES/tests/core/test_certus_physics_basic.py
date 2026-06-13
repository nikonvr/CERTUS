import pytest
import numpy as np
from certus.core._certus_physics_impl import (
    sellmeier_n_array,
    get_nk_cauchy,
    get_nk_cauchy_wrapper,
    get_nk_cauchy_simple,
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
)

def test_sellmeier_n_array():
    wls = np.array([100.0, 500.0, 1000.0]) # 100 is below min_wl
    
    # Random realistic coefficients
    B1, C1 = 1.0, 0.01
    B2, C2 = 0.5, 0.02
    B3, C3 = 1.0, 100.0
    min_wl = 200.0
    
    n_res = sellmeier_n_array(wls, B1, C1, B2, C2, B3, C3, min_wl)
    
    assert len(n_res) == 3
    # At 100.0 nm (below min_wl), it should return 1.0
    assert np.isclose(n_res[0], 1.0)
    
    # At 500.0 nm, it should be > 1.0
    assert n_res[1] > 1.0
    assert n_res[2] > 1.0

def test_cauchy_models():
    wls = np.array([0.5, 500.0, 600.0])
    
    n4 = 1.5  # n at 400nm
    n7 = 1.4  # n at 700nm
    
    res = get_nk_cauchy(n4, n7, wls)
    assert len(res) == 3
    
    # Below 1.0nm, should return A
    assert np.isfinite(res[0])
    assert res[1] > res[2] # Normal dispersion (n decreases with wl)

    res_wrapper = get_nk_cauchy_wrapper(n4, n7, wls)
    np.testing.assert_array_equal(res, res_wrapper)
    
    n_simple = get_nk_cauchy_simple(500.0, 1.4, 0.01)
    assert n_simple > 1.4

def test_tlu_epsilon():
    E_array = np.array([1.0, 2.0, 3.0, 4.0])
    Eg = 2.5
    A = 100.0
    E0 = 3.5
    C = 1.0
    Eu = 0.1
    eps_inf = 1.0
    
    eps2 = epsilon2_TLU_array(E_array, Eg, A, E0, C, Eu)
    assert len(eps2) == 4
    assert np.all(eps2 >= 0.0) # eps2 must be positive
    
    # Below Eg (but close), eps2 > 0 due to Urbach tail
    assert eps2[1] > 0.0
    
    # Above Eg
    assert eps2[2] > 0.0
    
    eps1 = epsilon1_TL_analytic(E_array, Eg, A, E0, C, eps_inf)
    assert len(eps1) == 4
    assert np.all(np.isfinite(eps1))
