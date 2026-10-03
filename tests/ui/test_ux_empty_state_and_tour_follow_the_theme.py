"""The ink of the empty states and of the guided tour follows the theme (audit UX A05, ETAT D82).

`color: palette(text)` reads the QPalette of the widget, and a CERTUS window does not keep its QPalette in step with
its theme: the dark theme is painted by style sheets. Measured 2026-10-02 on RE in dark mode, the empty-state titles
and the coach-mark titles resolved to black on a navy ground, and the descriptions to a fixed light grey, which on the
light theme is 1.98:1 on white (WCAG AA asks 4.5:1 for text this size).

The ink is now a token of the palette, written by an f-string: `CertusTheme.refresh_widget_sheets()` rewrites it on
the theme toggle. Three things are pinned: no sheet reads the QPalette, each ink is the token it should be in both
themes, and it stays readable on the ground it sits on.
"""

from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QLabel, QWidget

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_empty_state import build_empty_state
from certus.ui.certus_onboarding import TourStep, _build_overlay_class
from certus.ui.certus_theme import CertusTheme


@pytest.fixture(autouse=True)
def light_palette():
    """Every test starts and ends in the light palette: `CertusTheme` is a class, its palette is process state."""
    CertusTheme.configure("light")
    yield
    CertusTheme.configure("light")


def _ink(label: QLabel) -> str:
    match = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{6})", label.styleSheet())
    assert match, f"no colour in the sheet of {label.objectName()!r}: {label.styleSheet()!r}"
    return match.group(1).lower()


def _empty_state():
    """The widget itself: its labels die with it, so the caller must keep it."""
    return build_empty_state(None, title="No layers yet", description="Add a layer from the toolbar.")


def _labels(state):
    return state.findChild(QLabel, "empty-title"), state.findChild(QLabel, "empty-desc")


def _coach_labels():
    parent = QWidget()
    parent.resize(640, 480)
    overlay = _build_overlay_class()(parent, "TEST", [(TourStep(title="Welcome", body="Load a file first."), None)])
    coach = overlay._coach
    return parent, [coach.findChild(QLabel, name) for name in ("coach-title", "coach-body", "coach-progress")]


EXPECTED_INK = ("TEXT_MAIN", "TEXT_SUB")


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_empty_state_ink_is_the_ink_of_the_theme(qapp, mode) -> None:
    CertusTheme.configure(mode)
    state = _empty_state()
    for label, token in zip(_labels(state), EXPECTED_INK, strict=True):
        assert "palette(" not in label.styleSheet(), label.styleSheet()
        assert _ink(label) == str(getattr(CertusTheme, token)).lower(), (label.objectName(), mode)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_coach_mark_ink_is_the_ink_of_the_theme(qapp, mode) -> None:
    CertusTheme.configure(mode)
    parent, labels = _coach_labels()
    try:
        for label, token in zip(labels, ("TEXT_MAIN", "TEXT_SUB", "TEXT_SUB"), strict=True):
            assert "palette(" not in label.styleSheet(), label.styleSheet()
            assert _ink(label) == str(getattr(CertusTheme, token)).lower(), (label.objectName(), mode)
    finally:
        parent.deleteLater()


def test_the_ink_follows_the_toggle_of_a_window_that_is_already_built(qapp) -> None:
    """A widget built in the light theme is repainted by the toggle: that is what `palette(...)` could not do."""
    state = _empty_state()
    title, desc = _labels(state)
    assert _ink(title) == str(CertusTheme.TEXT_MAIN).lower()

    CertusTheme.configure("dark")
    CertusTheme.refresh_widget_sheets()

    assert _ink(title) == str(CertusTheme.TEXT_MAIN).lower()
    assert _ink(desc) == str(CertusTheme.TEXT_SUB).lower()
    assert _ink(title) != "#0f172a", "the title kept the ink of the light theme"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_description_is_readable_on_the_ground_it_sits_on(qapp, mode) -> None:
    CertusTheme.configure(mode)
    state = _empty_state()
    _, desc = _labels(state)
    for ground in (CertusTheme.BACKGROUND, CertusTheme.SURFACE):
        assert contrast_ratio(_ink(desc), str(ground)) >= 4.5, (mode, _ink(desc), str(ground))
