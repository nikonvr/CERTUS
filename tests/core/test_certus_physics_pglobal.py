import pytest
import numpy as np
from certus.core._certus_physics_impl import make_cost_function

def test_make_cost_function_creates_callable():
    wls = np.array([400.0, 500.0, 600.0])
    # 1 layer
    n_layers_T = np.array([[complex(2.0, 0.0), complex(2.0, 0.0), complex(2.0, 0.0)]]).T
    n_sub = np.array([complex(1.5, 0.0), complex(1.5, 0.0), complex(1.5, 0.0)])
    
    tgt_vals = np.array([0.5, 0.5, 0.5])
    tgt_weights = np.array([1.0, 1.0, 1.0])
    min_d = 0.0
    has_back = False
    
    cost_func = make_cost_function(
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        wls=wls,
        tgt_vals=tgt_vals,
        tgt_weights=tgt_weights,
        min_d=min_d,
        has_back=has_back,
        n_back_T=np.array([]),
        d_back=np.array([])
    )
    
    assert callable(cost_func)
    
    # Try calling it with a valid thickness array
    ep = np.array([100.0])  # 100nm layer
    cost = cost_func(ep)
    
    assert np.isfinite(cost)
    assert cost >= 0.0

def test_make_cost_function_with_backside():
    wls = np.array([500.0])
    n_layers_T = np.array([[complex(2.0, 0.0)]]).T
    n_sub = np.array([complex(1.5, 0.0)])
    
    tgt_vals = np.array([0.5])
    tgt_weights = np.array([1.0])
    min_d = 0.0
    has_back = True
    
    n_back_T = np.array([[complex(1.8, 0.0)]]).T
    d_back = np.array([50.0])
    
    cost_func = make_cost_function(
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        wls=wls,
        tgt_vals=tgt_vals,
        tgt_weights=tgt_weights,
        min_d=min_d,
        has_back=has_back,
        n_back_T=n_back_T,
        d_back=d_back
    )
    
    ep = np.array([100.0])
    cost = cost_func(ep)
    
    assert np.isfinite(cost)
    assert cost >= 0.0
