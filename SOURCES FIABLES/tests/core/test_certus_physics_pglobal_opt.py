import pytest
import numpy as np
from certus.core._certus_physics_impl import PGlobalConfig, PGlobalOptimizer

def test_pglobal_optimizer_init():
    config = PGlobalConfig(
        n_samples_per_iter=100,
        max_feval=500,
        max_active_clusters=2
    )
    
    def dummy_cost(ep):
        return np.sum((ep - 50.0)**2)
        
    bounds = [(10.0, 100.0)]
    optimizer = PGlobalOptimizer(
        objective=dummy_cost,
        bounds=bounds,
        config=config
    )
    assert optimizer.config.n_samples_per_iter == 100
    assert optimizer.config.max_feval == 500
    assert len(optimizer.bounds) == 1
    
    # Just running 1 iteration to verify it doesn't crash
    best_sample = optimizer.optimize(max_iter=1)
    
    assert best_sample is not None
    assert np.isfinite(best_sample.y)
    assert len(best_sample.x) == 1
    assert 10.0 <= best_sample.x[0] <= 100.0
