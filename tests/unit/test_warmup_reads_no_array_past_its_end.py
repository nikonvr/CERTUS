"""warmup_physics never reads an array past its end (D23).

Numba compiles no bounds check. A kernel that loops over the wavelengths and reads n[i], k[i] and n_sub[i]
reads past the end of shorter arrays, silently. warmup_physics -- run in the background at the start of every
application, and at the start of every headless test -- gave calculate_RT_single_layer_backside_array 10 values
for 50 wavelengths. Where one of those arrays ends at the edge of its allocation, the read is an access violation
in every thread of the parallel loop at once: measured 2026-10-03 with the arrays placed before a PAGE_NOACCESS
page, nine "Windows fatal exception: access violation" interleaved, the signature of the stop of
tests/headless/test_metal_single.py the same day.

With the JIT disabled the kernels run as Python and numpy checks every index: a read past the end raises
IndexError. The run is in a subprocess because Numba reads NUMBA_DISABLE_JIT when it is imported, and the
tracer counts an IndexError even when a warmup catches it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_RUN_THE_WARMUP_INTERPRETED = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, os.getcwd())
    certus_dir = os.path.join(os.getcwd(), "certus")
    raised = []

    def tracer(frame, event, arg):
        if event == "exception" and issubclass(arg[0], IndexError) and frame.f_code.co_filename.startswith(certus_dir):
            raised.append(f"{os.path.relpath(frame.f_code.co_filename)}:{frame.f_lineno} {arg[1]}")
        return tracer

    import certus_physics

    sys.settrace(tracer)
    certus_physics.warmup_physics(silent=True)
    sys.settrace(None)
    print("RAISED", raised)
    sys.exit(1 if raised else 0)
    """
)


@pytest.mark.unit
def test_warmup_physics_reads_no_array_past_its_end():
    env = dict(os.environ, NUMBA_DISABLE_JIT="1", QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run(
        [sys.executable, "-c", _RUN_THE_WARMUP_INTERPRETED],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (proc.stdout[-3000:], proc.stderr[-3000:])
