"""CERTUS-INDEX-SPLINE - the static helpers of the window, as plain functions: what a result dictionary says of the fit, how a mesh of knots and its changes are written in the log, the grids. The mixins of the window call them here; the window keeps each one as a static method of the same name, the very function (moved out of certus_index_spline_eventsextras_mixin.py and certus_index_spline_manualmesh_mixin.py). A leaf of the group: it imports no module of the window."""

from __future__ import annotations

from typing import Any

import numpy as np

from certus.utils.certus_index_utils import _lam_uniform_grid


def _rmse_from_result_dict(d: dict) -> float:
    """RMSE displayable for comparison (priority to  rmse  key, else ?MSE)."""

    r = d.get("rmse")

    if r is not None and np.isfinite(float(r)):
        return float(r)

    m = float(d.get("mse", float("nan")))

    if np.isfinite(m):
        return float(np.sqrt(max(m, 0.0)))

    return float("inf")


def _runtime_metrics_from_result_dict(d: dict | None) -> tuple[float, float]:

    if not isinstance(d, dict):
        return float("nan"), float("nan")

    try:
        d_nm = float(d.get("d_nm", float("nan")))

    except (TypeError, ValueError):
        d_nm = float("nan")

    rmse = _rmse_from_result_dict(d)

    if not np.isfinite(rmse):
        rmse = float("nan")

    return d_nm, rmse


def _format_lambda_knots_for_log(lambda_knots_nm: Any, *, precision: int = 1, max_items: int = 200) -> str:
    from certus.spline.spline_pipeline_utils import _format_lambda_knots_nm_for_log
    return _format_lambda_knots_nm_for_log(lambda_knots_nm, precision=precision, max_items=max_items)


def _manual_mesh_change_log_line(label: str, summary: dict[str, Any]) -> str:

    k_before = int(summary.get("k_before", 0))

    k_after = int(summary.get("k_after", 0))

    delta_k = int(summary.get("delta_k", 0))

    before_txt = _format_lambda_knots_for_log(summary.get("before_lambda_knots_nm"))

    after_txt = _format_lambda_knots_for_log(summary.get("after_lambda_knots_nm"))

    removed_txt = _format_lambda_knots_for_log(summary.get("removed_lambda_knots_nm"))

    added_txt = _format_lambda_knots_for_log(summary.get("added_lambda_knots_nm"))

    removed_count = int(np.asarray(summary.get("removed_lambda_knots_nm", []), dtype=np.float64).size)

    added_count = int(np.asarray(summary.get("added_lambda_knots_nm", []), dtype=np.float64).size)

    return (
        f"{str(label).strip()} | K {k_before}->{k_after} (Delta {delta_k:+d}) | "
        f"before={before_txt} | after={after_txt} | removed={removed_count} {removed_txt} | "
        f"added={added_count} {added_txt}"
    )


def _summarize_manual_mesh_change(before_sigma_knots: Any, after_sigma_knots: Any) -> dict[str, Any]:
    from certus.spline.spline_pipeline_utils import _sigma_mesh_change_summary_for_log
    return _sigma_mesh_change_summary_for_log(before_sigma_knots, after_sigma_knots)


def _lam_uniform_grid_nm(lo_h: float, hi_h: float, step: float) -> np.ndarray:
    return _lam_uniform_grid(lo_h, hi_h, step)


def _status_iteration_metric(
    display_dict: dict,
    fallback_dict: dict,
) -> tuple[str, int]:

    for key, label in (
        ("nit_total", "evals [global optimizer]"),
        ("nit_combined", "evals [global optimizer]"),
        ("nfev_lbfgsb", "evals [L-BFGS-B local-polish]"),
        ("nit_polish", "iters [cubic-spline-sigma-polish]"),
    ):
        raw = display_dict.get(key, fallback_dict.get(key, None))
        if raw is None:
            continue
        try:
            return label, max(0, int(raw))
        except (TypeError, ValueError):
            continue
    return "iters [cubic-spline-sigma-polish]", 0
