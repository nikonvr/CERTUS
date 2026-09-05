"""The main action of METAL must be on screen, and its fields must be painted.

Step 2.16 recorded two defects at 1366x768:

  * the "Run" button sat 469 px BELOW the bottom of the window, so the module's
    primary action could not be reached without scrolling a panel that gave no
    sign of scrolling;
  * the four parameter cards did not paint on BILAYER - 640 px of white, 13 of
    the 15 fields invisible.

Measured 2026-09-05, both are resolved:

    BILAYER  Run  y=584  bottom=628  offscreen=0 px   fields 15/15 visible
    SINGLE   Run  y=584  bottom=628  offscreen=0 px   fields 10/10 visible

This test exists so they stay resolved. The horizontal half of the same step -
143 px and 24 px of panel clipped behind ScrollBarAlwaysOff - is guarded by
test_ux_no_horizontal_scroll.py.

1366x768 on purpose: at 1920x1080 neither defect appears, which is why measuring
one size hid them (defect J4).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "__CERTUS_METAL_REACH__"

METAL_MODULES = ["CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER"]


def _worker_main(tag: str) -> None:
    import time

    sys.path.insert(0, str(ROOT))
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_metal_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QPushButton

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1366, 768)
    win.show()

    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    offscreen = 0
    found_run = False
    for button in win.findChildren(QPushButton):
        if "run" not in button.text().strip().lower():
            continue
        found_run = True
        top = button.mapTo(win, qtcore.QPoint(0, 0)).y()
        offscreen = max(offscreen, top + button.height() - win.height())

    fields = win.findChildren((QLineEdit, QAbstractSpinBox, QComboBox))
    out = {
        "found_run": found_run,
        "run_offscreen_px": max(0, offscreen),
        "fields": len(fields),
        "fields_visible": sum(1 for f in fields if f.isVisible()),
    }
    win.close()
    print(MARKER + json.dumps(out))


def _measure(tag: str) -> dict:
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--worker", tag],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(MARKER)]
    assert hit, f"Worker crashed for {tag}:\n{proc.stderr}"
    return json.loads(hit[0][len(MARKER) :])


@pytest.mark.parametrize("tag", METAL_MODULES)
def test_the_run_button_is_on_screen(tag: str) -> None:
    """The primary action must be reachable without scrolling a hidden panel."""
    row = _measure(tag)
    assert row["found_run"], f"{tag} has no Run button: this test would prove nothing"
    assert row["run_offscreen_px"] == 0, (
        f"{tag} @ 1366x768: the Run button sits {row['run_offscreen_px']} px below the window"
    )


@pytest.mark.parametrize("tag", METAL_MODULES)
def test_the_parameter_fields_are_painted(tag: str) -> None:
    """A card of white space where the parameters should be is not a form."""
    row = _measure(tag)
    assert row["fields"] > 0, f"{tag} exposes no input field at all"
    assert row["fields_visible"] == row["fields"], (
        f"{tag} @ 1366x768: only {row['fields_visible']} of {row['fields']} fields are painted"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2])
        sys.exit(0)
