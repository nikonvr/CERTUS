"""`IndexTableDialog` lives in its own module and the substrate window module still hands it out (audit v2, plan S5.3).

`certus_substrate_ui.py` held two classes: the window (`SubstrateIndexGUI`, 840 lines) and a 680-line dialog that compares three refractive-index laws
(`IndexTableDialog`, 457 lines of `__init__`). The window module was one of the 19 files over 1 500 lines; the dialog is a unit of its own and moved to
`certus_substrate_index_dialog.py`, the code byte for byte (the splitting tool compares each moved node with its original, and refuses otherwise).

What the split must keep, and what these tests pin:
    the old import path     `from certus.ui.certus_substrate_ui import IndexTableDialog` still works, and gives the SAME class
    no cycle                the new module does not import the window module (it would be a cycle of two, and a reason for the dialog to need the window)
    the surface             the four public methods and `__init__`, nothing lost on the way
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEW_MODULE = ROOT / "certus" / "ui" / "certus_substrate_index_dialog.py"
WINDOW_MODULE = ROOT / "certus" / "ui" / "certus_substrate_ui.py"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_the_class_is_defined_in_its_own_module():
    from certus.ui import certus_substrate_index_dialog

    assert certus_substrate_index_dialog.IndexTableDialog.__module__ == "certus.ui.certus_substrate_index_dialog"


def test_the_window_module_still_hands_out_the_same_class():
    from certus.ui import certus_substrate_index_dialog, certus_substrate_ui

    assert certus_substrate_ui.IndexTableDialog is certus_substrate_index_dialog.IndexTableDialog


def test_the_window_module_no_longer_defines_it():
    tree = ast.parse(WINDOW_MODULE.read_text(encoding="utf-8-sig"))
    defined = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "IndexTableDialog" not in defined
    assert "SubstrateIndexGUI" in defined


def test_the_new_module_does_not_import_the_window_module():
    assert "certus.ui.certus_substrate_ui" not in imported_modules(NEW_MODULE)


def test_the_new_module_imports_alone_in_a_fresh_interpreter():
    done = subprocess.run(
        [sys.executable, "-c", "import certus.ui.certus_substrate_index_dialog as m; print(m.IndexTableDialog.__name__)"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-400:]
    assert done.stdout.strip() == "IndexTableDialog"


@pytest.mark.parametrize("name", ["copy_summary_to_clipboard", "copy_to_clipboard", "show_model_params_dialog", "toggle_raw_plots", "__init__"])
def test_the_class_keeps_each_of_its_methods(name):
    from certus.ui.certus_substrate_index_dialog import IndexTableDialog

    assert name in vars(IndexTableDialog)
    assert callable(vars(IndexTableDialog)[name])


def test_the_window_module_is_no_longer_a_long_file():
    assert len(WINDOW_MODULE.read_text(encoding="utf-8-sig").splitlines()) <= 1500
