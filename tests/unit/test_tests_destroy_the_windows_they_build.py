"""A test file that builds CERTUS main windows destroys them when each test ends (D11, D23).

Closing a CERTUS window only hides it: a window a test builds and merely closes lives until the
interpreter exits, with its plots, timers and worker references. Measured 2026-09-28: one FIELD
window left alive by tests/test_field_module.py was enough for the process to die at shutdown
once tests/headless/test_field.py had run too (0xc0000005 / 0xc0000409, every test passed, no
pytest summary), and for a following tests/ui file to crash in QApplication.setFont.

The rule: a tracked test file that calls a `Certus...App(...)` constructor runs under
`qt_lifecycle` -- through an autouse fixture of its own, or of a conftest above it.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_WINDOW = re.compile(r"Certus\w*App")


def _builds_a_window(tree: ast.AST) -> bool:
    """A `Certus...App(...)` call, or a window class looked up by name (getattr) and called."""
    uses_getattr = False
    names_a_window = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if _WINDOW.fullmatch(name):
                return True
            uses_getattr = uses_getattr or name == "getattr"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and (
            _WINDOW.fullmatch(node.value) or node.value == "CertusHub"
        ):
            names_a_window = True
    return uses_getattr and names_a_window


def _has_autouse_lifecycle(tree: ast.AST) -> bool:
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        autouse = any(
            isinstance(d, ast.Call)
            and any(k.arg == "autouse" and isinstance(k.value, ast.Constant) and k.value.value for k in d.keywords)
            for d in func.decorator_list
        )
        delegates = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "qt_lifecycle"
            for n in ast.walk(func)
        )
        if autouse and delegates:
            return True
    return False


def _tracked_test_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "tests"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if line.endswith(".py")]


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def test_every_test_file_that_builds_a_window_destroys_it() -> None:
    files = _tracked_test_files()
    covered_dirs = {
        path.parent for path in files if path.name == "conftest.py" and _has_autouse_lifecycle(_parse(path))
    }
    offenders = []
    for path in files:
        if path.name == "conftest.py" or path.name == Path(__file__).name:
            continue
        tree = _parse(path)
        if not _builds_a_window(tree) or _has_autouse_lifecycle(tree):
            continue
        if any(directory in covered_dirs for directory in path.parents):
            continue
        offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"these files build CERTUS windows outside qt_lifecycle: {offenders}"


def test_the_guard_sees_a_window_and_a_lifecycle() -> None:
    """The two detectors are not vacuous."""
    assert _builds_a_window(ast.parse("win = CertusFieldApp()"))
    assert not _builds_a_window(ast.parse("win = CertusTheme()"))
    assert _builds_a_window(ast.parse("cls = getattr(module, 'CertusStratApp')\nwin = cls()"))
    lifecycle = (
        "@pytest.fixture(autouse=True)\n"
        "def f(qapp, monkeypatch):\n"
        "    yield from qt_lifecycle(qapp, monkeypatch, 'x')\n"
    )
    assert _has_autouse_lifecycle(ast.parse(lifecycle))
    assert not _has_autouse_lifecycle(ast.parse(lifecycle.replace("autouse=True", "scope='module'")))
