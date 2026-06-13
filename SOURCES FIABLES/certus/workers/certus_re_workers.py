import time
import traceback

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from concurrent.futures import ThreadPoolExecutor, as_completed
import joblib

from functools import partial
from types import SimpleNamespace
from typing import Any, Protocol, Callable

import numpy as np

from scipy.optimize import least_squares

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

from certus.core.certus_re_config import (
    REWorkerRequest,
    REPhase3Result,
    REPhase4Result,
    _top_result_dto,
    _set_top_result_dto,
    _prepend_result_dto,
    RE_RESULT_LABEL_WITH_DRIFT,
)

from certus.utils.certus_re_helpers import (
    _re_apply_correc,
    _re_correc_to_nk_preview_payload,
    _re_calc_spectrum_for_config,
    _re_p4_ap_band_intervals_str,
    _re_log_objective_diagnostic,
    re_substrate_cauchy_phi_matrix,
    re_substrate_cauchy_barrier_residuals_jac,
    RE_GUI_DEFAULT_RE_PHASE3_SHAKES,
    RE_SUB_CAUCHY_BARRIER_SQRT_W,
    RE_SUB_CAUCHY_TUBE_DELTA,
    RE_LBFGSB_FTOL,
    RE_LBFGSB_GTOL,
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    _re_sort_results_best_for_table_and_apply,
    RE_GUI_DEFAULT_RE_PHASE1_RESTARTS,
    re_envelope_max_delta_n,
    re_knots_wavelengths,
    RE_P4_BEAM_AP_BOUNDS_DEG,
    RE_GUI_DEFAULT_RE_PHASE2_TOP_K,
    RE_GUI_DEFAULT_RE_QWOT_ALPHA,
    RE_P4_AP_FD_STEP_DEG,
    RE_P4_BEAM_N_KNOTS,
    RE_PHASE2B_MAXITER,
    RE_PHASE2_SPLINE_PREFIT_MAXITER,
    RE_PHASE4_APERTURE_SCAN_POINTS,
    RE_PHASE4_TRF_MAX_NFEV,
    RE_PHASE4_TRF_TOL_FACTOR,
    RE_RANKING_ALPHA_REF,
    _re_trf_residual_rms,
    re_compute_spline_basis_matrix,
    re_compute_tikhonov_weights,
)

from certus.workers.certus_re_worker_utils import (
    shake_sigmas_adaptive,
    p2_result_to_correc_tuple,
    re_enrich_results_ranking_fields,
    re_finalize_ranking_log_suffix,
    re_finalize_finished_main_log_line,
    re_finalize_rmse_milestone_log_line,
    re_finalize_progress_message_done,
    re_live_plot_wls_and_dispersion_nk,
    re_trf_thickness_bounds,
    re_trf_bounds_scipy_tuples,
    re_phase1_trf_runs_multistart,
    RE_CORREC_NOMINAL_PCT,
    re_build_p2_progress_plan,
    re_progress_pct_p1,
    re_progress_pct_p2a,
    re_progress_pct_p2b,
    re_progress_pct_p3,
    resolve_re_qwot_alphas,
)

from certus.utils.certus_re_results_builder import REResultsBuilder as REResultsPayloadBuilder
from certus.core.certus_re_solvers import REUserStopRequested

from certus.ui.certus_qt_widgets import QThread

from certus.ui.certus_ui import WorkerSignals

from certus.core.certus_re_objectives import (
    _prepare_re_run_context_setup,
    _build_re_mse_grad_helper,
    _build_qwot_helpers,
)




