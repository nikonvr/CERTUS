"""Chantier 44: STRAT and RE run Numba on TBB when it is installed; every other module stays on OpenMP.

TBB took a full STRAT search on the reference from 1339 s to 1074 s with the same bits and RE's example from 28.2 s to
17.5 s, but DESIGN's parallel sums change order from one TBB run to the next and INDEX gained nothing, so only STRAT and
RE ask for it. Two ways in, both checked in a fresh interpreter (the layer is chosen once per process): the entry point
configures it, and a process it starts inherits the request through the environment and needs Intel TBB's DLL directory
registered again.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TBB_INSTALLED = (Path(sys.prefix) / "Library" / "bin" / "tbb12.dll").is_file()

KERNEL = """
import numba, numpy as np
from numba import njit, prange
@njit(parallel=True)
def twice(a):
    out = np.empty_like(a)
    for i in prange(a.size):
        out[i] = 2.0 * a[i]
    return out
twice(np.ones(64))
print("LAYER=" + numba.threading_layer())
"""


def _layer(code: str, env_layer: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NUMBA_THREADING", "_CERTUS_NUMBA"))}
    if env_layer:
        env["NUMBA_THREADING_LAYER"] = env_layer
    out = subprocess.run([sys.executable, "-c", code + KERNEL], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=300)
    line = next((x for x in out.stdout.splitlines() if x.startswith("LAYER=")), None)
    assert line is not None, out.stderr[-800:]
    return line.removeprefix("LAYER=")


@pytest.mark.skipif(not TBB_INSTALLED, reason="Intel TBB (pip `tbb`) is not installed")
def test_the_tbb_configuration_runs_on_tbb():
    code = ("from certus.core.certus_core import TBB_THREADING_LAYER, configure_numba_env\n"
            "configure_numba_env(threading_layer=TBB_THREADING_LAYER)\n")
    assert _layer(code, None) == "tbb"


@pytest.mark.skipif(not TBB_INSTALLED, reason="Intel TBB (pip `tbb`) is not installed")
def test_a_process_started_by_strat_or_re_stays_on_tbb():
    """What a pool process sees: the request in its environment, and only `certus_core` imported."""
    assert _layer("import certus.core.certus_core\n", "threadsafe") == "tbb"


def test_the_other_modules_stay_on_openmp():
    code = "from certus.core.certus_core import configure_numba_env\nconfigure_numba_env()\n"
    assert _layer(code, None) == "omp"


def test_only_strat_and_re_ask_for_tbb():
    asking = sorted(p.name for p in ROOT.glob("CERTUS_*.py")
                    if "threading_layer=TBB_THREADING_LAYER" in p.read_text(encoding="utf-8"))
    assert asking == ["CERTUS_RE.py", "CERTUS_STRAT.py"]
