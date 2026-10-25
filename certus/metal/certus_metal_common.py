"""

CERTUS METAL COMMON

===================

Shared base classes and utilities for CERTUS-METAL and CERTUS-METAL SINGLE.

"""

import functools
import logging
import os
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import QEvent, QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    get_resource_path,
)
from certus.core.certus_metrology import ValidationStatus
from certus.core.certus_text_format import format_count_kmg

# The shared defaults live in certus_metal_defaults, a module without Qt that the
# METAL computation modules can import; they are re-exported here unchanged.
from certus.metal.certus_metal_defaults import (
    DEFAULT_EM_MAX,
    DEFAULT_EM_MIN,
    DEFAULT_EXCEL_FILENAME,
    DEFAULT_MAXITER,
    DEFAULT_MIN_KNOT_DISTANCE,
    DEFAULT_MUTATION_MAX,
    DEFAULT_MUTATION_MIN,
    DEFAULT_NK_MAX,
    DEFAULT_NK_MIN,
    DEFAULT_NUM_KNOTS,
    DEFAULT_POPSIZE,
    DEFAULT_RECOMBINATION,
    DEFAULT_TOL,
    DEFAULT_UPDATING,
    DEFAULT_WORKERS,
)
from certus.utils.certus_data import (
    ReportSection,
    build_standard_report,
    read_data_file_robust,
)
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_ux import OBJ, build_premium_overrides

METAL_GLOBAL_STATUS = "global"
METAL_LOCAL_STATUS = "local"
METAL_PROGRESS_PHASE_GLOBAL = "global_opt"
METAL_PROGRESS_PHASE_LOCAL = "local_opt"
METAL_PROGRESS_PHASE_BEAM = "beam"
METAL_PROGRESS_ENHANCED_UI = os.environ.get("CERTUS_METAL_ENHANCED_PROGRESS", "1").strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class MetalProgressEvent:
    """Canonical progress payload shared by METAL UI and worker callbacks."""

    phase: str
    progress_pct: int
    message: str
    iteration: int = 0
    max_iteration: int = 0
    evaluation_count: int = 0
    best_cost: float = float("inf")
    elapsed_s: float = 0.0
    mode: str = METAL_GLOBAL_STATUS


def normalize_percent_column(values: np.ndarray) -> np.ndarray:
    """Normalize a reflectance/transmittance column to the [0, 1] range.

    Values > 1 are assumed to be percent (0-100) and divided by 100.
    Otherwise the input is returned unchanged. NaN-safe and all-NaN safe.

    Used by METAL apps' ``on_file_loaded`` to handle mixed-unit inputs.
    """

    arr = np.asarray(values)
    if arr.size == 0:
        return arr
    finite = np.isfinite(arr)
    if not np.any(finite):
        return arr
    try:
        vmax = float(np.max(arr[finite]))
    except (TypeError, ValueError):
        return arr
    return arr / 100.0 if vmax > 1.0 else arr


def build_metal_target_data(data: np.ndarray, *, include_t: bool = True, include_rback: bool = True) -> dict[str, np.ndarray]:
    """Convert a loaded METAL spectrum array to the canonical dict schema.

    The canonical schema is:
    ``{"lambda": ..., "R": ..., "T": ..., "Rback": ...}``

    Missing channels are filled with ``NaN`` arrays so downstream code can
    safely test availability with ``np.all(np.isnan(...))``.
    """

    arr = np.asarray(data)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("METAL target data requires at least two columns: lambda, R")

    wls = arr[:, 0]
    target = {
        "lambda": wls,
        "R": normalize_percent_column(arr[:, 1]),
        "T": np.full_like(wls, np.nan),
        "Rback": np.full_like(wls, np.nan),
    }

    if include_t and arr.shape[1] >= 3:
        target["T"] = normalize_percent_column(arr[:, 2])

    if include_rback and arr.shape[1] >= 4:
        target["Rback"] = normalize_percent_column(arr[:, 3])

    return target


def _format_beam_status(cur: int, tot: int, best: float) -> str:
    """Return the standard METAL beam-analysis status line."""

    rmse = float(np.sqrt(best)) if best >= 0 else 0.0
    return f"Thickness {cur}/{tot} | Best RMSE: {rmse:.2e}"


