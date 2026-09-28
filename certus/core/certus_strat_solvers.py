# =============================================================================
# CERTUS STRAT - Core numerical and physics logic
# =============================================================================
import os
from pathlib import Path
import concurrent.futures



import io

import json

import logging


import threading




from typing import Any

import numpy as np

import pandas as pd




# Import access config
from certus.utils.certus_exclusions import filter_params_for_serialization
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    get_resource_path,
    certus_timestamp_file,
)

from certus.utils.certus_data import (
    PerformanceMonitor,
)

from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    arange_inclusive,
    calculate_detailed_growth,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    calculate_extrema_distances,
    compute_batch_rmse,
    compute_T_front_at_layer,
    find_nucleation_adaptive_kernel,
    get_refractive_index,
    get_refractive_clues_vectorized,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    update_run_states_kernel,
    validate_wavelengths_batch,
    validate_backside_real_clues,
)

# Import context system (replaces global variables)



# Robust db clues (fixed xlsx)



import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import (
    _validate_candidates_phase_a as _service_validate_candidates_phase_a,
)


_validate_phase_a_bridge_lock = threading.Lock()

# Global scientific display configuration

PERF_MONITOR = PerformanceMonitor()

# setup_numba_cache skipped (handled by configure_numba_env + file lock)

# === CACHE SYSTEM FOR PLOTS ===
# PlotCache and ThreadSafeCounter have been extracted to certus_strat_context.
# Imported here for full backward compatibility.
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter  # noqa: E402

from certus.core.certus_strat_objectives import (
    _run_phase_a_hybrid_loop,
    _normalize_phase_a_results,
)
from certus.utils.certus_strat_context import (
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_for_params,
)

# _convert_solution_to_strategy has been moved to certus_strat_ranking.py

# _generate_elite_candidate_strategies has been moved to certus_strat_consensus.py


def _export_phase_a_observability_json(params: dict[str, Any], payload: dict[str, Any]) -> None:
    """Export lightweight observability JSON for audit/tracing."""

    if not bool(params.get("export_observability_json", True)):
        return

    try:
        report_dir = get_resource_path("reports")

        os.makedirs(report_dir, exist_ok=True)

        ts = certus_timestamp_file()

        out_path = str(Path(report_dir) / f"STRAT_observability_{ts}.json")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger_local = params.get("logger")

        if logger_local:
            logger_local.info(f"📈 Observability JSON saved: '{out_path}'")

    except NUMERICAL_FAULT_EXCEPTIONS:
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


# _find_k_best_groupings_dp_sequential and mine_strategies_for_block_count have been moved to certus_strat_ranking.py

# _get_best_noise_results has been moved to certus_strat_robustness.py

# _calculate_strategy_spectral_resolution, _build_layer_wavelengths_from_strategy,
# and _validate_strategy_min_transmission_floor have been moved to certus_strat_robustness.py

# _apply_strategy_ranking has been moved to certus_strat_ranking.py

# _parse_noise_factors, _resolve_robustness_noise_levels, and _filter_valid_robustness_strategies have been moved to certus_strat_robustness.py

# Consensus & ELITE refinement functions have been moved to certus_strat_consensus.py

# Robustness simulation and scoring logic has been moved to certus_strat_robustness.py


def generate_excel_report(
    nominal_results: dict[str, Any],
    opti_results: dict[str, Any],
    final_results: dict[str, Any],
    params: dict[str, Any],
) -> io.BytesIO:

    include_secondary_rmse_stats = bool(params.get("include_secondary_rmse_stats", False))

    # Check for xlsxwriter availability

    engine = "xlsxwriter"

    try:
        import xlsxwriter  # check availability only

        _ = xlsxwriter

    except ImportError:
        engine = "openpyxl"

        if params.get("logger"):
            params["logger"].warning(
                "'xlsxwriter' module missing. Falling back to 'openpyxl' (formatting may be limited)."
            )

    with PERF_MONITOR.measure("generate_excel_report"):
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine=engine) as writer:
            params_clean = {k: str(v) for k, v in filter_params_for_serialization(params).items()}

            pd.DataFrame.from_dict(params_clean, orient="index", columns=["Value"]).to_excel(
                writer, sheet_name="Parameters"
            )

            best_blocks = final_results.get("optimal_blocks", opti_results.get("blocks", []))

            blocks_df = pd.DataFrame(
                [
                    {
                        "Block": i + 1,
                        "Start Layer": b["start"] + 1,
                        "End Layer": b["end"],
                        "Num Layers": int(b.get("num_layers", int(b.get("end", 0)) - int(b.get("start", 0)))),
                        "Wavelength (nm)": b["wavelength"],
                    }
                    for i, b in enumerate(best_blocks)
                ]
            )

            blocks_df.to_excel(writer, sheet_name="Best Strategy Blocks", index=False)

            if "all_strategies_results" in final_results:
                strategies_summary = []

                for res in final_results["all_strategies_results"]:
                    strat = res["strategy"]

                    actual_changes = strat["n_blocks"] - 1

                    max_requested = strat.get("max_changes_requested", actual_changes)

                    violated = strat.get("constraint_violated", False)

                    nominal_rmse = strat.get("avg_rmse_nominal", None)

                    if nominal_rmse is None:
                        # Fallback: approximate nominal RMSE from 1.0x noise result when available.

                        r_list = res.get("results_per_noise", [])

                        target = None

                        for r in r_list:
                            if abs(float(r.get("noise_level", 0.0)) - 1.0) < 0.1:
                                target = r

                                break

                        if target is None and r_list:
                            target = r_list[0]

                        nominal_rmse = target.get("rmse_mean", np.nan) if target else np.nan

                    strategies_summary.append(
                        {
                            "Rank": len(
                                [
                                    r
                                    for r in final_results["all_strategies_results"]
                                    if r["robustness_score"] < res["robustness_score"]
                                ]
                            )
                            + 1,
                            "Strategy ID": strat["strategy_id"],
                            "Blocks": strat["n_blocks"],
                            "Wavelength Changes": actual_changes,
                            "Max Requested": max_requested,
                            "Constraint Violated": "YES" if violated else "NO",
                            "Nominal RMSE": nominal_rmse,
                            "Robustness Score": res["robustness_score"],
                        }
                    )

                strategies_df = pd.DataFrame(strategies_summary)

                strategies_df = strategies_df.sort_values("Rank")

                strategies_df.to_excel(writer, sheet_name="All Strategies Results", index=False)

            robustness_data = []

            for res in final_results.get("results_per_noise", []):
                row = {
                    "Noise Level (%)": res["noise_level"],
                    "RMSE P95": res.get("rmse_p95", res["rmse_mean"]),
                }

                if include_secondary_rmse_stats:
                    row["RMSE Mean"] = res["rmse_mean"]

                    row["RMSE Std"] = res["rmse_std"]

                robustness_data.append(row)

            if robustness_data:
                pd.DataFrame(robustness_data).to_excel(writer, sheet_name="Robustness Best Strategy", index=False)

        output.seek(0)

        return output
