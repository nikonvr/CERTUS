"""Schema documentation for the SplineResult dict used throughout the CERTUS pipeline.

This module defines ``TypedDict`` classes that document the implicit schema of the
``result`` dictionary flowing between workers, GUI, pipeline, and export layers.

**Usage** — annotate function signatures for IDE autocompletion and linter checks::

    from certus_result_schema import SplineResultDict

    def _plot_result(self, r: SplineResultDict, *, plot_source: str = "maj") -> None:
        ...

No runtime behaviour is changed.  All fields are optional (``total=False``).
"""

from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Core solver result — always present after a successful optimisation
# ---------------------------------------------------------------------------
class SplineCoreResult(TypedDict, total=False):
    """Minimal fields produced by every solver run (L-BFGS-B, PGlobal, etc.)."""

    # --- Spectral grid & optical constants ---
    lam_nm: NDArray[np.float64]
    """Wavelength grid (nm), shape (N,)."""

    n_lam: NDArray[np.float64]
    """Refractive index n(λ), shape (N,)."""

    k_lam: NDArray[np.float64]
    """Extinction coefficient k(λ), shape (N,)."""

    ln_k_lam: NDArray[np.float64]
    """ln(k(λ)), shape (N,). Removed by best-live strip."""

    # --- Thickness ---
    d_nm: float
    """Film thickness (nm)."""

    # --- Fit quality ---
    rmse: float
    """Root-mean-square error of the fit."""

    mse: float
    """Mean-square error of the fit (rmse² fallback)."""

    # --- Spline mesh ---
    sigma_knots: NDArray[np.float64]
    """σ-space knot positions, shape (K,)."""

    sigma_knots_L: NDArray[np.float64]
    """λ-space knot positions (nm), shape (K,)."""

    sigma_knots_n: NDArray[np.float64]
    """n values at knot positions, shape (K,)."""

    x: NDArray[np.float64]
    """Packed optimisation vector (n + ln_k + d), shape (2K+1,)."""

    x_encoding: str
    """Encoding label for x (e.g. 'n_lnk_d')."""

    # --- Solver metadata ---
    op_id: str
    """Unique operation identifier."""

    nfev_pglobal: int
    """Number of function evaluations (PGlobal)."""

    nit_polish: int
    """Number of iterations (L-BFGS-B polish)."""

    nvalid: int
    """Number of valid spectral points used."""

    ok: bool
    """True if optimisation converged."""

    status: str
    """Solver termination status string."""

    run_manifest: dict[str, Any]
    """Full run configuration snapshot."""


# ---------------------------------------------------------------------------
# Substrate
# ---------------------------------------------------------------------------
class SubstrateFields(TypedDict, total=False):
    substrate_name: str
    """Substrate material name."""

    substrate_n_offset: float
    """Applied Δn_sub shift."""

    n_sub_base: float
    """Base substrate index (before shift)."""

    n_sub_effective: float
    """Effective substrate index (after shift)."""


# ---------------------------------------------------------------------------
# Theoretical spectra
# ---------------------------------------------------------------------------
class TheoreticalSpectraFields(TypedDict, total=False):
    t_theo: NDArray[np.float64]
    """Theoretical transmittance, shape (N,)."""

    r_theo: NDArray[np.float64]
    """Theoretical reflectance, shape (N,)."""

    t_is_ratio: bool
    """True if t_theo is T/T_sub ratio."""


# ---------------------------------------------------------------------------
# Adaptive mesh & auto-knot
# ---------------------------------------------------------------------------
class AdaptiveMeshFields(TypedDict, total=False):
    adaptive_mesh: bool
    """True if adaptive mesh was used."""

    smart_mesh: bool
    """True if smart mesh initialisation was used."""

    auto_knot_stages: list[dict[str, Any]]
    """List of auto-knot stage snapshots."""

    auto_knots_K_best: int
    """K value of the best auto-knot stage."""

    auto_knot_best_stage_index: int
    """Index of the best stage in auto_knot_stages."""

    split_knots_refine: bool
    """True if split-knot refinement was applied."""


# ---------------------------------------------------------------------------
# Non-linear k profile
# ---------------------------------------------------------------------------
class NonLinearKFields(TypedDict, total=False):
    n_lam_nl: NDArray[np.float64]
    """n(λ) after non-linear k profile, shape (N,)."""

    k_lam_nl: NDArray[np.float64]
    """k(λ) after non-linear k profile, shape (N,)."""

    d_nm_nl: float
    """Thickness after NL profile refit."""

    nl_optim_ok: bool
    nl_profile_mode: str
    nl_alpha_budget_mode: str
    nl_alpha_grid_n: int
    nl_alpha_grid_step: float
    nl_second_pass_applied: bool
    nl_second_pass_maxfun: int
    nl_lam_nm: NDArray[np.float64]
    nk_profile_interp: Any


