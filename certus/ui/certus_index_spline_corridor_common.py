"""CERTUS-INDEX-SPLINE corridors - the constants and the k-axis helper that the three corridor mixins share (moved out of certus_index_spline_corridors.py, S5.3)."""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# d corridor (abs / adaptive): defaults tightened ~4x vs legacy (1e-3 / 1e-4).
_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4


_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5


# RMSE margin of the robust interval drawn under the local parabola of the RMSE(d) tab (sp_corridor_rmse_delta). Not the
# tolerance of the corridor calculation above (sp_corr_rmse_delta), which goes into the configuration of the solver.
_DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA: float = 2e-4


# Minimum half-width (linear k) applied to the Corridors n/k tab display (consistent envelope + tooltip).
_CORRIDOR_K_TAB_MIN_HALF_WIDTH: float = 1e-4


_K_PLOT_YMIN: float = 1e-6
_K_PLOT_YMAX: float = 1e-2


def _apply_fixed_log_k_axis(plot_w: Any | None) -> None:
    """Force the CERTUS k-plot convention on every k graph."""
    if plot_w is None:
        return
    try:
        # 1. Force the internal Log mode first
        plot_w.setLogMode(False, True)

        # 2. Sync the control menu (pyqtgraph 'A' button)
        # to prevent _apply_sensible_empty_range from breaking things
        try:
            plot_w.plotItem.ctrl.logYCheck.setChecked(True)
        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # 3. Set the Y range using log10 exponents
        # This is the most stable method when Log mode is active
        ymin_log = np.log10(_K_PLOT_YMIN)
        ymax_log = np.log10(_K_PLOT_YMAX)
        plot_w.setYRange(ymin_log, ymax_log, padding=0)

    except (AttributeError, RuntimeError, TypeError):
        # The window's logger, fetched here: a module-level `logger` in this leaf would have to be re-exported by the
        # facade, where it would shadow the window's own.
        logging.getLogger("CERTUS_INDEX_SPLINE").debug("_apply_fixed_log_k_axis failed", exc_info=True)
