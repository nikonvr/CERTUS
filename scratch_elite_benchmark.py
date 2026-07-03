import time
import numpy as np
import concurrent.futures
from certus.core.certus_strat_consensus import _apply_elite_refinement_if_enabled
from certus.utils.certus_strat_context import GlobalStrategyContext
from unittest.mock import MagicMock

def dummy_task(*args, **kwargs):
    # Simulate CPU-bound work
    total = 0
    for i in range(100000):
        total += i
    return {"strategy": "test", "rmse": 0.5, "robustness_score": 1.0}

# We must monkeypatch at the module level for ProcessPoolExecutor
import certus.core.certus_strat_consensus
certus.core.certus_strat_consensus._test_strategy_robustness_task = dummy_task

if __name__ == "__main__":
    ctx = GlobalStrategyContext()
    ctx.params = {"elite_rounds": 1, "elite_max_candidates_per_round": 100, "worker_count": 4}
    ctx.noise_levels = [0.1]
    
    # Dummy candidates
    candidates = [(i, {"strategy": "test"}) for i in range(100)]
    
    # 1. ThreadPoolExecutor (Before)
    t0 = time.time()
    certus.core.certus_strat_consensus.concurrent.futures.ProcessPoolExecutor = concurrent.futures.ThreadPoolExecutor
    _apply_elite_refinement_if_enabled(ctx, candidates, lambda x, **kwargs: x)
    t1 = time.time()
    
    print(f"ThreadPoolExecutor (Before): {t1-t0:.2f}s")
    
    # 2. ProcessPoolExecutor (After)
    t0 = time.time()
    certus.core.certus_strat_consensus.concurrent.futures.ProcessPoolExecutor = concurrent.futures.ProcessPoolExecutor
    _apply_elite_refinement_if_enabled(ctx, candidates, lambda x, **kwargs: x)
    t1 = time.time()
    
    print(f"ProcessPoolExecutor (After): {t1-t0:.2f}s")
