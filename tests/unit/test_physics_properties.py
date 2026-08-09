import numpy as np
from hypothesis import given, settings, strategies as st

from certus.physics.certus_strat_batch import calculate_RT_batch_kernel

@settings(max_examples=100, deadline=None)
@given(
    d_h=st.floats(min_value=0.0, max_value=2000.0),
    d_l=st.floats(min_value=0.0, max_value=2000.0),
    n_h=st.floats(min_value=1.5, max_value=3.0),
    n_l=st.floats(min_value=1.0, max_value=2.0),
    n_sub=st.floats(min_value=1.0, max_value=3.0),
    wl=st.floats(min_value=300.0, max_value=2000.0),
)
def test_tmm_energy_conservation(d_h, d_l, n_h, n_l, n_sub, wl):
    """
    Checks the conservation of energy (R + T == 1) for a bi-layer
    transparent (H/L) sur un substrat transparent.
    """
    wls = np.array([wl], dtype=np.float64)
    nH_arr = np.array([n_h + 0j], dtype=np.complex128)
    nL_arr = np.array([n_l + 0j], dtype=np.complex128)
    nSub_arr = np.array([n_sub + 0j], dtype=np.complex128)
    
    #2 layers (H then L)
    thicknesses_batch = np.array([[d_h, d_l]], dtype=np.float64)
    
    R_batch, T_batch = calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, thicknesses_batch)
    
    R = float(R_batch[0, 0])
    T = float(T_batch[0, 0])
    
    #Conservation of energy (A = 0 because real indices)
    assert np.isclose(R + T, 1.0, atol=1e-12)
    assert -1e-12 <= R <= 1.0 + 1e-12
    assert -1e-12 <= T <= 1.0 + 1e-12

@settings(max_examples=50, deadline=None)
@given(
    d_base=st.floats(min_value=10.0, max_value=500.0),
    epsilon=st.floats(min_value=1e-5, max_value=1e-2),
)
def test_tmm_thickness_continuity(d_base, epsilon):
    """
    Check continuity: a small variation in thickness causes
    une petite variation de R et T.
    """
    wls = np.array([500.0], dtype=np.float64)
    nH_arr = np.array([2.0 + 0j], dtype=np.complex128)
    nL_arr = np.array([1.5 + 0j], dtype=np.complex128)
    nSub_arr = np.array([1.52 + 0j], dtype=np.complex128)
    
    # Batch de 2 : base vs base + epsilon
    thicknesses_batch = np.array([
        [d_base, d_base],
        [d_base + epsilon, d_base]
    ], dtype=np.float64)
    
    R_batch, T_batch = calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, thicknesses_batch)
    
    R_base = R_batch[0, 0]
    R_eps  = R_batch[1, 0]
    
    #The variation of R must be bounded by O(epsilon) (Lipschitzian)
    # L'ordre de grandeur de dR/dd est k0 * nH ~ 2*pi / 500 * 2 = 0.025
    #So delta R < 0.1 * epsilon
    assert abs(R_eps - R_base) < 0.2 * epsilon