def elevate_spline_knots(
    x_old: np.ndarray,
    k_old: int,
    l_min: float,
    l_max: float,
    offset: int = 1
) -> np.ndarray:
    """
    Project an optimal solution from k_old knots to (k_old + 1) knots for a Metal layer.
    
    The vector `x_old` has `offset` base parameters at the beginning:
    - Single Metal: offset=1 (eM)
    - Bilayer Metal: offset=4 (eM, eL, n_infini, A)
    
    The remaining parameters are:
    - n_knots: k_old elements
    - k_knots: k_old elements
    - lambda_internes: max(0, k_old - 2) elements
    """
    from scipy.interpolate import CubicSpline
    
    base_params = x_old[:offset]
    n_old = x_old[offset : offset + k_old]
    k_old_vals = x_old[offset + k_old : offset + 2 * k_old]
    lambdas_old = x_old[offset + 2 * k_old :]
    
    # Reconstruct original knot lambdas
    if len(lambdas_old) > 0:
        l_old = np.concatenate(([l_min], np.sort(lambdas_old), [l_max]))
    else:
        l_old = np.array([l_min, l_max])
        
    # Inject exactly ONE new knot in the middle of the largest existing frequency gap (1/lambda)
    # This preserves all previously optimized knot positions and distributes knots more physically
    f_old = 1.0 / l_old
    f_diffs = np.abs(np.diff(f_old))
    max_gap_idx = np.argmax(f_diffs)
    
    new_f = (f_old[max_gap_idx] + f_old[max_gap_idx + 1]) / 2.0
    new_lambda = 1.0 / new_f
    
    l_new = np.insert(l_old, max_gap_idx + 1, new_lambda)
    
    # Interpolate n and k values at the new knot positions
    # Use natural boundary conditions just like the target objective
    n_new = CubicSpline(l_old, n_old, bc_type="natural")(l_new)
    k_new = CubicSpline(l_old, k_old_vals, bc_type="natural")(l_new)
    
    # Extract the internal lambdas
    lambdas_new = l_new[1:-1]
    
    return np.concatenate((base_params, n_new, k_new, lambdas_new))


def build_metal_progress_event(
    *,
    phase: str,
    progress_pct: int,
    message: str,
    iteration: int = 0,
    max_iteration: int = 0,
    evaluation_count: int = 0,
    best_cost: float = float("inf"),
    elapsed_s: float = 0.0,
    mode: str = METAL_GLOBAL_STATUS,
) -> MetalProgressEvent:
    return MetalProgressEvent(
        phase=phase,
        progress_pct=int(max(0, min(100, progress_pct))),
        message=str(message),
        iteration=int(max(0, iteration)),
        max_iteration=int(max(0, max_iteration)),
        evaluation_count=int(max(0, evaluation_count)),
        best_cost=float(best_cost),
        elapsed_s=float(max(0.0, elapsed_s)),
        mode=str(mode),
    )


def normalize_metal_progress_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = build_metal_progress_event(
        phase=str(payload.get("phase", payload.get("mode", METAL_GLOBAL_STATUS))),
        progress_pct=int(payload.get("progress_pct", 0) or 0),
        message=str(payload.get("message", "")),
        iteration=int(payload.get("iteration", 0) or 0),
        max_iteration=int(payload.get("max_iteration", 0) or 0),
        evaluation_count=int(payload.get("evaluation_count", 0) or 0),
        best_cost=float(payload.get("best_cost", payload.get("mse", float("inf")))),
        elapsed_s=float(payload.get("elapsed_s", 0.0) or 0.0),
        mode=str(payload.get("mode", METAL_GLOBAL_STATUS)),
    )
    out = dict(payload)
    out.update({
        "phase": event.phase,
        "progress_pct": event.progress_pct,
        "message": event.message,
        "iteration": event.iteration,
        "max_iteration": event.max_iteration,
        "evaluation_count": event.evaluation_count,
        "best_cost": event.best_cost,
        "elapsed_s": event.elapsed_s,
        "mode": event.mode,
    })
    return out


def build_metal_progress_status_text(payload: dict[str, Any]) -> str:
    """Return a stable human-readable progress line for METAL UI."""

    if not METAL_PROGRESS_ENHANCED_UI:
        return str(payload.get("message", "")) or f"{str(payload.get('mode', METAL_GLOBAL_STATUS)).upper()} running"

    p = normalize_metal_progress_payload(payload)
    mode = str(p.get("mode", METAL_GLOBAL_STATUS)).upper()
    iteration = int(p.get("iteration", 0) or 0)
    max_iteration = int(p.get("max_iteration", 0) or 0)
    progress_pct = int(p.get("progress_pct", 0) or 0)
    evaluation_count = int(p.get("evaluation_count", 0) or 0)
    best_cost = float(p.get("best_cost", float("inf")))
    elapsed_s = float(p.get("elapsed_s", 0.0) or 0.0)
    return (
        f"[{mode}] {progress_pct}% | Gen: {iteration}/{max_iteration} | Evals: {format_count_kmg(evaluation_count)} | "
        f"Best RMSE: {np.sqrt(max(best_cost, 0.0)):.4f} | Time: {int(elapsed_s)}s"
    )


def build_metal_startup_log_lines(app, *, variant_label: str, params: dict[str, Any]) -> list[str]:
    """Build a consistent startup log block for METAL apps."""

    target_file = Path(getattr(app, "_last_target_file", "") or "")
    target_name = target_file.name if target_file.name else "Unknown"
    lines = [
        "=" * 50,
        f"STARTING {variant_label} OPTIMIZATION",
        f"Target File: {target_name}",
        f"Wavelength Range: {params['lmin_filter']} - {params['lmax_filter']} nm",
        f"Metal Thickness Range: {params['eM_min']} - {params['eM_max']} nm",
    ]
    if "num_knots" in params:
        lines.append(f"Knots: {params['num_knots']} (min dist: {params.get('min_knot_dist', 'N/A')})")
    lines.append("=" * 50)
    return lines


