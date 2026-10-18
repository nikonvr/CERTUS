"""Each pytest-xdist worker has its own private preferences directory.

`tests/conftest.py` makes one directory per session. The workers of pytest-xdist are children of the controller and
inherit its environment, so they all shared the controller's directory: `test_save_export_config` wrote the shared
`certus_export.json` while `test_the_automatic_export_is_off_under_test` read it (one failure out of 5 504 tests in a
16-worker run, reports/AUDIT_SUITE_CERTUS_2026-10-18.md, C02).

Skipped when pytest-xdist is not installed: without it there are no workers.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("xdist")

ROOT = Path(__file__).resolve().parents[2]

#: A pytest plugin that notes, for every test that runs, which worker ran it and the directory it sees.
PROBE = '''
import os


def pytest_runtest_setup(item):
    line = os.environ.get("PYTEST_XDIST_WORKER", "none") + "\\t" + os.environ.get("CERTUS_CONFIG_DIR", "") + "\\n"
    with open(os.environ["PREFS_PROBE_OUT"], "a", encoding="utf-8") as out:
        out.write(line)
'''


@pytest.mark.unit
def test_every_xdist_worker_has_its_own_private_preferences_directory(tmp_path) -> None:
    (tmp_path / "prefs_probe.py").write_text(PROBE, encoding="utf-8")
    out = tmp_path / "records.txt"
    env = {k: v for k, v in os.environ.items() if k != "CERTUS_CONFIG_DIR"}
    env.update(PYTHONPATH=str(tmp_path), PREFS_PROBE_OUT=str(out))
    for var in ("TMPDIR", "TEMP", "TMP"):  # the directory of the session lands here, as in the neighbouring test
        env[var] = str(tmp_path)
    target = "tests/unit/test_user_preferences_are_isolated.py::test_the_suite_runs_on_private_preferences"
    # --dist each: every worker runs the test, so all three report.
    run = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-cov", "-p", "no:cacheprovider",
         "-p", "prefs_probe", "-n", "3", "--dist", "each"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    records = dict(line.split("\t") for line in out.read_text(encoding="utf-8").splitlines())
    assert sorted(records) == ["gw0", "gw1", "gw2"]
    assert len(set(records.values())) == 3, records
