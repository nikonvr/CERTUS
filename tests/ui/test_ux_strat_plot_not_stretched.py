"""STRAT's main scientific view must not be stretched (plan UX, 4.3).

The plot area of STRAT is a ``QLabel`` fed a rendered pixmap, and it was built
with ``setScaledContents(True)`` - which stretches the image to fill the widget
**without keeping its aspect ratio**. On a metrology tool that is not cosmetic:
a distorted plot misrepresents the very quantities it exists to show, and the
distortion changes with the window size, so two screenshots of the same run
disagree.

``_apply_pixmap`` re-applied the flag on every refresh, so the defect came back
after each plot update.

This guard checks the property that matters - the ratio survives - rather than
the implementation that happens to provide it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


@pytest.fixture(scope="module")
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1200, 800)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _wide_pixmap():
    """A 2:1 pixmap - any stretching to a squarer widget is then obvious."""
    from PyQt6.QtGui import QPixmap

    pm = QPixmap(400, 200)
    pm.fill()
    return pm


def test_the_plot_label_does_not_stretch_its_pixmap(strat):
    assert not strat.main_plot_widget.hasScaledContents(), (
        "STRAT's plot label stretches its pixmap to the widget, ignoring the "
        "aspect ratio: the displayed curve is distorted"
    )


def test_refreshing_the_plot_does_not_re_enable_stretching(strat):
    """The flag was re-applied on every _apply_pixmap call, so it kept coming back."""
    strat._apply_pixmap(_wide_pixmap())

    assert not strat.main_plot_widget.hasScaledContents(), (
        "_apply_pixmap re-enabled stretching: the defect returns on every refresh"
    )


def test_an_oversized_plot_is_fitted_without_distortion(strat):
    """Turning stretching off must not simply crop a too-large plot.

    With ``setScaledContents(False)`` a pixmap larger than the label is clipped,
    which would trade one defect for a worse one. It has to be scaled down with
    its ratio preserved.
    """
    from PyQt6.QtGui import QPixmap

    label = strat.main_plot_widget
    w, h = label.width(), label.height()
    if w < 50 or h < 50:
        pytest.skip("plot label has no usable size in this layout")

    source = QPixmap(w * 3, int(w * 3 / 2))  # 2:1, three times too wide
    source.fill()
    strat._apply_pixmap(source)

    shown = label.pixmap()
    assert shown is not None and not shown.isNull(), "no pixmap ended up on the label"
    assert shown.width() <= w and shown.height() <= h, (
        f"the plot ({shown.width()}x{shown.height()}) overflows its label ({w}x{h}): it is being cropped, not fitted"
    )
    source_ratio = source.width() / source.height()
    shown_ratio = shown.width() / shown.height()
    assert abs(shown_ratio - source_ratio) < 0.02, (
        f"aspect ratio changed while fitting: source {source_ratio:.3f}, shown {shown_ratio:.3f}"
    )


def test_the_guard_would_catch_stretching_coming_back():
    """Negative control: hasScaledContents is really the property at stake."""
    from PyQt6.QtWidgets import QLabel

    faulty = QLabel()
    faulty.setScaledContents(True)
    assert faulty.hasScaledContents(), "the property no longer reports stretching"
    faulty.deleteLater()
