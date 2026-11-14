"""Exercise the real kernel benchmark and its slowdown verdict in the serial performance suite."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import bench_kernels as bench  # noqa: E402


def test_the_real_kernels_run_and_a_real_slowdown_is_caught(tmp_path, monkeypatch, capsys):
    """One real kernel, measured and baselined here, then made twice as slow: the tool must say so (no fake clock, no fake kernel)."""
    path = tmp_path / "real.json"
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--write-baseline", "--baseline", str(path)]) == 0
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--baseline", str(path)]) == 0  # itself, a minute later: inside the tolerance

    kernels = importlib.import_module("certus.core._certus_physics_impl")
    original = kernels.calculate_bare_substrate_RT

    def twice_the_work(*args):
        original(*args)
        return original(*args)

    monkeypatch.setattr(kernels, "calculate_bare_substrate_RT", twice_the_work)
    capsys.readouterr()
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--baseline", str(path)]) == 1
    assert "REGRESSION: bare_substrate: slower" in capsys.readouterr().err
