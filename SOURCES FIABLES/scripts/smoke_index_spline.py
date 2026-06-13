#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke INDEX SPLINE : une commande pour imports + sous-suite pytest ciblée.

Contourne les ``addopts`` de ``pytest.ini`` (coverage / seuil 80 %) qui ne
mesurent pas les modules ``spline_*.py``.

Usage (depuis la racine du dépôt)::

    python scripts/smoke_index_spline.py

Ou uniquement les tests marqués ``index_spline_smoke``::

    python -m pytest -m index_spline_smoke -o addopts="--strict-markers --strict-config -q --tb=short"
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Ordre : smoke imports d’abord, puis unitaires spline, puis intégration spline / Smart Init / lois.
_SMOKE_PYTEST_TARGETS = (
    "tests/test_smoke_certus_index_spline.py",
    "tests/unit/test_spline_presets.py",
    "tests/unit/test_spline_codecs.py",
    "tests/unit/test_spline_objective.py",
    "tests/test_spline_rmse_lambda_window.py",
    "tests/test_spline_optimizer_comparison.py",
    "tests/test_spline_performance_optimization.py",
    "tests/test_smart_init_d_preserves.py",
    "tests/test_penalized_spline.py",
    "tests/test_direct_laws_total.py",
)


def main() -> int:
    os.chdir(REPO)
    missing = [p for p in _SMOKE_PYTEST_TARGETS if not (REPO / p).is_file()]
    if missing:
        print("Fichiers de tests manquants :", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 2

    addopts = "--strict-markers --strict-config -q --tb=short"
    paths = [str(REPO / p) for p in _SMOKE_PYTEST_TARGETS]
    cmd = [sys.executable, "-m", "pytest", *paths, "-o", f"addopts={addopts}"]
    print("Smoke INDEX SPLINE:", " ".join(cmd), flush=True)
    return int(subprocess.call(cmd, cwd=REPO, env=os.environ.copy()))


if __name__ == "__main__":
    sys.exit(main())
