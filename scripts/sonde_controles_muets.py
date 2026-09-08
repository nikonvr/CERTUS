"""Count the controls that explain nothing, across every window of the suite.

Same definition as ``tests/ui/test_ux_orphan_modules_tooltips.py``: a control is
a visible button, check box, combo, spin box or line edit that the operator can
aim at. Qt's internal line edit inside a spin box is excluded - the operator
sees the spin box, and Qt shows the parent's tooltip over it anyway.
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def controls(win):
    from PyQt6.QtWidgets import (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QLineEdit,
        QPushButton,
        QToolButton,
    )

    out = []
    for w in win.findChildren((QPushButton, QToolButton, QCheckBox, QComboBox, QAbstractSpinBox, QLineEdit)):
        if not w.isVisible():
            continue
        if isinstance(w, QLineEdit) and w.objectName() == "qt_spinbox_lineedit":
            continue
        out.append(w)
    return out


def main() -> int:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from scripts.audit_ux_certus import MODULES

    app = QApplication.instance() or QApplication([])

    total_controls = 0
    total_mute = 0
    for tag, (modname, clsname) in MODULES.items():
        try:
            cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
            win = cls()
            win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            win.resize(1920, 1080)
            win.show()
            app.processEvents()
        except Exception as exc:  # noqa: BLE001 - a window that will not build is a result
            print(f"{tag:<26} BUILD FAILED: {type(exc).__name__}: {exc}")
            continue

        found = controls(win)
        mute = [w for w in found if not w.toolTip().strip()]
        total_controls += len(found)
        total_mute += len(mute)
        flag = "" if not mute else "  <-"
        print(f"{tag:<26} {len(mute):>3} mute / {len(found):>3} controls{flag}")
        for w in mute[:8]:
            label = (w.text() if hasattr(w, "text") else "") or ""
            print(f"      {type(w).__name__}: {str(label)[:44]!r}")
        if len(mute) > 8:
            print(f"      ... and {len(mute) - 8} more")

        win.close()
        app.processEvents()

    print(f"\nTOTAL  {total_mute} mute control(s) out of {total_controls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
