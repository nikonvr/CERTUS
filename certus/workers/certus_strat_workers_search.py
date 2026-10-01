
from typing import TYPE_CHECKING

from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
from certus.core.certus_strat_workers_dto import WorkerThreadResult

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class StrategySearchStrategy:
    def execute(self, worker: WorkerThread) -> None:
        """

        Execute Step 2: Optimized Hybrid Strategy.

        This method performs the hybrid optimization strategy including:

        - Block strategy optimization using hybrid algorithms

        - Performance metrics calculation and analysis

        - Result visualization and plotting

        - Progress tracking and timing measurement

        Args:

            worker: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes timing measurement

            - Emits progress and plot signals

            - Handles optimization result processing

        """

        if worker.timing_logger:
            worker.timing_logger.start("Step 2: Optimized Hybrid Strategy")

        opti_results = optimize_block_strategy_hybrid(worker.params, worker.signals.progress, worker.signals.plot)

        if worker.params.get("show_plots", True) and "raw_results_thickness" in opti_results:
            worker.signals.plot.emit(opti_results["raw_results_thickness"], "pyqtgraph_heatmap")

        if worker.timing_logger:
            worker.timing_logger.end("Step 2: Optimized Hybrid Strategy")

        worker.signals.finished.emit(WorkerThreadResult.for_step_2(opti_results=opti_results).to_legacy_dict())