class REWorker(QThread):
    """Two-stage RE: (1) TRF Deltaln(lambda) trapezoidal, thicknesses only, tabulated n;

    (2a) TRF DeltaRe splines only (thicknesses = end of phase 1);

    (2b) joint TRF thicknesses + splines + lambda₂ + optional Cauchy substrate (a0,a1,a2), tube |n-n_tab|<=Delta.

    Same index model as `re_apply_re_index_model` / `_compute_re_rmse`.

    """

    def __init__(self, cfg: dict[str, Any] | REWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, REWorkerRequest) else REWorkerRequest.from_legacy(cfg)

        # Keep legacy attribute for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

        self._stop = False

    def request_stop(self) -> None:
        """Cooperative stop (Stop button  not only QThread.requestInterruption)."""

        self._stop = True

    def _execute_phase1(self) -> list[dict]:
        from certus.core.certus_re_solvers import re_execute_phase1
        return re_execute_phase1(self)

    def _execute_phase1_p4_scan(self) -> None:
        from certus.core.certus_re_solvers import re_execute_phase1_p4_scan
        return re_execute_phase1_p4_scan(self)

    def _execute_phase2_splines(self) -> None:
        from certus.core.certus_re_solvers import re_execute_phase2_splines
        return re_execute_phase2_splines(self)

    def _execute_phase2_candidate(self, *args, **kwargs):
        from certus.core.certus_re_solvers import re_execute_phase2_candidate
        return re_execute_phase2_candidate(self, *args, **kwargs)

    def _run_phase4_joint_trf(self, *args, **kwargs):
        from certus.core.certus_re_solvers import re_run_phase4_joint_trf
        return re_run_phase4_joint_trf(self, *args, **kwargs)

    def _execute_phase3_shakes(self) -> None:
        """Phase 3: perturbations + short TRF refits (escape local minima)."""

        L = self._re_phase_ns

        results = L.results

        _p2_ctx = L._p2_ctx

        _use_sub_c3 = bool(L._use_sub_c3_shared)

        if not _p2_ctx:
            logging.warning("RE phase 3 skipped: phase-2 context unavailable.")

            return

        _nk = int(_p2_ctx["_nk"])

        i0 = int(_p2_ctx["i0"])

        i_lam = int(_p2_ctx["i_lam"])

        i_cu = i_lam + 1

        b_lb = np.asarray(_p2_ctx["b_lb"], dtype=np.float64)

        b_ub = np.asarray(_p2_ctx["b_ub"], dtype=np.float64)

        bounds_p2_trf = _p2_ctx["bounds_p2_trf"]

        _cb2_ref = _p2_ctx["_cb2_ref"]


        _p2_trf_log_tag = _p2_ctx["_p2_trf_log_tag"]

        _eval_both_p2 = _p2_ctx["_eval_both_p2"]

        _fun_res_p2 = _p2_ctx["_fun_res_p2"]

        _jac_res_p2 = _p2_ctx["_jac_res_p2"]

        n_layers_count = L.n_layers_count

        _alpha_slot = L._alpha_slot

        _a_p3 = L._a_p3

        re_p2_plan = L.re_p2_plan

        pl = re_p2_plan[0] if re_p2_plan else None

        _pct_p3 = L._pct_p3

        _emit_re_prog = L._emit_re_prog

        _emit_re_spectrum_live = L._emit_re_spectrum_live

        _report_mse_spectral = L._report_mse_spectral

        _compute_qwot_rmse = L._compute_qwot_rmse

        _rmse_combined = L._rmse_combined

        rmse_final_milestone = L.rmse_final_milestone

        # Phase 3: Shake & Refit

        RE_PHASE3_SHAKE_EP_SIGMA_PCT = 1.5

        RE_PHASE3_SHAKE_SPL_SIGMA = 0.01

        RE_PHASE3_SHAKE_MAXITER = 80

        n_shakes = int(self.cfg.get("re_phase3_shake_rounds", RE_GUI_DEFAULT_RE_PHASE3_SHAKES))

        if n_shakes > 0 and not self._stop and results:
            _alpha_slot[0] = _a_p3

            _sk_sh = self.cfg.get("re_phase3_shake_seed", -1)

            try:
                _sk_i = int(_sk_sh)

            except (TypeError, ValueError):
                _sk_i = -1

            _rng3 = np.random.default_rng((_sk_i % (2**32)) if _sk_i >= 0 else None)

            best_res = results[0]
            best_res_dto = REPhase4Result.from_legacy_dict(best_res)

            x_best = np.concatenate(
                [
                    best_res_dto.ep,
                    best_res_dto.re_dh_knots,
                    best_res_dto.re_dl_knots,
                    [best_res_dto.re_spline_lam_node2_nm],
                    (
                        [best_res_dto.re_sub_cauchy_a0, best_res_dto.re_sub_cauchy_a1, best_res_dto.re_sub_cauchy_a2]
                        if _use_sub_c3 and best_res_dto.re_sub_cauchy_a0 is not None
                        else []
                    ),
                ]
            )

            rmse_best = float(best_res_dto.rmse_combined)

            cor_best = p2_result_to_correc_tuple(best_res, _use_sub_c3)

            _cb2_ref[0] = {
                "x": None,
                "res": None,
                "jac": None,
                "mse": None,
                "best_rmse_combined": None,
                "i": 0,
                "last_emit": time.perf_counter(),
                "tk_w_c": None,
                "tk_lam2": None,
            }

            _p2_trf_log_tag = ["phase 3 warmup"]

            _p2_trf_log_tag[0] = "pre-phase 3 warmup"

            _eval_both_p2(np.asarray(x_best, dtype=np.float64))

            _r0_ref = _cb2_ref[0].get("res")

            if _r0_ref is None:
                _r0_ref = np.array([0.0], dtype=np.float64)

            _rn0 = float(np.linalg.norm(_r0_ref))

            try:
                from scipy.stats.qmc import LatinHypercube

                _lhs_samples = LatinHypercube(d=n_layers_count + 2 * _nk, seed=_rng3).random(n=n_shakes)

                _lhs_samples = _lhs_samples * 2.0 - 1.0

            except ImportError:
                _lhs_samples = _rng3.uniform(-1.0, 1.0, (n_shakes, n_layers_count + 2 * _nk))

            for _si in range(n_shakes):
                if self._stop:
                    break

                _sig_ep, _sig_sp = shake_sigmas_adaptive(
                    _rn0,
                    base_ep_sigma_pct=float(
                        self.cfg.get(
                            "re_phase3_shake_ep_sigma_pct",
                            RE_PHASE3_SHAKE_EP_SIGMA_PCT,
                        )
                    ),
                    base_spl_sigma=float(
                        self.cfg.get(
                            "re_phase3_shake_spl_sigma",
                            RE_PHASE3_SHAKE_SPL_SIGMA,
                        )
                    ),
                    ref_norm=float(self.cfg.get("re_phase3_shake_ref_norm", 1.0)),
                )

                x_shake = np.array(x_best, dtype=np.float64).copy()

                _u = _lhs_samples[_si]

                x_shake[:n_layers_count] += _u[:n_layers_count] * (_sig_ep / 100.0 * x_best[:n_layers_count])

                x_shake[i0:i_lam] += _u[n_layers_count:] * _sig_sp

                np.clip(x_shake, b_lb, b_ub, out=x_shake)

                _p2_trf_log_tag[0] = f"phase 3 shake {_si + 1}/{n_shakes}"

                _cr3 = _cb2_ref[0]

                if _cr3 is not None:
                    _cr3["i"] = 0

                    _cr3["x"] = None

                    _cr3["res"] = None

                    _cr3["jac"] = None

                    _cr3["mse"] = None

                    _cr3["best_rmse_combined"] = None

                    _cr3["last_emit"] = time.perf_counter()

                try:
                    res_sh = least_squares(
                        _fun_res_p2,
                        x_shake,
                        method="trf",
                        bounds=bounds_p2_trf,
                        jac=_jac_res_p2,
                        x_scale="jac",
                        ftol=RE_LBFGSB_FTOL * 10,
                        gtol=RE_LBFGSB_GTOL * 10,
                        max_nfev=RE_PHASE3_SHAKE_MAXITER,
                    )

                except REUserStopRequested:
                    logging.info("RE phase 3  stopped by user (keeping best phase 2 result)")

                    break

                x_sh = res_sh.x

                ep_sh = np.asarray(x_sh[:n_layers_count], dtype=np.float64).flatten()

                dh_sh = np.asarray(x_sh[i0 : i0 + _nk], dtype=np.float64).flatten()

                dl_sh = np.asarray(x_sh[i0 + _nk : i_lam], dtype=np.float64).flatten()

                lam_sh = float(x_sh[i_lam])

                knots_sh = re_knots_wavelengths(lam_sh)

                if _use_sub_c3:
                    th_sh = np.asarray(x_sh[i_cu : i_cu + 3], dtype=np.float64).ravel()

                    cor_sh = ("spline_sub3", dh_sh, dl_sh, lam_sh, float(th_sh[0]), float(th_sh[1]), float(th_sh[2]))

                else:
                    cor_sh = ("spline", dh_sh, dl_sh, lam_sh)

                rmse_p2_sh = float(np.sqrt(max(_report_mse_spectral(ep_sh, cor_sh), 0.0)))

                rmse_qwot_sh = _compute_qwot_rmse(ep_sh, cor_sh)

                rmse_comb_sh = _rmse_combined(rmse_p2_sh, rmse_qwot_sh)

                if rmse_comb_sh < rmse_best - 1e-8:
                    x_best = res_sh.x.copy()

                    rmse_best = rmse_comb_sh

                    logging.info(f"RE phase 3 shake #{_si + 1}: improved -> RMSE_combined={rmse_best:.6f}")

                    phase3_result = REPhase3Result(
                        label=RE_RESULT_LABEL_WITH_DRIFT,
                        ep=np.asarray(ep_sh, dtype=np.float64).flatten(),
                        a=0.0,
                        b=0.0,
                        f=0.0,
                        re_dh_knots=np.asarray(dh_sh, dtype=np.float64).flatten(),
                        re_dl_knots=np.asarray(dl_sh, dtype=np.float64).flatten(),
                        re_knots_nm=np.asarray(knots_sh, dtype=np.float64).flatten(),
                        re_spline_lam_node2_nm=float(lam_sh),
                        rmse=float(rmse_p2_sh),
                        rmse_qwot=float(rmse_qwot_sh),
                        rmse_combined=float(rmse_comb_sh),
                        nfev=int(best_res_dto.nfev + res_sh.nfev),
                        success=bool(res_sh.success),
                        nfev_phase1=int(best_res_dto.nfev_phase1),
                        nfev_phase2_prefit=int(best_res_dto.nfev_phase2_prefit),
                        re_sub_cauchy_a0=float(th_sh[0]) if _use_sub_c3 else None,
                        re_sub_cauchy_a1=float(th_sh[1]) if _use_sub_c3 else None,
                        re_sub_cauchy_a2=float(th_sh[2]) if _use_sub_c3 else None,
                    )
                    _phase3_as_p4 = REPhase4Result.from_legacy_dict(phase3_result.to_legacy_dict())
                    _set_top_result_dto(results, _phase3_as_p4)

                    cor_best = cor_sh

                    rmse_final_milestone[0] = float(_phase3_as_p4.rmse_combined)

                    _shake_best = float(_cb2_ref[0].get("best_rmse_combined", rmse_comb_sh))

                    if pl is not None:
                        _emit_re_prog(
                            _pct_p3(pl, _si, 1.0),
                            f"RE phase 3 shake {_si + 1}/{n_shakes}: "
                            f"best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}",
                        )

                    else:
                        _emit_re_prog(
                            97.0,
                            f"RE phase 3 shake {_si + 1}/{n_shakes}: "
                            f"best_shake RMSE={float(_shake_best):.6f} | best_global RMSE={float(rmse_best):.6f}",
                        )

                    _new_top_dto = _top_result_dto(results)
                    if _new_top_dto is not None and _new_top_dto.rmse_combined < best_res_dto.rmse_combined:
                        _emit_re_spectrum_live(
                            np.asarray(_new_top_dto.ep, dtype=np.float64).flatten(),
                            int(_new_top_dto.nfev),
                            correc=cor_best,
                            force=True,
                            rmse_override=float(_new_top_dto.rmse_combined),
                        )


    def _finalize_re_run(
        self,
        *,
        results: list[dict],
        rmse_initial_sp: float,
        rmse_initial_q: float,
        rmse_initial_u: float,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        _alpha_slot: list[float],
        _alpha_rank_ref: float,
        re_qwot_alphas: tuple[float, float, float, float],
        _compute_qwot_rmse_raw,
        _compute_qwot_rmse,
        _correc_nom: tuple,
        _emit_re_spectrum_live,
        _report_t0: float,
        _re_pct_hi: list[float],
        n_sub_nominal: np.ndarray,
        wls: np.ndarray,
        lambda_ref: float,
        ep0: np.ndarray,
    ) -> None:
        """Sort/finalize RE results, emit final spectrum, logs and finished payload."""

        # Stop fallback, then best combined + tie-break + ranking enrichment.
        _top_result = REResultsPayloadBuilder.finalize_reconcile_top(
            results=results,
            stop_requested=bool(self._stop),
            cfg_ep0=self.cfg.get("ep0"),
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_initial_u=rmse_initial_u,
            alpha_rank_ref=_alpha_rank_ref,
            compute_qwot_rmse_raw=_compute_qwot_rmse_raw,
            sort_results=_re_sort_results_best_for_table_and_apply,
            enrich_results=re_enrich_results_ranking_fields,
        )
        _top_dto = REPhase4Result.from_legacy_dict(_top_result) if _top_result else None

        if _top_dto is not None:
            rmse_final_milestone[0] = float(_top_dto.rmse_combined)

        _stop_live_payload = REResultsPayloadBuilder.stop_live_emit_payload(
            stop_requested=bool(self._stop),
            top_result=_top_result,
            correc_nominal=_correc_nom,
            p2_to_correc=p2_result_to_correc_tuple,
        )
        if _stop_live_payload is not None:
            _emit_re_spectrum_live(
                _stop_live_payload["ep"],
                _stop_live_payload["nfev"],
                correc=_stop_live_payload["correc"],
                force=bool(_stop_live_payload["force"]),
                rmse_override=float(_stop_live_payload["rmse_override"]),
            )

        _tot = time.perf_counter() - _report_t0
        _top_metrics = REResultsPayloadBuilder.top_metrics(_top_result)
        _best_sp = float(_top_metrics["best_sp"])
        _best_ot = float(_top_metrics["best_ot"])
        _best = float(_top_metrics["best_combined"])
        rmse_final_u = float(_top_metrics["rmse_final_u"])

        if results:
            _a_gui = float(self.cfg.get("re_qwot_penalty_weight", RE_GUI_DEFAULT_RE_QWOT_ALPHA))
            _diag_payload = REResultsPayloadBuilder.final_diagnostic_payload(
                best_sp=float(_best_sp),
                best_ot=float(_best_ot),
                alpha_current=float(_alpha_slot[0]),
                alpha_gui=_a_gui,
                rmse_final_u=float(rmse_final_u),
                rmse_initial_u=float(rmse_initial_u),
                rmse_initial_sp=float(rmse_initial_sp),
                rmse_initial_q=float(rmse_initial_q),
            )

            logging.info("RE  final summary (progress readout / e.g. reverse_sample.xlsx) ")

            _re_log_objective_diagnostic(
                "final ( from last TRF phase)",
                _diag_payload["best_sp"],
                _diag_payload["ot_fin"],
                _diag_payload["alpha_current"],
            )

            _re_log_objective_diagnostic(
                "final (same sp/QWOT,  from base cfg / preset  comparison)",
                _diag_payload["best_sp"],
                _diag_payload["ot_fin"],
                _diag_payload["alpha_gui"],
            )

            logging.info(
                "RE summary  gains vs init: Delta RMSE=%+.6f | Delta sp=%+.6f | Delta QWOT=%+.6f",
                _diag_payload["delta_rmse"],
                _diag_payload["delta_sp"],
                _diag_payload["delta_qwot"],
            )

            _cauchy_diag = REResultsPayloadBuilder.cauchy_barrier_diagnostic_payload(
                top_result=_top_result,
                wls=wls,
                lambda_ref=lambda_ref,
                n_sub_nominal=n_sub_nominal,
                barrier_sqrt_w=float(
                    self.cfg.get(
                        "re_sub_cauchy_barrier_sqrt_w",
                        RE_SUB_CAUCHY_BARRIER_SQRT_W,
                    )
                ),
                tube_delta=float(RE_SUB_CAUCHY_TUBE_DELTA),
                substrate_phi_matrix=re_substrate_cauchy_phi_matrix,
                barrier_residuals_jac=re_substrate_cauchy_barrier_residuals_jac,
            )
            if _cauchy_diag is not None:
                logging.info(
                    "RE diag [Cauchy substrate barrier] ||r||=%.4g, %d/%d non-zero residuals "
                    "(tube |nn_tab|<=%.3g)  active boundary -> constraint saturated; zeros -> inside tube.",
                    _cauchy_diag["res_norm"],
                    _cauchy_diag["n_active"],
                    _cauchy_diag["n_total"],
                    _cauchy_diag["tube_delta"],
                )

        _tail = REResultsPayloadBuilder.finalize_tail_bundle(
            results=results,
            top_result=_top_result,
            ep0=ep0,
            alpha_rank_ref=_alpha_rank_ref,
            elapsed_s=_tot,
            best_sp=_best_sp,
            best_ot=_best_ot,
            best_combined=_best,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=bool(self._stop),
            re_qwot_alphas=re_qwot_alphas,
            ranking_log_suffix=re_finalize_ranking_log_suffix,
            finished_main_log_line=re_finalize_finished_main_log_line,
            rmse_milestone_log_line=re_finalize_rmse_milestone_log_line,
            progress_message_done=re_finalize_progress_message_done,
        )
        logging.info(_tail["finished_main_log"])
        logging.info(_tail["rmse_milestone_log"])

        _re_pct_hi[0] = 100.0

        self.signals.progress.emit(100, _tail["progress_done"])

        self.signals.finished.emit(_tail["finished_payload"])


    def _emit_re_spectrum_live_helper(
        self,
        ep_vec: np.ndarray,
        evals: int,
        *,
        correc: tuple,
        last_mse: float | None,
        force: bool,
        rmse_override: float | None,
        _re_live_emit: dict,
        n_lay_disp: np.ndarray,
        n_sub_disp: np.ndarray,
        is_H: np.ndarray,
        is_L: np.ndarray,
        wls_display: np.ndarray,
        lambda_ref: float,
        re_env_s: float,
        _re_env_on_wls_disp: np.ndarray,
        _mse_grad_accumulate_ep,
        wt_spectral: np.ndarray,
        _compute_qwot_rmse,
        _alpha_slot: list,
        _rmse_combined,
        oblique_config_meta: list,
        _re_state: dict,
        _ap_gui: float,
        oblique_tgts: list,
    ) -> None:
        if self._stop and not force:
            return

        now_te = time.perf_counter()
        if not force and _re_live_emit["t"] > 0.0 and (now_te - _re_live_emit["t"]) < 0.45:
            return

        _re_live_emit["t"] = now_te

        try:
            ep_use = np.asarray(ep_vec, dtype=np.float64).flatten()
            n_lm, n_sm = _re_apply_correc(
                n_lay_disp,
                n_sub_disp,
                is_H=is_H,
                is_L=is_L,
                wls=wls_display,
                lambda_ref=lambda_ref,
                correc=correc,
                re_env_s=re_env_s,
                env_cache=_re_env_on_wls_disp,
            )
            n_lay_T_corr = np.ascontiguousarray(n_lm.T)
            n_sub_use = np.ascontiguousarray(n_sm)

            if last_mse is not None and np.isfinite(last_mse):
                rs = float(np.sqrt(max(float(last_mse), 0.0)))
            else:
                _sp_mse = float(_mse_grad_accumulate_ep(ep_use, wt_spectral, False, correc)[0])
                rs = float(np.sqrt(max(_sp_mse, 0.0)))

            rq = float(_compute_qwot_rmse(ep_use, correc))
            al_q = float(_alpha_slot[0])

            if rmse_override is not None and np.isfinite(rmse_override):
                rmse_d = float(rmse_override)
            else:
                rmse_d = _rmse_combined(rs, rq)

            spectra_display = {}
            display_keys_done = set()

            for meta in oblique_config_meta:
                angle = float(meta["angle"])
                pol = str(meta["pol"])
                inc_back = bool(meta["include_backside"])
                dkey = (angle, pol, inc_back)

                if dkey in display_keys_done:
                    continue
                display_keys_done.add(dkey)

                R_o, T_o = _re_calc_spectrum_for_config(
                    wls_display,
                    n_lay_T_corr,
                    ep_use,
                    n_sub_use,
                    angle,
                    pol,
                    inc_back,
                    phase4_average=_re_state["is_phase4"],
                    beam_aperture=_ap_gui,
                    beam_aperture_knots_deg=_re_state["re_aperture_knots"],
                    beam_aperture_knots_lam_nm=_re_state["re_p4_beam_knots_lam_nm"],
                )
                spectra_display[dkey] = {"R": R_o, "T": T_o}

            if not spectra_display:
                return

            first_key = next(iter(spectra_display))
            Ts_first = spectra_display[first_key]["T"]
            _nk_prev = _re_correc_to_nk_preview_payload(correc)

            self.signals.result.emit(
                {
                    "type": "intermediate",
                    "wls": wls_display,
                    "Ts": Ts_first,
                    "ep": ep_use,
                    "rmse": rmse_d,
                    "rmse_sp": rs,
                    "rmse_qwot": rq,
                    "alpha_qwot": al_q,
                    "evals": int(evals),
                    "is_global_best": True,
                    "oblique_mode": True,
                    "spectra_display": spectra_display,
                    "oblique_tgts": oblique_tgts,
                    **_nk_prev,
                }
            )
        except NUMERICAL_FAULT_EXCEPTIONS as _emit_e:
            logging.debug("RE live spectrum emit: %s", _emit_e)

    def _build_re_run_context(self, _re_t0: float) -> Any:
        """Prepares grids, MSE/QWOT, self.ctx and self._re_phase_ns for RE phases."""
        logger.debug("_build_re_run_context ENTER")
        self.signals.progress.emit(1, "[DBG] _build_re_run_context: started")
        ctx, prep = _prepare_re_run_context_setup(self, _re_t0)
        _emit_re_prog = prep["_emit_re_prog"]
        _re_pct_hi = prep["_re_pct_hi"]
        wls = prep["wls"]
        _RE_P_SETUP = prep["_RE_P_SETUP"]
        _RE_P_P1 = prep["_RE_P_P1"]
        _mse_grad_accumulate_ep = _build_re_mse_grad_helper(self, ctx)
        mats = prep["mats"]
        stack = prep["stack"]
        ep0 = prep["ep0"]
        radius = prep["radius"]
        oblique_tgts = prep["oblique_tgts"]
        lambda_ref = prep["lambda_ref"]
        float_dtype = np.float64
        complex_dtype = np.complex128
        n_layers_count = prep["n_layers_count"]
        n_layers_nominal = prep["n_layers_nominal"]
        n_sub_nominal = prep["n_sub_nominal"]
        is_H = prep["is_H"]
        is_L = prep["is_L"]
        n_ref_nom_per_layer = prep["n_ref_nom_per_layer"]
        _lref_arr = prep["_lref_arr"]
        _p4_beam_knots_lam = prep["_p4_beam_knots_lam"]
        oblique_config_meta = prep["oblique_config_meta"]
        wt_spectral = prep["wt_spectral"]
        re_env_s = prep["re_env_s"]
        _re_env_on_wls = prep["_re_env_on_wls"]
        _ap_gui = prep["_ap_gui"]
        _re_state = prep["_re_state"]
        wls_min = prep["wls_min"]
        wls_max = prep["wls_max"]
        wls_display, n_sub_disp, n_lay_disp = re_live_plot_wls_and_dispersion_nk(
            mats,
            stack,
            wls_min,
            wls_max,
            float_dtype=float_dtype,
            complex_dtype=complex_dtype,
        )

        # Bounds: thicknesses only +/-radius %

        lb_ep, ub_ep = re_trf_thickness_bounds(ep0, radius)

        bounds_trf = (lb_ep, ub_ep)

        bounds = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)

        # --- QWOT RMSE helper (re_delta_qwot_per_layer = residu TRF) ---

        _qwot_helpers = _build_qwot_helpers(self, ep0, n_ref_nom_per_layer, is_H, is_L, lambda_ref, re_env_s, _lref_arr, ctx._alpha_slot)
        _get_delta_qwot = _qwot_helpers["_get_delta_qwot"]
        _compute_qwot_rmse = _qwot_helpers["_compute_qwot_rmse"]
        _compute_qwot_rmse_raw = _qwot_helpers["_compute_qwot_rmse_raw"]
        _rmse_combined = _qwot_helpers["_rmse_combined"]

        _re_env_on_wls_disp = re_envelope_max_delta_n(wls_display, scale=re_env_s)

        _re_live_emit = {"t": 0.0}
        # _ap_gui and _re_state already defined above (before REMseContext instantiation).

        def _emit_re_spectrum_live(
            ep_vec: np.ndarray,
            evals: int,
            *,
            correc: tuple,
            last_mse: float | None = None,
            force: bool = False,
            rmse_override: float | None = None,
        ) -> None:
            self._emit_re_spectrum_live_helper(
                ep_vec,
                evals,
                correc=correc,
                last_mse=last_mse,
                force=force,
                rmse_override=rmse_override,
                _re_live_emit=_re_live_emit,
                n_lay_disp=n_lay_disp,
                n_sub_disp=n_sub_disp,
                is_H=is_H,
                is_L=is_L,
                wls_display=wls_display,
                lambda_ref=lambda_ref,
                re_env_s=re_env_s,
                _re_env_on_wls_disp=_re_env_on_wls_disp,
                _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
                wt_spectral=wt_spectral,
                _compute_qwot_rmse=_compute_qwot_rmse,
                _alpha_slot=ctx._alpha_slot,
                _rmse_combined=_rmse_combined,
                oblique_config_meta=oblique_config_meta,
                _re_state=_re_state,
                _ap_gui=_ap_gui,
                oblique_tgts=oblique_tgts,
            )

        # --- Phase 1: TRF (Least Squares) Deltaln(lambda) trapezoidal, thickness only; tabulated (n,k) nominal ---

        n_starts = int(self.cfg.get("re_phase1_multistarts", RE_GUI_DEFAULT_RE_PHASE1_RESTARTS))

        runs = re_phase1_trf_runs_multistart(ep0, wt_spectral, lb_ep, ub_ep, n_starts, lhs_seed=42)

        n_sched = len(runs)

        _correc_nom = RE_CORREC_NOMINAL_PCT

        def _report_mse_spectral(ep_arr: np.ndarray, correc_t: tuple) -> float:

            return float(_mse_grad_accumulate_ep(ep_arr, wt_spectral, False, correc_t)[0])

        ep0_u = np.asarray(ep0, dtype=np.float64).flatten()

        rmse_initial_sp = float(np.sqrt(max(_report_mse_spectral(ep0_u, _correc_nom), 0.0)))

        rmse_initial_q = _compute_qwot_rmse(ep0_u, _correc_nom)

        _a_p1, _a_p2a, _a_p2b, _a_p3 = resolve_re_qwot_alphas(self.cfg, rmse_initial_sp, rmse_initial_q)

        ctx._alpha_slot[0] = _a_p1

        logging.info(
            "RE  QWOT (phase1=%g, 2a=%g, 2b=%g, 3=%g)  per_phase=%s adaptive_init=%s",
            _a_p1,
            _a_p2a,
            _a_p2b,
            _a_p3,
            bool(self.cfg.get("re_qwot_per_phase_schedule", True)),
            bool(self.cfg.get("re_qwot_adaptive_init_scale", False)),
        )

        rmse_initial_u = _rmse_combined(rmse_initial_sp, rmse_initial_q)

        _wp_ctx = self.cfg.get("re_workbook_path")

        if _wp_ctx:
            logging.info(
                "RE context  workbook: %s",
                Path(str(_wp_ctx)).name,
            )

        _n_tg_on = sum(1 for t in oblique_tgts if getattr(t, "on", True))

        _angles = sorted({float(t.angle) for t in oblique_tgts if getattr(t, "on", True)})

        logging.info(
            "RE context  lambda_ref=%.2f nm | objective grid [%.1f ... %.1f] nm (%d pts) | "
            "%d active targets | %d spectral blocks (weight Deltaln(lambda) trapezoidal) | incidence deg: %s | "
            "phase1 thickness radius +/-%g%%",
            float(lambda_ref),
            float(np.min(wls)) if wls.size else float("nan"),
            float(np.max(wls)) if wls.size else float("nan"),
            int(wls.size),
            _n_tg_on,
            len(oblique_config_meta),
            ", ".join(f"{a:g}" for a in _angles) if _angles else "",
            float(radius),
        )

        _re_log_objective_diagnostic(
            "initial (Excel design thicknesses)",
            rmse_initial_sp,
            rmse_initial_q,
            _a_p1,
        )

        _de_mx = int(self.cfg.get("re_phase1_de_maxiter", 0))

        _de_ps = int(self.cfg.get("re_phase1_de_popsize", 8))

        if _de_mx > 0 and not self._stop:
            try:
                from scipy.optimize import differential_evolution

                def _obj_de(x) -> float:

                    xa = np.asarray(x, dtype=np.float64).ravel()

                    v = float(_report_mse_spectral(xa, _correc_nom))

                    return float(np.sqrt(max(v, 0.0)))

                bounds_de = re_trf_bounds_scipy_tuples(lb_ep, ub_ep)

                res_de = differential_evolution(
                    _obj_de,
                    bounds_de,
                    maxiter=_de_mx,
                    popsize=max(5, _de_ps),
                    seed=int(self.cfg.get("re_phase1_de_seed", 42)),
                    polish=False,
                    workers=1,
                )

                runs.insert(
                    0,
                    (
                        "DE->TRF",
                        wt_spectral,
                        np.asarray(res_de.x, dtype=np.float64).ravel(),
                    ),
                )

                n_sched = len(runs)

                logging.info(
                    "RE phase1  differential_evolution seed (maxiter=%d, popsize=%d)",
                    _de_mx,
                    _de_ps,
                )

            except NUMERICAL_FAULT_EXCEPTIONS as _e_de:
                logging.warning("RE phase1 differential_evolution skipped: %s", _e_de)

        _any_spl_act = bool(self.cfg.get("re_refine_h", True)) or bool(self.cfg.get("re_refine_l", True))

        _re_top_k_cfg = max(1, int(self.cfg.get("re_phase2_top_k", RE_GUI_DEFAULT_RE_PHASE2_TOP_K)))

        _re_n_sh_cfg = max(0, int(self.cfg.get("re_phase3_shake_rounds", 4))) if _any_spl_act else 0

        _re_prefit_max_cfg = (
            int(
                self.cfg.get(
                    "re_phase2_spline_prefit_maxiter",
                    RE_PHASE2_SPLINE_PREFIT_MAXITER,
                )
            )
            if _any_spl_act
            else 0
        )

        _re_skip_2a_cfg = bool(self.cfg.get("re_phase2_skip_spline_prefit", False)) or not _any_spl_act

        _re_do_2a_cfg = (not _re_skip_2a_cfg) and (_re_prefit_max_cfg > 0)


        _maxiter_p2b = max(10, int(self.cfg.get("re_phase2b_maxiter", RE_PHASE2B_MAXITER)))

        _re_use_staged_order = bool(_any_spl_act)

        re_p2_plan: list[dict | None] = [None]

        _bind_p2_plan = partial(
            re_build_p2_progress_plan,
            re_top_k_cfg=_re_top_k_cfg,
            re_p_setup=_RE_P_SETUP,
            re_p_p1=_RE_P_P1,
            re_n_sh_cfg=_re_n_sh_cfg,
            re_do_2a_cfg=_re_do_2a_cfg,
        )

        _pct_p1 = partial(
            re_progress_pct_p1,
            re_p_setup=_RE_P_SETUP,
            re_p_p1=_RE_P_P1,
            n_sched=n_sched,
        )

        _pct_p2a = re_progress_pct_p2a

        _pct_p2b = re_progress_pct_p2b

        _pct_p3 = partial(re_progress_pct_p3, re_n_sh_cfg=_re_n_sh_cfg)

        results = []

        rmse_initial_milestone = [float(rmse_initial_u)]

        rmse_phase1_milestone = [float("nan")]

        rmse_final_milestone = [float("nan")]

        _emit_re_spectrum_live(
            ep0_u,
            0,
            correc=_correc_nom,
            force=True,
            rmse_override=rmse_initial_u,
        )

        self.ctx = SimpleNamespace(
            runs=runs,
            n_layers_count=n_layers_count,
            _emit_re_prog=_emit_re_prog,
            _pct_p1=_pct_p1,
            wt_spectral=wt_spectral,
            _correc_nom=_correc_nom,
            _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
            _compute_qwot_rmse=_compute_qwot_rmse,
            _rmse_combined=_rmse_combined,
            bounds_trf=bounds_trf,
            RE_LBFGSB_FTOL=RE_LBFGSB_FTOL,
            RE_LBFGSB_GTOL=RE_LBFGSB_GTOL,
            _report_mse_spectral=_report_mse_spectral,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _alpha_slot=ctx._alpha_slot,
            _a_p1=_a_p1,
            rmse_initial_u=rmse_initial_u,
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            _re_use_staged_order=_re_use_staged_order,
            cfg=self.cfg,
            _stop=self._stop,
        )

        self._re_phase_ns = SimpleNamespace(
            results=results,
            oblique_config_meta=oblique_config_meta,
            _re_use_staged_order=_re_use_staged_order,
            _emit_re_prog=_emit_re_prog,
            _RE_P_SETUP=_RE_P_SETUP,
            _RE_P_P1=_RE_P_P1,
            _re_state=_re_state,
            _ap_gui=_ap_gui,
            _mse_grad_accumulate_ep=_mse_grad_accumulate_ep,
            wt_spectral=wt_spectral,
            _correc_nom=_correc_nom,
            bounds_trf=bounds_trf,
            n_layers_count=n_layers_count,
            _compute_qwot_rmse=_compute_qwot_rmse,
            _rmse_combined=_rmse_combined,
            _report_mse_spectral=_report_mse_spectral,
            rmse_final_milestone=rmse_final_milestone,
            wls=wls,
            re_env_s=re_env_s,
            n_sub_nominal=n_sub_nominal,
            lambda_ref=lambda_ref,
            bounds=bounds,
            _alpha_slot=ctx._alpha_slot,
            _a_p2a=_a_p2a,
            _a_p2b=_a_p2b,
            _a_p3=_a_p3,
            re_p2_plan=re_p2_plan,
            _bind_p2_plan=_bind_p2_plan,
            _pct_p2a=_pct_p2a,
            _pct_p2b=_pct_p2b,
            _pct_p3=_pct_p3,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _re_n_sh_cfg=_re_n_sh_cfg,
            _any_spl_act=_any_spl_act,
            _maxiter_p2b=_maxiter_p2b,
            _re_pct_hi=_re_pct_hi,
            _use_sub_c3_shared=False,
            _p2_ctx={},
        )

        return SimpleNamespace(
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_initial_u=rmse_initial_u,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            _alpha_slot=ctx._alpha_slot,
            _a_p1=_a_p1,
            _a_p2a=_a_p2a,
            _a_p2b=_a_p2b,
            _a_p3=_a_p3,
            _correc_nom=_correc_nom,
            _emit_re_spectrum_live=_emit_re_spectrum_live,
            _compute_qwot_rmse_raw=_compute_qwot_rmse_raw,
            _compute_qwot_rmse=_compute_qwot_rmse,
            n_sub_nominal=n_sub_nominal,
            wls=wls,
            lambda_ref=lambda_ref,
            ep0=ep0,
            _re_pct_hi=_re_pct_hi,
            results=results,
            _re_t0=_re_t0,
        )


    def _compute_eval_both_p2(self, ctx, xv: np.ndarray, emit_interval: float = 3.0) -> tuple | None:

        if self._stop:
            raise REUserStopRequested()

        _c = ctx._cb2_ref[0]

        if _c is None:
            return

        # Phase 4: aperture knot values change MSE without changing xv  invalidate cache.

        _ph4_ap_now = None

        if ctx._re_state.get("is_phase4"):
            _kap = np.asarray(ctx._re_state["re_aperture_knots"], dtype=np.float64).ravel()[
                : int(RE_P4_BEAM_N_KNOTS)
            ]

            _ph4_ap_now = tuple(float(x) for x in _kap)

        if _c["x"] is not None and np.array_equal(xv, _c["x"]):
            if _ph4_ap_now is None:
                return

            if _c.get("_ph4_ap_snap") == _ph4_ap_now:
                return

        # S2: Invalidate Tikhonov weights when lam2 changes by >1 nm.

        cur_lam2 = float(xv[ctx.i_lam])

        if _c["tk_w_c"] is None or abs(cur_lam2 - (_c["tk_lam2"] or 0.0)) > 1.0:
            _c["tk_w_c"] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)

            _c["tk_lam2"] = cur_lam2

        tk_w_c = _c["tk_w_c"]

        _c["i"] += 1

        ep_x = np.asarray(xv[:ctx.n_layers_count], dtype=np.float64, copy=False)

        dh4 = xv[ctx.i0 : ctx.i0 + ctx._nk].copy()

        dl4 = xv[ctx.i0 + ctx._nk : ctx.i_lam].copy()

        lam2 = float(xv[ctx.i_lam])

        th4 = np.asarray(xv[ctx.i_cu : ctx.i_cu + 3], dtype=np.float64).ravel() if ctx._use_sub_c3 else None

        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam2), ctx.wls)

        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)

        if ctx._use_sub_c3:
            cor_spl = (
                "spline_cached_sub3",
                dh4,
                dl4,
                lam2,
                b_mat_c,
                env_c,
                tk_w_c,
                float(th4[0]),
                float(th4[1]),
                float(th4[2]),
            )

        else:
            cor_spl = ("spline_cached", dh4, dl4, lam2, b_mat_c, env_c, tk_w_c)

        mse, _, r_c, j_ep = ctx._mse_grad_accumulate_ep(ep_x, ctx.wt_spectral, True, cor_spl, return_residuals=True)

        if _c["i"] == 1:
            _n_fd = (ctx._n_joint_fd) if ctx._fd_1s else (ctx._n_joint_fd * 2)

            logging.info(
                "RE phase 2b  1st TRF eval: %d thick. analytic, %d FD residual blocks (%s)  FD_threads=%d",
                ctx.n_layers_count,
                _n_fd,
                "forward" if ctx._fd_1s else "centered",
                ctx._fd_nw,
            )

        J_var = np.zeros((len(r_c), ctx._n_joint_fd), dtype=np.float64)

        xv64 = np.asarray(xv, dtype=np.float64, copy=True)

        def _p2_fd_j_res(j: int) -> tuple[int, np.ndarray]:
            return self._evaluate_p2_fd_derivative(
                ctx,
                j,
                xv64,
                ep_x,
                r_c,
                b_mat_c,
                env_c,
                tk_w_c,
                dh4,
                dl4,
                lam2,
                th4,
            )

        _nw_j = min(ctx._fd_nw, ctx._n_joint_fd)

        _active_js = []

        _act_h = bool(self.cfg.get("re_refine_h", True))

        _act_l = bool(self.cfg.get("re_refine_l", True))

        for j in range(ctx._n_joint_fd):
            if j < ctx._nk and not _act_h:
                continue

            if ctx._nk <= j < 2 * ctx._nk and not _act_l:
                continue

            if j == 2 * ctx._nk and not (_act_h or _act_l):
                continue

            _active_js.append(j)

        if _nw_j <= 1:
            for j in _active_js:
                jj, j_col = _p2_fd_j_res(j)

                J_var[:, jj] = j_col

        else:
            _fd_executor_kind = str(self.cfg.get("re_phase2_fd_executor", "thread")).lower()
            _ex_p2 = _c.get("fd_executor")

            if _ex_p2 is None:
                # Use joblib instead of ThreadPool/ProcessPool for Phase 2 fd evaluation
                _backend = 'loky' if _fd_executor_kind == 'process' else 'threading'
                _ex_p2 = joblib.Parallel(n_jobs=_nw_j, backend=_backend)
                _c["fd_executor"] = _ex_p2

            try:
                # joblib blocks until all done and returns a list of results in order of _active_js
                results = _ex_p2(joblib.delayed(_p2_fd_j_res)(j) for j in _active_js)
                for res in results:
                    jj, j_col = res
                    J_var[:, jj] = j_col
            except Exception:
                if _fd_executor_kind == "process":
                    logging.getLogger(__name__).warning(
                        "RE phase2 FD process executor (loky) fallback to threading", exc_info=True
                    )
                    _fallback = joblib.Parallel(n_jobs=_nw_j, backend='threading')
                    _c["fd_executor"] = _fallback
                    results = _fallback(joblib.delayed(_p2_fd_j_res)(j) for j in _active_js)
                    for res in results:
                        jj, j_col = res
                        J_var[:, jj] = j_col
                else:
                    raise

        if ctx._use_sub_c3:
            J_spl = J_var[:, :ctx.n_sp]

            J_cu = J_var[:, ctx.n_sp : ctx.n_sp + 3]

            J_top = np.hstack([j_ep, J_spl, J_cu])

            sw_b = float(
                self.cfg.get(
                    "re_sub_cauchy_barrier_sqrt_w",
                    RE_SUB_CAUCHY_BARRIER_SQRT_W,
                )
            )

            r_b, J_b = re_substrate_cauchy_barrier_residuals_jac(
                th4,
                ctx._Phi_sub,
                ctx._n_tab_sub,
                sqrt_w=sw_b,
            )

            J_bot = np.hstack(
                [
                    np.zeros(
                        (len(r_b), ctx.n_layers_count + ctx.n_sp),
                        dtype=np.float64,
                    ),
                    J_b,
                ]
            )

            _c["res"] = np.concatenate((r_c, r_b))

            _c["jac"] = np.vstack([J_top, J_bot])

            _c["barrier_norm"] = float(np.linalg.norm(r_b))

        else:
            _c["res"] = r_c

            _c["jac"] = np.hstack([j_ep, J_var[:, :ctx.n_sp]])

            _c["barrier_norm"] = None

        _c["x"] = xv.copy()

        _c["mse"] = float(mse)

        _c["_ph4_ap_snap"] = _ph4_ap_now

        now = time.perf_counter()

        if _c["i"] == 1 or (now - _c["last_emit"]) >= emit_interval:
            _c["last_emit"] = now

            rs2 = float(np.sqrt(max(_c["mse"], 0.0)))

            rq2 = ctx._compute_qwot_rmse(ep_x, cor_spl)

            rmse_cur = ctx._rmse_combined(rs2, rq2)

            if ctx._p2_trf_log_tag[0] == "phase 4 finale":
                _ap_k = np.asarray(ctx._re_state["re_aperture_knots"], dtype=float).ravel()[
                    : int(RE_P4_BEAM_N_KNOTS)
                ]

                _lam_k = np.asarray(ctx._re_state.get("re_p4_beam_knots_lam_nm", []), dtype=float).ravel()[
                    : _ap_k.size
                ]

                _pairs = ", ".join(
                    f"(lambda={lk:.0f}nm->{ak:.2f})" for lk, ak in zip(_lam_k, _ap_k, strict=False)
                )

                ap_sfx = f" | ap=[{_pairs}]"

            else:
                ap_sfx = ""

            _bn = _c.get("barrier_norm")

            _bar_sfx = f" | ||barrier||={float(_bn):.4g}" if _bn is not None else ""

            _best_prev = _c.get("best_rmse_combined")

            if _best_prev is None or rmse_cur < float(_best_prev):
                _c["best_rmse_combined"] = float(rmse_cur)

            rmse_best_so_far = float(_c.get("best_rmse_combined", rmse_cur))

            _trf_rms_p2 = _re_trf_residual_rms(_c["res"])

            msg = (
                f"RE [{ctx._p2_trf_log_tag[0]}] TRF it ~{_c['i']}  "
                f"RMSE_facade(curr)={rmse_cur:.6f} | RMSE_facade(best)={rmse_best_so_far:.6f} "
                f"(sqrt(sp2+alpha·QWOT2); hors Tikhonov/pen H-L dans r) | "
                f"TRF_RMS(res)={_trf_rms_p2:.6g}{ap_sfx}{_bar_sfx}  {now - ctx._t_p2:.1f}s"
            )

            logging.info(msg)

            _intra_2b = min(
                0.92,
                float(_c["i"]) / float(max(ctx._maxiter_p2b, 1)),
            )

            ctx._emit_re_prog(
                ctx._pct_p2b(ctx.pl, ctx._p2_ki_slot[0], _intra_2b),
                msg,
            )

            ctx._emit_re_spectrum_live(ep_x, _c["i"], correc=cor_spl, last_mse=_c["mse"], force=False)

    def _compute_fun_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float = 3.0) -> Any:

        self._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)

        return ctx_p2._cb2_ref[0]["res"]

    def _compute_jac_res_p2(self, ctx_p2, xv: np.ndarray, emit_interval: float = 3.0) -> Any:

        self._compute_eval_both_p2(ctx_p2, xv, emit_interval=emit_interval)

        return ctx_p2._cb2_ref[0]["jac"]

    def _compute_eval_both_p2a(self, ctx, 
        x_sp: np.ndarray,
        _cb2a,
        ep_p1,
        _ki,
        _t_pf,
    ) -> tuple | None:

        if self._stop:
            raise REUserStopRequested()

        if _cb2a["x"] is not None and np.array_equal(x_sp, _cb2a["x"]):
            return

        # S2: Invalidate Tikhonov weights when lam2 changes by >1 nm.

        cur_lam2 = float(x_sp[2 * ctx._nk])

        if _cb2a["tk_w_c"] is None or abs(cur_lam2 - (_cb2a["tk_lam2"] or 0.0)) > 1.0:
            _cb2a["tk_w_c"] = re_compute_tikhonov_weights(re_knots_wavelengths(cur_lam2), ctx.wls)

            _cb2a["tk_lam2"] = cur_lam2

        tk_w_c = _cb2a["tk_w_c"]

        _cb2a["i"] += 1

        dh = np.asarray(x_sp[:ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)

        dl = np.asarray(x_sp[ctx._nk : 2 * ctx._nk], dtype=np.float64, copy=False).reshape(ctx._nk)

        lam_p = float(x_sp[2 * ctx._nk])

        # Cache the B_matrix and envelope for the central point and the 10 FD perturbations (dh, dl)

        b_mat_c = re_compute_spline_basis_matrix(re_knots_wavelengths(lam_p), ctx.wls)

        env_c = re_envelope_max_delta_n(ctx.wls, scale=ctx.re_env_s)

        cor_c = self._build_cached_spline_correc(
            ctx,
            dh,
            dl,
            lam_p,
            tk_w_c,
            cached=True,
            b_mat_c=b_mat_c,
            env_c=env_c,
        )

        mse, _, r_c, _ = ctx._mse_grad_accumulate_ep(
            ep_p1, ctx.wt_spectral, False, cor_c, return_residuals=True
        )

        if _cb2a["i"] == 1:
            _n_fd = ctx.n_sp if ctx._fd_1s else (ctx.n_sp * 2)

            logging.info(
                "RE phase 2a  1st TRF eval: 0 thick. analytic, %d FD residual blocks "
                "(%s)  FD_threads=%d",
                _n_fd,
                "forward" if ctx._fd_1s else "centered",
                ctx._fd_nw,
            )

            ctx._emit_re_prog(
                ctx._pct_p2a(ctx.pl, _ki, 0.05),
                "RE phase 2a  first FD objective+grad eval (may take a few s)...",
            )

        J_sp = np.zeros((len(r_c), ctx.n_sp), dtype=np.float64)

        x_c = np.asarray(x_sp, dtype=np.float64, copy=True)

        def _pf_fd_j_res(j: int) -> tuple[int, np.ndarray]:

            hs = ctx._p2fd_lam if j == 2 * ctx._nk else ctx._p2fd_spl

            xp = np.array(x_c, copy=True)
            xp[j] += hs
            cor_p = self._build_cached_spline_correc(
                ctx,
                xp[:ctx._nk],
                xp[ctx._nk : 2 * ctx._nk],
                float(xp[2 * ctx._nk]),
                tk_w_c,
                cached=(j < 2 * ctx._nk),
                b_mat_c=b_mat_c,
                env_c=env_c,
            )

            r_p = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_p, return_residuals=True)[2]

            if ctx._fd_1s:
                return j, (r_p - r_c) / hs

            xm = np.array(x_c, copy=True)
            xm[j] -= hs
            cor_m = self._build_cached_spline_correc(
                ctx,
                xm[:ctx._nk],
                xm[ctx._nk : 2 * ctx._nk],
                float(xm[2 * ctx._nk]),
                tk_w_c,
                cached=(j < 2 * ctx._nk),
                b_mat_c=b_mat_c,
                env_c=env_c,
            )

            r_m = ctx._mse_grad_accumulate_ep(ep_p1, ctx.wt_spectral, False, cor_m, return_residuals=True)[2]

            return j, (r_p - r_m) / (2.0 * hs)

        _nw_sp = min(ctx._fd_nw, ctx.n_sp)

        if _nw_sp <= 1:
            for j in range(ctx.n_sp):
                jj, j_col = _pf_fd_j_res(j)

                J_sp[:, jj] = j_col

        else:
            _ex_pf = _cb2a.get("fd_executor")

            if _ex_pf is None:
                _ex_pf = ThreadPoolExecutor(max_workers=_nw_sp)

                _cb2a["fd_executor"] = _ex_pf

            _f_pf = [_ex_pf.submit(_pf_fd_j_res, j) for j in range(ctx.n_sp)]

            for _fu in as_completed(_f_pf):
                jj, j_col = _fu.result()

                J_sp[:, jj] = j_col

        _cb2a["x"] = x_sp.copy()

        _cb2a["res"] = r_c

        _cb2a["jac"] = J_sp

        _cb2a["mse"] = float(mse)

        now = time.perf_counter()

        if _cb2a["i"] == 1 or (now - _cb2a["last_emit"]) >= 3.0:
            _cb2a["last_emit"] = now

            logging.info(
                "RE phase 2a  TRF iter ~%d (%.1fs since prefit start)",
                _cb2a["i"],
                now - _t_pf,
            )

            _intra_2a = min(
                0.92,
                float(_cb2a["i"]) / float(max(ctx._prefit_max, 1)),
            )

            ctx._emit_re_prog(
                ctx._pct_p2a(ctx.pl, _ki, _intra_2a),
                f"RE phase 2a  iter {_cb2a['i']} TRF spline prefit...",
            )

    def _compute_fun_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:

        self._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))

        return _cb2a["res"]

    def _compute_jac_res_p2a(self, ctx_p2, x_sp: np.ndarray, _cb2a) -> Any:

        self._compute_eval_both_p2a(ctx_p2, x_sp, _cb2a, np.asarray(ctx_p2.ep_p1, dtype=np.float64), int(ctx_p2._p2_ki_slot[0]), float(ctx_p2._t_p2))

        return _cb2a["jac"]


    def _execute_re_phases(self) -> None:
        """Orchestrate RE phases in nominal order."""
        REPhasesService(self).execute_all()

    def _finalize_from_context(self, fin) -> None:
        """Finalization adapter using the context built upstream."""

        _alpha_rank_ref = float(self.cfg.get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

        self._finalize_re_run(
            results=fin.results,
            rmse_initial_sp=fin.rmse_initial_sp,
            rmse_initial_q=fin.rmse_initial_q,
            rmse_initial_u=fin.rmse_initial_u,
            rmse_initial_milestone=fin.rmse_initial_milestone,
            rmse_phase1_milestone=fin.rmse_phase1_milestone,
            rmse_final_milestone=fin.rmse_final_milestone,
            _alpha_slot=fin._alpha_slot,
            _alpha_rank_ref=_alpha_rank_ref,
            re_qwot_alphas=(
                float(fin._a_p1),
                float(fin._a_p2a),
                float(fin._a_p2b),
                float(fin._a_p3),
            ),
            _compute_qwot_rmse_raw=fin._compute_qwot_rmse_raw,
            _compute_qwot_rmse=fin._compute_qwot_rmse,
            _correc_nom=fin._correc_nom,
            _emit_re_spectrum_live=fin._emit_re_spectrum_live,
            _report_t0=fin._re_t0,
            _re_pct_hi=fin._re_pct_hi,
            n_sub_nominal=fin.n_sub_nominal,
            wls=fin.wls,
            lambda_ref=fin.lambda_ref,
            ep0=fin.ep0,
        )

    def _run_re_workflow(self) -> None:
        """Nominal body of the RE thread (without UI error handling)."""
        logger.debug("_run_re_workflow start")
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: building context...")
        _re_t0 = time.perf_counter()
        fin = self._build_re_run_context(_re_t0)
        logger.debug("_run_re_workflow context built")
        self.signals.progress.emit(1, f"[DBG] _run_re_workflow: context OK in {time.perf_counter()-_re_t0:.2f}s, executing phases...")
        self._execute_re_phases()
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: phases done, finalizing...")
        self._finalize_from_context(fin)
        self.signals.progress.emit(1, "[DBG] _run_re_workflow: finished.")

    def run(self) -> None:
        logger.info("RE worker run started")
        self.signals.progress.emit(1, "[DBG] REWorker.run(): thread started")
        try:
            self._run_re_workflow()
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("RE worker run failed: %s", e)
            self.signals.progress.emit(1, f"[DBG] REWorker.run() EXCEPTION: {e}")
            self.signals.error.emit(tb)
            self.signals.finished.emit(REResultsPayloadBuilder.build_error_payload(self.cfg.get("ep0")))

    def _get_phase4_aperture_bounds(self) -> tuple[float, float]:
        """Return validated beam aperture bounds for phase 4."""
        lo_ap, hi_ap = RE_P4_BEAM_AP_BOUNDS_DEG
        apb_cfg = self.cfg.get("re_phase4_ap_bounds_deg")
        if apb_cfg is not None:
            vb = np.asarray(apb_cfg, dtype=np.float64).ravel()
            if vb.size >= 2:
                c0, c1 = float(vb[0]), float(vb[1])
                if 0.0 < c0 < c1 < 90.0:
                    lo_ap, hi_ap = c0, c1
        return lo_ap, hi_ap

    def _run_phase4_aperture_scan(
        self,
        *,
        _emit_re_prog: Callable,
        _nap: int,
        _lo_ap: float,
        _hi_ap: float,
        _n_ap_scan: int,
        x0_base: np.ndarray,
        _eval_both_p2: Callable,
        _cb2_ref: list,
        _re_state: dict,
        _report_mse_spectral: Callable,
        _cor_base: tuple,
        ep_p4: np.ndarray,
        _kn_log: np.ndarray,
        _wmin_obj: float,
        _wmax_obj: float,
    ) -> tuple[list[tuple[float, float]], float, float, float, int, float]:
        """Run the aperture scan phase 4 logic."""
        _emit_re_prog(
            98.5,
            f"RE phase 4: scalar ap scan ({_n_ap_scan} pts, "
            f"{_lo_ap} to {_hi_ap} deg): same ap on all {_nap} lambda knots per trial "
            f"(flat beam during scan; joint TRF -> indep. ap per lambda knot)",
        )

        logging.info(
            "RE phase 4: during **scan**, a single ap is set at a time, "
            "replicated over all %d lambda knots (no chromatic steps at this stage).",
            _nap,
        )

        best_ap = 1.0
        best_ls_sq = float("inf")
        _p4_scan_emit = 1.0e9
        _p4_scan_trace: list[tuple[float, float]] = []
        _p4_cb_i_before_scan = int(_cb2_ref[0]["i"])
        _t_p4_scan_wall = time.perf_counter()

        for test_ap in np.linspace(_lo_ap, _hi_ap, _n_ap_scan):
            if self._stop:
                break
            _ta = float(test_ap)
            _re_state["re_aperture_knots"][:] = _ta
            _eval_both_p2(x0_base, emit_interval=_p4_scan_emit)
            _r_sc = _cb2_ref[0]["res"]
            _cost_sc = float(np.dot(_r_sc, _r_sc))
            _p4_scan_trace.append((_ta, _cost_sc))
            logging.debug(
                "RE phase 4 scan step | ap_deg=%.2f | ||r||^2=%.8g | n_res=%d",
                _ta,
                _cost_sc,
                int(_r_sc.size),
            )
            if _cost_sc < best_ls_sq:
                best_ls_sq = _cost_sc
                best_ap = _ta

        _re_state["re_aperture_knots"][:] = best_ap
        _eval_both_p2(x0_base, emit_interval=_p4_scan_emit)
        best_rmse_ap = float(np.sqrt(max(_report_mse_spectral(ep_p4, _cor_base), 0.0)))
        _p4_scan_wall_s = float(time.perf_counter() - _t_p4_scan_wall)
        _p4_scan_mse_evals = int(_cb2_ref[0]["i"]) - _p4_cb_i_before_scan

        logging.info(
            "RE phase 4 scan profile | wall_s=%.4f | MSE_ep_delta=%d | "
            "scan_steps=%d | s_per_MSE_ep%.5f | opt: re_phase4_aperture_scan_points "
            "ou snap grille / warm cache",
            _p4_scan_wall_s,
            _p4_scan_mse_evals,
            len(_p4_scan_trace),
            _p4_scan_wall_s / max(_p4_scan_mse_evals, 1),
        )

        if _p4_scan_trace:
            _costs = [c for _, c in _p4_scan_trace]
            _worst_ls = float(max(_costs))
            _spread = _worst_ls - float(best_ls_sq)

            logging.info(
                "RE phase 4 scan summary | n_steps=%d | best_ap_deg=%.2f | "
                "min||r||^2=%.8g | max||r||^2=%.8g | spread=%.8g | "
                "RMSE_sp(at_best)~%.6f | tune: re_phase4_aperture_scan_points bounds RE_P4_BEAM_AP_BOUNDS_DEG",
                len(_p4_scan_trace),
                best_ap,
                best_ls_sq,
                _worst_ls,
                _spread,
                best_rmse_ap,
            )

            logging.info(
                "RE phase 4 scan best plateaus (explicit): %s",
                _re_p4_ap_band_intervals_str(
                    _kn_log,
                    np.full(_nap, float(best_ap), dtype=np.float64),
                    _wmin_obj,
                    _wmax_obj,
                ),
            )

            logging.debug(
                "RE phase 4 scan detail | " + " | ".join(f"ap={a:.2f}||r||2={c:.6g}" for a, c in _p4_scan_trace)
            )

        return _p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap

    def _get_phase4_scan_inputs(self, x0_base: np.ndarray, _nap: int, _ap_gui: float, wls: np.ndarray, oblique_config_meta: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float], list[float], str]:
        """Build derived phase-4 scan inputs and diagnostics."""
        _kn_log = np.asarray(self._re_phase_ns._re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[:_nap]
        _p4_hi_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) >= 10.0})
        _p4_lo_ang = sorted({float(m["angle"]) for m in oblique_config_meta if float(m["angle"]) < 10.0})
        _kn_sorted_cfg = np.sort(np.asarray(_kn_log, dtype=np.float64).ravel().copy())
        _p4_band_thr = np.array([0.5 * (_kn_sorted_cfg[i] + _kn_sorted_cfg[i + 1]) for i in range(_nap - 1)], dtype=np.float64)
        _p4_scan_plateaus_s = _re_p4_ap_band_intervals_str(
            _kn_log,
            np.full(_nap, float(_ap_gui), dtype=np.float64),
            float(np.min(wls)),
            float(np.max(wls)),
        )
        return _kn_log, _p4_band_thr, _p4_scan_plateaus_s, _p4_hi_ang, _p4_lo_ang, repr(self.cfg.get("re_p4_beam_ap_knots_nm"))



    def _build_phase4_result(
        self,
        *,
        ep_f: np.ndarray,
        dh_v: np.ndarray,
        dl_v: np.ndarray,
        lam_v: float,
        th_v: np.ndarray | None,
        nfev_extra: int,
        p4_label_suffix: str,
        success: bool,
        best_res_dto: REPhase4Result,
        _use_sub_c3: bool,
        _report_mse_spectral,
        _compute_qwot_rmse,
        _rmse_combined,
        _re_state: dict[str, Any],
        wls: np.ndarray,
        _wmin_obj: float,
        _wmax_obj: float,
    ) -> tuple[REPhase4Result, float]:
        b_mc = re_compute_spline_basis_matrix(re_knots_wavelengths(lam_v), wls)
        env_c = re_envelope_max_delta_n(wls, scale=self._re_phase_ns.re_env_s)
        tk_mc = re_compute_tikhonov_weights(re_knots_wavelengths(lam_v), wls)

        if _use_sub_c3 and th_v is not None:
            cor_p4 = (
                "spline_cached_sub3",
                dh_v,
                dl_v,
                lam_v,
                b_mc,
                env_c,
                tk_mc,
                float(th_v[0]),
                float(th_v[1]),
                float(th_v[2]),
            )
        else:
            cor_p4 = (
                "spline_cached",
                dh_v,
                dl_v,
                lam_v,
                b_mc,
                env_c,
                tk_mc,
            )

        rmse_p4_sp = float(np.sqrt(max(_report_mse_spectral(ep_f, cor_p4), 0.0)))
        rmse_qwot_p4 = _compute_qwot_rmse(ep_f, cor_p4)
        rmse_comb_p4 = _rmse_combined(rmse_p4_sp, rmse_qwot_p4)

        _ak4 = np.asarray(_re_state["re_aperture_knots"], dtype=np.float64).ravel()[: int(RE_P4_BEAM_N_KNOTS)]
        _kn4 = np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[: int(RE_P4_BEAM_N_KNOTS)]

        logging.info(
            "RE phase 4 result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | "
            "ap_deg(n knots)=%s | knots_lam_nm=%s | label=%s | "
            "tune: re_envelope_scale re_qwot_penalty_weight alpha schedule",
            rmse_comb_p4,
            rmse_p4_sp,
            rmse_qwot_p4,
            np.array2string(_ak4, precision=2, separator=","),
            np.array2string(_kn4, precision=2, separator=","),
            p4_label_suffix,
        )

        logging.info(
            "RE phase 4 plateaus (result explicit): %s",
            _re_p4_ap_band_intervals_str(_kn4, _ak4, _wmin_obj, _wmax_obj),
        )

        phase4_result = REPhase4Result(
            label=RE_RESULT_LABEL_WITH_DRIFT + f" ({p4_label_suffix})",
            ep=np.asarray(ep_f, dtype=np.float64).flatten(),
            a=0.0,
            b=0.0,
            f=0.0,
            re_dh_knots=np.asarray(dh_v, dtype=np.float64).flatten(),
            re_dl_knots=np.asarray(dl_v, dtype=np.float64).flatten(),
            re_knots_nm=np.asarray(re_knots_wavelengths(lam_v), dtype=np.float64).flatten(),
            re_spline_lam_node2_nm=float(lam_v),
            rmse=float(rmse_p4_sp),
            rmse_qwot=float(rmse_qwot_p4),
            rmse_combined=float(rmse_comb_p4),
            nfev=int(best_res_dto.nfev) + int(nfev_extra),
            success=bool(success),
            nfev_phase1=int(best_res_dto.nfev_phase1),
            nfev_phase2_prefit=int(best_res_dto.nfev_phase2_prefit),
            re_p4_aperture_deg=float(np.mean(_ak4)),
            re_p4_beam_ap_knots_nm=np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64).ravel()[: int(RE_P4_BEAM_N_KNOTS)],
            re_p4_beam_ap_knots_deg=np.asarray(_ak4, dtype=np.float64).flatten(),
            re_sub_cauchy_a0=float(th_v[0]) if (_use_sub_c3 and th_v is not None) else None,
            re_sub_cauchy_a1=float(th_v[1]) if (_use_sub_c3 and th_v is not None) else None,
            re_sub_cauchy_a2=float(th_v[2]) if (_use_sub_c3 and th_v is not None) else None,
        )
        return phase4_result, rmse_comb_p4

    def _execute_phase4_beam(self) -> None:
        """Phase 4: beam aperture (stepped ap over lambda), scan + joint TRF."""

        L = self._re_phase_ns

        results = L.results

        _p2_ctx = L._p2_ctx

        _use_sub_c3 = bool(L._use_sub_c3_shared)

        if not _p2_ctx:
            logging.warning("RE phase 4 skipped: phase-2 context unavailable.")

            return

        _nk = int(_p2_ctx["_nk"])

        i0 = int(_p2_ctx["i0"])

        i_lam = int(_p2_ctx["i_lam"])

        i_cu = i_lam + 1

        _cb2_ref = _p2_ctx["_cb2_ref"]

        _p2_ki_slot = _p2_ctx["_p2_ki_slot"]

        _p2_trf_log_tag = _p2_ctx["_p2_trf_log_tag"]

        _eval_both_p2 = _p2_ctx["_eval_both_p2"]

        _fun_res_p2 = _p2_ctx["_fun_res_p2"]


        bounds_p2_trf = _p2_ctx["bounds_p2_trf"]

        oblique_config_meta = L.oblique_config_meta

        _re_state = L._re_state

        _emit_re_prog = L._emit_re_prog

        _re_use_staged_order = L._re_use_staged_order

        _correc_nom = L._correc_nom

        n_layers_count = L.n_layers_count

        wls = L.wls

        _ap_gui = L._ap_gui

        rmse_final_milestone = L.rmse_final_milestone



        _report_mse_spectral = L._report_mse_spectral

        _compute_qwot_rmse = L._compute_qwot_rmse

        _rmse_combined = L._rmse_combined

        re_env_s = L.re_env_s

        # --- Phase 4: R/T average at theta +/- ap/2 (ap = total angular width); 1D scan + short joint TRF ---

        _has_high_angle = any(float(meta["angle"]) >= 10.0 for meta in oblique_config_meta)

        _p4_best_seen_rmse: float | None = None

        if results and not self._stop:
            best_res = results[0]
            best_res_dto = REPhase4Result.from_legacy_dict(best_res)

            ep_p4 = np.asarray(best_res_dto.ep, dtype=np.float64)

            _x0_p4 = [ep_p4]

            if best_res_dto.re_dh_knots.size > 0:
                _x0_p4.append(np.asarray(best_res_dto.re_dh_knots, dtype=np.float64))

                _x0_p4.append(np.asarray(best_res_dto.re_dl_knots, dtype=np.float64))

                _x0_p4.append(np.array([best_res_dto.re_spline_lam_node2_nm], dtype=np.float64))

                if _use_sub_c3 and best_res_dto.re_sub_cauchy_a0 is not None:
                    _x0_p4.append(
                        np.array(
                            [
                                best_res_dto.re_sub_cauchy_a0,
                                best_res_dto.re_sub_cauchy_a1,
                                best_res_dto.re_sub_cauchy_a2,
                            ],
                            dtype=np.float64,
                        )
                    )

            if _has_high_angle and len(_x0_p4) > 1:
                _t_p4_wall = time.perf_counter()

                _emit_re_prog(
                    98.0,
                    (
                        f"RE step 3/3: full joint optimization + beam (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots)"
                        if _re_use_staged_order
                        else f"RE phase 4: beam aperture (stepped ap, {int(RE_P4_BEAM_N_KNOTS)} lambda knots) - re_phase4_* cfg"
                    ),
                )

                _re_state["is_phase4"] = True

                _re_state["p4_prof"] = {
                    "phy_wall_s": 0.0,
                    "phi_calls": 0,
                    "band_groups": 0,
                    "band_mask_steps": 0,
                    "meta_p4_count": 0,
                    "n_wls_union_max": 0,
                }

                _p4_scan_wall_s = 0.0

                _p4_trf_wall_s = 0.0

                _p4_scan_mse_evals = 0

                _p4_trf_mse_evals = 0

                x0_base = np.concatenate(_x0_p4)

                _cor_base = (
                    p2_result_to_correc_tuple(best_res, _use_sub_c3)
                    if best_res.get("re_dH_knots") is not None
                    else _correc_nom
                )

                _n_ap_scan = max(
                    4,
                    int(
                        self.cfg.get(
                            "re_phase4_aperture_scan_points",
                            RE_PHASE4_APERTURE_SCAN_POINTS,
                        )
                    ),
                )

                _lo_ap, _hi_ap = self._get_phase4_aperture_bounds()

                _p4_trf_nfev = int(self.cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))

                _p4_tol = float(self.cfg.get("re_phase4_trf_tol_factor", RE_PHASE4_TRF_TOL_FACTOR))

                _p4_fd_ap = float(self.cfg.get("re_p4_ap_fd_step_deg", RE_P4_AP_FD_STEP_DEG))

                _nap = int(RE_P4_BEAM_N_KNOTS)

                _kn_log, _p4_band_thr, _p4_scan_plateaus_s, _p4_hi_ang, _p4_lo_ang, _p4_cfg_knm = self._get_phase4_scan_inputs(
                    x0_base,
                    _nap,
                    _ap_gui,
                    wls,
                    oblique_config_meta,
                )

                _p4_ft_eff = float(RE_LBFGSB_FTOL) * _p4_tol

                _p4_gt_eff = float(RE_LBFGSB_GTOL) * _p4_tol

                _p4_band_thr_s = np.array2string(_p4_band_thr, precision=2, separator=",")

                _wmin_obj = float(np.min(wls))

                _wmax_obj = float(np.max(wls))

                logging.info(
                    "RE phase 4 config | wall_t0=same_block | n_wls_obj=%d "
                    "lambda_nm[min,max]=[%.2f,%.2f] | physics_groups=%d "
                    "angles_ge_10deg=%s | "
                    "knots_lam_nm(sorted_display)=%s | cfg_re_p4_beam_ap_knots_nm=%s | "
                    "band_fastpath_n=%d lambda_thresholds_nm=%s (paliers ap / bande) | "
                    "ap_bounds_deg=[%.4f,%.4f] | scan_grid=linspace_n=%d | "
                    "trf_max_nfev=%d | trf_tol_factor=%.4g -> ftol~%.3g xtol~%.3g gtol~%.3g | "
                    "ap_fd_step_deg=%.5g | joint_nvar=%d (n_layers=%d spline_block=%d sub_cauchy3=%s) | "
                    "re_beam_aperture_deg_init(cfg)=%.4f",
                    int(wls.size),
                    float(np.min(wls)),
                    float(np.max(wls)),
                    len(oblique_config_meta),
                    _p4_hi_ang,
                    np.array2string(_kn_log, precision=2, separator=","),
                    repr(_p4_cfg_knm),
                    _nap,
                    _p4_band_thr_s,
                    _lo_ap,
                    _hi_ap,
                    _n_ap_scan,
                    _p4_trf_nfev,
                    _p4_tol,
                    _p4_ft_eff,
                    _p4_ft_eff,
                    _p4_gt_eff,
                    _p4_fd_ap,
                    len(x0_base),
                    n_layers_count,
                    int(len(x0_base) - n_layers_count),
                    _use_sub_c3,
                    float(
                        self.cfg.get(
                            "re_beam_aperture_deg",
                            RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
                        )
                    ),
                )

                logging.info(
                    "RE phase 4 plateaus (scan grid, lambda intervals): %s",
                    _p4_scan_plateaus_s,
                )

                if _p4_lo_ang:
                    logging.info(
                        "RE phase 4 angle policy | P4 applied only for angles >=10: %s | "
                        "angles <10 kept without beam aperture averaging: %s",
                        _p4_hi_ang,
                        _p4_lo_ang,
                    )

                logging.info(
                    "RE phase 4 cost model | grep  P4 profile  +  P4 scan profile  +  TRF profile  "
                    "| one full MSE_ep: physics_groups × P4_block; P4_block (stepped lambda) <= %d bands "
                    "× (1 or 2) analytical oblique calls on lambda sub-grids | "
                    "scan: ~(n_scan+1) MSE_ep | TRF: each nfev LS = 1 residual; each jac ap = "
                    "1 MSE + %d FD(ap) + 1 restore (see SciPy njev)",
                    _nap,
                    _nap,
                )

                _p4_scan_trace, best_ap, best_ls_sq, _p4_scan_wall_s, _p4_scan_mse_evals, best_rmse_ap = self._run_phase4_aperture_scan(
                    _emit_re_prog=_emit_re_prog,
                    _nap=_nap,
                    _lo_ap=_lo_ap,
                    _hi_ap=_hi_ap,
                    _n_ap_scan=_n_ap_scan,
                    x0_base=x0_base,
                    _eval_both_p2=_eval_both_p2,
                    _cb2_ref=_cb2_ref,
                    _re_state=_re_state,
                    _report_mse_spectral=_report_mse_spectral,
                    _cor_base=_cor_base,
                    ep_p4=ep_p4,
                    _kn_log=_kn_log,
                    _wmin_obj=_wmin_obj,
                    _wmax_obj=_wmax_obj,
                )

                def _insert_p4_result(
                    *,
                    ep_f: np.ndarray,
                    dh_v: np.ndarray,
                    dl_v: np.ndarray,
                    lam_v: float,
                    th_v: np.ndarray | None,
                    nfev_extra: int,
                    p4_label_suffix: str,
                    success: bool,
                ) -> None:
                    phase4_result, rmse_comb_p4 = self._build_phase4_result(
                        ep_f=ep_f,
                        dh_v=dh_v,
                        dl_v=dl_v,
                        lam_v=lam_v,
                        th_v=th_v,
                        nfev_extra=nfev_extra,
                        p4_label_suffix=p4_label_suffix,
                        success=success,
                        best_res_dto=best_res_dto,
                        _use_sub_c3=_use_sub_c3,
                        _report_mse_spectral=_report_mse_spectral,
                        _compute_qwot_rmse=_compute_qwot_rmse,
                        _rmse_combined=_rmse_combined,
                        _re_state=_re_state,
                        wls=wls,
                        _wmin_obj=_wmin_obj,
                        _wmax_obj=_wmax_obj,
                    )
                    _prepend_result_dto(results, phase4_result)
                    rmse_final_milestone[0] = float(rmse_comb_p4)

                _p4_trf_wall_s, _p4_trf_mse_evals, _p4_best_seen_rmse = self._run_phase4_joint_trf(
                    p4_trf_nfev=_p4_trf_nfev,
                    nap=_nap,
                    x0_base=x0_base,
                    best_ap=best_ap,
                    lo_ap=_lo_ap,
                    hi_ap=_hi_ap,
                    bounds_p2_trf=bounds_p2_trf,
                    p4_fd_ap=_p4_fd_ap,
                    p4_tol=_p4_tol,
                    i0=i0,
                    i_lam=i_lam,
                    i_cu=i_cu,
                    nk=_nk,
                    n_layers_count=n_layers_count,
                    use_sub_c3=_use_sub_c3,
                    kn_log=_kn_log,
                    wmin_obj=_wmin_obj,
                    wmax_obj=_wmax_obj,
                    fun_res_p2=_fun_res_p2,
                    eval_both_p2=_eval_both_p2,
                    cb2_ref=_cb2_ref,
                    re_state=_re_state,
                    p2_trf_log_tag=_p2_trf_log_tag,
                    p2_ki_slot=_p2_ki_slot,
                    insert_p4_result=_insert_p4_result,
                    results=results,
                )

                if not self._stop:
                    logging.info(
                        "RE phase 4: joint TRF disabled | re_phase4_trf_max_nfev=0  "
                        "scan-only (raise max_nfev to polish ap knots + thickness+splines jointly)"
                    )

                    rmse_q_scan = _compute_qwot_rmse(ep_p4, _cor_base)

                    rmse_c_scan = _rmse_combined(float(best_rmse_ap), rmse_q_scan)

                    _sk = np.asarray(_re_state["re_aperture_knots"], dtype=np.float64).ravel()[
                        : int(RE_P4_BEAM_N_KNOTS)
                    ]

                    _skn = np.asarray(_re_state["re_p4_beam_knots_lam_nm"], dtype=float).ravel()[
                        : int(RE_P4_BEAM_N_KNOTS)
                    ]

                    logging.info(
                        "RE phase 4 scan-only result | RMSE_sum=%.6f RMSE_sp=%.6f RMSE_qwot=%.6f | "
                        "min||r||^2(scan)=%.8g | ap_deg(n knots)=%s | knots_lam_nm=%s",
                        rmse_c_scan,
                        float(best_rmse_ap),
                        rmse_q_scan,
                        float(best_ls_sq),
                        np.array2string(_sk, precision=2, separator=","),
                        np.array2string(_skn, precision=2, separator=","),
                    )

                    logging.info(
                        "RE phase 4 scan-only plateaus (explicit): %s",
                        _re_p4_ap_band_intervals_str(
                            _skn,
                            _sk,
                            _wmin_obj,
                            _wmax_obj,
                        ),
                    )

                    phase4_scan = REPhase4Result.from_legacy_dict(best_res)
                    phase4_scan = REPhase4Result(
                        label=RE_RESULT_LABEL_WITH_DRIFT + " (P4 aperture scan)",
                        ep=phase4_scan.ep,
                        a=phase4_scan.a,
                        b=phase4_scan.b,
                        f=phase4_scan.f,
                        re_dh_knots=phase4_scan.re_dh_knots,
                        re_dl_knots=phase4_scan.re_dl_knots,
                        re_knots_nm=phase4_scan.re_knots_nm,
                        re_spline_lam_node2_nm=phase4_scan.re_spline_lam_node2_nm,
                        rmse=float(best_rmse_ap),
                        rmse_qwot=float(rmse_q_scan),
                        rmse_combined=float(rmse_c_scan),
                        nfev=phase4_scan.nfev,
                        success=True,
                        nfev_phase1=phase4_scan.nfev_phase1,
                        nfev_phase2_prefit=phase4_scan.nfev_phase2_prefit,
                        re_p4_aperture_deg=float(np.mean(_sk)),
                        re_p4_beam_ap_knots_nm=np.asarray(
                            _re_state["re_p4_beam_knots_lam_nm"], dtype=np.float64
                        ).ravel()[: int(RE_P4_BEAM_N_KNOTS)],
                        re_p4_beam_ap_knots_deg=np.asarray(_sk, dtype=np.float64).flatten(),
                        re_sub_cauchy_a0=phase4_scan.re_sub_cauchy_a0,
                        re_sub_cauchy_a1=phase4_scan.re_sub_cauchy_a1,
                        re_sub_cauchy_a2=phase4_scan.re_sub_cauchy_a2,
                    )
                    _prepend_result_dto(results, phase4_scan)

                    rmse_final_milestone[0] = float(rmse_c_scan)

                _re_state["is_phase4"] = False

                _pp_fin = _re_state.get("p4_prof")

                _wall_p4_tot = float(time.perf_counter() - _t_p4_wall)

                if _pp_fin is not None:
                    logging.info(
                        "RE phase 4 P4 profile (in each MSE_ep, blocks >= 10, lambda-stepped ap) - "
                        "inner_physics_wall_s=%.4f | oblique_phi_calls=%d | "
                        "meta_passes=%d | n_wls_union_max=%d | "
                        "band_groups=%d band_mask_steps=%d | "
                        "<=%d -calls/group (2×%d lambda knots); "
                        "vectorizing by band reduces Python overhead",
                        float(_pp_fin.get("phy_wall_s", 0.0)),
                        int(_pp_fin.get("phi_calls", 0)),
                        int(_pp_fin.get("meta_p4_count", 0)),
                        int(_pp_fin.get("n_wls_union_max", 0)),
                        int(_pp_fin.get("band_groups", 0)),
                        int(_pp_fin.get("band_mask_steps", 0)),
                        2 * int(RE_P4_BEAM_N_KNOTS),
                        int(RE_P4_BEAM_N_KNOTS),
                    )

                logging.info(
                    "RE phase 4 wall | total=%.3fs | scan=%.3fs | TRF=%.3fs | "
                    "overheadmax(0,total-scan-TRF-inner_physics) | "
                    "grep  RE phase 4  /  P4 profile  to retune cfg & code",
                    _wall_p4_tot,
                    float(_p4_scan_wall_s),
                    float(_p4_trf_wall_s),
                )

                _re_state["p4_prof"] = None

            elif _has_high_angle:
                logging.info(
                    "RE phase 4 skipped | reason=no_spline_state_on_best | "
                    "need re_dH_knots/re_dL_knots on results[0] (phase 2 splines)"
                )

                _emit_re_prog(
                    99.0,
                    "RE phase 4  skipped (no Delta Re splines on best candidate)",
                )

            else:
                logging.info(
                    "RE phase 4 skipped | reason=all_angles_below_10deg | beam average not applied for low incidence"
                )

                _emit_re_prog(99.0, "RE phase 4  skipped (all angles < 10 deg)")

            _emit_re_prog(99.0, "RE phase 4  done")

