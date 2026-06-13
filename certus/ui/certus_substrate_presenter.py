"""
CERTUS Substrate Presenter - MVC Architecture for Substrate Index
"""

import logging
from typing import Protocol, Any
import numpy as np
import pandas as pd

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_metrology import ValidationStatus
from certus.core.certus_substrate_index import (
    SUBSTRATE_INDEX_MODELS,
    _prepare_substrate_index_input,
    _resolve_sellmeier_settings,
    _synthesize_validation_status,
    _finalize_substrate_run,
    _compute_sellmeier_index,
    _compute_analytical_index,
    _auto_fit_sellmeier,
    _safe_sellmeier_residual,
    IndexCore,
)

logger = logging.getLogger("CERTUS")

class SubstrateIndexView(Protocol):
    def is_cancel_requested(self) -> bool: ...
    def set_busy(self, busy: bool) -> None: ...
    def show_warning(self, title: str, message: str) -> None: ...
    def show_error(self, title: str, message: str) -> None: ...
    def log_message(self, message: str, level: str = "INFO") -> None: ...
    def update_progress(self, current: int, total: int, phase: str, extra_info: str = "") -> None: ...
    def stop_progress(self, message: str) -> None: ...
    def display_results(self, x: np.ndarray, n_results_raw: dict[str, np.ndarray], n_results_by_model: dict[str, dict[str, np.ndarray]], rmse_row: dict[str, dict[str, float]], n_fit_meta: dict[str, dict[str, dict]], wl_min_fit: float, wl_max_fit: float, quality_summary: str) -> None: ...

