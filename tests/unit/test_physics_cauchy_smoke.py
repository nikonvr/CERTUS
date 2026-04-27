import numpy as np
import pytest
from _certus_physics_impl import get_nk_cauchy_wrapper

def test_cauchy_values_at_anchors():
    """Verify Cauchy model returns expected values at anchor points (400, 700 nm)."""
    lam = np.array([400.0, 550.0, 700.0])
    
    # Test case 1: constant n=1.5
    n = get_nk_cauchy_wrapper(1.5, 1.5, lam)
    np.testing.assert_allclose(n, 1.5)

    # Test case 2: normal dispersion
    # n_400 = 1.6, n_700 = 1.5
    n = get_nk_cauchy_wrapper(1.6, 1.5, lam)
    assert n[0] == 1.6
    assert n[2] == 1.5
    assert 1.5 < n[1] < 1.6
