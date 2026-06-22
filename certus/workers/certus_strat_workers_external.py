
from typing import TYPE_CHECKING, Any
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_strat_core import APP_CONTEXT
from certus.utils.certus_strat_context import StratContext
from certus.workers.certus_strat_workers_dto import WorkerThreadResult
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_strat_service import calculate_nominal_properties, extract_best_rmse, select_best_strat_result
from certus.core.certus_strat_core import generate_excel_report
from certus.core.certus_core import get_export_config, get_resource_path, certus_timestamp_file
from pathlib import Path
from certus.core.certus_core import SUBSTRATE_MAPPING
import certus.utils.certus_strat_service as _strat_service_module
import traceback
import time

from certus.core.certus_strat_config import precompute_clues_and_matrices
from certus.core.certus_strat_robustness import run_final_simulation_block

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class ExternalEvaluationStrategy:
    def execute(self, worker: "WorkerThread") -> None:

        worker.params["logger"].info("--- STEP 33: EXTERNAL STRATEGIES SIMULATION ---")

        loaded_strategies = worker.params.get("loaded_strategies", [])

        if not loaded_strategies:
            raise ValueError("No strategies loaded in params['loaded_strategies']")

        if not worker.opti_results:
            nominal_results = getattr(worker, "nominal_results", None)
            if nominal_results is None:
                nominal_results, _ = calculate_nominal_properties(worker.params)

            p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

            clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                worker.params, p_thick_nominal, worker.params["logger"]
            )

            worker.opti_results = {
                "p_thick_nominal": p_thick_nominal,
                "clues_at_wl": clues_at_wl,
                "nominal_matrix_cache": nominal_matrix_cache,
                "all_wls": all_wls,
                "p_thick_nominal": p_thick_nominal,
            }

        sim_context = worker.opti_results.copy()

        sim_context["all_strategies"] = loaded_strategies

        num_runs = int(worker.params.get("robustness_num_runs", 150))

        worker.params["logger"].info(f"🚀 Simulating {len(loaded_strategies)} external strategies ({num_runs} runs)...")

        final_results = run_final_simulation_block(sim_context, worker.params, num_runs)

        if "all_strategies_results" in final_results:
            worker.signals.show_strategies_table.emit(final_results["all_strategies_results"])

        if worker.params.get("export_excel", True):
            # SAFETY — reuse cached nominal properties to avoid redundant calculation
            nominal_results = getattr(worker, "nominal_results", None)
            if nominal_results is None:
                nominal_results, _ = calculate_nominal_properties(worker.params)

            excel_data = generate_excel_report(nominal_results, sim_context, final_results, worker.params)

            # Keep signal contract (excel_data, metadata).

            best_rmse = extract_best_rmse(final_results.get("all_strategies_results", []))
            worker.logger.info("STRAT Export (Simulation): Extracted best RMSE %f from strategies results", best_rmse)

            metadata = {
                "rmse": best_rmse,
                "strategies_count": len(final_results.get("all_strategies_results", [])),
                "params": {k: v for k, v in worker.params.items() if k not in ["logger", "materials_db", "clues_at_wl"]},
            }

            worker.signals.excel_ready.emit(excel_data, metadata)

        if worker.params.get("show_plots", True):
            if "all_strategies_results" in final_results:
                heatmap_data = worker.opti_results.get("raw_results_thickness", None)

                strat_data = {
                    "strategies": final_results["all_strategies_results"],
                    "p_thick_nominal": worker.opti_results["p_thick_nominal"],
                    "heatmap_data": heatmap_data,
                }

                worker.signals.plot.emit(strat_data, "block_assignments")