class REPhasesService:
    """Thin service layer to orchestrate RE worker phases."""

    def __init__(
        self,
        worker: REWorker,
        steps: list["REPhaseStep"] | None = None,
        state_service: "REPhaseStateService | None" = None,
    ) -> None:
        self._worker = worker
        self._state_service = state_service or REPhaseStateService()
        self._steps = steps or [
            REPhase1Step(),
            REPhase1P4ScanStep(),
            REPhase2Step(),
            REPhase3Step(),
            REPhase4Step(),
        ]

    def execute_phase1(self) -> None:
        w = self._worker
        w._re_phase_ns.results[:] = w._execute_phase1()

    def execute_phase1_p4_scan(self) -> None:
        self._worker._execute_phase1_p4_scan()

    def execute_phase2(self) -> None:
        w = self._worker
        self._state_service.prepare_phase2_state(w)
        w._execute_phase2_splines()

    def execute_phase3(self) -> None:
        self._worker._execute_phase3_shakes()

    def execute_phase4(self) -> None:
        self._worker._execute_phase4_beam()

    def execute_all(self) -> None:
        for step in self._steps:
            step.run(self)

class REPhaseStep(Protocol):
    """Contract for one executable RE phase step."""

    def run(self, service: REPhasesService) -> None: ...

class REPhaseStateService:
    """State transitions extracted from worker for phase orchestration."""

    def prepare_phase2_state(self, worker: REWorker) -> None:
        worker._re_phase_ns._re_state["is_phase4"] = False
        worker._re_phase_ns._use_sub_c3_shared = False
        worker._re_phase_ns._p2_ctx = {}

class REPhase1Step:
    def run(self, service: REPhasesService) -> None:
        service.execute_phase1()

class REPhase1P4ScanStep:
    def run(self, service: REPhasesService) -> None:
        service.execute_phase1_p4_scan()

class REPhase2Step:
    def run(self, service: REPhasesService) -> None:
        service.execute_phase2()

class REPhase3Step:
    def run(self, service: REPhasesService) -> None:
        service.execute_phase3()

class REPhase4Step:
    def run(self, service: REPhasesService) -> None:
        service.execute_phase4()




# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# =============================================================================

# MAIN APPLICATION

# =============================================================================