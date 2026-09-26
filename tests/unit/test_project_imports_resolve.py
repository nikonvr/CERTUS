"""Every name imported from the project's own packages must exist -- even inside a function.

A lazy import of a missing name fails only when its line runs, and wrapped in a
`try/except` it fails SILENTLY. Found 2026-09-26 by this sweep, eight such imports:

- the live preview of METAL SINGLE and BILAYER imported two substrate functions that
  never existed, on every progress tick, and swallowed the ImportError;
- the INDEX SPLINE corridors and execution modules kept fallbacks to a function moved to
  `spline_visual_utils` in June -- one of them bound a no-op copy in its place;
- three scripts died at import, one of them since the repository's first commit.

The sweep covers every tracked `.py` outside `tests/` (a test importing a missing name
already fails at collection) and follows `from certus... import name` at any depth.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = ("certus", "certus_physics")


def _tracked_sources() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, capture_output=True, check=False
    )
    if out.returncode != 0 or not out.stdout:
        pytest.skip("git ls-files unavailable: the sweep needs the tracked file list")
    files = [f for f in out.stdout.decode("utf-8").split("\0") if f]
    return [f for f in files if not f.startswith("tests/")]


def _project_imports(src: str) -> list[tuple[int, str, str]]:
    """(line, module, name) for every `from <project package> import name`, at any depth."""
    found = []
    for node in ast.walk(ast.parse(src)):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] in PROJECT_PACKAGES
        ):
            found += [(node.lineno, node.module, a.name) for a in node.names if a.name != "*"]
    return found


def _missing(imports: list[tuple[str, str, str]]) -> list[str]:
    modules: dict[str, object] = {}
    bad = []
    for where, module, name in imports:
        if module not in modules:
            try:
                modules[module] = importlib.import_module(module)
            except ImportError as exc:
                modules[module] = exc
        mod = modules[module]
        if isinstance(mod, ImportError):
            bad.append(f"{where}: module {module} does not import ({mod})")
        elif not hasattr(mod, name):
            try:
                importlib.import_module(f"{module}.{name}")
            except ImportError:
                bad.append(f"{where}: {module} has no name {name!r}")
    return bad


@pytest.mark.unit
def test_every_imported_project_name_exists() -> None:
    imports = []
    for rel in _tracked_sources():
        try:
            src = (ROOT / rel).read_text(encoding="utf-8-sig")
            found = _project_imports(src)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        imports += [(f"{rel}:{line}", module, name) for line, module, name in found]
    # The sweep must actually see the code base: 6 933 imported names on 2026-09-26.
    assert len(imports) > 3000
    assert _missing(imports) == []


@pytest.mark.unit
def test_the_sweep_reports_a_missing_name_hidden_in_a_try() -> None:
    """Negative control: the exact shape of the METAL defect must be caught."""
    src = (
        "def on_progress():\n"
        "    try:\n"
        "        from certus.core._certus_physics_impl import get_nk_sio2\n"
        "    except ImportError:\n"
        "        pass\n"
    )
    found = _project_imports(src)
    assert found == [(3, "certus.core._certus_physics_impl", "get_nk_sio2")]
    assert _missing([("probe:3", found[0][1], found[0][2])]) != []
