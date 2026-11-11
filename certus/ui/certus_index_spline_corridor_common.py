"""CERTUS-INDEX-SPLINE corridors - the constants and the k-axis helper that the three corridor mixins share (moved out of certus_index_spline_corridors.py, S5.3)."""

from __future__ import annotations

import os
from typing import Any

import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# d corridor (abs / adaptive): defaults tightened ~4x vs legacy (1e-3 / 1e-4).
_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4


_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5


# Minimum half-width (linear k) applied to the Corridors n/k tab display (consistent envelope + tooltip).
_CORRIDOR_K_TAB_MIN_HALF_WIDTH: float = 1e-4


def _apply_fixed_log_k_axis(plot_w: Any | None) -> None:
    """Force the CERTUS log-k axis convention locally in this module."""
    if plot_w is None:
        return
    try:
        ymin_log = np.log10(1e-6)
        ymax_log = np.log10(1e-2)
        plot_w.setLogMode(False, True)
        try:
            plot_w.plotItem.ctrl.logYCheck.setChecked(True)
        except (AttributeError, RuntimeError):
            pass
        plot_w.setYRange(ymin_log, ymax_log, padding=0)
    except (AttributeError, RuntimeError, TypeError):
        import logging
        logging.getLogger("CERTUS").debug("_apply_fixed_log_k_axis failed", exc_info=True)
