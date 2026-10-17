"""A UX worker removes the scratch directory its QSettings isolation creates.

Every UX worker redirects `QSettings` to INI files in a `tempfile.mkdtemp` directory, and most leave by `os._exit` (D23), which
skips `atexit`: each worker left one empty directory behind in the user's temporary folder. On 2026-10-12 there were 14 614 of
them (`certus_{audit,help,focus,metal,hs,share,sortsafe,stacksort}_qs_*`), a month of validations.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELP_TEST = Path(__file__).with_name("test_ux_help_matches_reality.py")
SCRATCH = re.compile(r'mkdtemp\(prefix="certus_[a-z]+_qs_"\)')


def _creators() -> list[Path]:
    files = [*sorted(ROOT.joinpath("tests", "ui").glob("*.py")), ROOT / "scripts" / "audit_ux_certus.py"]
    return [p for p in files if SCRATCH.search(p.read_text(encoding="utf-8"))]


def test_the_guard_sees_the_files_that_create_a_scratch_directory() -> None:
    """A rename of the prefix must not turn the guard below into a test of nothing."""
    names = {p.name for p in _creators()}

    assert "audit_ux_certus.py" in names
    assert "test_ux_help_matches_reality.py" in names


@pytest.mark.parametrize("path", _creators(), ids=lambda p: p.name)
def test_every_file_that_creates_a_scratch_directory_removes_it(path: Path) -> None:
    assert "shutil.rmtree" in path.read_text(encoding="utf-8"), f"{path.name} creates a scratch directory and never removes it"


def test_a_worker_leaves_no_scratch_directory_behind(tmp_path: Path) -> None:
    """Run a real worker with its temporary folder inside `tmp_path`: nothing of its QSettings isolation may stay there."""
    scratch_root = tmp_path / "temp"
    scratch_root.mkdir()
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
        TEMP=str(scratch_root),
        TMP=str(scratch_root),
        TMPDIR=str(scratch_root),
    )
    done = subprocess.run(
        [sys.executable, str(HELP_TEST), "--worker", "CERTUS_INDEX"],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )

    assert "__CERTUS_HELP_REALITY__" in done.stdout, f"the worker gave no result (exit {done.returncode}):\n{done.stderr[-800:]}"
    assert [p.name for p in scratch_root.iterdir() if "_qs_" in p.name] == []