class CertusSubstratePresenter:
    def __init__(self, view: SubstrateIndexView):
        self.view = view
        self.df: pd.DataFrame | None = None
        self.last_run_manifest = None
        self.validation_status = "OK"
        self.validation_warnings = []
        self.last_loaded_measurement_path = ""

    def calculate_index(self, df: pd.DataFrame, fit_range: tuple[float, float], sellmeier_settings: dict[str, Any]) -> None:
        if df is None:
            return

        self.view.set_busy(True)
        self.view.log_message("Substrate index calculation started.", "INFO")

        try:
            prepared_df, x, groups, wl_min_fit, wl_max_fit, prep_warnings = _prepare_substrate_index_input(df)
            if prepared_df is None or x is None or groups is None or wl_min_fit is None or wl_max_fit is None:
                msg = "; ".join(prep_warnings) if prep_warnings else "invalid input"
                self.view.show_warning("Substrate Index", f"Cannot start calculation: {msg}.")
                self.view.stop_progress("Invalid input")
                return

            self.df = prepared_df

            ui_lo, ui_hi = fit_range
            wl_min_fit = float(max(ui_lo, float(np.nanmin(x))))
            wl_max_fit = float(min(ui_hi, float(np.nanmax(x))))

            if wl_min_fit >= wl_max_fit:
                self.view.show_warning("Fit range", "\u03bb min fit must be strictly less than \u03bb max fit.")
                self.view.stop_progress("Invalid fit range")
                return

            sell_timeout_cfg, sell_de_maxiter, sell_ls_max_nfev, sell_log_l1l2 = _resolve_sellmeier_settings(
                auto_enabled=sellmeier_settings.get("auto", False),
                timeout_spin_value=sellmeier_settings.get("timeout", 10.0),
                de_iter_value=sellmeier_settings.get("de_iter", 300),
                ls_nfev_value=sellmeier_settings.get("ls_nfev", 3000),
                log_l1l2_enabled=sellmeier_settings.get("log_l1l2", False),
            )

            logger.info("Sellmeier settings: auto=%s | timeout=%s | de_maxiter=%d | ls_nfev=%d | reparam=%s",
                sellmeier_settings.get("auto"), "unlimited" if sell_timeout_cfg is None else f"{float(sell_timeout_cfg):.1f}s",
                int(sell_de_maxiter), int(sell_ls_max_nfev), "ln(Li)" if sell_log_l1l2 else "linear(Li)"
            )

            self.view.update_progress(1, 1, phase="Fit 3 laws (toutes colonnes)")

            n_results_raw, n_results_by_model, rmse_row, n_fit_meta = self._compute_n_results(
                x, groups, wl_min_fit, wl_max_fit,
                sellmeier_timeout_s=sell_timeout_cfg,
                sellmeier_de_maxiter=sell_de_maxiter,
                sellmeier_ls_max_nfev=sell_ls_max_nfev,
                sellmeier_log_l1l2=sell_log_l1l2,
            )
            try:
                self.validation_status, self.validation_warnings = _synthesize_validation_status(n_fit_meta)
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                logger.warning("SUBSTRATE validation status synthesis failed: %s", exc)
                self.validation_status = "OK"
                self.validation_warnings = []
            
            try:
                status_val = ValidationStatus(str(self.validation_status))
            except ValueError:
                status_val = ValidationStatus.OK

            self.last_run_manifest = _finalize_substrate_run(
                wl_min_fit=float(wl_min_fit),
                wl_max_fit=float(wl_max_fit),
                rmse_row=rmse_row,
                source_path=str(self.last_loaded_measurement_path),
                status_val=status_val,
                warnings_list=list(self.validation_warnings),
                sellmeier_log_l1l2=bool(sell_log_l1l2),
            )

            quality_summary = "n/a"
            try:
                first_key = next(iter(n_fit_meta.keys()))
                first_model_key = next(iter(n_fit_meta.get(first_key, {}).keys()))
                qmeta = n_fit_meta.get(first_key, {}).get(first_model_key, {})
                quality_summary = f"{first_key} / {first_model_key}: {qmeta.get('source', 'n/a')}"
            except Exception:
                pass

            self.view.display_results(
                x, n_results_raw, n_results_by_model, rmse_row, n_fit_meta, wl_min_fit, wl_max_fit, quality_summary
            )

        except Exception as e:
            logger.error("Calculation error: %s", e)
            self.view.show_error("Calculation Error", str(e))
            self.view.stop_progress("Error")

    def _compute_n_results(
        self,
        x: np.ndarray,
        groups: dict[str, list],
        wl_min_fit: float,
        wl_max_fit: float,
        *,
        sellmeier_timeout_s: float | None = None,
        sellmeier_de_maxiter: int = 300,
        sellmeier_ls_max_nfev: int = 3000,
        sellmeier_log_l1l2: bool | None = None,
    ):
        n_results_raw: dict[str, np.ndarray] = {}
        n_results_by_model: dict[str, dict[str, np.ndarray]] = {}
        rmse_row: dict[str, dict[str, float]] = {}
        n_fit_meta: dict[str, dict[str, dict]] = {}
        total_cols = sum(len(v) for v in groups.values())
        total_steps = max(total_cols * len(SUBSTRATE_INDEX_MODELS), 1)
        done_steps = 0
        col_idx = 0
        xa = np.asarray(x, dtype=np.float64)
        m_rmse_geom = IndexCore._fit_mask(xa, wl_min_fit, wl_max_fit) & np.isfinite(xa)

        for bare_col_name, sub_cols in groups.items():
            for cn in sub_cols:
                col_idx += 1
                if self.view.is_cancel_requested():
                    raise RuntimeError("Calculation cancelled by user.")

                self.view.update_progress(done_steps, total_steps, phase=f"Columns {col_idx}/{max(total_cols, 1)}", extra_info=str(cn))

                try:
                    n_vals = self.df[cn].values
                except KeyError:
                    n_vals = np.full_like(xa, np.nan)
                n_raw_base = np.asarray(n_vals, dtype=np.float64)
                
                out_key = f"n ({cn})"
                n_results_raw[out_key] = n_raw_base
                by_model: dict[str, np.ndarray] = {}
                rms_m: dict[str, float] = {}
                meta_m: dict[str, dict] = {}
                m_rmse_mask = m_rmse_geom & np.isfinite(n_raw_base)

                for mk, mlabel in SUBSTRATE_INDEX_MODELS:
                    if self.view.is_cancel_requested():
                        raise RuntimeError("Calculation cancelled by user.")
                    done_steps += 1
                    
                    try:
                        if mk == "sellmeier":
                            meta_m[mk], by_model[mk] = _auto_fit_sellmeier(
                                xa, n_raw_base, wl_min_fit, wl_max_fit,
                                max_duration_s=sellmeier_timeout_s,
                                de_maxiter=sellmeier_de_maxiter,
                                ls_max_nfev=sellmeier_ls_max_nfev,
                                log_l1l2=sellmeier_log_l1l2
                            )
                            diff = _safe_sellmeier_residual(meta_m[mk].get("params", []), xa[m_rmse_mask], n_raw_base[m_rmse_mask], log_l1l2=sellmeier_log_l1l2)
                            rms_m[mk] = float(np.sqrt(np.mean(diff**2))) if diff.size else float("inf")
                        else:
                            meta_m[mk], by_model[mk] = _compute_analytical_index(mk, xa, n_raw_base, wl_min_fit, wl_max_fit)
                            diff = by_model[mk][m_rmse_mask] - n_raw_base[m_rmse_mask]
                            rms_m[mk] = float(np.sqrt(np.mean(diff**2))) if diff.size else float("inf")
                    except Exception as e:
                        logger.error("Failed to fit %s for %s: %s", mk, cn, e)
                        by_model[mk] = np.full_like(xa, np.nan)
                        rms_m[mk] = float("inf")
                        meta_m[mk] = {"error": str(e)}
                        
                    self.view.update_progress(done_steps, total_steps, phase=f"Columns {col_idx}/{max(total_cols, 1)}", extra_info=f"{cn} ({mk})")

                n_results_by_model[out_key] = by_model
                rmse_row[out_key] = rms_m
                n_fit_meta[out_key] = meta_m

        return n_results_raw, n_results_by_model, rmse_row, n_fit_meta
