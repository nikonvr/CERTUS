"""An empty plot must say it is empty (plan UX, 4.4).

Opened with nothing loaded, SMOOTHER shows a "Wavelength (nm)" axis graduated
from 0 to 1 and an "Amplitude" axis from 0 to 1, and says nothing. Those
gradations are Qt's default range, not a measurement - but they read as one, so
the window looks like it displays data when it displays none.

The check is on the property that matters: with no data loaded, the plot must
carry a readable message. How that message is drawn is left open.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


@pytest.fixture
def smoother(qapp):
    from PyQt6.QtCore import Qt

    from certus.utils.certus_curve_smoother import CurveSmootherGUI

    win = CurveSmootherGUI()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _plot_texts(win) -> list[str]:
    """Every piece of text drawn inside the plot area."""
    import pyqtgraph as pg

    texts = []
    for item in win.plot_widget.plotItem.items:
        if isinstance(item, pg.TextItem):
            texts.append(item.toPlainText() if hasattr(item, "toPlainText") else str(item.textItem.toPlainText()))
    return [t for t in texts if t and t.strip()]


def test_the_window_starts_with_no_data(smoother):
    """Contrôle négatif : if data were loaded, the empty state would be untestable."""
    assert getattr(smoother, "df", None) is None, "the window opened with data already loaded"


def test_an_empty_plot_carries_a_message(smoother):
    texts = _plot_texts(smoother)
    assert texts, (
        "the plot is empty and says nothing: its axes graduated 0 to 1 read as a measurement when there is none"
    )


def test_the_message_disappears_once_data_is_plotted(smoother):
    """An empty-state notice left over a real curve would be worse than none."""
    import numpy as np
    import pandas as pd

    assert _plot_texts(smoother), "no empty-state message to begin with"

    smoother.df = pd.DataFrame({"lambda": np.linspace(400.0, 800.0, 50), "sample": np.linspace(0.1, 0.9, 50)})
    smoother.update_plot()

    assert not _plot_texts(smoother), f"the empty-state message is still shown over real data: {_plot_texts(smoother)}"
