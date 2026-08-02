import pytest
import numpy as np
from unittest.mock import MagicMock
from certus.core.certus_index_objectives import (
    _phase23_cached_get,
    _phase23_cached_set,
    Phase23SplineObjective,
)

def test_phase23_cached_get_set():
    cache = None
    x = np.array([1.0, 2.0])
    
    # Empty cache
    assert _phase23_cached_get(cache, x) is None
    
    # Set cache with cost
    cache = _phase23_cached_set(cache, x, cost=42.0)
    assert cache["cost"] == 42.0
    assert np.array_equal(cache["x"], x)
    
    # Get cache
    assert _phase23_cached_get(cache, x) == cache
    
    # Get with different shape
    assert _phase23_cached_get(cache, np.array([1.0])) is None
    
    # Get with different value
    assert _phase23_cached_get(cache, np.array([1.0, 3.0])) is None
    
    # Set with grad
    grad = np.array([0.1, 0.2])
    cache = _phase23_cached_set(cache, x, cost=42.0, grad=grad)
    assert np.array_equal(cache["grad"], grad)
    
class MockIRGlobalObjective:
    def __init__(self):
        self._wl_um_min = 0.4
        self._wl_um_max = 2.0
        self._wl_um_vis = np.array([0.5, 0.6])
        self._n_tlu_ref_vis = np.array([1.5, 1.5])
        self.n_tol = 0.1
        self.wl_um = np.array([0.5, 0.6, 1.0, 1.5])
        self.n_ref_global = None
        self.n_ref_tol = 0.1
        
    def _compute_cost(self, n, k):
        return 123.45

def test_phase23_spline_objective_pole_guard():
    base_obj = MockIRGlobalObjective()
    knot_lambda_um = np.array([0.5, 1.0, 1.5])
    k_max = 1.0
    
    obj = Phase23SplineObjective(base_obj, knot_lambda_um, k_max)
    
    # x = [p_sell(5), log_k_knot_values(num_knots)]
    # p_sell = [A, B, L1, C, L2]
    # If L1 or L2 is inside range [0.4, 2.0], returns 1e12
    x = np.array([1.0, 1.0, 1.0, 1.0, 3.0, 0.0, 0.0, 0.0]) # L1=1.0 is inside [0.4, 2.0]
    
    cost = obj(x)
    assert cost == 1e12
    
def test_phase23_spline_objective_vis_continuity():
    base_obj = MockIRGlobalObjective()
    knot_lambda_um = np.array([0.5, 1.0, 1.5])
    k_max = 1.0
    obj = Phase23SplineObjective(base_obj, knot_lambda_um, k_max)
    
    # Poles outside [0.4, 2.0]
    x = np.array([10.0, 1.0, 0.1, 1.0, 3.0, 0.0, 0.0, 0.0]) 
    # With A=10, the sellmeier equation will give n around sqrt(10) ~ 3.16 which is far from _n_tlu_ref_vis (1.5)
    # This should violate vis continuity (difference > 0.1)
    cost = obj(x)
    assert cost == 1e12

def test_phase23_spline_objective_caching():
    base_obj = MockIRGlobalObjective()
    knot_lambda_um = np.array([0.5, 1.0, 1.5])
    k_max = 1.0
    obj = Phase23SplineObjective(base_obj, knot_lambda_um, k_max)
    
    # valid values for n~1.5: 
    # n = sqrt(1 + A * w^2 / (w^2 - L1^2) + C * w^2 / (w^2 - L2^2))
    # Let A=1.25, L1=0.1, C=0, L2=3.0 -> n ~ sqrt(1 + 1.25) ~ sqrt(2.25) = 1.5
    x = np.array([2.25, 0.0, 0.1, 0.0, 3.0, -10.0, -10.0, -10.0])
    
    cost = obj(x)
    assert cost == 123.45
    
    # Check that it cached
    assert obj._cache is not None
    assert obj._cache["cost"] == 123.45
    
    # Call again should hit cache
    base_obj._compute_cost = MagicMock(return_value=999.0) # change to see if cache is used
    cost2 = obj(x)
    assert cost2 == 123.45 # returned from cache

