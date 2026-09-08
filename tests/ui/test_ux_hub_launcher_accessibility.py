"""The HUB launchers must be reachable without a mouse (plan UX, 4.2).

The welcome window is the first thing the suite shows, and its ten module
launchers are ``QFrame`` subclasses, not buttons. Measured before this guard:
no focus policy, no key handling and no accessible name anywhere in
``certus_hub_widgets.py`` - the entry point of the whole suite was mouse-only
and mute to a screen reader.

A launcher must therefore:

- accept keyboard focus, so Tab can reach it;
- activate on Enter / Return / Space, like any button;
- carry an accessible name, so it can be announced.

⚠️ The activation test builds a STANDALONE card on purpose. In the real window
the signal is wired to ``launch_module``, so emitting it there would spawn a
CERTUS process per card - which is exactly what happened while this guard was
being written.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


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


# =============================================================================
# The real window: inspection only, never activation
# =============================================================================


def test_the_hub_shows_launchers_at_all(hub):
    """Guard against the guard: an empty list would make everything below pass."""
    assert len(_launchers(hub)) >= 9, f"only {len(_launchers(hub))} launcher(s) found"


def test_every_launcher_accepts_keyboard_focus(hub):
    from PyQt6.QtCore import Qt

    unreachable = [
        c.accessibleName() or type(c).__name__
        for c in _launchers(hub)
        if not (c.focusPolicy() & Qt.FocusPolicy.TabFocus)
    ]
    assert not unreachable, f"launcher(s) that Tab cannot reach - the suite's entry point is mouse-only: {unreachable}"


def test_every_launcher_carries_an_accessible_name(hub):
    anonymous = [type(c).__name__ for c in _launchers(hub) if not c.accessibleName().strip()]
    assert not anonymous, f"{len(anonymous)} launcher(s) a screen reader cannot announce: {sorted(set(anonymous))}"


# =============================================================================
# A standalone card: activation, with nothing wired behind it
# =============================================================================


@pytest.fixture
def standalone_card(qapp):
    from certus.ui.certus_hub_widgets import ApplicationCard

    card = ApplicationCard("Test Module", "subtitle", "description", "does_not_exist.py", "T", "#0f62fe")
    try:
        yield card
    finally:
        card.close()


@pytest.mark.parametrize("key_name", ["Key_Return", "Key_Enter", "Key_Space"])
def test_a_launcher_activates_on_the_keyboard(standalone_card, key_name):
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent

    fired: list[int] = []
    standalone_card.activated.connect(lambda *_a: fired.append(1))
    standalone_card.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            getattr(Qt.Key, key_name),
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert fired, f"a launcher ignores {key_name}"


def test_an_unrelated_key_does_not_activate(standalone_card):
    """Negative control: the handler must not fire on just any key."""
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent

    fired: list[int] = []
    standalone_card.activated.connect(lambda *_a: fired.append(1))
    standalone_card.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier))

    assert not fired, "the launcher activated on an unrelated key"
