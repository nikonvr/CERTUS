"""
CERTUS Professional Reset Framework
Standardized reset functionality for all CERTUS applications
Provides consistent "Clear / Reset" behavior across the entire suite
"""

import gc
import logging
from typing import Any

from PyQt6.QtWidgets import QMessageBox, QPlainTextEdit, QTextEdit

from certus_errors import NUMERICAL_FAULT_EXCEPTIONS


__all__ = [
    "CertusResetManager",
    "create_reset_button",
    "reset_app_to_defaults",
]


class CertusResetManager:
    """
    Professional reset manager for CERTUS applications.

    Provides standardized, complete reset functionality that ensures:
    - All workers are stopped cleanly
    - All UI elements are cleared
    - All memory is freed
    - Application returns to factory default state
    """

    def __init__(self, app_instance: Any) -> None:
        """Initialize reset manager with application instance"""
        self.app = app_instance
        self.logger = logging.getLogger(__name__)

    def reset_to_defaults(self) -> bool:
        """
        Complete application reset to factory defaults.
        Works even when optimization/workflow is in a loop: workers run in threads,
        so the main thread stays in the event loop and the button click is processed.
        Uses _request_stop (e.g. STRAT stop_requested), _cleanup_worker (INDEX),
        request_stop/requestInterruption/stop() to stop workers cleanly.

        Returns:
            bool: True if reset was completed, False if cancelled
        """
        # 1. User confirmation
        if not self._confirm_reset():
            return False

        try:
            # 2. Stop all workers
            self._stop_all_workers()

            # 3. Clear all UI elements
            self._clear_ui_elements()

            # 4. Reset all plots
            self._reset_all_plots()

            # 5. Clear internal state
            self._clear_internal_state()

            # 6. Handle detached windows
            self._handle_detached_windows()

            # 7. Force garbage collection
            self._force_memory_cleanup()

            # 8. Load defaults
            self._load_application_defaults()

            # 8b. Keep visual outputs empty after defaults are restored
            self._clear_visual_outputs_post_defaults()

            # 9. Final UI refresh
            self._final_ui_refresh()

            self.logger.info("Application reset to defaults completed successfully")
            return True

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Reset failed: {e}", exc_info=True)
            QMessageBox.critical(self.app, "Reset Error", f"An error occurred during reset:\n{e}")
            return False

    def _confirm_reset(self) -> bool:
        """Show confirmation dialog to user"""
        reply = QMessageBox.question(
            self.app,
            "Reset to Defaults",
            "This will clear ALL data and reset the application\n"
            "to factory defaults. Any unsaved work will be lost.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _stop_all_workers(self) -> None:
        """Stop all running worker threads (DESIGN, INDEX, STRAT, METAL). Works even when code is in a loop: workers run in threads, main thread stays in event loop."""
        if hasattr(self.app, "_request_stop"):
            try:
                self.app._request_stop()
            except (AttributeError, RuntimeError, TypeError) as e:
                self.logger.debug(f"_request_stop: {e}")
        if hasattr(self.app, "_cleanup_worker"):
            try:
                self.app._cleanup_worker()
            except (AttributeError, RuntimeError, TypeError) as e:
                self.logger.debug(f"_cleanup_worker: {e}")
        workers = [
            "optim_worker",
            "eval_worker",
            "col_worker",
            "needle_worker",
            "warmup_worker",
            "worker",
            "beam_worker",
            "optimization_thread",
            "beam_thread",
            "_worker",
            "_worker2",
            "_beam_worker",
            "_thread",
            "_thread2",
            "_beam_thread",  # INDEX QThreads
        ]
        for worker_name in workers:
            worker = getattr(self.app, worker_name, None)
            if worker is None:
                continue
            if hasattr(worker, "isRunning") and worker.isRunning():
                self.logger.debug(f"Stopping worker: {worker_name}")

                if hasattr(worker, "request_stop"):
                    worker.request_stop()
                elif hasattr(worker, "requestInterruption"):
                    worker.requestInterruption()
                if hasattr(worker, "stop"):
                    try:
                        worker.stop()
                    except (AttributeError, RuntimeError) as e:
                        self.logger.debug(f"worker.stop: {e}")

                # Wait a bit for graceful shutdown
                if not worker.wait(2000):
                    self.logger.critical(
                        f"Worker '{worker_name}' did not stop within 2s timeout. "
                        f"Skipping terminate() to avoid unsafe thread kill."
                    )

                setattr(self.app, worker_name, None)

        # Stop progress widget if present
        if hasattr(self.app, "progress_widget"):
            self.app.progress_widget.stop("Reset by user")

    def _clear_ui_elements(self) -> None:
        """Clear all UI elements to default state"""
        # Clear text areas
        text_elements = ["log_text", "console_text", "results_text"]
        for elem_name in text_elements:
            elem = getattr(self.app, elem_name, None)
            if elem:
                elem.clear()

        # Clear all text widgets generically (covers structure_text and custom log panes)
        for text_widget in self.app.findChildren((QTextEdit, QPlainTextEdit)):
            try:
                text_widget.clear()
            except (AttributeError, RuntimeError) as e:
                self.logger.debug(f"Could not clear text widget {text_widget}: {e}")

        # Reset labels (DESIGN, INDEX, STRAT, METAL)
        label_defaults = {
            "best_rmse_label": "Best RMSE:  N/A",
            "status_label": "Ready",
            "stats_label": "♟️ 0  | 🎲 0  |  🌈️ 0",
            "lbl_status": "Ready",
        }
        for label_name, default_text in label_defaults.items():
            label = getattr(self.app, label_name, None)
            if label:
                label.setText(default_text)

        # Reset buttons
        button_states = {"undo_btn": False, "redo_btn": False, "btn_stop": False, "btn_run": True}

        for btn_name, enabled_state in button_states.items():
            btn = getattr(self.app, btn_name, None)
            if btn:
                btn.setEnabled(enabled_state)

        # Clear tables (DESIGN: front/back/target; STRAT: table; INDEX/METAL: various)
        table_names = [
            "front_table",
            "back_table",
            "target_table",
            "results_table",
            "strategies_table",
            "table",
        ]
        for table_name in table_names:
            table = getattr(self.app, table_name, None)
            if table and hasattr(table, "setRowCount"):
                table.setRowCount(0)
        # STRAT: stack_table in widgets
        if hasattr(self.app, "widgets") and isinstance(getattr(self.app, "widgets", None), dict):
            stack_table = self.app.widgets.get("stack_table")
            if stack_table and hasattr(stack_table, "setRowCount"):
                stack_table.setRowCount(0)

    def _clear_text_outputs_only(self) -> None:
        """Clear only user-facing text outputs without touching restored UI state."""
        text_elements = ["log_text", "console_text", "results_text"]
        for elem_name in text_elements:
            elem = getattr(self.app, elem_name, None)
            if elem:
                try:
                    elem.clear()
                except (AttributeError, RuntimeError) as e:
                    self.logger.debug(f"Could not clear text element {elem_name}: {e}")

        for text_widget in self.app.findChildren((QTextEdit, QPlainTextEdit)):
            try:
                text_widget.clear()
            except (AttributeError, RuntimeError) as e:
                self.logger.debug(f"Could not clear text widget {text_widget}: {e}")

    def _reset_all_plots(self) -> None:
        """Reset all plot widgets to pristine state (DESIGN, INDEX, METAL)"""
        plot_names = [
            "spectrum_plot",
            "profile_plot",
            "nk_plot",
            "color_plot",
            "reflectance_plot",
            "plot_spectrum",
            "plot_convergence",
            "plot_nk",
        ]

        for plot_name in plot_names:
            plot_widget = getattr(self.app, plot_name, None)
            if plot_widget and hasattr(plot_widget, "plotItem"):
                # Clear all items
                plot_widget.plotItem.clear()

                # Reset axes labels
                try:
                    plot_widget.plotItem.setLabel("left", "")
                    plot_widget.plotItem.setLabel("bottom", "")
                    plot_widget.plotItem.setTitle("")
                    plot_widget.plotItem.showGrid(x=True, y=True)
                    plot_widget.plotItem.autoRange()
                except (AttributeError, RuntimeError) as e:
                    self.logger.debug(f"Could not reset plot axes for {plot_name}: {e}")

                # Clear tracking if available
                if hasattr(plot_widget, "clear_tracking"):
                    plot_widget.clear_tracking()

        # Generic fallback for plot widgets not covered by the curated list
        try:
            import pyqtgraph as pg

            plot_widget_class = pg.PlotWidget
        except ImportError:
            plot_widget_class = None
        if plot_widget_class is None:
            return
        for plot_widget in self.app.findChildren(plot_widget_class):
            if not hasattr(plot_widget, "plotItem"):
                continue
            try:
                plot_widget.plotItem.clear()
                if hasattr(plot_widget, "clear_tracking"):
                    plot_widget.clear_tracking()
                plot_widget.plotItem.setLabel("left", "")
                plot_widget.plotItem.setLabel("bottom", "")
                plot_widget.plotItem.setTitle("")
                plot_widget.plotItem.showGrid(x=True, y=True)
                plot_widget.plotItem.autoRange()
            except (AttributeError, RuntimeError) as e:
                self.logger.debug(f"Could not generically reset plot widget {plot_widget}: {e}")

    def _clear_visual_outputs_post_defaults(self) -> None:
        """Ensure logs and plots stay empty even if _load_defaults repopulates them."""
        self._clear_text_outputs_only()
        self._reset_all_plots()

    def _clear_internal_state(self) -> None:
        """Clear all internal application state"""
        # Clear data structures
        data_structures = [
            "pareto_history",
            "latest_results",
            "target_data",
            "beam_stats",
            "undo_stack",
            "accumulated_evals",
        ]

        for struct_name in data_structures:
            struct = getattr(self.app, struct_name, None)
            if struct:
                if hasattr(struct, "clear"):
                    struct.clear()
                else:
                    setattr(self.app, struct_name, {} if isinstance(struct, dict) else [])

        # Reset counters and flags
        # Preserve existing stat_counters keys (apps define their own keys)
        existing_counters = getattr(self.app, "stat_counters", {})
        reset_counters = {k: 0 for k in existing_counters}
        counter_defaults = {
            "stat_counters": reset_counters,
            "_current_eval_generation": 0,
            "_best_eval_rmse": float("inf"),
            "_workflow_stopped": False,
            "_initial_cleared": False,
        }

        for attr_name, default_value in counter_defaults.items():
            setattr(self.app, attr_name, default_value)

        # Clear plot caches
        cache_names = ["_live_curves", "_live_curve", "_live_points", "_oblique_spectrum_colors", "curve_points"]

        for cache_name in cache_names:
            cache = getattr(self.app, cache_name, None)
            if cache:
                if hasattr(cache, "clear"):
                    cache.clear()
                else:
                    setattr(self.app, cache_name, {} if isinstance(cache, dict) else [])

    def _handle_detached_windows(self) -> None:
        """Close all detached windows"""
        # Main detached window
        if hasattr(self.app, "detached_window") and self.app.detached_window:
            self.app.detached_window.close()
            self.app.detached_window = None

        # Plot windows dictionary
        if hasattr(self.app, "detached_plot_windows"):
            for win in self.app.detached_plot_windows.values():
                try:
                    win.close()
                except (AttributeError, RuntimeError) as e:
                    self.logger.debug(f"Error closing detached window: {e}")
            self.app.detached_plot_windows = {}

        # Auxiliary windows
        if hasattr(self.app, "close_all_auxiliary_windows"):
            self.app.close_all_auxiliary_windows()

    def _force_memory_cleanup(self) -> None:
        """Force garbage collection to free memory"""
        try:
            # Clear any material caches
            if hasattr(self.app, "materials_db"):
                self.app.materials_db.clear_cache()

            # Force Python garbage collection
            gc.collect()

            # UI updates are driven by the normal event loop; no manual processEvents.

        except (AttributeError, RuntimeError, TypeError) as e:
            self.logger.debug(f"Memory cleanup warning: {e}")

    def _load_application_defaults(self) -> None:
        """Load application-specific defaults"""
        # This method should be overridden by each application
        # to load its specific default values
        if hasattr(self.app, "_load_defaults"):
            self.app._load_defaults()
        else:
            self.logger.warning("Application does not have _load_defaults method")

    def _final_ui_refresh(self) -> None:
        """Final UI refresh after reset"""
        # Force UI idle state
        if hasattr(self.app, "_force_idle"):
            self.app._force_idle()

        # UI refresh occurs via the regular event loop.

        # Intentionally keep logs empty after reset


def create_reset_button(app_instance, use_app_reset: bool = False) -> "QPushButton":
    """
    Create a standardized reset button for any CERTUS application.

    Args:
        app_instance: The application instance
        use_app_reset: If True and app has reset_to_defaults(), use it instead of the framework reset.

    Returns:
        QPushButton: Configured reset button
    """
    from PyQt6.QtWidgets import QPushButton, QStyle

    # Create button
    reset_btn = QPushButton("🔄  Clear / Reset")
    reset_btn.setIcon(reset_btn.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))

    # Set tooltip
    reset_btn.setToolTip(
        "Reset the entire application to factory defaults.\n"
        "Stops any running processes, clears all data and results,\n"
        "and reloads the default configuration."
    )

    # Professional styling
    reset_btn.setStyleSheet("""
        QPushButton {
            background-color: #5a3a00;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }
        QPushButton:hover {
            background-color: #7a4a00;
        }
        QPushButton:pressed {
            background-color: #4a2a00;
        }
        QPushButton:disabled {
            background-color: #3a2a00;
            color: #888;
        }
    """)

    if use_app_reset and hasattr(app_instance, "reset_to_defaults"):
        reset_btn.clicked.connect(app_instance.reset_to_defaults)
    else:
        reset_manager = CertusResetManager(app_instance)
        reset_btn.clicked.connect(reset_manager.reset_to_defaults)

    return reset_btn