# ---------------------------------------------------------------------------
# Seg-spline-sigma variant (polish with different sigma basis)
# ---------------------------------------------------------------------------
class SegSplineSigmaFields(TypedDict, total=False):
    x_seg_spline_sigma: NDArray[np.float64]
    """x vector from seg-spline-sigma polish."""

    n_lam_seg_spline_sigma: NDArray[np.float64]
    """n(λ) from seg-spline-sigma polish."""

    k_lam_seg_spline_sigma: NDArray[np.float64]
    """k(λ) from seg-spline-sigma polish."""

    d_nm_seg_spline_sigma: float
    """Thickness from seg-spline-sigma polish."""


# ---------------------------------------------------------------------------
# Corridor profiling (envelope uncertainty)
# ---------------------------------------------------------------------------
class CorridorFields(TypedDict, total=False):
    """Keys produced by the corridor profiling worker.

    These keys are volatile: they are stripped by
    ``_strip_worker_final_fields_inconsistent_with_live_merge`` when the
    displayed curves (n/k) are replaced by a best-live snapshot, because
    the corridor data would no longer be physically consistent.

    They are restored in ``_finish_curve_minimum_deep_worker_done`` from
    ``_last_result`` when the deep polish does not invalidate them.
    """

    profile_d_enabled: bool
    """Gate flag: True if corridor profiling was executed.
    Controls whether ``_refresh_corridor_table`` populates the Data Corridor tab."""

    corridor_n_lo: NDArray[np.float64]
    """Lower envelope of n(λ), shape (N,)."""

    corridor_n_hi: NDArray[np.float64]
    """Upper envelope of n(λ), shape (N,)."""

    corridor_k_lo: NDArray[np.float64]
    """Lower envelope of k(λ), shape (N,)."""

    corridor_k_hi: NDArray[np.float64]
    """Upper envelope of k(λ), shape (N,)."""

    manual_corridor_active: bool
    """True if corridor was triggered manually (not via pipeline)."""


# ---------------------------------------------------------------------------
# Corridor profiling — RMSE(d) grid scan metadata
# ---------------------------------------------------------------------------
class CorridorGridFields(TypedDict, total=False):
    profile_d_status: str
    """Grid status: 'ok', 'degenerate', 'manual_grid', 'manual_grid_empty'."""

    profile_d_values_nm: NDArray[np.float64]
    """d values scanned (nm), shape (M,)."""

    profile_d_rmse_values: NDArray[np.float64]
    """RMSE at each d value, shape (M,)."""

    profile_d_rmse_thresh: float
    """RMSE threshold for corridor inclusion."""

    profile_d_full_results: list[dict[str, Any]]
    """Full solver snapshots for each grid point."""

    profile_d_n_curves: list[NDArray[np.float64]]
    """n(λ) curves at each d value."""

    profile_d_k_curves: list[NDArray[np.float64]]
    """k(λ) curves at each d value."""

    profile_d_seed_gate_eval_count: int
    profile_d_seed_gate_kept_rate: float

    # --- Manual grid metadata ---
    profile_d_manual_grid_d0_seed_nm: float
    profile_d_manual_grid_nominal_pack_d_nm: float
    profile_d_manual_grid_total_points: int
    profile_d_manual_grid_base_done_points: int
    profile_d_manual_grid_extra_done_points: int
    profile_d_manual_grid_extra_points: int
    profile_d_manual_grid_done_points: int
    profile_d_manual_grid_coverage_complete: bool
    profile_d_manual_grid_elapsed_ms: float
    profile_d_manual_grid_progress: float
    profile_d_manual_grid_point_kind: str
    profile_d_manual_grid_point_status_code: int
    profile_d_manual_grid_breakpoint_count: int
    profile_d_manual_grid_breakpoint_events: list[dict[str, Any]]
    profile_d_manual_grid_global_opt_runs: int
    profile_d_manual_grid_global_opt_improved: int
    profile_d_manual_grid_best_global_rmse: float
    profile_d_manual_grid_best_global_result: dict[str, Any]
    profile_d_manual_grid_curve_minimum_result: dict[str, Any]
    profile_d_manual_grid_curve_beats_nominal: bool
    profile_d_manual_grid_curve_vs_nominal_delta_rmse: float


# ---------------------------------------------------------------------------
# Bootstrap corridor
# ---------------------------------------------------------------------------
class BootstrapCorridorFields(TypedDict, total=False):
    boot_corridor_n_lo: NDArray[np.float64]
    boot_corridor_n_hi: NDArray[np.float64]
    boot_corridor_k_lo: NDArray[np.float64]
    boot_corridor_k_hi: NDArray[np.float64]


# ---------------------------------------------------------------------------
# Spectral RMSE diagnostics
# ---------------------------------------------------------------------------
class SpectralRmseFields(TypedDict, total=False):
    spectral_rmse: float
    spectral_rmse_segments: list[dict[str, Any]]
    spectral_rmse_best_value: float
    spectral_rmse_best_label: str
    spectral_rmse_seg_spline_sigma: float


# ---------------------------------------------------------------------------
# GUI display state (injected by _display_result_prefer_best_live)
# ---------------------------------------------------------------------------
class GuiDisplayFields(TypedDict, total=False):
    gui_display_from_best_live: bool
    """True when displayed curves come from a best-live snapshot, not the final worker result."""

    gui_worker_raw_rmse: float
    """RMSE of the actual final worker result (before best-live override)."""

    gui_best_live_rmse: float
    """RMSE of the best-live snapshot that replaced the final result."""

    gui_solver_snapshot_for_corridors: dict[str, Any]
    """Solver state snapshot used as seed for corridor profiling."""


