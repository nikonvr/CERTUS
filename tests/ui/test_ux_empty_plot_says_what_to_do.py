"""An empty plot carries a card that says what to do, and the card follows the data (U10, C1).

The card of a table followed only the resizes and once covered fresh results (2026-09-04); this one follows the
items of the plot and every `setData` of its curves.
"""

from __future__ import annotations

import numpy as np


def _plot(qapp):
    import pyqtgraph as pg
    from PyQt6.QtWidgets import QWidget

    host = QWidget()
    plot = pg.PlotWidget(host)
    plot.resize(400, 300)
    host.show()
    qapp.processEvents()
    return host, plot


def test_the_card_follows_the_data_of_the_curves(qapp) -> None:
    from certus.ui.certus_empty_state import attach_plot_empty_state

    host, plot = _plot(qapp)
    curve = plot.plot([], [])
    card = attach_plot_empty_state(plot, title="No spectrum loaded", description="Load a spectrum.")
    assert card.isVisible()

    curve.setData(np.arange(5.0), np.arange(5.0))
    assert not card.isVisible()

    plot.clear()
    assert card.isVisible()

    plot.plot(np.arange(3.0), np.ones(3))
    assert not card.isVisible()
    host.close()


def test_the_card_lets_the_mouse_through(qapp) -> None:
    from PyQt6.QtCore import Qt

    from certus.ui.certus_empty_state import attach_plot_empty_state

    host, plot = _plot(qapp)
    card = attach_plot_empty_state(plot, title="No data", description="Load data.")
    assert card.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    host.close()
