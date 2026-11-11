"""The FIELD window imports nothing of STRAT: the path of the indices database lives in the core.

`certus/ui/certus_field_ui.py` imported `_resolve_strat_indices_db_path` from `certus.workers.certus_strat_workers`: to
find one spreadsheet, opening FIELD loaded the whole worker module of another program, and a change in the STRAT
workers could break FIELD (audit of the corridors, F12; plan, phase 7a).

The function is in `certus.core.certus_indices_db` now, under the two programs. The STRAT workers import it back, so
the modules and scripts that read it there get the very same object.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELD = [
    *sorted(
        path
        for folder in ("certus/ui", "certus/workers", "certus/core", "certus/physics", "certus/utils")
        for path in (ROOT / folder).glob("certus_field*.py")
    ),
    ROOT / "CERTUS_FIELD.py",
]
NAME = "_resolve_strat_indices_db_path"


def imported_modules(path: Path) -> set[str]:
    """Every module `path` imports, at module level or inside a function."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
    return found


def test_the_field_family_is_found():
    assert len(FIELD) >= 6
    assert all(path.is_file() for path in FIELD)


def test_no_module_of_field_imports_a_module_of_strat():
    offenders = {
        path.name: sorted(module for module in imported_modules(path) if "strat" in module.lower())
        for path in FIELD
    }
    assert {name: modules for name, modules in offenders.items() if modules} == {}


def test_the_strat_workers_still_expose_the_very_same_function():
    core = importlib.import_module("certus.core.certus_indices_db")
    workers = importlib.import_module("certus.workers.certus_strat_workers")
    assert getattr(workers, NAME) is getattr(core, NAME)
    assert getattr(core, NAME).__module__ == "certus.core.certus_indices_db"


def test_the_core_module_imports_no_interface_and_no_worker():
    modules = imported_modules(ROOT / "certus" / "core" / "certus_indices_db.py")
    assert [m for m in modules if m.startswith(("PyQt6", "certus.ui", "certus.workers"))] == []


def test_the_path_is_an_existing_spreadsheet_of_the_repository():
    path = Path(getattr(importlib.import_module("certus.core.certus_indices_db"), NAME)())
    assert path.is_absolute()
    assert path.name in ("indices.xlsx", "clues.xlsx")
    assert path.exists()
