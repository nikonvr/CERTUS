import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path
import pyqtgraph as pg
from PyQt6.QtWidgets import QMessageBox

from certus.ui.certus_ui import CertusTheme, show_toast
from certus.utils.certus_index_utils import DataType

# Fake exception for toast wrapper if not found
try:
    from certus.spline.certus_index_spline_core import NUMERICAL_FAULT_EXCEPTIONS
except ImportError:
    NUMERICAL_FAULT_EXCEPTIONS = Exception

def _log_loaded_spectrum_metadata(logger, filepath: str, df: pd.DataFrame) -> None:
    """Log canonical metadata for a newly loaded spectrum file."""
    fp_abs = Path(filepath).resolve()
    logger.info("-" * 60)
    logger.info("[FILE] Spectrum loaded: %s", fp_abs)
    logger.info("[FILE] Name: %s", Path(filepath).name)
    logger.info("[FILE] Dimensions: %d rows × %d columns", df.shape[0], df.shape[1])
    logger.info("-" * 60)

def _detected_data_type_label(data_type: DataType) -> str:
    """Return human-readable label for detected spectral data type."""
    type_labels = {
        DataType.TRANSMISSION: " Detected:  TRANSMISSION only",
        DataType.REFLECTION: " Detected:  REFLECTION only",
        DataType.BOTH: " Detected: TRANSMISSION + REFLECTION",
    }
    return type_labels[data_type]

def _update_lambda_bounds_from_target_data(
    target_data: pd.DataFrame,
    sb_lmin,
    sb_lmax,
    logger,
) -> tuple[float, float]:
    """Update lambda spinbox bounds from target data and log range."""
    lmin = float(target_data["lambda"].min())
    lmax = float(target_data["lambda"].max())
    sb_lmin.setValue(lmin)
    sb_lmax.setValue(lmax)
    logger.info("[INDEX.LOAD] spectral range | min=%.1f nm | max=%.1f nm", lmin, lmax)
    return lmin, lmax

def _source_type_label(data_type: DataType) -> str:
    """Return compact source-type label for load summary dialog."""
    return {
        DataType.TRANSMISSION: "Transmission",
        DataType.REFLECTION: "Reflection",
        DataType.BOTH: "Transmission + Reflection",
    }.get(data_type, "Unknown")

def _is_qt_offscreen_mode() -> bool:
    """Return True when Qt is running in offscreen mode."""
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"

def _notify_user(
    parent,
    title: str,
    message: str,
    *,
    level: str = "info",
    blocking: bool = False,
    duration_ms: int = 4000,
) -> None:
    """Unified user feedback: toast-first for non-blocking messages."""
    text = f"{title}: {message}" if title else message

    if not blocking:
        try:
            show_toast(parent, text, level=level, duration_ms=duration_ms)
            return
        except NUMERICAL_FAULT_EXCEPTIONS:
            logging.getLogger("CERTUS").debug("Toast notification failed", exc_info=True)

    if _is_qt_offscreen_mode():
        logging.getLogger("CERTUS").warning("%s", text)
        return

    if level in ("error", "critical"):
        QMessageBox.critical(parent, title or "Error", message)
    elif level == "warning":
        QMessageBox.warning(parent, title or "Warning", message)
    else:
        QMessageBox.information(parent, title or "Info", message)

def _update_loaded_file_label(lbl_file, filepath: str) -> str:
    """Update file label widget and return basename."""
    fname = Path(filepath).name
    lbl_file.setText(f" {fname}")
    lbl_file.setStyleSheet(f"color: {CertusTheme.SUCCESS}; font-weight: bold;")
    lbl_file.setToolTip(filepath)
    return fname

def _set_spectrum_plot_title(plot_spectrum, source_name: str) -> None:
    """Set standardized spectrum title from source name."""
    src_name = Path(source_name).stem
    plot_spectrum.plotItem.setTitle(f"Spectrum      {src_name}")

def _display_detected_data_type(lbl_data_type, logger, data_type: DataType) -> str:
    """Display and log detected source data type label."""
    type_label = _detected_data_type_label(data_type)
    lbl_data_type.setText(type_label)
    logger.info("[INDEX.LOAD] data analysis | type=%s", type_label)
    return type_label

def _prepare_nk_plot_inputs(wls, sub_df, res, logger) -> tuple | None:
    """Prepare n/k arrays and optional IR mask metadata for plotting."""
    if "n_calc" not in sub_df.columns or "k_calc" not in sub_df.columns:
        logger.error(f"Missing n_calc or k_calc in sub_df. Columns: {list(sub_df.columns)}")
        return None

    n_values = sub_df["n_calc"].values.copy()
    k_values = sub_df["k_calc"].values.copy()
    method_str = res.optimization_stats.get("method", "")
    lambda_max_fit = getattr(res.config, "lambda_max_fit", None)
    tlu_mode = lambda_max_fit is not None and "Spline" not in method_str and res.tlu_params is not None

    if tlu_mode:
        ir_mask_ui = wls > lambda_max_fit
        n_values[ir_mask_ui] = np.nan
        k_values[ir_mask_ui] = np.nan

    if np.all(np.isnan(n_values)) or np.all(np.isnan(k_values)):
        logger.error(
            f"n_calc or k_calc are all NaN! n_valid={np.sum(~np.isnan(n_values))}, k_valid={np.sum(~np.isnan(k_values))}"
        )
        return None

    return n_values, k_values, method_str, lambda_max_fit, tlu_mode

class KLogAxisItem(pg.AxisItem):
    """Custom AxisItem to format log10(k) values as decimal linear strings without scientific notation"""
    def tickStrings(self, values, scale, _spacing):
        strings = []
        for v in values:
            try:
                s = np.format_float_positional(10**v, precision=6, trim="-")
                strings.append(s)
            except Exception:
                strings.append("")
        return strings
