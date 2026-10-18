"""A bare `pytest` run is quiet, and `-q` still ends on the summary line that the scripts read.

An AI assistant pays for every byte a command prints. Until 2026-10-18 `addopts` carried `--verbose`, so `pytest tests/oracle/` printed
one line per test: 150 899 bytes for 1 146 tests, against 3 424 bytes once the option is gone (measured). The same line carried
`--cov=certus` and three coverage reports, so every run also wrote `htmlcov/` and `coverage.xml` and printed a table nobody had asked for.

What is pinned, and why each piece:

* `addopts` names no verbosity option. Coverage is one flag away (`--cov=certus`), so it is not a default either.
* `addopts` has no `-q`. A caller that adds its own (the CI, `scripts/validate_parallel.py`) would reach `-qq`, which drops the final
  summary line: `parse_summary` would then read a finished run as one that produced nothing.
* A run under the repository's configuration, on a scratch test: the default output lists no test by name (`PASSED` is what `--verbose`
  prints), nothing measures coverage, and `-q` still ends on `1 passed in`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"

# Options that change how much a run prints. `-q` is here too: it belongs to the caller, never to the defaults.
VERBOSITY = {"-v", "-vv", "-vvv", "--verbose", "-q", "-qq", "--quiet", "-rA", "-rP", "-ra", "--durations"}


def _addopts() -> list[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return shlex.split(config["tool"]["pytest"]["ini_options"]["addopts"])


def test_the_defaults_name_no_verbosity_option():
    named = [option for option in _addopts() if option in VERBOSITY]
    assert not named, (
        f"`addopts` in pyproject.toml names {named}: a verbose default floods a bare run (150 KB for the oracle), "
        "and a `-q` default turns the caller's own `-q` into `-qq`, which drops the summary line"
    )


def test_the_defaults_measure_no_coverage():
    named = [option for option in _addopts() if option.startswith("--cov")]
    assert not named, f"`addopts` in pyproject.toml names {named}: every run would measure coverage and write htmlcov/ and coverage.xml"


@pytest.fixture(scope="module")
def scratch(tmp_path_factory) -> Path:
    folder = tmp_path_factory.mktemp("quiet_run")
    (folder / "test_scratch.py").write_text("def test_scratch():\n    assert True\n", encoding="utf-8")
    return folder


def _run(folder: Path, *options: str) -> str:
    """pytest under the repository's own configuration, rooted in `folder`; the caller's PYTEST_* variables stay out of it."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    command = [sys.executable, "-m", "pytest", "-c", str(PYPROJECT), "--rootdir", str(folder), "-p", "no:cacheprovider", *options, str(folder)]
    done = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=folder, env=environment, timeout=180, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def test_a_bare_run_lists_no_test_and_measures_no_coverage(scratch):
    output = _run(scratch)
    assert "1 passed" in output
    assert "PASSED" not in output, "the default run prints one line per test (`--verbose`)"
    assert "coverage" not in output.lower(), "the default run measures coverage"


def test_a_quiet_run_still_ends_on_the_summary_line(scratch):
    output = _run(scratch, "-q")
    assert "1 passed in" in output, "`-q` on top of the defaults must keep the summary line (a `-q` in addopts makes it `-qq`)"
