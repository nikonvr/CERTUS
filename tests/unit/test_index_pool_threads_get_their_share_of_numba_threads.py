"""D91: the threads of INDEX's optimizer pool run their parallel kernels with their share of Numba's threads.

`numba.set_num_threads` holds for the thread that calls it. PGlobalOptimizerINDEX set the share in the thread that
coordinates, before opening its pool, so every pool thread kept all of Numba's threads: n_workers times the machine.
The production workers call the optimizer with one worker today; the parallel branch is what this pins.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_PROCESS = """
import json, sys, threading
sys.path.insert(0, ".")
import numpy as np
import numba
from certus_physics.structures import PGlobalConfig
from certus.core.certus_index_solvers import PGlobalOptimizerINDEX, _get_cpu_count

seen = {}
def objective(x):
    seen[threading.get_ident()] = numba.get_num_threads()
    return float(np.dot(x, x))

config = PGlobalConfig(n_samples_per_iter=8, max_feval=40, max_time=20.0, local_search_budget=5,
                       reduction_ratio=0.5, max_active_clusters=4)
PGlobalOptimizerINDEX(objective, np.array([[0.0, 1.0], [0.0, 1.0]]), n_workers=4, config=config).optimize(max_iter=2)
main = threading.get_ident()
print("@@" + json.dumps({"pool": sorted({n for t, n in seen.items() if t != main}), "cpu": _get_cpu_count(),
                         "limit": numba.config.NUMBA_NUM_THREADS}))
"""


def test_each_pool_thread_runs_with_its_share():
    env = {**os.environ, "NUMBA_NUM_THREADS": "8"}
    out = subprocess.run([sys.executable, "-c", _PROCESS], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    line = next((x for x in out.stdout.splitlines() if x.startswith("@@")), None)
    assert line is not None, out.stderr[-1500:]
    got = json.loads(line[2:])

    share = min(got["limit"], max(1, got["cpu"] // 4))
    assert got["pool"], "no objective call ran in a pool thread"
    assert got["pool"] == [share]