def reset_app_to_defaults(app_instance: Any, *, confirm: bool = True) -> bool:
    """One-liner to reset any CERTUS application to its factory defaults.

    This is the **opt-in replacement** for the duplicated ``reset_to_defaults``
    methods currently living in ``CertusDesignApp``, ``CertusIndexSplineApp``
    and ``CertusREApp`` (audit §A7). Those apps can shrink their custom
    implementation to::

        def reset_to_defaults(self):
            from certus_reset_framework import reset_app_to_defaults
            return reset_app_to_defaults(self)

    Parameters
    ----------
    app_instance : object
        Any CERTUS app exposing standard hooks
        (``_request_stop``, ``_cleanup_worker``, ``_load_defaults``,
        ``_force_idle`` — all optional). The manager introspects the app
        and only calls the hooks that exist.
    confirm : bool, default True
        When False, skip the modal confirmation dialog (useful for
        programmatic resets from the command palette or from unit tests).

    Returns
    -------
    bool
        ``True`` if the reset was completed, ``False`` if the user cancelled
        or an error was caught and logged.
    """

    manager = CertusResetManager(app_instance)
    if not confirm:
        # Bypass the confirmation dialog by making ``_confirm_reset`` a no-op.
        manager._confirm_reset = lambda: True  # type: ignore[method-assign]
    return manager.reset_to_defaults()
