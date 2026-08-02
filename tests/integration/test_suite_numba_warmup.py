import pytest
import numpy as np

# Skip test if certus_physics is missing
try:
    from certus_physics import calculate_RT_vectorized_real
    from certus.core.certus_core import get_float_dtype, get_complex_dtype
    PHYSICS_AVAILABLE = True
except ImportError:
    PHYSICS_AVAILABLE = False

@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="certus_physics non disponible")
def test_numba_jit_warmup():
    """
    Test that Numba JIT functions compile and execute successfully.
    This prevents 'TypingError' at runtime during heavy optimization loops.
    """
    float_dtype = get_float_dtype()
    complex_dtype = get_complex_dtype()
    
    # Dummy data
    lambda_array = np.array([400.0, 500.0, 600.0], dtype=float_dtype)
    n_sub_array = np.array([1.5, 1.5, 1.5], dtype=float_dtype)
    k_sub_array = np.array([0.0, 0.0, 0.0], dtype=float_dtype)
    
    # Layers (n_array, k_array, thickness)
    thicknesses = np.array([100.0], dtype=float_dtype)
    n_layers_all_wls = np.array([[1.45], [1.45], [1.45]], dtype=complex_dtype)  # (n_wls, n_layers)
    n_substrate_all_wls = np.array([1.5, 1.5, 1.5], dtype=complex_dtype) # (n_wls,)
    wls = np.array([400.0, 500.0, 600.0], dtype=float_dtype)
    
    # Calculate RT
    try:
        R, T = calculate_RT_vectorized_real(
            thicknesses=thicknesses,
            n_layers_all_wls=n_layers_all_wls,
            n_substrate_all_wls=n_substrate_all_wls,
            wls=wls,
            with_backside=False
        )
    except Exception as e:
        pytest.fail(f"Numba JIT compilation or execution failed: {e}")
    
    # Ensure shape is correct and no NaNs
    assert R.shape == lambda_array.shape
    assert T.shape == lambda_array.shape
    assert not np.any(np.isnan(R))
    assert not np.any(np.isnan(T))
