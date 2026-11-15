"""A plot is exported with the data it was given, not with what the view shows (audit 2026-11-15, M-L4d).

``iter_plot_data_series`` read ``item.getData()``. For a pyqtgraph ``PlotDataItem`` that is the *displayed* dataset: in
log mode the exported values were log10 of the data, and with clipping to the view or downsampling the file held only
the part of the curve on screen.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from certus.utils.certus_export import iter_plot_data_series

X = np.linspace(400.0, 800.0, 401)
Y = 0.5 + 0.4 * np.sin(X / 30.0)


def test_a_log_axis_does_not_change_the_exported_values(qapp) -> None:
    plot = pg.PlotWidget()
    plot.plot(X, Y, name="T")
    plot.getPlotItem().setLogMode(x=False, y=True)
    qapp.processEvents()

    [(name, x, y)] = iter_plot_data_series(plot.getPlotItem())

    assert name == "T"
    np.testing.assert_array_equal(x, X)
    np.testing.assert_array_equal(y, Y)
    plot.close()


def test_a_zoomed_and_clipped_view_exports_the_whole_curve(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    curve = plot.plot(X, Y, name="T")
    curve.setClipToView(True)
    curve.setDownsampling(ds=8, auto=False, method="subsample")
    plot.getPlotItem().setXRange(500.0, 520.0, padding=0)
    plot.show()
    qapp.processEvents()

    [(_name, x, y)] = iter_plot_data_series(plot.getPlotItem())

    np.testing.assert_array_equal(x, X)
    np.testing.assert_array_equal(y, Y)
    plot.close()
