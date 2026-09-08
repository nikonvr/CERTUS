"""Every control of the two never-audited modules must explain itself (plan UX, 4.4).

SMOOTHER and SUBSTRATE INDEX received none of the earlier phases' work. Measured
2026-09-08: SMOOTHER had 4 buttons out of 12 and all 3 of its fields without a
tooltip; SUBSTRATE INDEX 2 buttons out of 11 and 2 spin boxes.

⚠️ A tooltip must be DEDUCED from what the widget actually does - the slot it is
connected to, the range it declares. A tooltip that is merely plausible is worse
than none: it will be believed. Where the role could not be established from the
code, the widget is left alone and named in the plan.

The internal line edit of a spin box is excluded: Qt creates it, the operator
sees the spin box, and Qt shows the parent's tooltip over it anyway.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

MODULES_UNDER_TEST = ("CERTUS_SMOOTHER", "CERTUS_SUBSTRATE_INDEX")


@pytest.fixture(scope="module", params=MODULES_UNDER_TEST)
def window(request, qapp):
    from PyQt6.QtCore import Qt

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[request.param]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1920, 1080)
    win.show()
    win._certus_tag = request.param
    try:
        yield win
    finally:
        win.close()


def _controls(win):
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
        # Qt's own sub-widget inside a spin box: not something the operator aims at.
        if isinstance(w, QLineEdit) and w.objectName() == "qt_spinbox_lineedit":
            continue
        out.append(w)
    return out


def test_there_are_controls_to_inspect(window):
    """Contrôle négatif : an empty list would make the guard pass on anything."""
    assert len(_controls(window)) >= 8, f"{window._certus_tag}: only {len(_controls(window))} control(s) found"


def test_every_control_carries_a_tooltip(window):
    mute = []
    for w in _controls(window):
        if not w.toolTip().strip():
            label = (w.text() if hasattr(w, "text") else "") or type(w).__name__
            mute.append(f"{type(w).__name__}:{str(label)[:34]}")
    assert not mute, f"{window._certus_tag}: {len(mute)} control(s) with nothing to explain them: {mute}"
