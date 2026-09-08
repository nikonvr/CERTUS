"""No control anywhere in the suite may leave the operator guessing (plan UX, 6).

``test_ux_orphan_modules_tooltips`` covers the two modules that had never been
audited. This one asks the same question of all eleven windows at once, so the
criterion "fields with no tooltip = 0" is measured rather than assumed.

📏 Measured 2026-09-08 across the whole suite: **12 mute controls out of 346**,
all of them in CERTUS_DESIGN and all of them the same widget - the refractive
index spin boxes of the Materials card. Every other window was already at zero.
The plan carried "19" from an earlier count; the number had gone stale.

⚠️ A tooltip must be DEDUCED from what the widget does. These say the material,
the wavelength their column is headed with, and the range the code declares -
nothing that is not already in ``_build_materials_group``.

The internal line edit of a spin box is excluded: Qt creates it, the operator
sees the spin box, and Qt shows the parent's tooltip over it anyway.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

from scripts.audit_ux_certus import MODULES


@pytest.fixture(scope="module", params=list(MODULES.keys()))
def window(request, qapp):
    from PyQt6.QtCore import Qt

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
        if isinstance(w, QLineEdit) and w.objectName() == "qt_spinbox_lineedit":
            continue
        out.append(w)
    return out


def test_there_are_controls_to_inspect(window):
    """Contrôle négatif : an empty list would make the test below pass on anything."""
    assert len(_controls(window)) >= 5, f"{window._certus_tag}: only {len(_controls(window))} control(s) found"


def test_every_control_explains_itself(window):
    mute = []
    for w in _controls(window):
        if not w.toolTip().strip():
            label = (w.text() if hasattr(w, "text") else "") or type(w).__name__
            mute.append(f"{type(w).__name__}:{str(label)[:34]}")
    assert not mute, f"{window._certus_tag}: {len(mute)} control(s) with nothing to explain them: {mute}"
