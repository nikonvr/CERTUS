"""D87: in the frozen build, two Python threads must be able to run parallel kernels at the same time.

Every module that computes does so: a pool of workers (DESIGN, RE phase 1, STRAT robustness), or the GUI thread
beside its QThread (INDEX). The frozen build used to force Numba's `workqueue` layer, which ends the process
("Numba workqueue threading layer is terminating: Concurrent access has been detected") the first time it happens:
simulated on 2026-10-06, DESIGN, INDEX, RE, METAL SINGLE and STRAT all stopped with exit code 3. The test reads
`configure_numba_env` in a fresh interpreter that believes it is frozen (`sys.frozen`), as an application starts.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_FROZEN_PROCESS = """
import json, os, sys, threading
sys.path.insert(0, ".")
for name in ("NUMBA_CACHE_DIR", "NUMBA_NUM_THREADS", "NUMBA_THREADING_LAYER", "_CERTUS_NUMBA_CONFIGURED"):
    os.environ.pop(name, None)
sys.frozen = True  # what PyInstaller sets: the configuration takes the road of the executable
from certus.core.certus_core import configure_numba_env
configure_numba_env()
import numpy as np
from numba import njit, prange, threading_layer

@njit(parallel=True)
def spread(x):
    out = np.empty_like(x)
    for i in prange(x.size):
        acc = 0.0
        for j in range(200):
            acc += np.sin(x[i] + j)
        out[i] = acc
    return out

data = np.linspace(0.0, 1.0, 20000)
spread(data)  # compile once, before the threads

def run():
    for _ in range(40):
        spread(data)

threads = [threading.Thread(target=run) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("@@" + json.dumps({"layer": threading_layer(), "env": os.environ.get("NUMBA_THREADING_LAYER")}))
"""


def test_the_frozen_configuration_runs_parallel_kernels_from_several_threads_at_once():
    out = subprocess.run([sys.executable, "-c", _FROZEN_PROCESS], cwd=ROOT, capture_output=True, text=True, timeout=600)

    assert "Concurrent access has been detected" not in out.stderr, out.stderr[-800:]
    assert out.returncode == 0, out.stderr[-800:]
    line = next((x for x in out.stdout.splitlines() if x.startswith("@@")), None)
    assert line is not None, out.stderr[-800:]
    got = json.loads(line[2:])
    assert got["env"] == "omp"  # the layer the sources use, which is thread-safe
    assert got["layer"] == "omp"  # and the one Numba actually loaded