# ---------------------------------------------------------------------------
# Pipeline watermarks
# ---------------------------------------------------------------------------
class PipelineFields(TypedDict, total=False):
    pipeline_best_rmse_watermark: float
    pipeline_best_rmse_stage: str


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------
class MiscFields(TypedDict, total=False):
    extra_sigma_knots: NDArray[np.float64]
    L_nodes: NDArray[np.float64]
    n_nodes_physical: NDArray[np.float64]
    n_seg: int
    continuous_model: Any
    coeffs: NDArray[np.float64]
    pwl_baseline_mse: float
    rmse_fit_lambda_nm: NDArray[np.float64]
    window_nm: tuple[float, float]
    n_mono_band_nm: tuple[float, float]
    n_lo: NDArray[np.float64]
    n_hi: NDArray[np.float64]
    k_lo: NDArray[np.float64]
    k_hi: NDArray[np.float64]
    dlo: float
    dhi: float
    pglobal_max_iter: int


# ---------------------------------------------------------------------------
# Composite : the full result dict
# ---------------------------------------------------------------------------
class SplineResultDict(
    SplineCoreResult,
    SubstrateFields,
    TheoreticalSpectraFields,
    AdaptiveMeshFields,
    NonLinearKFields,
    SegSplineSigmaFields,
    CorridorFields,
    CorridorGridFields,
    BootstrapCorridorFields,
    SpectralRmseFields,
    GuiDisplayFields,
    PipelineFields,
    MiscFields,
    total=False,
):
    """Full result dictionary flowing through the CERTUS INDEX_SPLINE pipeline.

    This TypedDict is **documentation-only** — it does not enforce anything at
    runtime.  Use it as a type annotation to get IDE autocompletion and linter
    checks on key names::

        def process(result: SplineResultDict) -> None:
            d = result["d_nm"]        # IDE knows this is float
            n = result["corridor_n_lo"]  # IDE knows this is NDArray | None
            typo = result["corridr_n_lo"]  # linter/IDE warns: key not in TypedDict

    See the ``CorridorFields`` docstring for the lifecycle rules of corridor keys.
    """

    pass


def _validate_project_numeric_array(data: dict[str, Any], array_key: str) -> None:
    """Validate a numeric list/array field used by project configs."""

    from certus_errors import CorruptedProjectError

    val = data[array_key]
    if not isinstance(val, (list, np.ndarray)):
        raise CorruptedProjectError(
            "Invalid data structure",
            f"Expected list/array for '{array_key}', got {type(val).__name__}",
            "Verify the file has not been manually edited or corrupted.",
        )

    for idx, item in enumerate(val):
        try:
            f_val = float(item)
            if not np.isfinite(f_val):
                raise ValueError(f"Value at index {idx} of '{array_key}' is not finite")
        except (TypeError, ValueError) as e:
            raise CorruptedProjectError(
                "Invalid value in array",
                f"Expected finite number at index {idx} of '{array_key}', got {item}",
                "Ensure the array only contains finite numerical values.",
            ) from e


def validate_project_dict(data: Any) -> None:
    """Validate a loaded Smart Init Index Config dictionary structure."""
    from certus_errors import CorruptedProjectError

    if not isinstance(data, dict):
        raise CorruptedProjectError(
            "Invalid file format",
            "Project config must be a JSON object/dictionary.",
            "Ensure the file is not empty and is a valid JSON.",
        )

    required_keys = ["sigma_knots", "n_nodes_physical", "L_nodes", "d_nm"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise CorruptedProjectError(
            "Missing required parameter",
            f"The parameter '{missing[0]}' is missing from the project config.",
            "Ensure the file was saved correctly by the CERTUS application.",
        )

    try:
        loaded_d = float(data["d_nm"])
        if not np.isfinite(loaded_d):
            raise ValueError("Thickness is not finite")
    except (TypeError, ValueError) as e:
        raise CorruptedProjectError(
            "Invalid thickness value",
            f"Expected numeric finite 'd_nm', got {data.get('d_nm')}",
            "Verify that thickness is a valid finite float value.",
        ) from e

    for array_key in ("sigma_knots", "n_nodes_physical", "L_nodes"):
        _validate_project_numeric_array(data, array_key)

    sk_size = len(data["sigma_knots"])
    if sk_size < 2:
        raise CorruptedProjectError(
            "Insufficient knots",
            f"Found {sk_size} knots; at least 2 are required.",
            "Choose a configuration with 2 or more knots.",
        )

    if len(data["n_nodes_physical"]) != sk_size or len(data["L_nodes"]) != sk_size:
        raise CorruptedProjectError(
            "Inconsistent parameters size",
            f"Knot count ({sk_size}) does not match 'n_nodes_physical' ({len(data['n_nodes_physical'])}) or 'L_nodes' ({len(data['L_nodes'])}).",
            "Make sure the array lengths are identical.",
        )

