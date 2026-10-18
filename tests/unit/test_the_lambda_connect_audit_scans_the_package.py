"""The lambda-connect audit of the CI reads the package, not only the launchers of the root.

`tools/lambda_connect_audit.py --ci --max-count 0` answered "0 sites" for as long as the code lived at the root of
the repository. When it moved into `certus/` the audit went on reading `root.glob("*.py")`: the ten launchers. It
reported "clean" while `git grep` finds 44 `connect(lambda ...)` in `certus/` (reports/AUDIT_SUITE_CERTUS_2026-10-18.md,
C19). The risk it guards, a lambda that captures `self` and keeps a closed window alive, is defect D11 of docs/ETAT.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _audit_module():
    spec = importlib.util.spec_from_file_location("lambda_connect_audit", ROOT / "tools" / "lambda_connect_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.unit
def test_the_audit_counts_the_launchers_and_the_packages_and_nothing_else(tmp_path) -> None:
    site = "button.clicked.connect(lambda: self.run())\n"
    _write(tmp_path / "CERTUS_LAUNCHER.py", site)
    _write(tmp_path / "certus" / "ui" / "widget.py", site)
    _write(tmp_path / "certus_physics" / "shim.py", site)
    _write(tmp_path / "tests" / "test_widget.py", site)  # a test may use one
    _write(tmp_path / "scripts" / "tool.py", site)  # so may a script
    _write(tmp_path / ".claude" / "worktrees" / "copy" / "certus" / "ui" / "widget.py", site)  # a copy of the repo

    hits = _audit_module()._scan(tmp_path)

    assert sorted(name for name, _line, _text in hits) == [
        "CERTUS_LAUNCHER.py",
        "certus/ui/widget.py",
        "certus_physics/shim.py",
    ]
