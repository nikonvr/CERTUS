# =============================================================================

# CERTUS REVERSE ENGINEERING MODULE

# Functional area: Post-deposition Analysis & Drift Correction

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: only make small, reversible changes here until dedicated tests cover
# worker phases, result formatting, and critical reverse-engineering flows.
# Prefer extracting pure helpers before moving Qt classes or numerical kernels.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-RE.py - Reverse Engineering & Drift Correction

=========================================================

"""

from __future__ import annotations

# Numba configuration BEFORE any import pulling @njit (see CERTUS_HUB.py).
# Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next to it
# sources, in the cloud synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

# RE: +/-% thickness search radius for L-BFGS-B (no toolbar control; fixed default).
# Keeping this module tight: prefer helpers/tests over broad structural moves.
import sys
from typing import Any

import numpy as np

from certus.core.certus_core import (
    create_module_environment,
)
from certus.ui.certus_qt_widgets import (
    QApplication,
)
from certus.ui.certus_ui import (
    CertusBaseApp,
    CertusTheme,
    init_certus_app,
    open_command_line_file,
)
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS, RE_SUB_CAUCHY_TUBE_DELTA
from certus.utils.certus_re_math import re_substrate_cauchy_n_re_from_theta
from certus.workers.certus_re_workers import REWorker
from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker
from certus_physics import (  # TMM, targets, RMSE (same bundle as `certus_re_helpers`)
    Layer,
    ObliqueTarget,
    calc_spectrum_front_wrapper,
    calc_spectrum_full_exact_wrapper,
    init_thickness,
)

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_RE")

script_dir = env["script_dir"]

# =============================================================================

# FURTHER IMPORTS

# =============================================================================


# RE helpers: explicit re-exports (ARCH-1; replaced the legacy for-loop that copied certus_re_helpers into globals()).

from certus.utils.certus_re_helpers import (
    RE_SPLINE_NODE2_DEFAULT_NM,
    TabularMaterial,
    _parse_re_rmse_combined_from_progress_message,
    _re_calc_spectrum_for_config,
    _re_find_measurement_wavelength_column,
    _re_header_is_wavelength_label,
    _re_p4_ap_staircase_polyline,
    _re_p4_kwargs_from_opt_result,
    _re_p4_sort_knot_pairs,
    _re_parse_design_qwot_rows,
    _re_resolve_re_workbook_sheets,
    _re_rmse_oblique_weighted,
    parse_re_column_header,
    re_knots_wavelengths,
)

# Configure GUI

# Conditional Excel Import (OPENPYXL_AVAILABLE used elsewhere in module)

# =============================================================================

# LOGGING CONFIGURATION

# =============================================================================

# Logger initialized in CertusREApp

# This ensures consistency with other CERTUS modules

# script_dir already set by bootstrap_app()

# =============================================================================

# AUTOMATIC PRECISION ADAPTATION

# =============================================================================

# Use wrappers if single precision enabled

# Wrappers enforce (d,n) consistency with CFG single-precision when enabled.

calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# =============================================================================

# WORKERS (REWorker below; warmup + spectral eval in certus_spectral_workers)

# =============================================================================




from certus.ui.certus_re_excel_mixin import CertusREExcelMixin
from certus.ui.certus_re_layout_mixin import CertusRELayoutMixin
from certus.ui.certus_re_plot_mixin import CertusREPlotMixin
from certus.ui.certus_re_state_mixin import CertusREStateMixin
from certus.ui.certus_re_table_mixin import CertusRETableMixin
from certus.ui.certus_re_workers_mixin import CertusREWorkersMixin


class CertusREApp(
    CertusRELayoutMixin,
    CertusREStateMixin,
    CertusRETableMixin,
    CertusREPlotMixin,
    CertusREExcelMixin,
    CertusREWorkersMixin,
    CertusBaseApp,
):
    """CERTUS application  reverse engineering (Excel measurements)."""

    APP_NAME = "CERTUS_RE"
    APP_TITLE = "CERTUS  Reverse Engineering"
    DEFAULT_WIDTH = 1440
    DEFAULT_HEIGHT = 640
    MIN_WIDTH = 1020
    MIN_HEIGHT = 520

    def __init__(self):
        """Initialize CERTUS_RE (reverse engineering, Excel input, evaluation + REWorker)."""

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Shared state with base (tables, spectrum)

        self.target_widgets: list = []

        self.ep_current: np.ndarray | None = None

        self.last_result: dict = {}

        self._best_eval_result: dict | None = None

        self._best_eval_rmse: float = float("inf")

        self.target_scatter = None

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        self.detached_window = None

        self.eval_timer = None

        self._current_eval_generation = 0

        # Oblique mode

        self.oblique_mode = False

        # Workers (RE: spectral evaluation + REWorker only)

        self.eval_worker: EvalWorker | None = None

        self._re_worker: REWorker | None = None

        self.warmup_worker: WarmupWorker | None = None

        self.accumulated_evals = 0

        self._re_nfev_cumulative = 0  # cumulative RE nfev for the Evals bar

        self._warmup_done = False

        self._re_loaded = False  # True after a successful load_reverse_engineering()

        self._re_workbook_path: str | None = None  # last loaded RE .xlsx (logs / worker cfg)

        self._re_mode_active = False  # True while a RE optimization is running

        self._re_tabular_H: TabularMaterial | None = None

        self._re_tabular_L: TabularMaterial | None = None

        self._re_tabular_Sub: TabularMaterial | None = None

        self._re_targets: list = []  # full ObliqueTarget list (not in widget) for RE

        self._re_meas_lambda_min_nm: float | None = None

        self._re_meas_lambda_max_nm: float | None = None

        self._re_opt_a_pct = 0.0

        self._re_opt_b_pct = 0.0

        self._re_opt_f_pct = 0.0

        self._re_spline_dH: np.ndarray | None = None

        self._re_spline_dL: np.ndarray | None = None

        self._re_spline_lam2_nm: float | None = None

        self._re_sub_cauchy_a0: float | None = None

        self._re_sub_cauchy_a1: float | None = None

        self._re_sub_cauchy_a2: float | None = None

        # n(lambda) preview during REWorker (corrected indices = same *correc* as live spectrum)

        self._re_nk_preview_dH: list[float] | None = None

        self._re_nk_preview_dL: list[float] | None = None

        self._re_nk_preview_lam2: float | None = None

        self._re_nk_preview_sub012: list[float] | None = None

        self._re_backside_summary_html: str = ""

        # Phase 4 (beam): last best result applied aligns RMSE / UI evaluation on the P4 fit.

        self._re_p4_display_beam_active: bool = False

        self._re_p4_display_ap_knots_deg: np.ndarray | None = None

        self._re_p4_display_ap_knots_nm: np.ndarray | None = None

        # Last RE results table snapshot (Run RE)  reopened via "Display results".

        self._re_last_results_snapshot: dict[str, Any] | None = None

        # After an RE Run: alpha QWOT phase 2b (aligns _compute_re_rmse with the worker).

        self._re_rmse_qwot_alpha_ref: float | None = None

        # Last alpha emitted live: change -> reset of the status bar best RMSE (comparable metric).

        self._re_last_live_alpha_qwot: float | None = None

        # RE Options (initialised before UI)

        self.cfg: dict[str, Any] = {}

        # Theme Application

        CertusTheme.apply_to_app(QApplication.instance())

        # UI Construction

        self._build_ui()

        self._setup_shortcuts()

        self._load_defaults()

        # RE does not call _finalize_init, so restore the persisted geometry /
        # splitters explicitly. closeEvent already calls _qs_save: without this
        # the preferences were written at every exit and never read back.
        self._qs_restore()

        # This module skips _finalize_init, so the cross-cutting affordances it
        # installs have to be requested explicitly: command palette, shortcuts
        # overlay, Help menu, empty states and accessible names. Measured
        # 2026-09-04: without this call the window had no Ctrl+K, no Help menu
        # and not one input field with an accessible name.
        self.install_common_affordances()

        # Warmup JIT.
        # These five lines used to sit AFTER the `return` of _get_optim_wls,
        # i.e. they were unreachable: RE performed no JIT warmup at all and the
        # status bar never showed the compiling message. The first evaluation
        # paid the full Numba compilation instead.
        self.status_label.setText("Compiling JIT kernels...")

        self.warmup_worker = WarmupWorker()

        self.warmup_worker.finished.connect(self._on_warmup_done)

        self.warmup_worker.start()
        self.mark_config_saved()

    def _get_optim_wls(self) -> np.ndarray:
        if self._re_targets and len(self._re_targets) > 0:
            return self._re_targets[0].wls
        return np.array([])


def main():

    # RE starts WarmupWorker itself; the global JIT warmup thread would compile the same kernels a second time.
    app = init_certus_app(jit_warmup=False)
    certus_app = CertusREApp()
    certus_app.show()
    open_command_line_file(certus_app)

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback

        print(f"Exception during execution: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
