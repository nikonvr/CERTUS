"""
Audit mémoire / GC type STRAT (Monte Carlo, grosses grilles).

Approximation : copies de tableaux numpy (résultats / heatmaps) + gc.collect.
Ne lance pas la GUI STRAT ni la DB ; utile pour suivre pic tracemalloc et coût GC.
"""

from __future__ import annotations

import gc
import time

import numpy as np
import pytest


@pytest.mark.performance
class TestStratMonteCarloSyntheticAudit:
    N_RUNS = 30
    # ~30 × 2 tableaux × 400 × 600 × 8 o ~ 115 Mo de données vivantes à un instant
    SHAPE = (400, 600)

    @pytest.mark.skipif(
        not hasattr(gc, "collect"),
        reason="gc standard requis",
    )
    def test_synthetic_grid_peak_tracemalloc_and_gc_time(self):
        import tracemalloc

        tracemalloc.start()
        t_build = time.perf_counter()
        history: list[np.ndarray] = []
        for _ in range(self.N_RUNS):
            a = np.random.randn(*self.SHAPE).astype(np.float64)
            b = a.copy()
            history.append(a)
            history.append(b)
            if len(history) > 8:
                history.pop(0)
        build_s = time.perf_counter() - t_build
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        t_gc = time.perf_counter()
        n = gc.collect()
        gc_s = time.perf_counter() - t_gc

        del history
        gc.collect()

        assert build_s < 120.0
        assert peak < 600 * 1024 * 1024
        assert gc_s < 30.0
        assert n >= 0
