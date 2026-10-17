"""A probe forces no Rate lever unless it is asked to: its default (8th argument = 0) is the production.

It used to force `rate_by_swing` to False, which production arms since 2026-08-22, so every measurement at the default ran without the
placement of Rate where the optical signal is too poor to stop on. 👤 2026-10-12: Rate must be integrated in every scenario.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _levers(par_swing: int) -> dict:
    code = (
        "import importlib.util as u; s = u.spec_from_file_location('probe', 'scripts/probe_blocs_vs_plantage.py'); "
        f"m = u.module_from_spec(s); s.loader.exec_module(m); print(m._leviers_rate({par_swing}))"
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "CERTUS_TAIL_CUTS": "16,20", "CERTUS_RATE_SETS": "22-25"}
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return ast.literal_eval(done.stdout.strip().splitlines()[-1])


def test_at_zero_nothing_is_forced() -> None:
    assert _levers(0) == {}


@pytest.mark.parametrize(
    ("par_swing", "by_swing", "tail", "sets", "keep"),
    [(1, True, [], [], 0), (2, False, [16, 20], [], 0), (3, True, [16, 20], [], 4), (4, False, [], [[22, 25]], 0), (5, True, [16, 20], [], 0)],
)
def test_the_other_values_keep_their_meaning(par_swing, by_swing, tail, sets, keep) -> None:
    assert _levers(par_swing) == {
        "rate_by_swing": by_swing,
        "rate_tail_sweep": tail,
        "rate_layer_sets": sets,
        "rate_tail_keep_optical": keep,
    }
