"""Dedicated RE results builder facade for incremental ARCH-1 decoupling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from certus.workers.certus_re_worker_utils import (
    REResultsBuilder as _LegacyREResultsBuilder,
    re_result_dict_stop_before_first_trf,
)


@dataclass(frozen=True)
class REResultsBuilder:
    """RE results payload builder boundary (delegates to legacy implementation)."""

    @staticmethod
    def build_finished_payload(
        *,
        results: list[dict[str, Any]],
        ep0: np.ndarray,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        stopped_by_user: bool = False,
        re_qwot_alphas: tuple[float, float, float, float] | None = None,
    ) -> dict[str, Any]:
        return _LegacyREResultsBuilder.build_finished_payload(
            results=results,
            ep0=ep0,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=stopped_by_user,
            re_qwot_alphas=re_qwot_alphas,
        )

    @staticmethod
    def build_error_payload(ep0: list[float] | None) -> dict[str, Any]:
        return _LegacyREResultsBuilder.build_error_payload(ep0)

    @staticmethod
    def ensure_results_and_top(
        *,
        results: list[dict[str, Any]],
        stop_requested: bool,
        cfg_ep0: Any,
        rmse_initial_sp: float,
        rmse_initial_q: float,
        rmse_initial_u: float,
    ) -> dict[str, Any] | None:
        """Ensure a fallback stop result exists and return top legacy result."""
        if not results and stop_requested:
            ep0_stop = np.asarray(cfg_ep0, dtype=np.float64).flatten()
            results.append(
                re_result_dict_stop_before_first_trf(
                    ep0_stop,
                    rmse_initial_sp=rmse_initial_sp,
                    rmse_initial_q=rmse_initial_q,
                    rmse_initial_u=rmse_initial_u,
                )
            )
        return results[0] if results else None

    @staticmethod
    def sort_enrich_and_top(
        *,
        results: list[dict[str, Any]],
        alpha_rank_ref: float,
        compute_qwot_rmse_raw: Callable[..., float],
        sort_results: Callable[[list[dict[str, Any]]], None],
        enrich_results: Callable[..., None],
    ) -> dict[str, Any] | None:
        """Sort final results, enrich ranking fields, and return top result."""
        sort_results(results)
        if results:
            enrich_results(
                results,
                alpha_rank_ref=alpha_rank_ref,
                compute_qwot_rmse_raw=compute_qwot_rmse_raw,
            )
            return results[0]
        return None

    @staticmethod
    def finalize_reconcile_top(
        *,
        results: list[dict[str, Any]],
        stop_requested: bool,
        cfg_ep0: Any,
        rmse_initial_sp: float,
        rmse_initial_q: float,
        rmse_initial_u: float,
        alpha_rank_ref: float,
        compute_qwot_rmse_raw: Callable[..., float],
        sort_results: Callable[[list[dict[str, Any]]], None],
        enrich_results: Callable[..., None],
    ) -> dict[str, Any] | None:
        """Stop fallback, then sort/enrich: single entry point for final top result."""
        early_top = REResultsBuilder.ensure_results_and_top(
            results=results,
            stop_requested=stop_requested,
            cfg_ep0=cfg_ep0,
            rmse_initial_sp=rmse_initial_sp,
            rmse_initial_q=rmse_initial_q,
            rmse_initial_u=rmse_initial_u,
        )
        after_sort = REResultsBuilder.sort_enrich_and_top(
            results=results,
            alpha_rank_ref=alpha_rank_ref,
            compute_qwot_rmse_raw=compute_qwot_rmse_raw,
            sort_results=sort_results,
            enrich_results=enrich_results,
        )
        return after_sort if after_sort is not None else early_top

    @staticmethod
    def top_metrics(top_result: dict[str, Any] | None) -> dict[str, float]:
        """Compute final scalar metrics from the top legacy result payload."""
        if top_result is None:
            nan = float("nan")
            return {
                "best_sp": nan,
                "best_ot": nan,
                "best_combined": nan,
                "rmse_final_u": nan,
            }

        best_sp = float(top_result.get("rmse", float("nan")))
        best_ot = float(top_result.get("rmse_qwot", float("nan")))
        best_combined = float(top_result.get("rmse_combined", float("nan")))
        return {
            "best_sp": best_sp,
            "best_ot": best_ot,
            "best_combined": best_combined,
            "rmse_final_u": best_combined,
        }

    @staticmethod
    def final_diagnostic_payload(
        *,
        best_sp: float,
        best_ot: float,
        alpha_current: float,
        alpha_gui: float,
        rmse_final_u: float,
        rmse_initial_u: float,
        rmse_initial_sp: float,
        rmse_initial_q: float,
    ) -> dict[str, float]:
        """Normalize final diagnostic scalars used by RE finalize logs."""
        ot_fin = float(best_ot) if np.isfinite(float(best_ot)) else 0.0
        return {
            "best_sp": float(best_sp),
            "ot_fin": ot_fin,
            "alpha_current": float(alpha_current),
            "alpha_gui": float(alpha_gui),
            "delta_rmse": float(rmse_final_u) - float(rmse_initial_u),
            "delta_sp": float(best_sp) - float(rmse_initial_sp),
            "delta_qwot": ot_fin - float(rmse_initial_q),
        }

    @staticmethod
    def cauchy_barrier_diagnostic_payload(
        *,
        top_result: dict[str, Any] | None,
        wls: np.ndarray,
        lambda_ref: float,
        n_sub_nominal: np.ndarray,
        barrier_sqrt_w: float,
        tube_delta: float,
        substrate_phi_matrix: Callable[[np.ndarray, float], np.ndarray],
        barrier_residuals_jac: Callable[..., tuple[np.ndarray, Any]],
    ) -> dict[str, float | int] | None:
        """Compute substrate Cauchy barrier diagnostics, if coefficients exist."""
        if top_result is None:
            return None
        a0 = top_result.get("re_sub_cauchy_a0")
        a1 = top_result.get("re_sub_cauchy_a1")
        a2 = top_result.get("re_sub_cauchy_a2")
        if a0 is None or a1 is None or a2 is None:
            return None

        th_f = np.array([float(a0), float(a1), float(a2)], dtype=np.float64)
        phi_f = substrate_phi_matrix(wls, float(lambda_ref))
        ntab_f = np.real(np.asarray(n_sub_nominal, dtype=np.complex128)).astype(np.float64).ravel()
        rbf, _ = barrier_residuals_jac(th_f, phi_f, ntab_f, sqrt_w=float(barrier_sqrt_w))
        n_active = int(np.sum(np.abs(rbf) > 1e-14))
        return {
            "res_norm": float(np.linalg.norm(rbf)),
            "n_active": n_active,
            "n_total": int(len(rbf)),
            "tube_delta": float(tube_delta),
        }

    @staticmethod
    def finalize_message_bundle(
        *,
        results: list[dict[str, Any]],
        top_result: dict[str, Any] | None,
        alpha_rank_ref: float,
        elapsed_s: float,
        best_sp: float,
        best_ot: float,
        best_combined: float,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        stopped_by_user: bool,
        ranking_log_suffix: Callable[[dict[str, Any], float], str],
        finished_main_log_line: Callable[[float, float, float, float, str, int], str],
        rmse_milestone_log_line: Callable[[list[float], list[float], list[float]], str],
        progress_message_done: Callable[..., str],
    ) -> dict[str, str]:
        """Build all final RE log/progress messages in one place."""
        rank_line = (
            ranking_log_suffix(top_result, alpha_rank_ref) if top_result is not None and len(results) > 0 else ""
        )
        return {
            "rank_line": rank_line,
            "finished_main_log": finished_main_log_line(
                elapsed_s,
                best_sp,
                best_ot,
                best_combined,
                rank_line,
                len(results),
            ),
            "rmse_milestone_log": rmse_milestone_log_line(
                rmse_initial_milestone,
                rmse_phase1_milestone,
                rmse_final_milestone,
            ),
            "progress_done": progress_message_done(
                stopped_by_user=stopped_by_user,
                elapsed_s=elapsed_s,
                best_sp=best_sp,
                best_ot=best_ot,
                best_combined=best_combined,
            ),
        }

    @staticmethod
    def finalize_tail_bundle(
        *,
        results: list[dict[str, Any]],
        top_result: dict[str, Any] | None,
        ep0: np.ndarray,
        alpha_rank_ref: float,
        elapsed_s: float,
        best_sp: float,
        best_ot: float,
        best_combined: float,
        rmse_initial_milestone: list[float],
        rmse_phase1_milestone: list[float],
        rmse_final_milestone: list[float],
        stopped_by_user: bool,
        re_qwot_alphas: tuple[float, float, float, float] | None,
        ranking_log_suffix: Callable[[dict[str, Any], float], str],
        finished_main_log_line: Callable[[float, float, float, float, str, int], str],
        rmse_milestone_log_line: Callable[[list[float], list[float], list[float]], str],
        progress_message_done: Callable[..., str],
    ) -> dict[str, Any]:
        """Log/progress text + final finished signal payload in one call."""
        msgs = REResultsBuilder.finalize_message_bundle(
            results=results,
            top_result=top_result,
            alpha_rank_ref=alpha_rank_ref,
            elapsed_s=elapsed_s,
            best_sp=best_sp,
            best_ot=best_ot,
            best_combined=best_combined,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=stopped_by_user,
            ranking_log_suffix=ranking_log_suffix,
            finished_main_log_line=finished_main_log_line,
            rmse_milestone_log_line=rmse_milestone_log_line,
            progress_message_done=progress_message_done,
        )
        fin = REResultsBuilder.build_finished_payload(
            results=results,
            ep0=ep0,
            rmse_initial_milestone=rmse_initial_milestone,
            rmse_phase1_milestone=rmse_phase1_milestone,
            rmse_final_milestone=rmse_final_milestone,
            stopped_by_user=stopped_by_user,
            re_qwot_alphas=re_qwot_alphas,
        )
        return {**msgs, "finished_payload": fin}

    @staticmethod
    def stop_live_emit_payload(
        *,
        stop_requested: bool,
        top_result: dict[str, Any] | None,
        correc_nominal: tuple[Any, ...],
        p2_to_correc: Callable[[dict[str, Any], bool], tuple[Any, ...]],
    ) -> dict[str, Any] | None:
        """Build live spectrum payload for stop-mode emission."""
        if not stop_requested or top_result is None:
            return None
        ep = np.asarray(top_result.get("ep", []), dtype=np.float64).flatten()
        nfev = int(top_result.get("nfev", 0))
        rmse = float(top_result.get("rmse_combined", float("nan")))
        dh = np.asarray(top_result.get("re_dH_knots", []), dtype=np.float64)
        dl = np.asarray(top_result.get("re_dL_knots", []), dtype=np.float64)
        if dh.size > 0 and dl.size > 0:
            use_sub_c3 = top_result.get("re_sub_cauchy_a0") is not None
            correc = p2_to_correc(top_result, bool(use_sub_c3))
        else:
            correc = correc_nominal
        return {
            "ep": ep,
            "nfev": nfev,
            "correc": correc,
            "rmse_override": rmse,
            "force": True,
        }
