from __future__ import annotations

# -*- coding: utf-8 -*-
"""
CERTUS INDEX SPLINE UI
Modularized User Interface for Spline Index characterization app.
Contains CertusIndexSplineApp, LiveIndexMonitor, and companions.
"""
#!/usr/bin/env python3


"""

CERTUS-INDEX-SPLINE  Global fit of n(lambda), k(lambda) as piecewise-linear in sigma=1/lambda (ln k at nodes).

Standalone: no imports from CERTUS_INDEX nor certus_swanepool. Local optimization only.

P1 boundary: preserve the stronger local structure of this module. Keep settings,
persistence, spline editing, workers, and numerical helpers separated; avoid
large moves without dedicated tests for smart init, validation, and resume flows.
# Keep this file locally cohesive; prefer tiny helper/test updates over broad refactors.

"""


import logging
from threading import Event
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg

from certus.core.certus_core import (
    create_module_environment,
)
from certus.spline.certus_index_spline_core import (
    _MAIN_SPLITTER_LAYOUT_REV,
    _QS_LAST_SPECTRUM,
    _QS_MAIN_SPLITTER_LAYOUT_REV,
    _QS_MAIN_SPLITTER_STATE,
    _QS_RIGHT_SPLITTER_STATE,
    _QS_SPECTRUM_FIT_R,
    _QS_SPECTRUM_FIT_T,
    _QS_SPECTRUM_FIT_TREL,
    _QS_SPECTRUM_WR,
    _QS_SPECTRUM_WT,
    _QS_SPLINE_APP,
    _QS_SPLINE_ORG,
    _QS_SPLINE_UNCERTAINTY_DEFAULTS_REV,
    _UNCERTAINTY_DEFAULTS_REV,
    SIO2_DEFAULT_D_HI_NM,
    SIO2_DEFAULT_D_LO_NM,
)
from certus.ui.certus_index_spline_corridors import (
    _CORRIDOR_K_TAB_MIN_HALF_WIDTH,
    _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN,
    _DEFAULT_CORRIDOR_RMSE_DELTA,
    _K_PLOT_YMAX,
    _K_PLOT_YMIN,
    _apply_fixed_log_k_axis,
    _CorridorGenMixin,
    _CorridorWorkerMixin,
    _DataMixin,
)
from certus.ui.certus_index_spline_execution import (
    _CorridorExportMixin,
    _RunMixin,
)
from certus.ui.certus_index_spline_rendering import (
    _PlotMixin,
    _UIBuilderMixin,
)
from certus.ui.certus_index_spline_settings import (
    _CorridorControlMixin,
    _SettingsMixin,
)
from certus.ui.certus_ui import (
    CertusTheme,
)
from certus.utils.certus_index_utils import (
    _get_substrate_n_array_spline,
)
from certus.utils.certus_ux import Typography

# Bootstrap

_env = create_module_environment(__file__, "CERTUS_INDEX_SPLINE")

_SCRIPT_DIR = _env["script_dir"]

logger = logging.getLogger("CERTUS_INDEX_SPLINE")

_QS_NK_PROFILE_INTERP = "nk_profile_interp"

_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY = "spline_simple_auto_uncertainty"

_QS_SMART_INIT_DEEP = "smart_init_deep_pglobal_after_manual"

_QS_SMART_INIT_TWO_PHASE = "smart_init_deep_two_phase_enabled"

# _UNCERTAINTY_DEFAULTS_REV (spline core): increment it to reapply corridor / bootstrap / SiO2 defaults once on existing
# workstations.

# INDEX-SPLINE defaults for thin SiO2 layers (~1.6-1.8 ?m) on sapphire, TSIO2-type spectra (UV-IR, T/Tsub).

# Aligned on a validated session (Fast profile, mesh K=14 if lambda_max > 4000 nm, RMSE window 250-5000 nm).

SIO2_DEFAULT_NK_PROFILE_INTERP: str = "smooth"

SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM: float = 250.0

SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM: float = 5000.0

SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED: bool = True

# Auto-Best uses manual mode with a uniform sigma mesh and 12 anchor nodes

# (N_seg=11 -> K=12), quality preset, without adaptive/auto-K stages.

AUTO_BEST_MANUAL_N_SEG: int = 11  # K = N_seg + 1 = 12 wavelengths via sigma=1/lambda

# Adaptive mesh worker defaults (outside Auto-Best), aligned with core behavior.

from certus.spline.certus_index_spline_core import (
    SplineOptConfig,
)
from certus.spline.certus_index_spline_excel_export import (
    _ExcelExportMixin,
)
from certus.spline.spline_profile_corridors import (
    compute_regular_grid_rmse_profile,
    quick_pwlnk_refit_result_dict,
)
from certus.ui.certus_index_spline_corridor_jobs import (
    _worker_corridor_rmse_healer,
    _worker_corridor_rmse_regular_grid,
    _worker_curve_minimum_deep_refit,
)


