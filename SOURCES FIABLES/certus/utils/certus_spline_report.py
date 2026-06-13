#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spline report builder: Excel export for INDEX_SPLINE results.

Extracted from CERTUS_INDEX_SPLINE.py for maintainability.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, K_MAX_LIMIT
from certus.utils.certus_index_utils import _lam_uniform_grid
from certus_physics import calculate_bare_substrate_RT
from certus.spline.certus_index_spline_core import (
    _to_fraction_T,
    ensure_lam_nm_array,
    substrate_id_from_name,
)
from certus.spline.spline_objective import (
    build_spline_objective_masked_grid,
    spline_objective_mse_on_masked_grid,
)
from certus.spline.spline_profile_corridors import enforce_min_k_corridor_half_width

logger = logging.getLogger("CERTUS")


def _log10_k_safe(k: np.ndarray) -> np.ndarray:
    """Compute log10(k) safely, returning NaN for k <= 0 or non-finite values."""
    k = np.asarray(k, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(np.isfinite(k) & (k > 0.0), np.log10(k), np.nan)
    return result


def _mergesort_order_lambda(lam_nm: np.ndarray) -> np.ndarray:
    """Indices to permute spectral columns by increasing lambda (stable sort)."""
    lam = np.asarray(lam_nm, dtype=np.float64).ravel()
    return np.argsort(lam, kind="mergesort") if lam.size else np.arange(0, dtype=np.intp)


def _get_script_dir() -> Path:
    """Lazy resolve to avoid circular imports."""
    try:
        from CERTUS_INDEX_SPLINE import _SCRIPT_DIR
        return Path(_SCRIPT_DIR)
    except ImportError:
        return Path(".")


def _get_substrate_n_array_spline(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Delegate to the main module function."""
    from CERTUS_INDEX_SPLINE import _get_substrate_n_array_spline as _impl
    return _impl(substrate_id, wavelengths_nm)


@dataclass
class SplineReportContext:
    result: dict[str, Any]
    df: pd.DataFrame | None
    spectrum_path: str
    t_is_ratio: bool
    sub_name: str
    rmse_fit_lambda_tuple: tuple[float, float, float]
    lam_mask_callable: Callable[[np.ndarray], np.ndarray]
    opt_config: Any

class SplineReportBuilder:
    """UX-4 / P2: Standalone builder for Spline reports to decouple data preparation from GUI."""

    def __init__(self, ctx: SplineReportContext, logger=None) -> None:
        self.ctx = ctx
        self.logger = logger

    def _write_summary_sheets(
        self,
        writer: Any,
        *,
        result: dict,
        rmse_solver_txt: str,
        rmse_spl_txt: str,
        best_line: str,
        rw_rep: tuple[float, float, float] | None,
        export_fallback_lam: bool,
        spectre_filtre: bool,
    ) -> None:
        """Write Summary, RMSE_Index_Comparison, and Substrate_Indices sheets."""

        sig_knots = result.get("sigma_knots", np.array([0, 1]))
        smin, smax = float(sig_knots[0]), float(sig_knots[-1])

        if rw_rep is not None:
            lo_r, hi_r = float(rw_rep[0]), float(rw_rep[1])
            fen_txt = f"[{lo_r:.2f}, {hi_r:.2f}]"
            if export_fallback_lam:
                spec_txt = "Fallback: all finite lambda (empty objective mask)"
            elif spectre_filtre:
                spec_txt = "Only lambda in objective mask (RMSE window + valid data)"
            else:
                spec_txt = "All lambda from result (window covers grid or no excluded points)"
        else:
            fen_txt = "- (full objective spectrum)"
            spec_txt = (
                "Fallback: all finite lambda (mask error)"
                if export_fallback_lam
                else "All lambda points from result"
            )

        gui_live = bool(result.get("gui_display_from_best_live"))
        rmse_w_fin = result.get("gui_worker_raw_rmse")
        rmse_live_gui = result.get("gui_best_live_rmse")
        live_note = (
            f"Yes - displayed RMSE={float(rmse_live_gui):.6f}, final worker dict RMSE={float(rmse_w_fin):.6f}"
            if gui_live
            and rmse_w_fin is not None
            and rmse_live_gui is not None
            and np.isfinite(float(rmse_w_fin))
            and np.isfinite(float(rmse_live_gui))
            else ("Yes (details: gui_best_live_rmse / gui_worker_raw_rmse)" if gui_live else "No")
        )
        spectre_ordre = "increasing lambda (mergesort, aligned with Data table / Spectrum tab)"

        delta_ns_val = float(result.get("substrate_n_offset", 0.0))
        n_sub_base_arr = np.asarray(result.get("n_sub_base", []), dtype=np.float64).ravel()
        n_sub_eff_arr = np.asarray(result.get("n_sub_effective", []), dtype=np.float64).ravel()
        n_sub_base_str = f"{np.mean(n_sub_base_arr):.6f}" if n_sub_base_arr.size > 0 else "N/A"
        n_sub_eff_str = f"{np.mean(n_sub_eff_arr):.6f}" if n_sub_eff_arr.size > 0 else "N/A"

        pd.DataFrame(
            {
                "Indicator": [
                    "Final RMSE (result dict)",
                    "Spectral RMSE - solver ref (mesh, before mesh polish)",
                    "Spectral RMSE - cubic spline sigma mesh (spectral polish)",
                    "Best model (mesh polish spline sigma)",
                    "Thickness (nm) final model",
                    "Substrate offset delta_ns",
                    "Substrate n_base (mean)",
                    "Substrate n_effective (mean)",
                    "Display = best live snapshot (GUI)",
                    "Spectrum sheet - Wavelength order",
                    "RMSE lambda window (nm)",
                    "Spectrum sheet (lambda lines)",
                    "Variable u",
                    "Model Type",
                    "sigma_min (1/nm)",
                    "sigma_max (1/nm)",
                    "Export Date",
                ],
                "Value": [
                    f"{result.get('rmse', 'N/A'):.6f}"
                    if isinstance(result.get("rmse"), (int, float))
                    else "N/A",
                    rmse_solver_txt,
                    rmse_spl_txt,
                    best_line,
                    f"{result.get('d_nm', 'N/A'):.2f}"
                    if isinstance(result.get("d_nm"), (int, float))
                    else "N/A",
                    f"{delta_ns_val:+.6f}",
                    n_sub_base_str,
                    n_sub_eff_str,
                    live_note,
                    spectre_ordre,
                    fen_txt,
                    spec_txt,
                    f"u = (sigma - {smin:.6e}) / ({smax:.6e} - {smin:.6e}), sigma = 1/lambda",
                    "Spline in sigma (1/lambda): sigma nodes + ln(k) + cubic interpolation",
                    f"{smin:.6e}",
                    f"{smax:.6e}",
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ],
            }
        ).to_excel(writer, sheet_name="Summary", index=False)

        compare_note = (
            "L-BFGS-B spectral polish on sigma mesh (cubic spline between nodes, same objective mask). "
            f"Solver reference (before mesh polish): RMSE={rmse_solver_txt}. "
            f"Polished model: {best_line}."
        )
        pd.DataFrame(
            {
                "Metric": [
                    "Spectral RMSE - solver ref (before mesh polish)",
                    "Spectral RMSE - cubic spline sigma (polish)",
                    "Best (internal label)",
                    "Criteria",
                    "Note",
                ],
                "Value": [
                    rmse_solver_txt,
                    rmse_spl_txt,
                    str(result.get("spectral_rmse_best_label", "")).strip() or "-",
                    "Same mask and weights as spline objective (build_spline_objective_masked_grid).",
                    compare_note,
                ],
            }
        ).to_excel(writer, sheet_name="RMSE_Index_Comparison", index=False)

        substrate_data = {
            "Parameter": [
                "Substrate n_base (mean)",
                "Substrate n_effective (mean)",
                "Substrate delta_ns (offset)",
                "Substrate offset applied",
                "Substrate data points (n_sub_base)",
                "Substrate data points (n_sub_effective)",
            ],
            "Value": [
                n_sub_base_str,
                n_sub_eff_str,
                f"{delta_ns_val:+.6f}",
                "Yes" if abs(delta_ns_val) > 1e-12 else "No",
                f"{len(n_sub_base_arr)} points" if n_sub_base_arr.size > 0 else "N/A",
                f"{len(n_sub_eff_arr)} points" if n_sub_eff_arr.size > 0 else "N/A",
            ],
            "Description": [
                "Base substrate refractive index (no offset)",
                "Effective substrate index (with delta_ns applied)",
                "Manual substrate offset parameter (delta_ns)",
                "Whether delta_ns offset was applied to this result",
                "Count of substrate n_base values in result",
                "Count of substrate n_effective values in result",
            ],
        }
        pd.DataFrame(substrate_data).to_excel(writer, sheet_name="Substrate_Indices", index=False)

    def _write_analysis_sheets(
        self,
        writer: Any,
        *,
        result: dict,
        _result_float,
    ) -> None:
        """Write Profile_d_RMSE, Profile_d_CHI2, Reg_Sensitivity, Bootstrap_* and Manifest sheets."""
        logger = self.logger

        # RMSE(d) profile
        d_prof = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_prof = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        if d_prof.size and r_prof.size == d_prof.size:
            od = np.argsort(d_prof, kind="mergesort")
            pd.DataFrame({"d_nm": d_prof[od], "rmse": r_prof[od]}).to_excel(
                writer, sheet_name="Profile_d_RMSE", index=False
            )
        c_prof = np.asarray(result.get("profile_d_chi2_values", []), dtype=np.float64).ravel()
        if d_prof.size and c_prof.size == d_prof.size:
            od = np.argsort(d_prof, kind="mergesort")
            pd.DataFrame({"d_nm": d_prof[od], "chi2": c_prof[od]}).to_excel(
                writer, sheet_name="Profile_d_CHI2", index=False
            )

        # Regularization sensitivity
        w_reg = np.asarray(result.get("reg_sens_weights", []), dtype=np.float64).ravel()
        d_lo = np.asarray(result.get("reg_sens_d_lo_nm", []), dtype=np.float64).ravel()
        d_hi = np.asarray(result.get("reg_sens_d_hi_nm", []), dtype=np.float64).ravel()
        w_n = np.asarray(result.get("reg_sens_mean_width_n", []), dtype=np.float64).ravel()
        w_k = np.asarray(result.get("reg_sens_mean_width_k", []), dtype=np.float64).ravel()
        n_v = np.asarray(result.get("reg_sens_n_valid", []), dtype=np.int64).ravel()
        if w_reg.size and d_lo.size == w_reg.size and d_hi.size == w_reg.size:
            pd.DataFrame(
                {
                    "reg_weight_lnk": w_reg,
                    "d_lo_nm": d_lo,
                    "d_hi_nm": d_hi,
                    "mean_width_n": w_n if w_n.size == w_reg.size else np.full_like(w_reg, np.nan),
                    "mean_width_k": w_k if w_k.size == w_reg.size else np.full_like(w_reg, np.nan),
                    "n_valid": n_v if n_v.size == w_reg.size else np.zeros_like(w_reg, dtype=np.int64),
                }
            ).to_excel(writer, sheet_name="Reg_Sensitivity", index=False)

        # Bootstrap
        _boot_meta_present = (
            result.get("boot_n") is not None
            or np.asarray(result.get("boot_d_lo_samples_nm", []), dtype=np.float64).size > 0
            or np.asarray(result.get("boot_runs_b", []), dtype=np.int64).size > 0
        )
        if _boot_meta_present:
            try:
                df_boot = pd.DataFrame(
                    {
                        "boot_n": [int(result.get("boot_n", 0))],
                        "boot_n_ok": [int(result.get("boot_n_ok", 0))],
                        "boot_seed": [int(result.get("boot_seed", 0))],
                        "boot_mode": [str(result.get("boot_mode", "-"))],
                        "boot_block_len": [int(result.get("boot_block_len", 1))],
                        "boot_percentile": [_result_float("boot_percentile")],
                        "boot_sigma_t": [_result_float("boot_sigma_t")],
                        "boot_sigma_r": [_result_float("boot_sigma_r")],
                        "boot_d_lo_q_nm": [_result_float("boot_d_lo_q_nm")],
                        "boot_d_hi_q_nm": [_result_float("boot_d_hi_q_nm")],
                    }
                )
                df_boot.to_excel(writer, sheet_name="Bootstrap_summary", index=False)

                dls = np.asarray(result.get("boot_d_lo_samples_nm", []), dtype=np.float64).ravel()
                dhs = np.asarray(result.get("boot_d_hi_samples_nm", []), dtype=np.float64).ravel()
                if dls.size and dhs.size == dls.size:
                    pd.DataFrame({"d_lo_nm": dls, "d_hi_nm": dhs}).to_excel(
                        writer, sheet_name="Bootstrap_d_samples", index=False
                    )

                rb = np.asarray(result.get("boot_runs_b", []), dtype=np.int64).ravel()
                rok = np.asarray(result.get("boot_runs_ok", []), dtype=np.int64).ravel()
                rd0 = np.asarray(result.get("boot_runs_d_lo_nm", []), dtype=np.float64).ravel()
                rd1 = np.asarray(result.get("boot_runs_d_hi_nm", []), dtype=np.float64).ravel()
                rnv = np.asarray(result.get("boot_runs_n_valid", []), dtype=np.int64).ravel()
                if rb.size and rok.size == rb.size and rd0.size == rb.size and rd1.size == rb.size:
                    pd.DataFrame(
                        {
                            "b": rb,
                            "ok": rok,
                            "d_lo_nm": rd0,
                            "d_hi_nm": rd1,
                            "n_valid": rnv if rnv.size == rb.size else np.zeros_like(rb),
                        }
                    ).to_excel(writer, sheet_name="Bootstrap_runs", index=False)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.exception("Export Excel: bootstrap")

        # Manifest
        run_manifest = result.get("run_manifest")
        if isinstance(run_manifest, dict) and run_manifest:
            manifest_rows = [{"Key": str(k), "Value": str(v)} for k, v in run_manifest.items()]
            pd.DataFrame(manifest_rows).to_excel(writer, sheet_name="Manifest", index=False)

    def _write_corridor_nk_sheets(
        self,
        writer: Any,
        *,
        result: dict,
        corr_grid_ok: bool,
        lam_src_full: np.ndarray,
        ord_lam_full: np.ndarray,
        cn_ref_f: np.ndarray,
        ck_ref_f: np.ndarray,
        cn_lo_f: np.ndarray,
        cn_hi_f: np.ndarray,
        ck_lo_f: np.ndarray,
        ck_hi_f: np.ndarray,
    ) -> None:
        """Write Corridors_nk or Corridors_bootstrap Excel sheets."""

        if corr_grid_ok:
            try:
                ord_cf = ord_lam_full
                lam_cf = np.asarray(lam_src_full, dtype=np.float64).ravel()[ord_cf]

                nref_c = (
                    cn_ref_f[ord_cf].copy()
                    if cn_ref_f.size == lam_src_full.size
                    else np.full(lam_cf.shape, np.nan, dtype=np.float64)
                )
                kref_c = (
                    ck_ref_f[ord_cf].copy()
                    if ck_ref_f.size == lam_src_full.size
                    else np.full(lam_cf.shape, np.nan, dtype=np.float64)
                )

                log10_k_ref_col = np.full(lam_cf.shape, np.nan, dtype=np.float64)
                if ck_ref_f.size == lam_src_full.size and np.any(np.isfinite(ck_ref_f)):
                    log10_k_ref_col = _log10_k_safe(ck_ref_f[ord_cf])

                corr_full: dict[str, Any] = {
                    "Wavelength (nm)": lam_cf,
                    "n_corridor_ref (d profiling)": nref_c,
                    "k_corridor_ref (d profiling)": kref_c,
                    "log10_k_corridor_ref": log10_k_ref_col,
                    "n_corridor_lo": cn_lo_f[ord_cf],
                    "n_corridor_hi": cn_hi_f[ord_cf],
                    "k_corridor_lo": ck_lo_f[ord_cf],
                    "k_corridor_hi": ck_hi_f[ord_cf],
                    "log10_k_corridor_lo": _log10_k_safe(ck_lo_f[ord_cf]),
                    "log10_k_corridor_hi": _log10_k_safe(ck_hi_f[ord_cf]),
                }

                bn_lo = np.asarray(result.get("boot_corridor_n_lo", []), dtype=np.float64).ravel()
                bn_hi = np.asarray(result.get("boot_corridor_n_hi", []), dtype=np.float64).ravel()
                bk_lo = np.asarray(result.get("boot_corridor_k_lo", []), dtype=np.float64).ravel()
                bk_hi = np.asarray(result.get("boot_corridor_k_hi", []), dtype=np.float64).ravel()

                if (
                    bn_lo.size == lam_src_full.size
                    and bn_hi.size == lam_src_full.size
                    and bk_lo.size == lam_src_full.size
                    and bk_hi.size == lam_src_full.size
                ):
                    corr_full["boot_n_lo"] = bn_lo[ord_cf]
                    corr_full["boot_n_hi"] = bn_hi[ord_cf]
                    corr_full["boot_k_lo"] = bk_lo[ord_cf]
                    corr_full["boot_k_hi"] = bk_hi[ord_cf]
                    corr_full["boot_log10_k_lo"] = _log10_k_safe(bk_lo[ord_cf])
                    corr_full["boot_log10_k_hi"] = _log10_k_safe(bk_hi[ord_cf])

                pd.DataFrame(corr_full).to_excel(writer, sheet_name="Corridors_nk", index=False)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.exception("Export Excel: feuille Corridors_nk")

        else:
            try:
                bn_lo2 = np.asarray(result.get("boot_corridor_n_lo", []), dtype=np.float64).ravel()
                bn_hi2 = np.asarray(result.get("boot_corridor_n_hi", []), dtype=np.float64).ravel()
                bk_lo2 = np.asarray(result.get("boot_corridor_k_lo", []), dtype=np.float64).ravel()
                bk_hi2 = np.asarray(result.get("boot_corridor_k_hi", []), dtype=np.float64).ravel()

                if (
                    bn_lo2.size == lam_src_full.size
                    and bn_hi2.size == lam_src_full.size
                    and bk_lo2.size == lam_src_full.size
                    and bk_hi2.size == lam_src_full.size
                    and bn_lo2.size > 0
                ):
                    ord_b = ord_lam_full
                    lam_b = np.asarray(lam_src_full, dtype=np.float64).ravel()[ord_b]
                    pd.DataFrame(
                        {
                            "Wavelength (nm)": lam_b,
                            "boot_n_lo": bn_lo2[ord_b],
                            "boot_n_hi": bn_hi2[ord_b],
                            "boot_k_lo": bk_lo2[ord_b],
                            "boot_k_hi": bk_hi2[ord_b],
                            "boot_log10_k_lo": _log10_k_safe(bk_lo2[ord_b]),
                            "boot_log10_k_hi": _log10_k_safe(bk_hi2[ord_b]),
                        }
                    ).to_excel(writer, sheet_name="Corridors_bootstrap", index=False)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.exception("Export Excel: Corridors_bootstrap sheet")

    def _write_best_indices_sheet(
        self,
        writer: Any,
        *,
        result: dict,
        lam_src_full: np.ndarray,
        n_best_src: np.ndarray,
        k_best_src: np.ndarray,
        d_best_export: float,
        best_pretty: str,
        best_lbl: str,
        best_v: Any,
        rmse_best_recalc_txt: str,
        rmse_solver_txt: str,
        rmse_spl_txt: str,
        corr_grid_ok: bool,
    ) -> None:
        """Write the 'Best indices' sheet: n/k on uniform 2/5/10 nm grids + corridor metadata."""

        lo = (
            float(np.nanmin(lam_src_full[np.isfinite(lam_src_full)]))
            if np.any(np.isfinite(lam_src_full))
            else float("nan")
        )

        hi = (
            float(np.nanmax(lam_src_full[np.isfinite(lam_src_full)]))
            if np.any(np.isfinite(lam_src_full))
            else float("nan")
        )

        ls_src = np.asarray(lam_src_full, dtype=np.float64).ravel()
        n_bs = np.asarray(n_best_src, dtype=np.float64).ravel()
        k_bs = np.asarray(k_best_src, dtype=np.float64).ravel()

        grid_parts: list[pd.DataFrame] = []

        if n_bs.size == ls_src.size and k_bs.size == ls_src.size and ls_src.size > 0:
            ord_i = np.argsort(ls_src, kind="mergesort")
            ls_s = ls_src[ord_i]
            n_s = n_bs[ord_i]
            k_s = k_bs[ord_i]

            for step in (2.0, 5.0, 10.0):
                lam_g = _lam_uniform_grid(lo, hi, step)
                if lam_g.size == 0:
                    continue
                n_g = np.interp(lam_g, ls_s, n_s, left=np.nan, right=np.nan)
                k_g = np.interp(lam_g, ls_s, k_s, left=np.nan, right=np.nan)
                grid_parts.append(
                    pd.DataFrame(
                        {
                            "Step (nm)": np.full(lam_g.size, step, dtype=np.float64),
                            "Wavelength (nm)": lam_g,
                            "n_best": n_g,
                            "k_best": k_g,
                        }
                    )
                )

        df_grids = (
            pd.concat(grid_parts, ignore_index=True)
            if grid_parts
            else pd.DataFrame(columns=["Step (nm)", "Wavelength (nm)", "n_best", "k_best"])
        )

        def _result_float(key: str) -> float:
            v = result.get(key)
            if v is None:
                return float("nan")
            try:
                return float(v)
            except (TypeError, ValueError):
                return float("nan")

        desc_rows = [
            "Source / method",
            "Chosen model (spectral RMSE mesh polish - spline cubique sigma)",
            "Internal label",
            "Spectral RMSE (chosen value)",
            "Spectral RMSE (control, result mesh + objective mask)",
            "Thickness d associated with chosen model (nm)",
            "n/k Corridors (d profiling): active",
            "Corridors: d interval (nm)",
            "Corridors: mode",
            "Corridors: conf (LR)",
            "Corridors: Deltachi2 (LR)",
            "Corridors: sigma_T (LR)",
            "Corridors: sigma_R (LR)",
            "Corridors: alpha (RMSE <= alpha * RMSE_opt)",
            "Corridors: RMSE_opt (threshold reference)",
            "Corridors: ref RMSE source (spectral_rmse_segments | dict_rmse | recalc_objective)",
            "Corridors: RMSE_threshold",
            "Table: 2 nm then 5 nm then 10 nm grids",
            "Spectral RMSE - solver ref (before mesh polish)",
            "Spectral RMSE - cubic spline sigma (polish)",
        ]

        val_rows = [
            "numpy.interp on lambda (sorted result mesh) from n(lambda), k(lambda) "
            "curves of the best polish; uniform sub-sampling steps 2, 5 and 10 nm on [lambda_min, lambda_max].",
            best_pretty,
            str(best_lbl) if best_lbl else "-",
            f"{float(best_v):.6f}" if best_v is not None and np.isfinite(float(best_v)) else "N/A",
            rmse_best_recalc_txt,
            f"{d_best_export:.4f}" if np.isfinite(d_best_export) else "N/A",
            "Yes (corridor_* vectors present, aligned with lam_nm)" if corr_grid_ok else "No",
            (
                f"[{float(result.get('profile_d_interval_nm')[0]):.3f}, {float(result.get('profile_d_interval_nm')[1]):.3f}]"
                if corr_grid_ok
                and isinstance(result.get("profile_d_interval_nm"), (tuple, list))
                and len(result.get("profile_d_interval_nm")) == 2
                else "-"
            ),
            str(result.get("profile_d_mode", "-")),
            f"{_result_float('profile_d_lr_conf'):.3f}"
            if np.isfinite(_result_float("profile_d_lr_conf"))
            else "-",
            f"{_result_float('profile_d_lr_delta_chi2'):.6f}"
            if np.isfinite(_result_float("profile_d_lr_delta_chi2"))
            else "-",
            f"{_result_float('profile_d_sigma_t'):.6g}"
            if np.isfinite(_result_float("profile_d_sigma_t"))
            else "-",
            f"{_result_float('profile_d_sigma_r'):.6g}"
            if np.isfinite(_result_float("profile_d_sigma_r"))
            else "-",
            f"{_result_float('profile_d_rmse_alpha'):.3f}"
            if np.isfinite(_result_float("profile_d_rmse_alpha"))
            else "-",
            f"{_result_float('profile_d_rmse_opt'):.6f}"
            if np.isfinite(_result_float("profile_d_rmse_opt"))
            else "-",
            str(result.get("profile_d_rmse_ref_source", "-")),
            f"{_result_float('profile_d_rmse_thresh'):.6f}"
            if np.isfinite(_result_float("profile_d_rmse_thresh"))
            else "-",
            "Column \u2018Step (nm)\u2019 separates the three blocks; same spectral interval.",
            rmse_solver_txt,
            rmse_spl_txt,
        ]

        df_head = pd.DataFrame({"Description": desc_rows, "Value": val_rows})
        sheet_best = "Best indices"
        df_head.to_excel(writer, sheet_name=sheet_best, index=False)

        if not df_grids.empty:
            df_grids.to_excel(
                writer,
                sheet_name=sheet_best,
                index=False,
                startrow=len(df_head) + 2,
            )


    def _align_to_lam(self, a: np.ndarray, name: str, lam_src_full: np.ndarray) -> np.ndarray:
    
        v = np.asarray(a, dtype=np.float64).ravel()
    
        if v.size == lam_src_full.size:
            return v
    
        out = np.full(lam_src_full.shape, np.nan, dtype=np.float64)
    
        n_m = int(min(v.size, lam_src_full.size))
    
        if n_m > 0:
            out[:n_m] = v[:n_m]
    
        if lam_src_full.size and v.size != lam_src_full.size:
            self.logger.warning(
                "Export Excel: len(%s)=%d ? len(lam_nm)=%d - padded with NaN.",
                name,
                int(v.size),
                int(lam_src_full.size),
            )
    
        return out

    def _spectral_rmse_export(
            self,
            n_arr: np.ndarray,
            k_arr: np.ndarray,
            d_nm_c: float,
            cfg_ex: Any,
            lam_src_full: np.ndarray,
            *,
            d_nm_use: float | None = None,
        ) -> tuple[str, float]:
    
        d_eff = float(d_nm_use) if d_nm_use is not None and np.isfinite(float(d_nm_use)) else float(d_nm_c)
    
        if cfg_ex is None or not np.isfinite(d_eff):
            return "N/A", float("nan")

        g = build_spline_objective_masked_grid(cfg_ex)
        if g is None:
            return "N/A", float("nan")

        lam_f, _, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = g
        n_sub_eff = np.asarray(n_sub_f, dtype=np.float64)
        ls = np.asarray(lam_src_full, dtype=np.float64).ravel()
        na = np.asarray(n_arr, dtype=np.float64).ravel()
        ka = np.asarray(k_arr, dtype=np.float64).ravel()

        if na.size != ls.size or ka.size != ls.size:
            return "N/A", float("nan")

        ord_i = np.argsort(ls, kind="mergesort")
        ls_s = ls[ord_i]
        n_f = np.interp(lam_f, ls_s, na[ord_i], left=np.nan, right=np.nan)
        k_f = np.interp(lam_f, ls_s, ka[ord_i], left=np.nan, right=np.nan)

        if not np.all(np.isfinite(n_f) & np.isfinite(k_f)):
            return "N/A", float("nan")

        try:
            mse_v = spline_objective_mse_on_masked_grid(
                cfg_ex,
                lam_f=lam_f,
                n_sub_f=n_sub_eff,
                w=w,
                inv_npix=inv_npix,
                t_exp_f=t_exp_f,
                r_exp_f=r_exp_f,
                n_l=n_f,
                k_l=k_f,
                d=float(d_eff),
            )
            if np.isfinite(mse_v) and mse_v < 1e29:
                r = float(np.sqrt(mse_v))
                return f"{r:.6f}", r
        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.exception("Spectral RMSE Excel export (model comparison)")

        return "N/A", float("nan")

    def _rmse_pref_result(self, key: str, n_a: np.ndarray, k_a: np.ndarray, d_alt: float, result: dict, d_nm_c: float, cfg_ex: Any, lam_src_full: np.ndarray) -> tuple[str, float]:
        v = result.get(key)
        if v is not None and np.isfinite(float(v)):
            fv = float(v)
            return f"{fv:.6f}", fv
        d_use = d_alt if np.isfinite(d_alt) else None
        return self._spectral_rmse_export(n_a, k_a, d_nm_c, cfg_ex, lam_src_full, d_nm_use=d_use)

    def _build_spec_rows(
        self,
        *,
        lam: np.ndarray,
        n_lam: np.ndarray,
        k_lam: np.ndarray,
        n_spl_spec: np.ndarray,
        k_spl_spec: np.ndarray,
        ratio_exp_pct: np.ndarray,
        ratio_theo_pct: np.ndarray,
        corr_grid_ok: bool,
        keep: np.ndarray,
        ord_ex: np.ndarray,
        cn_ref_f: np.ndarray,
        ck_ref_f: np.ndarray,
        cn_lo_f: np.ndarray,
        cn_hi_f: np.ndarray,
        ck_lo_f: np.ndarray,
        ck_hi_f: np.ndarray,
        boot_spec_ok: bool,
        bsn_lo: np.ndarray,
        bsn_hi: np.ndarray,
        bsk_lo: np.ndarray,
        bsk_hi: np.ndarray,
    ) -> dict[str, Any]:
        spec_rows: dict[str, Any] = {
            "Wavelength (nm)": lam,
            "n_film (final model)": n_lam,
            "k_film (final model)": k_lam,
            "n_cubic_spline_sigma_spectral_polish": n_spl_spec,
            "k_cubic_spline_sigma_spectral_polish": k_spl_spec,
            "Ratio_Exp (%)": ratio_exp_pct,
            "Ratio_Theo (%)": ratio_theo_pct,
        }
        if corr_grid_ok:
            spec_rows.update(self._build_corridor_spec_rows(lam, keep, ord_ex, cn_ref_f, ck_ref_f, cn_lo_f, cn_hi_f, ck_lo_f, ck_hi_f))
        if boot_spec_ok:
            spec_rows.update(self._build_boot_spec_rows(keep, ord_ex, bsn_lo, bsn_hi, bsk_lo, bsk_hi))
        return spec_rows

    def _build_corridor_spec_rows(
        self,
        lam: np.ndarray,
        keep: np.ndarray,
        ord_ex: np.ndarray,
        cn_ref_f: np.ndarray,
        ck_ref_f: np.ndarray,
        cn_lo_f: np.ndarray,
        cn_hi_f: np.ndarray,
        ck_lo_f: np.ndarray,
        ck_hi_f: np.ndarray,
    ) -> dict[str, Any]:
        cnk = cn_ref_f[keep][ord_ex] if cn_ref_f.size else np.full(lam.shape, np.nan)
        ckk = ck_ref_f[keep][ord_ex] if ck_ref_f.size else np.full(lam.shape, np.nan)
        return {
            "n_corridor_ref (d profiling)": cnk,
            "k_corridor_ref (d profiling)": ckk,
            "log10_k_corridor_ref": _log10_k_safe(ck_ref_f[keep][ord_ex]) if cn_ref_f.size and ck_ref_f.size else np.full(lam.shape, np.nan),
            "n_corridor_lo": cn_lo_f[keep][ord_ex],
            "n_corridor_hi": cn_hi_f[keep][ord_ex],
            "k_corridor_lo": ck_lo_f[keep][ord_ex],
            "k_corridor_hi": ck_hi_f[keep][ord_ex],
            "log10_k_corridor_lo": _log10_k_safe(ck_lo_f[keep][ord_ex]),
            "log10_k_corridor_hi": _log10_k_safe(ck_hi_f[keep][ord_ex]),
        }

    def _build_boot_spec_rows(
        self,
        keep: np.ndarray,
        ord_ex: np.ndarray,
        bsn_lo: np.ndarray,
        bsn_hi: np.ndarray,
        bsk_lo: np.ndarray,
        bsk_hi: np.ndarray,
    ) -> dict[str, Any]:
        return {
            "boot_n_lo": bsn_lo[keep][ord_ex],
            "boot_n_hi": bsn_hi[keep][ord_ex],
            "boot_k_lo": bsk_lo[keep][ord_ex],
            "boot_k_hi": bsk_hi[keep][ord_ex],
            "boot_log10_k_lo": _log10_k_safe(bsk_lo[keep][ord_ex]),
            "boot_log10_k_hi": _log10_k_safe(bsk_hi[keep][ord_ex]),
        }

    def _build_mesh_parameters_df(self, result: dict) -> pd.DataFrame:
        xb = np.asarray(result.get("x", np.zeros(1)), dtype=np.float64)
        labels = ["Thickness d (nm)"] + [f"Coeff_n_{i}" for i in range(1, 10)] + [f"Coeff_logk_{i}" for i in range(1, 10)]
        while len(labels) < len(xb):
            labels.append(f"Param_{len(labels)}")
        return pd.DataFrame({"Index": np.arange(len(xb)), "Meaning": labels[: len(xb)], "Value": xb})

    def _write_export_workbook(
        self,
        *,
        out_path: str,
        spec_rows: dict[str, Any],
        result: dict,
        corr_grid_ok: bool,
        lam_src_full: np.ndarray,
        cn_ref_f: np.ndarray,
        ck_ref_f: np.ndarray,
        cn_lo_f: np.ndarray,
        cn_hi_f: np.ndarray,
        ck_lo_f: np.ndarray,
        ck_hi_f: np.ndarray,
        best_params: tuple[np.ndarray, np.ndarray, float, str, str, Any, str, str],
        rmse_solver_txt: str,
        rmse_spl_txt: str,
        rw_rep: tuple[float, float, float] | None,
        export_fallback_lam: bool,
        spectre_filtre: bool,
    ) -> None:
        n_best_src, k_best_src, d_best_export, best_pretty, best_lbl, best_v, rmse_best_recalc_txt, best_line = best_params
        ord_lam_full = _mergesort_order_lambda(lam_src_full)

        def _result_float(key: str) -> float:
            v = result.get(key)
            if v is None:
                return float("nan")
            try:
                return float(v)
            except (TypeError, ValueError):
                return float("nan")

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            pd.DataFrame(spec_rows).to_excel(writer, sheet_name="Spectrum", index=False)
            self._build_mesh_parameters_df(result).to_excel(writer, sheet_name="Mesh_Parameters", index=False)
            self._write_summary_sheets(
                writer,
                result=result,
                rmse_solver_txt=rmse_solver_txt,
                rmse_spl_txt=rmse_spl_txt,
                best_line=best_line,
                rw_rep=rw_rep,
                export_fallback_lam=export_fallback_lam,
                spectre_filtre=spectre_filtre,
            )
            self._write_corridor_nk_sheets(
                writer,
                result=result,
                corr_grid_ok=corr_grid_ok,
                lam_src_full=lam_src_full,
                ord_lam_full=ord_lam_full,
                cn_ref_f=cn_ref_f,
                ck_ref_f=ck_ref_f,
                cn_lo_f=cn_lo_f,
                cn_hi_f=cn_hi_f,
                ck_lo_f=ck_lo_f,
                ck_hi_f=ck_hi_f,
            )
            self._write_best_indices_sheet(
                writer,
                result=result,
                lam_src_full=lam_src_full,
                n_best_src=n_best_src,
                k_best_src=k_best_src,
                d_best_export=d_best_export,
                best_pretty=best_pretty,
                best_lbl=best_lbl,
                best_v=best_v,
                rmse_best_recalc_txt=rmse_best_recalc_txt,
                rmse_solver_txt=rmse_solver_txt,
                rmse_spl_txt=rmse_spl_txt,
                corr_grid_ok=corr_grid_ok,
            )
            self._write_analysis_sheets(writer, result=result, _result_float=_result_float)

    def _select_best_export_model(
        self,
        *,
        result: dict,
        n_res_full: np.ndarray,
        k_res_full: np.ndarray,
        n_spl_full: np.ndarray,
        k_spl_full: np.ndarray,
        d_nm_c: float,
        d_spl_f: float,
        cfg_ex: Any,
        lam_src_full: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, float, str, str, Any, str]:
        best_lbl = str(result.get("spectral_rmse_best_label", "")).strip()
        best_v = result.get("spectral_rmse_best_value")
        best_pretty = {"Spline_cubique_sigma": "Polish on cubic sigma-spline mesh"}.get(best_lbl, best_lbl or "-")
        best_line = f"{best_pretty} - RMSE={float(best_v):.6f}" if best_v is not None and np.isfinite(float(best_v)) and best_lbl else "N/A (see RMSE columns)"
        has_spl_cols = bool(np.any(np.isfinite(n_spl_full)) and np.any(np.isfinite(k_spl_full)))
        if best_lbl == "Spline_cubique_sigma" and not has_spl_cols:
            best_line = "N/A ('sigma spline' label without n_lam_seg_spline_sigma in dict)"
        if best_lbl == "Spline_cubique_sigma" and has_spl_cols:
            n_best_src = np.asarray(n_spl_full, dtype=np.float64).ravel().copy()
            k_best_src = np.asarray(k_spl_full, dtype=np.float64).ravel().copy()
            d_best_export = float(d_spl_f) if np.isfinite(d_spl_f) else float(d_nm_c)
        else:
            n_best_src = np.asarray(n_res_full, dtype=np.float64).ravel().copy()
            k_best_src = np.asarray(k_res_full, dtype=np.float64).ravel().copy()
            d_best_export = float(d_nm_c) if isinstance(d_nm_c, (int, float)) and np.isfinite(float(d_nm_c)) else float("nan")
        rmse_best_recalc_txt, _ = self._spectral_rmse_export(
            n_best_src, k_best_src, d_nm_c, cfg_ex, lam_src_full, d_nm_use=d_best_export if np.isfinite(d_best_export) else None
        )
        return n_best_src, k_best_src, d_best_export, best_pretty, best_lbl, best_v, rmse_best_recalc_txt, best_line

    def _prepare_export_arrays(self, result: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        lam_src_raw = result.get("lam_nm")
        if lam_src_raw is None and self.ctx.df is not None and "lambda" in self.ctx.df.columns:
            lam_src_raw = ensure_lam_nm_array(self.ctx.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("event=export_excel status=fallback reason=missing_lam_nm source=experimental_grid")
        lam_src_full = np.asarray(lam_src_raw if lam_src_raw is not None else [], dtype=np.float64).ravel()
        if lam_src_full.size == 0:
            raise ValueError("lam_nm indisponible pour export Excel.")

        n_res_full = self._align_to_lam(np.asarray(result.get("n_lam", []), dtype=np.float64).ravel(), "n_lam", lam_src_full)
        k_res_full = self._align_to_lam(np.asarray(result.get("k_lam", []), dtype=np.float64).ravel(), "k_lam", lam_src_full)
        t_theo_raw = np.asarray(result.get("t_theo", []), dtype=np.float64).ravel()
        if t_theo_raw.size == lam_src_full.size:
            t_theo_full = t_theo_raw
        else:
            t_theo_full = np.full(lam_src_full.shape, np.nan, dtype=np.float64)
            n_tt = int(min(t_theo_raw.size, lam_src_full.size))
            if n_tt > 0:
                t_theo_full[:n_tt] = t_theo_raw[:n_tt]

        ratio_exp_pct_full = np.full_like(lam_src_full, np.nan)
        if self.ctx.df is not None and "T" in self.ctx.df.columns:
            lam_raw = ensure_lam_nm_array(self.ctx.df["lambda"].to_numpy(dtype=np.float64))
            t_raw_all = _to_fraction_T(self.ctx.df["T"].to_numpy(dtype=np.float64))
            t_raw_interp = np.interp(lam_src_full, lam_raw, t_raw_all)
            ratio_exp_pct_full = t_raw_interp * 100.0 if result.get("t_is_ratio", self.ctx.t_is_ratio) else (t_raw_interp / np.maximum(calculate_bare_substrate_RT(lam_src_full, _get_substrate_n_array_spline(substrate_id_from_name(str(self.ctx.sub_name)), lam_src_full)), 1e-6)) * 100.0
        ratio_theo_pct_full = t_theo_full * 100.0
        rw_rep = self.ctx.rmse_fit_lambda_tuple
        m_obj = self.ctx.lam_mask_callable(lam_src_full)
        keep = m_obj > 0.5
        spectre_filtre = bool(rw_rep is not None and np.any(~keep) and np.count_nonzero(keep) > 0)
        export_fallback_lam = False
        if np.count_nonzero(keep) == 0:
            logger.warning("event=export_excel status=fallback reason=empty_objective_mask action=export_all_finite_lambda")
            keep = np.isfinite(lam_src_full)
            spectre_filtre = False
            export_fallback_lam = True
        cfg_ex = self.ctx.opt_config
        x_res = np.asarray(result.get("x", np.zeros(19)), dtype=np.float64)
        d_nm_val = result.get("d_nm")
        d_nm_c = float(d_nm_val) if isinstance(d_nm_val, (int, float)) and np.isfinite(float(d_nm_val)) else (float(x_res[0]) if x_res.size >= 1 and np.isfinite(float(x_res[0])) else float("nan"))
        n_spl_full = np.full(lam_src_full.shape, np.nan, dtype=np.float64)
        k_spl_full = np.full(lam_src_full.shape, np.nan, dtype=np.float64)
        n_sp = result.get("n_lam_seg_spline_sigma")
        k_sp = result.get("k_lam_seg_spline_sigma")
        if n_sp is not None and k_sp is not None and np.asarray(n_sp).size == lam_src_full.size and np.asarray(k_sp).size == lam_src_full.size:
            n_spl_full = np.asarray(n_sp, dtype=np.float64).ravel(); k_spl_full = np.asarray(k_sp, dtype=np.float64).ravel()
        d_spl_x = result.get("d_nm_seg_spline_sigma")
        d_spl_f = float(d_spl_x) if isinstance(d_spl_x, (int, float)) and np.isfinite(float(d_spl_x)) else float("nan")
        cn_lo_f = np.asarray(result.get("corridor_n_lo", []), dtype=np.float64).ravel(); cn_hi_f = np.asarray(result.get("corridor_n_hi", []), dtype=np.float64).ravel(); ck_lo_f = np.asarray(result.get("corridor_k_lo", []), dtype=np.float64).ravel(); ck_hi_f = np.asarray(result.get("corridor_k_hi", []), dtype=np.float64).ravel(); cn_ref_f = np.asarray(result.get("corridor_reference_n_lam", []), dtype=np.float64).ravel(); ck_ref_f = np.asarray(result.get("corridor_reference_k_lam", []), dtype=np.float64).ravel(); bsn_lo = np.asarray(result.get("boot_corridor_n_lo", []), dtype=np.float64).ravel(); bsn_hi = np.asarray(result.get("boot_corridor_n_hi", []), dtype=np.float64).ravel(); bsk_lo = np.asarray(result.get("boot_corridor_k_lo", []), dtype=np.float64).ravel(); bsk_hi = np.asarray(result.get("boot_corridor_k_hi", []), dtype=np.float64).ravel()
        corr_grid_ok = cn_lo_f.size == lam_src_full.size and cn_hi_f.size == lam_src_full.size and ck_lo_f.size == lam_src_full.size and ck_hi_f.size == lam_src_full.size and cn_lo_f.size > 0
        boot_spec_ok = bsn_lo.size == lam_src_full.size and bsn_hi.size == lam_src_full.size and bsk_lo.size == lam_src_full.size and bsk_hi.size == lam_src_full.size and bsn_lo.size > 0
        return (lam_src_full, n_res_full, k_res_full, t_theo_full, ratio_exp_pct_full, ratio_theo_pct_full, n_spl_full, k_spl_full, rw_rep, d_nm_c, keep, cn_lo_f, cn_hi_f, ck_lo_f, ck_hi_f, corr_grid_ok, spectre_filtre, cn_ref_f, ck_ref_f, bsn_lo, bsn_hi, bsk_lo, bsk_hi, boot_spec_ok, export_fallback_lam)

    def build_report(self, auto: bool = False, auto_export: bool | None = None) -> None:
        """Automatic saving of results to Excel (like CERTUS_DESIGN).

        Generates a timestamped file containing:

        - Spectrum: mod?le final n/k ; colonnes polish spectral spline cubique sigma si ``n_lam_seg_spline_sigma``.

          Lines sorted by increasing lambda. Corridors / boot in same order.

        - Corridors_nk: sorted lambda grid - profiling ref, corridor bounds, log10 k; bootstrap if aligned.

        - Comparaison_RMSE_indices: spectral RMSE (solver ref, sigma-spline polish) + best polished model.

        - Parameters: exported x vector.

        - Resume / Best indices: RMSE dict, sigma-spline polish, selected model.

        """
        if auto_export is not None:
            auto = auto_export

        result = self.ctx.result

        def _result_float(key: str) -> float:
            v = result.get(key)
            if v is None:
                return float("nan")
            try:
                return float(v)
            except (TypeError, ValueError):
                return float("nan")

        if result is None:
            if auto:
                return  # No result, nothing to export

            self.logger.warning("event=export_excel status=skipped reason=no_result")

            return

        # Determine the folder and filename (thickness in Angstrom in the name)

        last_spectrum_path = str(self.ctx.spectrum_path or "").strip()
        base_dir = Path(last_spectrum_path).parent if last_spectrum_path else _get_script_dir()

        ts = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")

        d_nm_fn = result.get("d_nm")

        if isinstance(d_nm_fn, (int, float)) and np.isfinite(float(d_nm_fn)):
            d_ang_int = int(round(float(d_nm_fn) * 10.0))

            fname = f"IndexSpline_Result_{ts}_d{d_ang_int}Ang.xlsx"

        else:
            fname = f"IndexSpline_Result_{ts}_dNA_Ang.xlsx"

        out_path = str(base_dir / fname)

        try:
            (
                lam_src_full,
                n_res_full,
                k_res_full,
                t_theo_full,
                ratio_exp_pct_full,
                ratio_theo_pct_full,
                n_spl_full,
                k_spl_full,
                rw_rep,
                d_nm_c,
                keep,
                cn_lo_f,
                cn_hi_f,
                ck_lo_f,
                ck_hi_f,
                corr_grid_ok,
                spectre_filtre,
                cn_ref_f,
                ck_ref_f,
                bsn_lo,
                bsn_hi,
                bsk_lo,
                bsk_hi,
                boot_spec_ok,
                export_fallback_lam,
            ) = self._prepare_export_arrays(result)
            cfg_ex = self.ctx.opt_config
            d_spl_x = result.get("d_nm_seg_spline_sigma")
            d_spl_f = float(d_spl_x) if isinstance(d_spl_x, (int, float)) and np.isfinite(float(d_spl_x)) else float("nan")
            rmse_spl_txt, _ = self._rmse_pref_result("spectral_rmse_seg_spline_sigma", n_spl_full, k_spl_full, d_spl_f, result, d_nm_c, cfg_ex, lam_src_full)
            rmse_solver_txt = "N/A"
            srv = result.get("spectral_rmse_segments")
            if srv is not None and np.isfinite(float(srv)):
                rmse_solver_txt = f"{float(srv):.6f}"
            has_spl_cols = bool(np.any(np.isfinite(n_spl_full)) and np.any(np.isfinite(k_spl_full)))
            best_lbl = str(result.get("spectral_rmse_best_label", "")).strip()
            best_v = result.get("spectral_rmse_best_value")

            n_best_src, k_best_src, d_best_export, best_pretty, best_lbl, best_v, rmse_best_recalc_txt, best_line = self._select_best_export_model(
                result=result,
                n_res_full=n_res_full,
                k_res_full=k_res_full,
                n_spl_full=n_spl_full,
                k_spl_full=k_spl_full,
                d_nm_c=d_nm_c,
                d_spl_f=d_spl_f,
                cfg_ex=cfg_ex,
                lam_src_full=lam_src_full,
            )

            lam = lam_src_full[keep]

            n_lam = n_res_full[keep]

            k_lam = k_res_full[keep]

            ratio_exp_pct = ratio_exp_pct_full[keep]

            ratio_theo_pct = ratio_theo_pct_full[keep]

            n_spl_spec = n_spl_full[keep]

            k_spl_spec = k_spl_full[keep]

            ord_ex = np.argsort(lam, kind="mergesort") if lam.size else np.arange(0, dtype=np.intp)

            if lam.size:
                lam = lam[ord_ex]

                n_lam = n_lam[ord_ex]

                k_lam = k_lam[ord_ex]

                ratio_exp_pct = ratio_exp_pct[ord_ex]

                ratio_theo_pct = ratio_theo_pct[ord_ex]

                n_spl_spec = n_spl_spec[ord_ex]

                k_spl_spec = k_spl_spec[ord_ex]

            cn_lo_f = np.asarray(result.get("corridor_n_lo", []), dtype=np.float64).ravel()

            cn_hi_f = np.asarray(result.get("corridor_n_hi", []), dtype=np.float64).ravel()

            ck_lo_f = np.asarray(result.get("corridor_k_lo", []), dtype=np.float64).ravel()

            ck_hi_f = np.asarray(result.get("corridor_k_hi", []), dtype=np.float64).ravel()

            cn_ref_f = np.asarray(result.get("corridor_reference_n_lam", []), dtype=np.float64).ravel()

            ck_ref_f = np.asarray(result.get("corridor_reference_k_lam", []), dtype=np.float64).ravel()

            # Corridor sheets: tables aligned on lam_nm (not only profile_d_enabled bool).

            corr_grid_ok = (
                cn_lo_f.size == lam_src_full.size
                and cn_hi_f.size == lam_src_full.size
                and ck_lo_f.size == lam_src_full.size
                and ck_hi_f.size == lam_src_full.size
                and cn_lo_f.size > 0
            )

            if cn_ref_f.size != lam_src_full.size:
                cn_ref_f = np.array([], dtype=np.float64)

            if ck_ref_f.size != lam_src_full.size:
                ck_ref_f = np.array([], dtype=np.float64)

            if ck_lo_f.size == lam_src_full.size and ck_hi_f.size == lam_src_full.size and ck_lo_f.size > 0:
                ck_ref_for_min = (
                    np.asarray(ck_ref_f, dtype=np.float64)
                    if ck_ref_f.size == ck_lo_f.size
                    else np.asarray(result.get("k_lam", []), dtype=np.float64).ravel()
                )
                ck_lo_f, ck_hi_f, k_min_changed_export = enforce_min_k_corridor_half_width(
                    np.asarray(ck_lo_f, dtype=np.float64),
                    np.asarray(ck_hi_f, dtype=np.float64),
                    np.asarray(ck_ref_for_min, dtype=np.float64),
                    min_half_width=1e-4,
                )
                if int(k_min_changed_export) > 0:
                    logger.info(
                        "Export Excel corridor k-min-width enforced | half_width=1.0e-4 | adjusted_points=%d",
                        int(k_min_changed_export),
                    )

            bsn_lo = np.asarray(result.get("boot_corridor_n_lo", []), dtype=np.float64).ravel()
            bsn_hi = np.asarray(result.get("boot_corridor_n_hi", []), dtype=np.float64).ravel()
            bsk_lo = np.asarray(result.get("boot_corridor_k_lo", []), dtype=np.float64).ravel()
            bsk_hi = np.asarray(result.get("boot_corridor_k_hi", []), dtype=np.float64).ravel()
            boot_spec_ok = (
                bsn_lo.size == lam_src_full.size
                and bsn_hi.size == lam_src_full.size
                and bsk_lo.size == lam_src_full.size
                and bsk_hi.size == lam_src_full.size
                and bsn_lo.size > 0
            )

            spec_rows = self._build_spec_rows(
                lam=lam,
                n_lam=n_lam,
                k_lam=k_lam,
                n_spl_spec=n_spl_spec,
                k_spl_spec=k_spl_spec,
                ratio_exp_pct=ratio_exp_pct,
                ratio_theo_pct=ratio_theo_pct,
                corr_grid_ok=corr_grid_ok,
                keep=keep,
                ord_ex=ord_ex,
                cn_ref_f=cn_ref_f,
                ck_ref_f=ck_ref_f,
                cn_lo_f=cn_lo_f,
                cn_hi_f=cn_hi_f,
                ck_lo_f=ck_lo_f,
                ck_hi_f=ck_hi_f,
                boot_spec_ok=boot_spec_ok,
                bsn_lo=bsn_lo,
                bsn_hi=bsn_hi,
                bsk_lo=bsk_lo,
                bsk_hi=bsk_hi,
            )

            self._write_export_workbook(
                out_path=out_path,
                spec_rows=spec_rows,
                result=result,
                corr_grid_ok=corr_grid_ok,
                lam_src_full=lam_src_full,
                cn_ref_f=cn_ref_f,
                ck_ref_f=ck_ref_f,
                cn_lo_f=cn_lo_f,
                cn_hi_f=cn_hi_f,
                ck_lo_f=ck_lo_f,
                ck_hi_f=ck_hi_f,
                best_params=(n_best_src, k_best_src, d_best_export, best_pretty, best_lbl, best_v, rmse_best_recalc_txt, best_line),
                rmse_solver_txt=rmse_solver_txt,
                rmse_spl_txt=rmse_spl_txt,
                rw_rep=rw_rep,
                export_fallback_lam=export_fallback_lam,
                spectre_filtre=spectre_filtre,
            )
            self.logger.info("event=export_excel status=success output=%s", fname)
            logger.info("event=export_excel status=success path=%s", out_path)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("Error export Excel: %s", e)

            logger.exception("Export Excel failed")

