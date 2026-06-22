
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
import numpy as np

from certus.core.certus_strat_robustness import run_final_simulation_block, _get_best_noise_results
from certus_physics import arange_inclusive
from certus_physics import get_refractive_clues_vectorized, calculate_RT_batch_kernel

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class RobustnessEvaluationStrategy:
    def execute(self, worker: "WorkerThread") -> None:
        """Execute Step 3: Robustness Test (classical workflow, non-Step-23).

        Runs final Monte Carlo simulations with thickness noise, aggregates
        statistics, exports to Excel, and emits the ``show_strategies_table``
        signal.

        Prerequisite: ``worker.opti_results`` must be populated by Step 2.
        Raises ``RuntimeError`` otherwise.

        ``db_instance`` note
        --------------------
        ``run_final_simulation_block`` and ``generate_excel_report`` both
        receive ``worker.params`` directly; they apply the same three-level
        db_instance fallback internally.  Do NOT strip ``materials_db`` or
        ``materials_db_instance`` from ``worker.params`` before calling them.
        """

        if not worker.opti_results:
            raise RuntimeError("Step 2 must be completed before Step 3")

        if worker.timing_logger:
            worker.timing_logger.start("Step 3: Robustness Test")

        num_runs = int(worker.params.get("robustness_num_runs", 150))

        final_results = run_final_simulation_block(worker.opti_results, worker.params, num_runs)

        if "all_strategies_results" in final_results:
            worker.signals.show_strategies_table.emit(final_results["all_strategies_results"])

        if worker.params.get("export_excel", True):
            # SAFETY — reuse cached nominal properties to avoid redundant calculation
            nominal_results = getattr(worker, "nominal_results", None)
            if nominal_results is None:
                nominal_results, _ = calculate_nominal_properties(worker.params)

            excel_data = generate_excel_report(nominal_results, worker.opti_results, final_results, worker.params)

            # Prepare metadata for auto-naming and HTML

            rmse_val = extract_best_rmse(final_results.get("all_strategies_results", []))
            worker.logger.info("STRAT Export (Classical): Extracted best RMSE %f from strategies results", rmse_val)

            metadata = {
                "rmse": rmse_val,
                "strategies_count": len(final_results.get("all_strategies_results", [])),
                "params": worker.params,
                "nominal_results": nominal_results,
                "opti_results": worker.opti_results,
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

            best_noise_results = _get_best_noise_results(final_results, worker.params["logger"])

            if best_noise_results is None:
                raise RuntimeError("Cannot retrieve robustness results")

            wavelengths = arange_inclusive(
                worker.params["wl_range"][0],
                worker.params["wl_range"][1],
                worker.params["wl_step"],
            )

            local_db = worker.params.get("materials_db_instance") or worker.params.get("materials_db") or APP_CONTEXT.get("materials_db")

            nH_arr = get_refractive_clues_vectorized(worker.params["nH_id"], wavelengths, db_instance=local_db).astype(
                np.complex128
            )

            nL_arr = get_refractive_clues_vectorized(worker.params["nL_id"], wavelengths, db_instance=local_db).astype(
                np.complex128
            )

            nSub_arr = get_refractive_clues_vectorized(
                worker.params["nSub_id"], wavelengths, db_instance=local_db
            ).astype(np.complex128)

            _, T_clean_batch = calculate_RT_batch_kernel(
                wavelengths,
                nH_arr,
                nL_arr,
                nSub_arr,
                np.array(worker.opti_results["p_thick_nominal"], dtype=np.float64).reshape(1, -1),
            )

            # Compute T_spectral_all for MC runs
            thick_all = np.array(best_noise_results["thicknesses_all"], dtype=np.float64)
            _, T_spectral_all = calculate_RT_batch_kernel(
                wavelengths,
                nH_arr,
                nL_arr,
                nSub_arr,
                thick_all,
            )
            best_noise_results["T_spectral_all"] = T_spectral_all.tolist()

            nominal_results_display = {
                "wavelengths": wavelengths,
                "T_spectral_nominal": T_clean_batch[0],
            }

            robust_data_pack = {
                "nominal": nominal_results_display,
                "best_noise": best_noise_results,
                "opti": worker.opti_results,
            }

            worker.signals.plot.emit(robust_data_pack, "robustness_popout")

        if worker.timing_logger:
            worker.timing_logger.end("Step 3: Robustness Test")

        worker.signals.finished.emit(WorkerThreadResult.for_step_3(final_results=final_results).to_legacy_dict())
