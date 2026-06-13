import numpy as np
import pyqtgraph as pg

def _add_pg_fit_band_outside_shading(
    plot_widget: pg.PlotWidget,
    fit_lo_nm: float,
    fit_hi_nm: float,
    x_min_nm: float,
    x_max_nm: float,
) -> None:
    """Semi-opaque vertical bands for lambda outside [fit_lo, fit_hi] (data between x_min and x_max)."""

    lo = float(min(fit_lo_nm, fit_hi_nm))

    hi = float(max(fit_lo_nm, fit_hi_nm))

    w0 = float(min(x_min_nm, x_max_nm))

    w1 = float(max(x_min_nm, x_max_nm))

    if not np.isfinite([lo, hi, w0, w1]).all() or w1 <= w0:
        return

    plot_item = plot_widget.plotItem

    brush = pg.mkBrush(88, 90, 98, 62)

    z_back = -40

    if w0 < lo:
        e = min(lo, w1)

        if e > w0:
            r = pg.LinearRegionItem([w0, e], movable=False, brush=brush, pen=pg.mkPen(None))

            r.setZValue(z_back)

            plot_item.addItem(r)

    if hi < w1:
        s = max(hi, w0)

        if w1 > s:
            r = pg.LinearRegionItem([s, w1], movable=False, brush=brush, pen=pg.mkPen(None))

            r.setZValue(z_back)

            plot_item.addItem(r)


def _nan_split_band_y(
    y,
    fit_mask: np.ndarray | None,
) -> tuple[np.ndarray | None, np.ndarray]:
    """If mask: (y out-of-band with internal NaN, y in-band). Otherwise: (None, y)."""

    y_arr = np.asarray(y, dtype=np.float64)

    if fit_mask is None:
        return None, y_arr

    return np.where(~fit_mask, y_arr, np.nan), np.where(fit_mask, y_arr, np.nan)


def _pg_plot_xy_split_band(
    plot_widget: pg.PlotWidget,
    wl,
    y,
    fit_mask: np.ndarray | None,
    pen_inside,
    pen_outside,
    **plot_kw,
):
    """Plot y(lambda); if fit_mask provided, out-of-band segment in gray then in-band segment."""

    wl_arr = np.asarray(wl, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(wl_arr) & np.isfinite(y_arr)
    if not np.any(finite):
        return None
    wl_arr = wl_arr[finite]
    y_arr = y_arr[finite]

    y_out, y_in = _nan_split_band_y(y_arr, fit_mask[finite] if fit_mask is not None and fit_mask.size == finite.size else fit_mask)

    if y_out is None:
        return plot_widget.plot(wl_arr, y_in, pen=pen_inside, **plot_kw)

    plot_widget.plot(wl_arr, y_out, pen=pen_outside)

    return plot_widget.plot(wl_arr, y_in, pen=pen_inside, **plot_kw)


def _pg_plot_scatter_split_band(
    plot_widget: pg.PlotWidget,
    wl,
    y,
    fit_mask: np.ndarray | None,
    symbol_pen_inside,
    symbol_pen_outside,
    *,
    symbol: str = "x",
    symbol_size: float = 5.0,
    name: str | None = None,
):
    """Scatter y(lambda) with symbols; fit out-of-band in gray if mask provided."""

    wl_arr = np.asarray(wl, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(wl_arr) & np.isfinite(y_arr)
    if not np.any(finite):
        return None
    wl_arr = wl_arr[finite]
    y_arr = y_arr[finite]

    fit_mask_arr = None
    if fit_mask is not None:
        fit_mask_arr = np.asarray(fit_mask, dtype=bool)
        if fit_mask_arr.size == finite.size:
            fit_mask_arr = fit_mask_arr[finite]
        elif fit_mask_arr.size != wl_arr.size:
            fit_mask_arr = None

    y_out, y_in = _nan_split_band_y(y_arr, fit_mask_arr)

    kw = {"pen": None, "symbol": symbol, "symbolSize": symbol_size}

    if y_out is None:
        return plot_widget.plot(wl_arr, y_in, symbolPen=symbol_pen_inside, name=name, **kw)

    plot_widget.plot(wl_arr, y_out, symbolPen=symbol_pen_outside, **kw)

    return plot_widget.plot(wl_arr, y_in, symbolPen=symbol_pen_inside, name=name, **kw)
