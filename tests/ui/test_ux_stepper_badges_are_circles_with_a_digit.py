"""The numbered badges of the stepper are circles with a digit in them, inside a real window (audit v2, plan S6.4b).

📏 Measured 2026-10-01 in CERTUS-INDEX-SPLINE, the one window that builds a `CertusStepper`:

    before   the 7 badges are 24 x 48 px, and their pixels are ONE colour: no digit. The active one is a flat blue rectangle.
    after    24 x 24 px, white digit pixels on the blue, a slate digit on the white.

The cause is the generic QPushButton rule of the window sheet, `padding: 8px 16px; min-height: 28px`: on a 24 px badge, 16 px of padding on
each side leaves no room for the digit (it is clipped away), and `min-height` stretches the circle. The badge sheet said nothing about
either, so it inherited both. The standalone stepper of the other tests, in a window without the application sheet, never showed it.
"""

from __future__ import annotations

import os
from collections import Counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_theme import CertusTheme


@pytest.fixture(autouse=True)
def light_palette():
    CertusTheme.configure("light")
    yield
    CertusTheme.configure("light")


def digit_contrast(button: QWidget) -> float:
    """Contrast between the dominant colour of a badge and the colour farthest from it (the digit). 1.0: nothing is drawn."""
    button.show()
    QApplication.processEvents()
    image: QImage = button.grab().toImage()
    counts = Counter(image.pixel(x, y) for y in range(image.height()) for x in range(image.width()))
    fill = QColor.fromRgb(counts.most_common(1)[0][0]).name()
    farthest = max((QColor.fromRgb(p).name() for p in counts), key=lambda c: contrast_ratio(c, fill))
    return contrast_ratio(farthest, fill)


@pytest.fixture
def stepper_in_a_window(qapp):
    from certus.ui.certus_ui_utils import apply_certus_theme
    from certus.ui.certus_ui_widgets_layout import CertusStepper

    window = QWidget()
    window.resize(400, 300)
    apply_certus_theme(window)  # the sheet every window of the suite carries, generic QPushButton rule included
    stepper = CertusStepper(["Un", "Deux", "Trois"], parent=window)
    stepper.set_step(1)
    window.show()
    QApplication.processEvents()
    try:
        yield stepper
    finally:
        window.close()


def test_the_window_sheet_does_carry_the_generic_button_rule_that_crushes_a_small_button(stepper_in_a_window):
    """Why the badge must say `padding` and `min-height` itself: a plain 24 px button in the same window is crushed the same way."""
    window = stepper_in_a_window.window()
    assert "padding: 8px 16px" in window.styleSheet() and "min-height: 28px" in window.styleSheet()
    crushed = QPushButton("2", window)
    crushed.setFixedSize(24, 24)
    crushed.setStyleSheet("QPushButton { background: #0f62fe; color: #ffffff; border: 2px solid #0f62fe; border-radius: 12px; font-weight: 700; }")
    assert digit_contrast(crushed) == pytest.approx(1.0), "no digit is drawn: the measure below can tell a crushed badge"


def test_a_badge_keeps_the_24_px_circle_it_asks_for_inside_a_window_that_carries_the_application_sheet(stepper_in_a_window):
    for badge in stepper_in_a_window._badges:
        assert badge.size() == QSize(24, 24), (badge.objectName(), badge.size())


def test_the_digit_of_every_badge_is_drawn_inside_such_a_window(stepper_in_a_window):
    ratios = {badge.objectName(): round(digit_contrast(badge), 2) for badge in stepper_in_a_window._badges}
    assert all(r >= 4.5 for r in ratios.values()), ratios


def test_the_stepper_of_index_spline_shows_its_numbers(qapp):
    """The real window: the only place the suite builds a stepper."""
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    win = CertusIndexSplineApp()
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        badges = [b for b in win.findChildren(QPushButton) if b.objectName().startswith("StepBadge_")]
        assert len(badges) >= 5
        assert {b.size() for b in badges} == {QSize(24, 24)}
        assert min(digit_contrast(b) for b in badges) >= 4.5
    finally:
        win.close()
