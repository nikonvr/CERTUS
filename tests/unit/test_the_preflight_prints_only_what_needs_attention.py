"""By default the preflight prints what needs attention, HEAD and the verdict; every passing check stays out.

Every session runs it first, and its 41 lines of passing checks were read for nothing (2026-10-19). `--verbose` keeps the
full report; `test_preflight_imports_the_runtime_dependencies.py` uses it to read one check.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PREFLIGHT = Path(os.environ.get("CERTUS_PREFLIGHT_UNDER_TEST", Path(__file__).resolve().parents[2] / "scripts" / "preflight.py"))


def _run(*args: str) -> str:
    proc = subprocess.run((sys.executable, str(PREFLIGHT), *args), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    return proc.stdout


def test_a_default_run_prints_no_passing_check_and_ends_with_the_verdict():
    lines = [line for line in _run().splitlines() if line.strip()]
    assert not [line for line in lines if "[OK ]" in line], "\n".join(lines)
    assert any(line.startswith("  [   ] HEAD:") for line in lines), "\n".join(lines)
    assert lines[-1].startswith("PREFLIGHT=") or lines[-1].startswith("Do NOT modify"), "\n".join(lines)


def test_verbose_keeps_every_check():
    assert "[OK ]" in _run("--verbose")