def _add_spectrum_thickness_badge(
    plot_w: Any | None, x_vals: np.ndarray, y_vals: np.ndarray, d_nm: float
) -> Any | None:
    """Add a visible thickness badge inside the spectral response plot."""
    if plot_w is None or not np.isfinite(float(d_nm)):
        return None

    x_arr = np.asarray(x_vals, dtype=np.float64).ravel()
    y_arr = np.asarray(y_vals, dtype=np.float64).ravel()
    m = np.isfinite(x_arr) & np.isfinite(y_arr)
    if not np.any(m):
        return None

    x_arr = x_arr[m]
    y_arr = y_arr[m]
    x_lo = float(np.min(x_arr))
    x_hi = float(np.max(x_arr))
    y_lo = float(np.min(y_arr))
    y_hi = float(np.max(y_arr))
    dx = float(max(x_hi - x_lo, 1e-9))
    dy = float(max(y_hi - y_lo, 1e-9))

    badge = pg.TextItem(
        html=(
            '<div style="background-color: rgba(15, 23, 42, 180); '
            'padding: 4px 8px; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px;">'
            f'<span style="color: {CertusTheme.PRIMARY}; font-size: {Typography.H3}pt;"><b>d = {float(d_nm):.2f} nm</b></span>'
            "</div>"
        ),
        anchor=(0.0, 1.0),
    )
    try:
        badge.setZValue(1000)
    except (AttributeError, RuntimeError):
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
    badge.setPos(x_lo + 0.03 * dx, y_hi - 0.04 * dy)
    try:
        plot_w.addItem(badge, ignoreBounds=True)
    except TypeError:
        plot_w.addItem(badge)
    return badge



def _smart_init_pw_nk_clipboard_df(curve_n: Any, curve_pk: Any) -> pd.DataFrame | None:
    """Build a DataFrame for Excel export from n(lambda) and ln k(lambda) plot items (k = exp(ln k), capped)."""

    xn, yn = curve_n.getData()

    xk, yk_ln = curve_pk.getData()

    xn = np.asarray(xn if xn is not None else [], dtype=float).ravel()

    yn = np.asarray(yn if yn is not None else [], dtype=float).ravel()

    xk = np.asarray(xk if xk is not None else [], dtype=float).ravel()

    yk_ln = np.asarray(yk_ln if yk_ln is not None else [], dtype=float).ravel()

    yk_k = np.full(yk_ln.shape, np.nan, dtype=float)

    m_ln = np.isfinite(yk_ln)

    yk_k[m_ln] = np.exp(np.minimum(yk_ln[m_ln], 700.0))

    n = int(max(xn.size, yn.size, xk.size, yk_k.size))

    if n == 0:
        return None

    def _pad(a: np.ndarray) -> np.ndarray:

        a = np.asarray(a, dtype=float).ravel()

        if a.size >= n:
            return a[:n].copy()

        return np.pad(a, (0, n - a.size), constant_values=np.nan)

    if xn.size == xk.size and xn.size > 0 and np.allclose(xn, xk, equal_nan=True):
        return pd.DataFrame({"lambda_nm": _pad(xn), "n": _pad(yn), "k": _pad(yk_k)})

    return pd.DataFrame(
        {
            "lambda_nm_n": _pad(xn),
            "n": _pad(yn),
            "lambda_nm_k": _pad(xk),
            "k": _pad(yk_k),
        }
    )

# --- GUI --------------------------------------------------------------------------


# LiveIndexMonitor is defined locally in this module


_D_SLIDER_STEPS_DEFAULT = 5000

class _LazyCertusIndexSplineApp:
    def __getattr__(self, name):
        from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
        return getattr(CertusIndexSplineApp, name)

CertusIndexSplineApp = _LazyCertusIndexSplineApp()

__all__ = [name for name in dir() if not name.startswith('__')] + [
    '_QS_SPLINE_ORG',
    '_QS_SPLINE_APP',
    '_QS_LAST_SPECTRUM',
    '_QS_SPECTRUM_FIT_T',
    '_QS_SPECTRUM_FIT_TREL',
    '_QS_SPECTRUM_FIT_R',
    '_QS_SPECTRUM_WT',
    '_QS_SPECTRUM_WR',
    '_QS_NK_PROFILE_INTERP',
    '_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY',
    '_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV',
    '_UNCERTAINTY_DEFAULTS_REV',
    '_apply_fixed_log_k_axis',
    '_DEFAULT_CORRIDOR_RMSE_DELTA',
    '_get_substrate_n_array_spline',
]

from certus.ui.certus_index_spline_mixins_ui import (
    _ConfigBuilderMixin,
    _MeshOptimizationMixin,
    _SmartInitDialogMixin,
    _UIMixin,
)
