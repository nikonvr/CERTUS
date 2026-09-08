"""A HUB launcher must behave like a button under the mouse (plan UX, 4.2).

``CERTUS_HUB`` replaced each card's ``mousePressEvent`` with a lambda that
ignores its event argument entirely. Three consequences, all measured:

- **any** mouse button launched the module - a right-click meant to open a
  context menu spawned a CERTUS process instead;
- the launch happened **on press**, so there was no way back: every button in
  every toolkit acts on release precisely so that pressing by mistake can be
  undone by sliding off the control before letting go;
- the assignment shadowed the class method, so the widget's own behaviour was
  unreachable and had to be duplicated for the keyboard.

⚠️ These tests drive a STANDALONE card. In the real window ``activated`` is
wired to ``launch_module``, so activating a card there spawns a CERTUS process
per card - which is what happened while the keyboard guard was being written.
The real window is only ever INSPECTED here, never activated.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


@pytest.fixture
def card(qapp):
    from certus.ui.certus_hub_widgets import ApplicationCard

    widget = ApplicationCard("Test Module", "subtitle", "description", "does_not_exist.py", "T", "#0f62fe")
    widget.resize(112, 130)
    try:
        yield widget
    finally:
        widget.close()


def _mouse(kind: str, button_name: str, pos):
    """Build a QMouseEvent at ``pos`` for the named button."""
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    button = getattr(Qt.MouseButton, button_name)
    etype = QEvent.Type.MouseButtonPress if kind == "press" else QEvent.Type.MouseButtonRelease
    # A press carries its own button in ``buttons``; a release no longer does.
    held = button if kind == "press" else Qt.MouseButton.NoButton
    point = QPointF(*pos)
    return QMouseEvent(etype, point, point, button, held, Qt.KeyboardModifier.NoModifier)


def _watch(widget) -> list[int]:
    fired: list[int] = []
    widget.activated.connect(lambda *_a: fired.append(1))
    return fired


INSIDE = (50.0, 40.0)
OUTSIDE = (400.0, 400.0)


# =============================================================================
# A standalone card: activation, with nothing wired behind it
# =============================================================================


def test_a_left_click_activates_the_card(card):
    """Contrôle négatif : if this failed, every test below would pass for free."""
    fired = _watch(card)
    card.mousePressEvent(_mouse("press", "LeftButton", INSIDE))
    card.mouseReleaseEvent(_mouse("release", "LeftButton", INSIDE))

    assert fired, "a left click does not activate the launcher at all"


def test_pressing_alone_does_not_activate(card):
    """A button acts when released, so a mistaken press can still be undone."""
    fired = _watch(card)
    card.mousePressEvent(_mouse("press", "LeftButton", INSIDE))

    assert not fired, "the module launched on press: there is no way back from a mis-click"


@pytest.mark.parametrize("button_name", ["RightButton", "MiddleButton"])
def test_only_the_left_button_activates(card, button_name: str):
    fired = _watch(card)
    card.mousePressEvent(_mouse("press", button_name, INSIDE))
    card.mouseReleaseEvent(_mouse("release", button_name, INSIDE))

    assert not fired, f"a {button_name} click launched the module"


def test_sliding_off_before_releasing_cancels(card):
    """The escape hatch every button has: press, slide away, let go, nothing happens."""
    fired = _watch(card)
    card.mousePressEvent(_mouse("press", "LeftButton", INSIDE))
    card.mouseReleaseEvent(_mouse("release", "LeftButton", OUTSIDE))

    assert not fired, "releasing outside the card still launched the module"


def test_a_release_without_a_press_does_nothing(card):
    """Guards against arming the card from a click that started elsewhere."""
    fired = _watch(card)
    card.mouseReleaseEvent(_mouse("release", "LeftButton", INSIDE))

    assert not fired, "a stray release activated the launcher"


# =============================================================================
# The real window: inspection only, never activation
# =============================================================================


@pytest.fixture(scope="module")
def hub(qapp):
    from PyQt6.QtCore import Qt

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _launchers(win) -> list:
    from certus.ui.certus_hub_widgets import BaseApplicationCard

    return win.findChildren(BaseApplicationCard)


def test_the_hub_shows_launchers_at_all(hub):
    """Guard against the guard: an empty list would make the test below pass."""
    assert len(_launchers(hub)) >= 9, f"only {len(_launchers(hub))} launcher(s) found"


def test_no_launcher_has_its_mouse_handler_replaced(hub):
    """Reads the wiring; it never fires it.

    An instance attribute shadowing ``mousePressEvent`` bypasses everything the
    class does - the button semantics above included.
    """
    patched = [
        c.accessibleName() or type(c).__name__
        for c in _launchers(hub)
        if "mousePressEvent" in vars(c) or "mouseReleaseEvent" in vars(c)
    ]
    assert not patched, (
        f"{len(patched)} launcher(s) have their mouse handler replaced by the window, "
        f"which bypasses the card's own button behaviour: {patched}"
    )
