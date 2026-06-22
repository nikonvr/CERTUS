
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

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class NominalAnalysisStrategy:
    def execute(self, worker: "WorkerThread") -> None:
        """

        Execute Step 1: Nominal Calculation & Sensitivity Check.

        This method performs initial analysis including:

        - Nominal property calculation for the design

        - Sensitivity matrix computation

        - SEEL analysis for error estimation

        - Visualization of results and stack structure

        Args:

            worker: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Emits plot signals for visualization

            - Calculates sensitivity for robustness analysis

            - Stores SEEL data in application context

        """

        worker.params["logger"].info("--- STEP 1: NOMINAL CALCULATION & SENSITIVITY CHECK ---")

        # Track C: Orchestrate Step 0 via headless service
        res = worker._service.run_step_0(worker.params, materials_db=APP_CONTEXT.get("materials_db"))
        nominal_results = res["nominal_results"]
        worker.nominal_results = nominal_results
        multipliers = res["multipliers"]
        sensitivity_data = res["sensitivity_data"]
        seel_data = res["seel_data"]

        APP_CONTEXT["seel_data"] = seel_data

        if worker.params.get("show_plots", True):
            worker.signals.plot.emit(sensitivity_data, "sensitivity_popup")

            stack_data = {
                "p_thick": nominal_results["physical_thicknesses_nominal"],
                "multipliers": multipliers,
                "nSub_id": worker.params.get("nSub_id"),
            }

            worker.signals.plot.emit(stack_data, "stack_visual")

            worker.signals.plot.emit(seel_data, "seel_analysis_plot")

        worker.signals.finished.emit(
            WorkerThreadResult.for_step_0(
                nominal_results=nominal_results,
                seel_data=seel_data,
            ).to_legacy_dict()
        )
