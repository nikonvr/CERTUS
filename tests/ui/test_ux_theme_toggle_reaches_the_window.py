"""Clicking the theme toggle must retheme the window (plan UX, 4.7).

``CertusThemeToggle.toggle`` ends with::

    if hasattr(w, "_apply_theme"):
        w._apply_theme()
    else:
        apply_certus_theme(w)

🔴 ``CertusBaseApp`` **defines** ``_apply_theme`` as a ``pass`` hook, so
``hasattr`` is true for every window of the suite and **the else branch is dead
code**. A window that does not override the hook therefore gets a no-op: the
palette switches, and its stylesheet is never rebuilt.

📏 Measured 2026-09-08, light window then one click on the toggle - does the
window stylesheet carry the dark surface afterwards?

    CERTUS_DESIGN        oui   (override in certus_design_ui)
    CERTUS_STRAT         oui   (override in certus_strat_ui_layout)
    CERTUS_INDEX_SPLINE  NON   <- no override, so nothing happens

⚠️ This guard checks the WINDOW stylesheet only. The widget-level sheets are a
separate, wider problem: they are f-strings frozen at construction, and 6 to 29
of them per window keep the old palette after a toggle. That limitation is
recorded in the plan; it needs those sheets moved into the global stylesheet,
which is a refactor and not a fix.

📌 SMOOTHER and SUBSTRATE INDEX carry **no toggle at all** - the two modules that
never went through the earlier phases. They are skipped here and named in the
plan rather than silently passing.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

MODULES_UNDER_TEST = ("CERTUS_DESIGN", "CERTUS_STRAT", "CERTUS_INDEX_SPLINE", "CERTUS_INDEX")


@pytest.fixture
def light_window(request, qapp, monkeypatch):
    """A window built in LIGHT, with the preference faked in memory.

    ⚠️ Nothing is written to the user's configuration: ``save_theme_config`` is
    replaced by an in-memory setter, so clicking the toggle cannot leave the
    machine in another theme than it started.
    """
    from PyQt6.QtCore import Qt

    from certus.core import certus_core
    from certus.ui import certus_ui_utils, certus_ui_widgets_utils
    from certus.ui.certus_theme import CertusTheme
    from scripts.audit_ux_certus import MODULES

    state = {"mode": "light"}
    for module in (certus_core, certus_ui_utils, certus_ui_widgets_utils):
        if hasattr(module, "load_theme_config"):
            monkeypatch.setattr(module, "load_theme_config", lambda: state["mode"])
        if hasattr(module, "save_theme_config"):
            monkeypatch.setattr(module, "save_theme_config", lambda m: state.__setitem__("mode", m) or True)

    tag = request.param
    modname, clsname = MODULES[tag]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        yield tag, win, state
    finally:
        win.close()
        CertusTheme.configure("light")


def _toggle_of(win):
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle

    return [w for w in win.findChildren(QWidget) if isinstance(w, CertusThemeToggle)]


@pytest.mark.parametrize("light_window", MODULES_UNDER_TEST, indirect=True)
def test_the_window_offers_a_theme_toggle(light_window):
    """Contrôle négatif : no toggle, and the test below would pass on nothing."""
    tag, win, _state = light_window
    assert _toggle_of(win), f"{tag}: no theme toggle found - the test below would be vacuous"


@pytest.mark.parametrize("light_window", MODULES_UNDER_TEST, indirect=True)
def test_toggling_rebuilds_the_window_stylesheet(light_window, qapp):
    from certus.ui.certus_theme import CertusTheme

    tag, win, state = light_window
    before = win.styleSheet()
    assert before, f"{tag}: the window carries no stylesheet at all"

    _toggle_of(win)[0].toggle()
    qapp.processEvents()

    assert state["mode"] == "dark", f"{tag}: the toggle did not even change the preference"
    dark_surface = CertusTheme.SURFACE.lower()
    assert dark_surface != "#ffffff", "the palette did not switch - nothing to look for"

    assert dark_surface in win.styleSheet().lower(), (
        f"{tag}: after one click on the theme toggle the window stylesheet still does not "
        f"carry the dark surface {dark_surface} - the window keeps its old theme"
    )


# =============================================================================
# The widget-level sheets: the other half of the problem
# =============================================================================


def _still_light(win) -> list[str]:
    """Widgets whose OWN stylesheet still paints the light surface."""
    import re

    from PyQt6.QtWidgets import QWidget

    pattern = re.compile(r"background(-color)?\s*:\s*#ffffff\b", re.IGNORECASE)
    return [
        f"{type(w).__name__}#{w.objectName() or '-'}"
        for w in win.findChildren(QWidget)
        if w.styleSheet() and pattern.search(w.styleSheet())
    ]


@pytest.mark.parametrize("light_window", ["CERTUS_DESIGN", "CERTUS_STRAT"], indirect=True)
def test_a_component_that_can_refresh_itself_actually_does(light_window, qapp):
    """A widget exposing ``refresh_theme`` must not keep the old palette.

    📏 Measured 2026-09-08 before this protocol existed: 20 widget stylesheets on
    DESIGN and 29 on STRAT stayed light after one click. ``CertusCard`` alone
    accounted for 6 and 19 of them - and it already carried a private method to
    re-apply its own sheet, which nothing ever called.
    """
    tag, win, _state = light_window
    _toggle_of(win)[0].toggle()
    qapp.processEvents()

    offenders = [name for name in _still_light(win) if _declares_refresh(win, name)]
    assert not offenders, (
        f"{tag}: {len(offenders)} widget(s) declare a theme refresh and still paint the old "
        f"palette after a toggle: {sorted(set(offenders))}"
    )


def _declares_refresh(win, label: str) -> bool:
    from PyQt6.QtWidgets import QWidget

    cls_name = label.split("#")[0]
    for w in win.findChildren(QWidget):
        if type(w).__name__ == cls_name:
            return callable(getattr(w, "refresh_theme", None))
    return False


#: Ratchet on what the protocol does NOT cover yet: plain QWidget, QPushButton,
#: QTextEdit, QStatusBar whose sheet is written inline at their call site, with
#: no class of their own to carry the method. Lowering these means moving those
#: sheets into the global stylesheet keyed by object name — a refactor of some
#: ninety call sites, not a fix.
#:
#: 📏 Mesuré le 2026-09-08, avant / après le protocole `refresh_theme` :
#:     HUB 6 -> 4 · DESIGN 20 -> 7 · STRAT 29 -> 7 · INDEX SPLINE 22 -> 11
#: Quatre classes partagées portaient donc les deux tiers du défaut.
TOGGLE_RESIDUE_MAX = {"CERTUS_DESIGN": 7, "CERTUS_STRAT": 7}


@pytest.mark.parametrize("light_window", sorted(TOGGLE_RESIDUE_MAX), indirect=True)
def test_the_uncovered_residue_does_not_grow(light_window, qapp):
    """Cliquet : the accepted limitation must not get worse unnoticed."""
    tag, win, _state = light_window
    _toggle_of(win)[0].toggle()
    qapp.processEvents()

    residue = _still_light(win)
    assert len(residue) <= TOGGLE_RESIDUE_MAX[tag], (
        f"{tag}: {len(residue)} widget(s) keep the light palette after a toggle, ceiling is "
        f"{TOGGLE_RESIDUE_MAX[tag]}: {sorted(set(residue))}"
    )
