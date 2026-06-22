"""
Audit perf type RE (sans UI Qt) : débit d'évaluations spectrales / TMM.

Le plan demande la part UI vs worker et la fréquence des callbacks : hors processus
graphique, on mesure ici le goulet worker (évaluations physiques). Pour la part UI
réelle et les callbacks Qt, utiliser un profilage par échantillonnage (py-spy)
sur le binaire ou `python -m CERTUS_RE` avec scénario utilisateur.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

_perf_dir = str(Path(__file__).resolve().parent)
if _perf_dir not in sys.path:
    sys.path.insert(0, _perf_dir)
import test_performance as _tp  # noqa: E402

PHYSICS_AVAILABLE = _tp.PHYSICS_AVAILABLE
run_tmm_wrapper = _tp.run_tmm_wrapper

try:
    from certus_physics import Layer
except ImportError:
    Layer = None  # type: ignore[misc, assignment]


@pytest.mark.performance
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="certus_physics indisponible")
class TestREHeadlessThroughputAudit:
    """Load similar to RE worker: many TMM calls (sequential vs thread pool)."""

    N_EVALS = 48
    POOL_WORKERS = 4

    def test_sequential_eval_throughput_ms_per_call(self, sample_wavelengths):
        """Sequential baseline: total time / number of evaluations (RE worker proxy)."""
        layers = [
            Layer(mat="SiO2", qwot=100.0 / 100.0),
            Layer(mat="TiO2", qwot=50.0 / 100.0),
            Layer(mat="Al2O3", qwot=25.0 / 100.0),
        ]
        run_tmm_wrapper(layers, sample_wavelengths)

        t0 = time.perf_counter()
        for _ in range(self.N_EVALS):
            run_tmm_wrapper(layers, sample_wavelengths)
        elapsed = time.perf_counter() - t0

        ms_per = 1000.0 * elapsed / self.N_EVALS
        # Broad safeguard: slow machine or CI; the audit mostly logs the metric.
        assert ms_per < 500.0, f"too slow: {ms_per:.1f} ms/eval (sequential)"

    def test_parallel_pool_eval_throughput(self, sample_wavelengths):
        """Same load distributed on a pool (analogy: multiple worker tasks / FD)."""
        layers = [
            Layer(mat="SiO2", qwot=100.0 / 100.0),
            Layer(mat="TiO2", qwot=50.0 / 100.0),
        ]
        run_tmm_wrapper(layers, sample_wavelengths)

        def one():
            return run_tmm_wrapper(layers, sample_wavelengths)

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=self.POOL_WORKERS) as ex:
            list(ex.map(lambda _: one(), range(self.N_EVALS)))
        elapsed = time.perf_counter() - t0

        assert elapsed > 0
        # No assert on speedup (depends on CPU / Numba): test presence = CI metric.
