"""Guards the tables where sorting would silently corrupt what the operator reads.

Two distinct families, both fixed by disabling sorting on the instance:

1. ROW ORDER IS THE PHYSICS. The engine reads these tables by row index, so a
   sort makes the computed filter differ from the displayed one.
2. CELLS ARE WIDGETS. Qt does not move cell widgets when sorting: a sort pairs
   one row's widgets with another row's data.

This guard exists because the hole was opened twice. docs/GEMINI_UX_TOP1_2026-09-04.md
step 2.9 warns: "do not restore sorting without the locks in the same change".
On 2026-09-04 the ExcelTableWidget.__init__ that enables sorting was restored and
the certus_lock_row_order() calls were not, which put the suite back in the exact
state that step exists to prevent.

Measured 2026-09-04, before the fix (all four ExcelTableWidget, sortable=True):

    CERTUS_RE    front_table       ['#', 'Mat', 'n@lambda0', 'QWOT', 'Thick(nm)']
    CERTUS_STRAT stack_table       ['#', 'Mat.', 'Mult.']
    CERTUS_FIELD table_design_res  "0 (Superstrate)", layers in order, substrate
    CERTUS_RE    target_table      every cell a widget (checkbox, combos, spinboxes)

and the positional readers that make family 1 dangerous:

    certus/ui/certus_strat_ui_state.py:1051  multipliers = [... for r in range(rowCount())]
    certus/ui/certus_strat_ui_state.py:559   config["stack_multipliers"] = ...  (persisted)
    certus/ui/certus_re_table_mixin.py:379   writes thicknesses back by row index

The DESIGN tables and FIELD table_layers are plain QTableWidget, so they are safe
today. They are covered anyway: converting one to ExcelTableWidget later would
re-open the hole in silence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARKER = "__CERTUS_SORT_SAFETY_TEST__"

# (module, class, path to the table on the window)
# "widgets:key" reaches into a dict attribute; a bare name is a plain attribute.
STACK_TABLES = [
    ("CERTUS_RE", "CertusREApp", "front_table"),
    ("certus.ui.certus_strat_ui", "CertusStratApp", "widgets:stack_table"),
    ("certus.ui.certus_field_ui", "CertusFieldApp", "table_design_res"),
    ("certus.ui.certus_field_ui", "CertusFieldApp", "table_layers"),
    ("certus.ui.certus_design_ui", "CertusDesignApp", "front_table"),
    ("certus.ui.certus_design_ui", "CertusDesignApp", "back_table"),
]

CELL_WIDGET_TABLES = [
    ("CERTUS_RE", "CertusREApp", "target_table"),
    ("certus.ui.certus_design_ui", "CertusDesignApp", "target_table"),
]


def _resolve(win, path: str):
    obj = win
    for part in path.split("."):
        if ":" in part:
            attr, key = part.split(":", 1)
            obj = getattr(obj, attr)[key]
        else:
            obj = getattr(obj, part)
    return obj


def _worker_main(mod_path: str, cls_name: str, path: str) -> None:
    sys.path.insert(0, REPO_ROOT)
    # Isolate QSettings before any certus module is imported
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_sortsafe_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()

    # Several modules rebuild their layout from deferred timers; the sorting flag
    # is only trustworthy once those have run.
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    table = _resolve(win, path)
    out = {
        "sortable": bool(table.isSortingEnabled()),
        "cls": type(table).__name__,
        "allow_flag": bool(getattr(table, "CERTUS_ALLOW_SORTING", False)),
    }
    win.close()
    print(MARKER + json.dumps(out))


def _measure(mod_path: str, cls_name: str, path: str) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("QT_QPA_PLATFORM", None)

    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--worker", mod_path, cls_name, path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(MARKER)]
    assert hit, f"Worker crashed for {cls_name}.{path}:\n{proc.stderr}"
    return json.loads(hit[0][len(MARKER) :])


@pytest.mark.parametrize("mod_path,cls_name,path", STACK_TABLES)
def test_stack_table_is_never_sortable(mod_path: str, cls_name: str, path: str) -> None:
    """A table holding an optical stack must not offer sorting.

    Row order carries the layer sequence and the engine reads it by index. If the
    operator can reorder it, the computed filter stops being the displayed one and
    nothing on screen says so.
    """
    data = _measure(mod_path, cls_name, path)
    assert data["sortable"] is False, (
        f"{cls_name}.{path} ({data['cls']}) is sortable: reordering its rows would "
        f"silently describe a different optical stack. Call certus_lock_row_order() on it."
    )


@pytest.mark.parametrize("mod_path,cls_name,path", CELL_WIDGET_TABLES)
def test_cell_widget_table_is_never_sortable(mod_path: str, cls_name: str, path: str) -> None:
    """A table whose cells are widgets must not offer sorting.

    Qt moves the items but leaves the cell widgets where they are, so a sort shows
    one target's checkbox and combos next to another target's wavelengths.
    """
    data = _measure(mod_path, cls_name, path)
    assert data["sortable"] is False, (
        f"{cls_name}.{path} ({data['cls']}) is sortable, but its cells are widgets: "
        f"Qt would leave them behind and pair them with another row's data. "
        f"Call certus_lock_row_order() on it."
    )


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0)
