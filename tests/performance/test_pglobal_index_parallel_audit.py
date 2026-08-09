"""
Checks parallel vs sequential mode of PGlobalOptimizerINDEX (CERTUS_INDEX).

- n_workers > 1: ThreadPoolExecutor created in optimize() (sampling + parallel phase).
- n_workers == 1: no executor, sequential loops (“frozen-safe” branch).
- get_safe_worker_count patched: n_workers by default follows the patch (import linked to CERTUS_INDEX).
"""

from __future__ import annotations

import sys

import numpy as np
import pytest


@pytest.mark.performance
class TestPGlobalIndexParallelModeAudit:
    @pytest.fixture
    def tiny_config(self):
        from certus_physics.structures import PGlobalConfig

        return PGlobalConfig(
            n_samples_per_iter=2,
            max_feval=20,
            max_time=5.0,
            local_search_budget=5,
            reduction_ratio=0.5,
            max_active_clusters=4,
        )

    def test_threadpool_only_when_n_workers_gt_one(self, monkeypatch, tiny_config):
        import CERTUS_INDEX as cidx
        from certus.core import certus_index_solvers as solvers

        real_tpe = solvers.ThreadPoolExecutor
        calls: list[tuple] = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return real_tpe(*args, **kwargs)

        monkeypatch.setattr(solvers, "ThreadPoolExecutor", spy)

        bounds = np.array([[0.0, 1.0], [0.0, 1.0]], dtype=np.float64)

        def objective(x):
            return float(np.dot(x, x))

        opt1 = cidx.PGlobalOptimizerINDEX(
            objective, bounds, n_workers=1, config=tiny_config
        )
        opt1.optimize(max_iter=0)
        assert calls == []

        opt2 = cidx.PGlobalOptimizerINDEX(
            objective, bounds, n_workers=3, config=tiny_config
        )
        opt2.optimize(max_iter=0)
        assert len(calls) == 1
        assert calls[0][1].get("max_workers") == 3

    def test_default_workers_use_certus_index_get_safe_worker_count(
        self, monkeypatch, tiny_config
    ):
        import CERTUS_INDEX as cidx
        import certus.core.certus_index_solvers as solvers

        monkeypatch.setattr(solvers, "get_safe_worker_count", lambda: 7)
        bounds = np.array([[0.0, 1.0]], dtype=np.float64)

        def objective(x):
            return float(x[0] ** 2)

        opt = cidx.PGlobalOptimizerINDEX(objective, bounds, n_workers=None, config=tiny_config)
        assert opt.n_workers == 7

    def test_frozen_build_worker_policy_matches_certus_core(self, monkeypatch):
        import certus.core.certus_core as certus_core

        monkeypatch.setattr(certus_core, "is_frozen", lambda: True)
        w = certus_core.get_safe_worker_count()
        if sys.version_info < (3, 14):
            assert w == 1
        else:
            exp = max(
                1,
                certus_core._get_cpu_count() - certus_core._RESERVED_CORES_FOR_WORKERS,
            )
            assert w == exp