def setup_beam_analysis_thread(app, worker) -> QThread:
    """Move a BeamAnalysisWorker onto a fresh QThread and wire standard signals.

    Factors the identical thread wiring used by both METAL apps
    (see ``run_beam_analysis`` in SINGLE/BILAYER). The worker is expected
    to expose ``run``, ``progress(cur, tot, best)``, ``finished(stats)``
    and ``error(str)`` signals, and the app is expected to provide
    ``status_label``, ``on_beam_finished`` and ``_on_beam_error``.

    Returns the created QThread (also stored on ``app.beam_thread``).
    Caller is responsible for ``thread.start()``.
    """

    thread = QThread()
    app.beam_thread = thread
    app.beam_worker = worker
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    worker.progress.connect(lambda cur, tot, best: getattr(app, "field_opt_status", app.status_label).setText(_format_beam_status(cur, tot, best)))
    worker.finished.connect(app.on_beam_finished)
    worker.error.connect(app._on_beam_error)
    # Proper cleanup to avoid memory leaks
    for signal in (worker.finished, worker.error):
        signal.connect(thread.quit)
        signal.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread


def teardown_beam_thread(app, stats) -> None:
    """Stop the beam-analysis worker thread and reset METAL buttons.

    Shared first block of ``CERTUS_METAL_SINGLE.on_beam_finished`` and
    ``CERTUS_METAL_BILAYER.on_beam_finished``. App-specific plot logic
    must be done separately by the caller.
    """

    thread = getattr(app, "beam_thread", None)
    if thread is not None:
        if thread.isRunning():
            thread.quit()
            if not thread.wait(3000):
                logging.critical(
                    "Beam thread did not stop within 3s in on_beam_finished - skipping terminate() to avoid unsafe thread kill."
                )
        app.beam_thread = None
    if hasattr(app, "btn_run"):
        app.btn_run.setEnabled(True)
    if hasattr(app, "btn_beam"):
        app.btn_beam.setEnabled(True)
    if hasattr(app, "btn_stop"):
        app.btn_stop.setEnabled(False)
    app.beam_stats = stats


class MetalOptimizationWorker(QObject):
    """Base Optimization Worker for METAL applications"""

    finished = pyqtSignal(dict)

    progress = pyqtSignal(dict)

    progress_snapshot = pyqtSignal(object)

    error = pyqtSignal(str)

    stats_update = pyqtSignal(str, int)

    def __init__(self, params) -> None:

        super().__init__()

        self.params = params

        self.is_running = True

        self.iteration_count = 0

        self.evaluation_count = 0

        self.best_candidate = {"x": None, "fun": float("inf")}

        self._last_progress_time = 0.0
        self._stop_event = None

    @pyqtSlot()
    def stop(self) -> None:
        """Request stop"""

        self.is_running = False

# BaseBeamAnalysisWorker removed (Dead Code)


@dataclass(frozen=True)
class MetalJobSpec:
    """Declarative description of a METAL job (SINGLE vs BILAYER).

    **P3 scaffold** — the ultimate goal is to fuse the 4 remaining duplicated
    hooks (``on_file_loaded``, ``on_optimization_finished``, ``on_beam_finished``,
    ``export_results``) between :class:`CertusMetalSingleApp` and
    :class:`CertusMetalBilayerApp` by parameterising ``MetalBaseApp`` with a
    :class:`MetalJobSpec` instance. See audit §A1 for the full plan.

    For now this dataclass documents the axis of variation; actual fusion is
    deferred until METAL GUI tests can validate behaviour on real datasets
    (Gaussian bands SINGLE vs DBSCAN multi-valley BILAYER).

    Attributes
    ----------
    variant : str
        ``"single"`` or ``"bilayer"``.
    n_layers : int
        Number of metal layers handled by the worker (1 for SINGLE, 2 for
        BILAYER).
    report_sheets : tuple[str, ...]
        Ordered list of Excel sheet names produced by ``export_results``.
        Used by the future ``build_standard_report`` adoption path.
    beam_analysis_kind : str
        ``"gaussian_bands"`` (SINGLE) or ``"dbscan_multi_valleys"`` (BILAYER).
    extra : dict[str, Any]
        Free-form bag for per-variant extras (bound prep, fit labels, ...).
    """

    variant: str
    n_layers: int
    report_sheets: tuple[str, ...] = ()
    beam_analysis_kind: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

# Canonical specs used when P3 fusion lands. Kept here so the two METAL apps
# can import them directly:
#   ``from certus.metal.certus_metal_common import METAL_SINGLE_SPEC, METAL_BILAYER_SPEC``
METAL_SINGLE_SPEC = MetalJobSpec(
    variant="single",
    n_layers=1,
    report_sheets=("Summary", "Fit Parameters", "Reflectance"),
    beam_analysis_kind="gaussian_bands",
)

METAL_BILAYER_SPEC = MetalJobSpec(
    variant="bilayer",
    n_layers=2,
    report_sheets=("Summary", "Fit Parameters", "Reflectance", "Layer Interactions"),
    beam_analysis_kind="dbscan_multi_valleys",
)


