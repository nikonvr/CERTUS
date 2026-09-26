"""A test that needs a QApplication borrows the session's one (R6, D23).

`app = QApplication.instance() or QApplication([])` in a test body is harmless as long as
another test created the application first. When that test is the first Qt test of its
process, the application it creates lives in a LOCAL variable and dies with the test: every
later Qt test then runs on a destroyed application. Measured 2026-09-27: the METAL unit files
alone gave one failure (`QThreadPool.globalInstance()` returned None), and followed by the
headless METAL tests the process died on a heap corruption (0xc0000374) while the bilayer
window closed. In the full unit suite an earlier test always held the application, which is
why nobody saw it.

The rule: a test function, or a fixture narrower than the session, that constructs an
application must receive the session's `qapp` before its body runs -- as its own parameter,
or through an autouse fixture of a conftest above it that takes `qapp`. Strings run in a
subprocess are not calls, so they are not concerned.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_APPLICATIONS = {"QApplication", "QCoreApplication", "QGuiApplication"}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constructs_an_application(func: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call) and _call_name(node.func) in _APPLICATIONS for node in ast.walk(func)
    )


def _fixture(func: ast.FunctionDef) -> tuple[bool, str, bool] | None:
    """(is a fixture, its scope, autouse) -- or None for a plain function."""
    for decorator in func.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _call_name(target) != "fixture":
            continue
        scope, autouse = "function", False
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if isinstance(keyword.value, ast.Constant):
                    if keyword.arg == "scope":
                        scope = keyword.value.value
                    elif keyword.arg == "autouse":
                        autouse = bool(keyword.value.value)
        return True, scope, autouse
    return None


def _parameters(func: ast.FunctionDef) -> set[str]:
    return {a.arg for a in [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]}


def _functions(tree: ast.AST):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _tracked_test_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "tests"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / line for line in out.splitlines() if line.endswith(".py")]


def _conftest_lends_qapp(conftest: Path) -> bool:
    """Does this conftest have an autouse fixture that takes `qapp`?"""
    tree = ast.parse(conftest.read_text(encoding="utf-8-sig"), filename=str(conftest))
    for func in _functions(tree):
        info = _fixture(func)
        if info and info[2] and "qapp" in _parameters(func):
            return True
    return False


def _covered_by_a_conftest(path: Path) -> bool:
    directory = path.parent
    while directory != ROOT and ROOT in directory.parents:
        conftest = directory / "conftest.py"
        if conftest.exists() and _conftest_lends_qapp(conftest):
            return True
        directory = directory.parent
    return False


def _offenders() -> list[str]:
    found = []
    for path in _tracked_test_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        covered = None
        for func in _functions(tree):
            info = _fixture(func)
            if info is None and not func.name.startswith("test"):
                continue
            if info is not None and info[1] == "session":
                continue
            if not _constructs_an_application(func) or "qapp" in _parameters(func):
                continue
            if covered is None:
                covered = _covered_by_a_conftest(path)
            if not covered:
                found.append(f"{path.relative_to(ROOT).as_posix()}::{func.name}")
    return found


def test_no_test_owns_a_qapplication_it_could_lose() -> None:
    offenders = _offenders()
    assert not offenders, (
        "these tests construct a QApplication without the session's `qapp`; the first Qt test "
        "of a process would destroy it on return. Take `qapp` as a parameter instead:\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_sees_the_pattern() -> None:
    """Negative control: the detector flags exactly the construct it exists for."""
    code = (
        "def test_local(monkeypatch):\n"
        "    app = QApplication.instance() or QApplication([])\n"
        "def test_borrowed(qapp):\n"
        "    app = QApplication.instance() or QApplication([])\n"
        "def test_only_instance():\n"
        "    app = QApplication.instance()\n"
        "def test_in_a_subprocess():\n"
        "    code = 'app = QApplication([])'\n"
    )
    flagged = {
        f.name for f in _functions(ast.parse(code))
        if _constructs_an_application(f) and "qapp" not in _parameters(f)
    }
    assert flagged == {"test_local"}
