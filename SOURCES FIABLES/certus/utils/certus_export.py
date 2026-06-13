from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

import logging
import numpy as np
import pandas as pd
import pyqtgraph as pg
from typing import Any

from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox
from PyQt6.QtCore import Qt

# Import shared strings from certus.ui.certus_ui to avoid duplication
from certus.ui.certus_ui import CERTUS_UI_STRINGS


def _export_series_label(item: Any, idx: int) -> str:
    """Extracts a human-readable label from a plot item."""
    name = getattr(item, "name", lambda: None)()
    if name is None:
        opts = getattr(item, "opts", {})
        if isinstance(opts, dict):
            name = opts.get("name")
    if name is None:
        name = getattr(item, "objectName", lambda: "")()
    return str(name).strip() if name else f"Series {idx + 1}"


def _export_y_values_for_item(item: Any, y: np.ndarray) -> np.ndarray:
    """If the curve stores ln(k) for display, export k = exp(y), not ln k."""
    y = np.asarray(y, dtype=float).reshape(-1)
    if not getattr(item, "_certus_export_y_as_exp_k", False):
        return y
    out = np.full(y.shape, np.nan, dtype=float)
    m = np.isfinite(y)
    out[m] = np.exp(np.minimum(y[m], 700.0))
    return out


def iter_plot_data_series(plot_item: pg.PlotItem | None) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """
    Extracts displayable (x, y) series from a pyqtgraph PlotItem.
    Includes PlotDataItem / curves, ScatterPlotItem, BarGraphItem (x vs height).
    """
    out: list[tuple[str, np.ndarray, np.ndarray]] = []
    if plot_item is None:
        return out
    try:
        items = plot_item.listDataItems()
    except NUMERICAL_FAULT_EXCEPTIONS :
        return out

    for idx, item in enumerate(items):
        try:
            if isinstance(item, pg.BarGraphItem):
                opts = getattr(item, "opts", {}) or {}
                x = np.asarray(opts.get("x", []), dtype=float).reshape(-1)
                h = np.asarray(opts.get("height", []), dtype=float).reshape(-1)
                if x.size == 0:
                    continue
                n = min(x.size, h.size)
                x, h = x[:n], h[:n]
                m = np.isfinite(x) & np.isfinite(h)
                x, h = x[m], h[m]
                if x.size == 0:
                    continue
                name = _export_series_label(item, idx)
                out.append((name, x, h))
                continue

            if hasattr(item, "getData"):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                x = np.asarray(x, dtype=float).reshape(-1)
                y = _export_y_values_for_item(item, np.asarray(y, dtype=float).reshape(-1))
                if x.size == 0:
                    continue
                n = min(x.size, y.size)
                x, y = x[:n], y[:n]
                m = np.isfinite(x) & np.isfinite(y)
                x, y = x[m], y[m]
                if x.size == 0:
                    continue
                name = _export_series_label(item, idx)
                out.append((name, x, y))

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.debug("iter_plot_data_series skip %s: %s", type(item).__name__, e)
            continue
    return out


def build_wide_dataframe_for_export(series: list[tuple[str, np.ndarray, np.ndarray]]) -> pd.DataFrame | None:
    """Columns {stem}_x / {stem}_y, NaN padding if lengths differ."""
    if not series:
        return None
    data: dict[str, np.ndarray] = {}
    seen: dict[str, int] = {}

    for idx, (name, x, y) in enumerate(series):
        base = (str(name).strip() if name else "") or "Curve"
        n = seen.get(base, 0)
        seen[base] = n + 1
        stem = base if n == 0 else f"{base}_{n + 1}"
        data[f"{stem}_x"] = np.asarray(x, dtype=float).reshape(-1)
        data[f"{stem}_y"] = np.asarray(y, dtype=float).reshape(-1)

    max_len = max(int(len(v)) for v in data.values())
    for k in list(data.keys()):
        v = data[k]
        if len(v) < max_len:
            data[k] = np.pad(v, (0, max_len - len(v)), constant_values=np.nan)
    return pd.DataFrame(data)




