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
    _N_SUBSTRATE_MODELS,
    _prepare_substrate_index_input,
    _resolve_sellmeier_settings,
    _synthesize_validation_status,
    _finalize_substrate_run,
    _model_selection_score, _rank_models_by_selection_score, _fit_summary_line,
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
                self.view.stop_progress("Error: Invalid input")
                return

            self.df = prepared_df

            ui_lo, ui_hi = fit_range
            wl_min_fit = float(max(ui_lo, float(np.nanmin(x))))
            wl_max_fit = float(min(ui_hi, float(np.nanmax(x))))

            if wl_min_fit >= wl_max_fit:
                self.view.show_warning("Fit range", "\u03bb min fit must be strictly less than \u03bb max fit.")
                self.view.stop_progress("Error: Invalid fit range")
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
            self.view.stop_progress("Done")

        except Exception as e:
            logger.error("Calculation error: %s", e)
            self.view.show_error("Calculation Error", str(e))
            self.view.stop_progress("Error")

    def _compute_n_results(self, x: np.ndarray, groups: dict[str, list], wl_min_fit: float, wl_max_fit: float, *, sellmeier_timeout_s: float | None=None, sellmeier_de_maxiter: int=300, sellmeier_ls_max_nfev: int=3000, sellmeier_log_l1l2: bool | None=None) -> tuple[dict[str, np.ndarray], dict[str, dict[str, np.ndarray]], dict[str, dict[str, float]], dict[str, dict[str, dict]]]:
        """Compute raw n(lambda) and all fitted variants for each substrate column."""
        n_results_raw: dict[str, np.ndarray] = {}
        n_results_by_model: dict[str, dict[str, np.ndarray]] = {}
        rmse_row: dict[str, dict[str, float]] = {}
        n_fit_meta: dict[str, dict[str, dict]] = {}
        total_cols = sum((len(v) for v in groups.values()))
        total_steps = max(total_cols * _N_SUBSTRATE_MODELS, 1)
        done_steps = 0
        col_idx = 0
        xa = np.asarray(x, dtype=np.float64)
        m_rmse_geom = IndexCore._fit_mask(xa, wl_min_fit, wl_max_fit) & np.isfinite(xa)
    
        def add_result(col_name, n_vals):
            nonlocal done_steps, col_idx
            if self.view.is_cancel_requested():
                raise RuntimeError('Calculation cancelled by user.')
            col_idx += 1
            if hasattr(self, 'progress_widget'):
                self.view.update_progress(done_steps, total_steps, phase=f'Columns {col_idx}/{max(total_cols, 1)}', extra_info=str(col_name))
            n_raw_base = np.asarray(n_vals, dtype=np.float64)
            finite_raw = np.asarray(n_raw_base, dtype=np.float64)[np.isfinite(n_raw_base)]
            if finite_raw.size:
                raw_min = float(np.min(finite_raw))
                raw_max = float(np.max(finite_raw))
            else:
                raw_min = float('nan')
                raw_max = float('nan')
            logger.info('Fit column %d/%d: %s | n_raw_range=[%.6f, %.6f]', col_idx, max(total_cols, 1), str(col_name), raw_min, raw_max)
            _i_min = int(np.argmin(n_raw_base))
            _i_max = int(np.argmax(n_raw_base))
            logger.info('Column anchors: lambda@n_min=%.1fnm lambda@n_max=%.1fnm', float(xa[_i_min]), float(xa[_i_max]))
            out_key = f'n ({col_name})'
            n_results_raw[out_key] = n_raw_base
            by_model: dict[str, np.ndarray] = {}
            rms_m: dict[str, float] = {}
            meta_m: dict[str, dict] = {}
            m_rmse_mask = m_rmse_geom & np.isfinite(n_raw_base)
            for mk, mlabel in SUBSTRATE_INDEX_MODELS:
                if self.view.is_cancel_requested():
                    raise RuntimeError('Calculation cancelled by user.')
                done_steps += 1
                if hasattr(self, 'progress_widget'):
                    self.view.update_progress(done_steps, total_steps, phase=f'Fit {done_steps}/{total_steps}', extra_info=f'{col_name}  {mlabel}')
                log_pre = mk == SUBSTRATE_INDEX_MODELS[0][0]
                _, n_fit, fit_meta = IndexCore.get_smoothed_and_fits(n_raw_base, xa, wl_min_fit, wl_max_fit, model_kind=mk, log_preprocess=log_pre, sellmeier_timeout_s=sellmeier_timeout_s, sellmeier_de_maxiter=sellmeier_de_maxiter, sellmeier_ls_max_nfev=sellmeier_ls_max_nfev, sellmeier_log_l1l2=sellmeier_log_l1l2, progress_cb=None)
                n_fit = np.asarray(n_fit, dtype=np.float64)
                by_model[mlabel] = n_fit
                if np.any(m_rmse_mask):
                    d = n_fit[m_rmse_mask] - n_raw_base[m_rmse_mask]
                    rmse_vs_raw = float(np.sqrt(np.mean(d * d)))
                else:
                    rmse_vs_raw = float('nan')
                meta_m[mlabel] = dict(fit_meta)
                src = str(fit_meta.get('source') or '')
                if src.startswith('fallback-raw') or src == 'skipped-insufficient-points':
                    rms_m[mlabel] = float('inf')
                    logger.info('Model %s | %s | RMSE(vs raw)=%.6g | source=%s - not eligible for best RMSE', str(col_name), mlabel, rmse_vs_raw if np.isfinite(rmse_vs_raw) else float('nan'), src)
                else:
                    rms_m[mlabel] = rmse_vs_raw if np.isfinite(rmse_vs_raw) else float('nan')
                    logger.info('Model %s | %s | RMSE(fit)=%.6g', str(col_name), mlabel, float(rms_m[mlabel]) if np.isfinite(rms_m[mlabel]) else float('nan'))
            n_results_by_model[out_key] = by_model
            rmse_row[out_key] = rms_m
            n_fit_meta[out_key] = meta_m
            i_edge = int(np.argmin(np.abs(xa - 4500.0)))
            score_m: dict[str, float] = {}
            selection_debug: dict[str, dict[str, float]] = {}
            for _mk, _ml in SUBSTRATE_INDEX_MODELS:
                arr = by_model.get(_ml)
                if arr is None:
                    score_m[_ml] = float('inf')
                    selection_debug[_ml] = {'rmse': float('inf'), 'score': float('inf'), 'mono_frac': float('inf'), 'prior_rmse': float('nan')}
                    continue
                rmse_v = float(rms_m.get(_ml, float('nan')))
                arr_np = np.asarray(arr, dtype=np.float64)
                score_v = _model_selection_score(rmse_fit=rmse_v, n_fit=arr_np, wl_nm=xa, fit_mask=m_rmse_mask, fit_meta=meta_m.get(_ml, {}), col_name=str(col_name))
                score_m[_ml] = score_v
                mono_cnt, mono_frac = IndexCore._monotonic_violation_stats(arr_np[m_rmse_mask]) if np.any(m_rmse_mask) else (0, 0.0)
                selection_debug[_ml] = {'rmse': rmse_v, 'score': score_v, 'mono_frac': float(mono_frac), 'prior_rmse': float('nan')}
            best_lab, best_score, best_rmse, ranked_models = _rank_models_by_selection_score(score_m=score_m, rms_m=rms_m, by_model=by_model, fit_mask=m_rmse_mask)
            if len(ranked_models) > 1 and np.isfinite(best_score):
                second_lab, second_score = ranked_models[1]
                rel_gap = (second_score - best_score) / max(1e-12, abs(best_score)) if np.isfinite(second_score) else float('inf')
                if rel_gap < 0.01 and len(best_lab) > len(second_lab):
                    logger.info('Tie-break: choosing simpler model %s over %s (scores %.6g vs %.6g).', second_lab, best_lab, float(second_score), float(best_score))
                    best_lab = second_lab
                    best_score = second_score
                    best_rmse = float(rms_m.get(best_lab, float('nan')))
            n_best = by_model.get(best_lab, n_raw_base)
            _r = np.asarray(n_best, dtype=np.float64) - np.asarray(n_raw_base, dtype=np.float64)
            logger.info('%s', _fit_summary_line(col_name=str(col_name), best_lab=best_lab, best_score=best_score, best_rmse=best_rmse, best_value_at_idx=float(n_best[i_edge]) if i_edge < len(n_best) else float('nan')))
        for c in groups['t_2f']:
            add_result(c, IndexCore.n_from_tnu2f(self._get_clean_fraction_column(x, c)))
        for c in groups['r_2f']:
            n_r2f = IndexCore.n_from_rnu2f(self._get_clean_fraction_column(x, c))
            n_r2f = IndexCore.enforce_normal_dispersion(x, n_r2f)
            add_result(c, n_r2f)
        for c in groups['r45s_1f']:
            add_result(c, IndexCore.n_from_r45s_single_face(self._get_clean_fraction_column(x, c)))
        for c in groups['r45s_2f']:
            add_result(c, IndexCore.n_from_r45s_single_face(IndexCore.single_face_from_two_face(self._get_clean_fraction_column(x, c))))
        for c in groups['r45p_1f']:
            add_result(c, IndexCore.n_from_r45p_single_face(self._get_clean_fraction_column(x, c)))
        for c in groups['r45p_2f']:
            add_result(c, IndexCore.n_from_r45p_single_face(IndexCore.single_face_from_two_face(self._get_clean_fraction_column(x, c))))
        return (n_results_raw, n_results_by_model, rmse_row, n_fit_meta)


    def _get_clean_fraction_column(self, x, c):
        y_raw = self.df[c].values
        y_clean = IndexCore.apply_dynamic_filtering(x, y_raw, 15, 2, False)
        y_clean = np.asarray(y_clean, dtype=np.float64)
        if y_clean.ndim > 1: y_clean = np.squeeze(y_clean)
        return IndexCore.to_fraction(y_clean)
