"""A dark window must not carry light-mode paint (plan UX, 4.7).

A stylesheet set on a widget is an f-string evaluated ONCE, while the widget is
built. ``apply_certus_theme`` is what configures the palette from the persisted
preference — and it is called at the END of the build. Every widget-level sheet
therefore froze the palette that happened to be loaded at import, which is the
light one.

📏 Measured 2026-09-08, dark preference:

    CERTUS_HUB      9 widget stylesheets out of 59 painting light colours
    CERTUS_DESIGN  34 out of 93

Among them the header band, the bottom bar, the log panel — and
``CertusThemeToggle``, the very control that switches the theme.

⚠️ **Two defects were cancelling each other**, which is why nobody saw it: the
value of a stat card is painted with ``TEXT``, the one token that is the SAME
dark navy in both modes. On a frozen-white card that reads fine. Fixing the
freeze ALONE would have put dark navy on a dark surface — 1.01:1, invisible.
The card now uses ``TEXT_MAIN``, which follows the theme.

📌 Out of scope, and it is a real limit: this says nothing about switching the
theme AT RUNTIME. Those widget sheets stay frozen at whatever the palette was
when the window was built; only a rebuild refreshes them.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

MODULES_UNDER_TEST = ("CERTUS_HUB", "CERTUS_DESIGN")


@pytest.fixture
def dark_window(request, qapp, monkeypatch):
    """A window built exactly as it launches, with a dark persisted preference."""
    from PyQt6.QtCore import Qt

    from certus.core import certus_core
    from certus.ui import certus_ui_utils
    from certus.ui.certus_theme import CertusTheme
    from scripts.audit_ux_certus import MODULES

    tag = request.param
    monkeypatch.setattr(certus_core, "load_theme_config", lambda: "dark")
    monkeypatch.setattr(certus_ui_utils, "load_theme_config", lambda: "dark")

    modname, clsname = MODULES[tag]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1600, 1000)
    win.show()
    qapp.processEvents()

    # Guard against the guard: if the preference never reached the palette,
    # everything below would compare dark paint against a light palette.
    assert CertusTheme.SURFACE.lower() != "#ffffff", (
        f"asked for dark but the window came up with SURFACE={CertusTheme.SURFACE}"
    )
    try:
        yield tag, win
    finally:
        win.close()
        CertusTheme.configure("light")


def _light_surface() -> str:
    from certus.ui.certus_theme import CertusTheme

    current = CertusTheme.SURFACE
    CertusTheme.configure("light")
    light = CertusTheme.SURFACE.lower()
    # Put the palette back where the caller had it.
    CertusTheme.configure("dark" if current.lower() != light else "light")
    return light


def _frozen(win, light_surface: str) -> list[str]:
    """Widget stylesheets painting the LIGHT surface as a background."""
    from PyQt6.QtWidgets import QWidget

    pattern = re.compile(rf"background(-color)?\s*:\s*{re.escape(light_surface)}\b", re.IGNORECASE)
    out = []
    for w in win.findChildren(QWidget):
        sheet = w.styleSheet()
        if sheet and pattern.search(sheet):
            out.append(f"{type(w).__name__}#{w.objectName() or '-'}")
    return out


class _Holder:
    """Minimal stand-in so the two controls can exercise the real scanner."""

    def __init__(self, child) -> None:
        self._child = child

    def findChildren(self, _cls):  # noqa: N802 - Qt naming
        return [self._child]


def test_the_probe_catches_a_rigged_widget(qapp):
    """Contrôle négatif : a widget deliberately painting white must be seen."""
    from PyQt6.QtWidgets import QWidget

    rigged = QWidget()
    rigged.setStyleSheet("background-color: #ffffff;")
    assert _frozen(_Holder(rigged), "#ffffff"), "the probe cannot see a widget painting the light surface"


def test_the_probe_ignores_white_TEXT_on_a_dark_widget(qapp):  # noqa: N802 - reads better capitalised
    """Contrôle positif : white as a LABEL colour is legitimate and must not fire.

    Without this, the guard would condemn every button whose label is white.
    """
    from PyQt6.QtWidgets import QWidget

    fine = QWidget()
    fine.setStyleSheet("background-color: #111827; color: #ffffff;")
    assert not _frozen(_Holder(fine), "#ffffff"), "the probe fires on a white label over a dark background"


@pytest.mark.parametrize("dark_window", MODULES_UNDER_TEST, indirect=True)
def test_there_are_widget_stylesheets_to_inspect(dark_window):
    """Contrôle négatif : no sheet, no finding, and the test below is vacuous."""
    from PyQt6.QtWidgets import QWidget

    _tag, win = dark_window
    sheets = [w for w in win.findChildren(QWidget) if w.styleSheet()]
    assert len(sheets) >= 20, f"only {len(sheets)} widget-level stylesheet(s) found"


@pytest.mark.parametrize("dark_window", MODULES_UNDER_TEST, indirect=True)
def test_no_widget_paints_the_light_surface_in_dark_mode(dark_window):
    tag, win = dark_window
    light = _light_surface()
    frozen = _frozen(win, light)
    assert not frozen, (
        f"{tag}: {len(frozen)} widget(s) still paint the light surface {light} on a dark "
        f"window - their stylesheet was built before the palette was set: {frozen[:10]}"
    )