def _extra_scene_plot_series(
    plot_widget: Any, plot_item: pg.PlotItem | None
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Curves on linked ViewBoxes (secondary axis) are missing from the primary PlotItem.listDataItems()."""
    extra: list[tuple[str, np.ndarray, np.ndarray]] = []
    if plot_item is None:
        return extra
    try:
        known = {id(x) for x in plot_item.listDataItems()}
    except NUMERICAL_FAULT_EXCEPTIONS :
        known = set()

    scene = plot_widget.scene() if hasattr(plot_widget, "scene") else None
    if scene is None:
        return extra

    idx = 0
    for item in scene.items():
        if id(item) in known:
            continue
        try:
            if isinstance(item, pg.BarGraphItem):
                opts = getattr(item, "opts", {}) or {}
                x = np.asarray(opts.get("x", []), dtype=float).reshape(-1)
                h = np.asarray(opts.get("height", []), dtype=float).reshape(-1)
                if x.size == 0:
                    continue
                n = min(x.size, h.size)
                x, h = x[:n], h[:n]
                m = np.isfinite(x) & np.isfinite(h)
                x, h = x[m], h[m]
                if x.size == 0:
                    continue
                name = _export_series_label(item, idx)
                extra.append((name, x, h))
                known.add(id(item))
                idx += 1
                continue

            if isinstance(item, pg.PlotDataItem):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                x = np.asarray(x, dtype=float).reshape(-1)
                y = _export_y_values_for_item(item, np.asarray(y, dtype=float).reshape(-1))
                if x.size == 0:
                    continue
                n = min(x.size, y.size)
                x, y = x[:n], y[:n]
                m = np.isfinite(x) & np.isfinite(y)
                x, y = x[m], y[m]
                if x.size == 0:
                    continue
                name = _export_series_label(item, idx)
                extra.append((name, x, y))
                known.add(id(item))
                idx += 1
                continue
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.debug("_extra_scene_plot_series skip %s: %s", type(item).__name__, e)
            continue
    return extra


def plot_dataframe_from_widget(plot_widget: Any) -> pd.DataFrame | None:
    """DataFrame: _certus_clipboard_df_provider if defined, else listDataItems + linked ViewBoxes + _curves."""
    prov = getattr(plot_widget, "_certus_clipboard_df_provider", None)
    if callable(prov):
        try:
            df = prov()
            if df is not None and not getattr(df, "empty", True):
                return df
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.debug("plot_dataframe_from_widget provider: %s", e)

    pi = getattr(plot_widget, "plotItem", None)
    series = iter_plot_data_series(pi)
    series.extend(_extra_scene_plot_series(plot_widget, pi))
    df = build_wide_dataframe_for_export(series)
    if df is not None and not df.empty:
        return df

    curves = getattr(plot_widget, "_curves", None)
    if not isinstance(curves, dict) or not curves:
        return None

    series: list[tuple[str, np.ndarray, np.ndarray]] = []
    for name, curve in curves.items():
        try:
            x_data, y_data = curve.getData()
            if x_data is None or y_data is None:
                continue
            x_data = np.asarray(x_data, dtype=float).reshape(-1)
            y_data = np.asarray(y_data, dtype=float).reshape(-1)
            if x_data.size == 0:
                continue
            n = min(x_data.size, y_data.size)
            x_data, y_data = x_data[:n], y_data[:n]
            m = np.isfinite(x_data) & np.isfinite(y_data)
            x_data, y_data = x_data[m], y_data[m]
            if x_data.size == 0:
                continue
            series.append((str(name), x_data, y_data))
        except NUMERICAL_FAULT_EXCEPTIONS :
            continue
    return build_wide_dataframe_for_export(series)


def copy_plot_to_clipboard_excel(plot_widget: Any) -> bool:
    """Copies TSV (tab separator) for Excel pasting."""
    df = plot_dataframe_from_widget(plot_widget)
    if df is None or df.empty:
        return False
    tsv = df.to_csv(sep="\t", index=False, lineterminator="\n")
    QApplication.clipboard().setText(tsv)
    return True


def show_copy_excel_feedback(parent: Any, ok: bool) -> None:
    """Display standardized user feedback after clipboard export."""
    if ok:
        QMessageBox.information(
            parent,
            CERTUS_UI_STRINGS["export"],
            CERTUS_UI_STRINGS["copy_excel_ok"],
        )
    else:
        QMessageBox.warning(
            parent,
            CERTUS_UI_STRINGS["export"],
            CERTUS_UI_STRINGS["copy_excel_failed"],
        )


def attach_excel_clipboard_context_menu(plot_widget: pg.PlotWidget) -> None:
    """Context menu: Copy data for Excel (single connection).
    Optional: define ``plot_widget._certus_clipboard_df_provider = lambda: pd.DataFrame(...)``
    for custom tabular export (layer stack, heatmap, etc.).
    """
    if getattr(plot_widget, "_certus_excel_clipboard_attached", False):
        return
    plot_widget._certus_excel_clipboard_attached = True
    plot_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _on_menu(pos) -> None:
        menu = QMenu(plot_widget)
        act = menu.addAction(CERTUS_UI_STRINGS["copy_excel_tsv"])
        act.setToolTip("TSV format for Excel")
        chosen = menu.exec(plot_widget.mapToGlobal(pos))
        if chosen != act:
            return
        ok = copy_plot_to_clipboard_excel(plot_widget)
        parent = plot_widget.window()
        if ok:
            QMessageBox.information(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_excel_ok"],
            )
        else:
            QMessageBox.warning(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_excel_failed"],
            )

    plot_widget.customContextMenuRequested.connect(_on_menu)
