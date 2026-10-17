"""The sets of layers the probe lays by Rate (8th argument = 4) are those of x2 unless the environment gives others.

x0.5 has other critical layers than x2 (22, 25, 28, then 46, 51, 62, against 32, 35, 39): a probe that could only lay by Rate the
layers of x2 could not test the idea on any other scale, and a set typed in the shell has to land in the artifact, not be dropped.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_LOAD = (
    "import importlib.util as u; s = u.spec_from_file_location('probe', 'scripts/probe_blocs_vs_plantage.py'); "
    "m = u.module_from_spec(s); s.loader.exec_module(m); print(m.RATE_SETS)"
)


def _rate_sets(value: str | None) -> list[list[int]]:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.pop("CERTUS_RATE_SETS", None)
    if value is not None:
        env["CERTUS_RATE_SETS"] = value
    done = subprocess.run([sys.executable, "-c", _LOAD], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return ast.literal_eval(done.stdout.strip().splitlines()[-1])


def test_without_the_variable_the_sets_are_those_of_x2() -> None:
    sets = _rate_sets(None)

    assert sets[0] == [32]
    assert [32, 35, 39] in sets


def test_the_variable_gives_the_sets_separated_by_semicolons() -> None:
    assert _rate_sets("22-25-28; 22-25-28-46 ;") == [[22, 25, 28], [22, 25, 28, 46]]
