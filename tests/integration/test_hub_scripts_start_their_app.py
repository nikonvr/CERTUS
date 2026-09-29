"""Every script the hub launches builds its application and reaches the Qt event loop.

From 2026-06-13 to 2026-09-29 the substrate index tool's script ended in `pass` where it had
called main(): the hub launched a process that imported the code and exited, and no test ran
the scripts. Each one runs here as __main__ in its own interpreter, with QApplication.exec
replaced by a marker, so that the event loop returns at once.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from certus.core.certus_hub_config import HUB_APP_CATALOG

ROOT = Path(__file__).resolve().parents[2]
MARKER = "EVENT-LOOP-REACHED"
PROBE = f"""
import runpy, sys
from PyQt6.QtWidgets import QApplication

def _exec(self=None):
    print("{MARKER}", flush=True)
    return 0

QApplication.exec = _exec
script = sys.argv[1]
sys.argv = [script]
runpy.run_path(script, run_name="__main__")
"""


@pytest.mark.parametrize("script", [item["script"] for item in HUB_APP_CATALOG])
def test_hub_script_reaches_the_event_loop(script: str) -> None:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    out = subprocess.run(
        [sys.executable, "-c", PROBE, script], cwd=ROOT, capture_output=True, text=True, timeout=600, env=env
    )
    assert MARKER in out.stdout, f"{script} never reached the event loop (exit {out.returncode}): {out.stderr[-1500:]}"
