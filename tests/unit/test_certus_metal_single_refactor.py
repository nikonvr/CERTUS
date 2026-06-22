import pytest
import numpy as np

# Mock implementation of get_nk_from_spline if not available directly for test
# We'll just import it from the module
from CERTUS_METAL_SINGLE import elevate_spline_knots, _single_RTRback_mse

def test_elevate_spline_knots_linear():
    """
    Test that projecting a linear spline (2 knots) to 3 knots
    results in a correctly interpolated midpoint.
    """
    l_min = 400.0
    l_max = 1200.0
    
    # 2 knots: eM=10.0, n=[1.0, 2.0], k=[0.5, 1.5]
    x_old = np.array([10.0, 1.0, 2.0, 0.5, 1.5])
    
    x_new = elevate_spline_knots(x_old, 2, l_min, l_max)
    
    # Expected with 1/lambda logic:
    # f = [1/400, 1/1200] -> mid is 1/600. New lambda = 600.0
    # n at 600 is 1.25 (linear interpolation between 400 and 1200)
    # k at 600 is 0.75
    assert np.isclose(x_new[0], 10.0) # eM
    
    # n values
    assert np.isclose(x_new[1], 1.0)
    assert np.isclose(x_new[2], 1.25)
    assert np.isclose(x_new[3], 2.0)
    
    # k values
    assert np.isclose(x_new[4], 0.5)
    assert np.isclose(x_new[5], 0.75)
    assert np.isclose(x_new[6], 1.5)
    
    # internal lambda
    assert np.isclose(x_new[7], 600.0)

def test_elevate_spline_knots_quadratic():
    """
    Test projecting from 3 knots to 4 knots.
    """
    l_min = 400.0
    l_max = 1000.0
    
    # 3 knots: eM=10.0
    # n = [1.0, 2.0, 1.0]
    # k = [0.5, 1.0, 0.5]
    # lambda = [700.0]
    x_old = np.array([10.0, 1.0, 2.0, 1.0, 0.5, 1.0, 0.5, 700.0])
    
    x_new = elevate_spline_knots(x_old, 3, l_min, l_max)
    
    # New should have 4 knots
    # n = 4 values, k = 4 values, lambda = 2 values
    # Total length: 1 (eM) + 4 (n) + 4 (k) + 2 (lambda) = 11
    assert len(x_new) == 11
    assert np.isclose(x_new[0], 10.0)
    
    # new lambdas are injected in the largest gap in 1/lambda space
    # l_old = [400, 700, 1000]
    # f_old = [1/400, 1/700, 1/1000] = [0.0025, 0.001428, 0.001]
    # f_diffs = [0.00107, 0.000428]
    # argmax is 0, so it injects at (0.0025 + 0.001428)/2 = 0.001964
    # 1 / 0.001964 = 509.090909...
    assert np.isclose(x_new[-2], 509.09090909090907)
    assert np.isclose(x_new[-1], 700.0)
    
    # n at 400 is 1.0
    assert np.isclose(x_new[1], 1.0)
    # n at 1000 is 1.0
    assert np.isclose(x_new[4], 1.0)
