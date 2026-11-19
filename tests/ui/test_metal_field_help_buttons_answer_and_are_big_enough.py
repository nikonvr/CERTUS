"""The "?" field-help buttons of METAL are a target one can hit, and they answer (UX audit 2026-11-18, item 4).

Measured at 1366 x 768: SINGLE had 7 of them 16 px wide, BILAYER 12 of them 20 px wide. They took the keyboard focus
and had no receiver of `clicked`: Tab reached a button that Enter, Space and a click left silent. Their help lived in
a tooltip only. The active area is now at least 24 x 24 px (the symbol stays "?"), and a click, Enter or Space shows
the help of the field.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton, QToolTip, QWidget

MIN_TARGET_PX = 24


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "METAL field help", main_windows_only=True)


@pytest.fixture
def shown(monkeypatch) -> list[str]:
    """Every help text the buttons show, recorded instead of drawn."""
    texts: list[str] = []
    monkeypatch.setattr(QToolTip, "showText", lambda _pos, text, *_a, **_k: texts.append(text))
    return texts


def _window(qapp, which: str):
    if which == "SINGLE":
        from certus.ui.certus_metal_single_gui import CertusMetalSingleApp as App
    else:
        from certus.ui.certus_metal_bilayer_gui import CertusMetalBilayerApp as App
    win = App()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1366, 768)
    win.show()
    qapp.processEvents()
    return win


def _help_buttons(win) -> list[QPushButton]:
    return [b for b in win.findChildren(QPushButton) if b.text() == "?" and b.toolTip()]


def _in_window(widget: QWidget, win) -> QRect:
    return QRect(widget.mapTo(win, widget.rect().topLeft()), widget.size())


@pytest.mark.parametrize("which", ["SINGLE", "BILAYER"])
def test_every_field_help_button_is_a_target_one_can_hit(qapp, which) -> None:
    win = _window(qapp, which)
    buttons = _help_buttons(win)
    assert buttons, "no field-help button found"
    small = [(b.toolTip()[:30], b.width(), b.height()) for b in buttons if min(b.width(), b.height()) < MIN_TARGET_PX]
    assert small == [], f"{which}: help buttons under {MIN_TARGET_PX} px"


@pytest.mark.parametrize("which", ["SINGLE", "BILAYER"])
def test_a_field_help_button_overlaps_nothing_at_1366_by_768(qapp, which) -> None:
    win = _window(qapp, which)
    overlaps = []
    for button in (b for b in _help_buttons(win) if b.isVisibleTo(win)):
        area = _in_window(button, win)
        for sibling in button.parentWidget().findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if sibling is button or not sibling.isVisibleTo(win) or sibling.isWindow():
                continue
            if area.intersects(_in_window(sibling, win)):
                overlaps.append((button.toolTip()[:30], type(sibling).__name__))
    assert overlaps == []


@pytest.mark.parametrize("which", ["SINGLE", "BILAYER"])
def test_click_enter_and_space_show_the_help_of_the_field(qapp, which, shown) -> None:
    win = _window(qapp, which)
    for button in _help_buttons(win):
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus, "the keyboard cannot reach the help"
        for press in (
            button.click,
            lambda b=button: QTest.keyClick(b, Qt.Key.Key_Return),
            lambda b=button: QTest.keyClick(b, Qt.Key.Key_Space),
        ):
            shown.clear()
            press()
            assert shown == [button.toolTip()], f"{which}: {button.toolTip()[:30]!r} stayed silent"
