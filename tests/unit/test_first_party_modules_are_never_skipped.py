"""A test imports CERTUS's own modules; it never `importorskip`s them.

`pytest.importorskip` turns an ImportError into a skip: pointed at the project's own code, it
hides the very breakage a test exists to report. Until 2026-09-28 nine calls did, two of them by
a bare module name that resolved only when an earlier import had put certus/ui or certus/core on
sys.path. Run alone, test_certus_measurement_excel_ui.py and test_certus_physics_structures.py
were skipped (measured: 1 passed, 2 skipped); in the full unit suite they ran.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tracked_python_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.split()


def _first_party_names(files: list[str]) -> set[str]:
    names = {Path(f).stem for f in files if "/" not in f}
    names |= {f.split("/")[0] for f in files if "/" in f}
    names |= {Path(f).stem for f in files if f.startswith("certus/")}
    return names


def _skipped_imports(tree: ast.AST) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", getattr(node.func, "id", None)) == "importorskip"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.append((node.lineno, node.args[0].value))
    return found


def test_no_test_importorskips_a_first_party_module() -> None:
    files = _tracked_python_files()
    first_party = _first_party_names(files)
    offenders = []
    for f in files:
        if not f.startswith("tests/"):
            continue
        tree = ast.parse((ROOT / f).read_text(encoding="utf-8-sig"), filename=f)
        for line, module in _skipped_imports(tree):
            if module.split(".")[0] in first_party:
                offenders.append(f"{f}:{line} {module}")
    assert not offenders, f"first-party modules imported through importorskip: {offenders}"


def test_the_guard_recognises_both_kinds_of_module() -> None:
    first_party = _first_party_names(["CERTUS_STRAT.py", "certus/ui/certus_measurement_excel_ui.py"])
    calls = _skipped_imports(ast.parse("pytest.importorskip('certus_measurement_excel_ui')\nimportorskip('PyQt6')"))
    assert [m.split(".")[0] in first_party for _, m in calls] == [True, False]
    assert "CERTUS_STRAT" in first_party
    assert "certus" in first_party
