"""The run state of a CERTUS window: busy / idle, errors, the running workers and the confirmation before closing (moved out of certus_base_app.py, S5.3)."""

import logging

from PyQt6.QtCore import QThread

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_ui_utils import open_dropped_file, show_toast


class CertusAppRunStateMixin:
    """The run state of a CERTUS window: busy / idle, errors, the running workers and the confirmation before closing (moved out of certus_base_app.py, S5.3)."""

    def _set_busy(self, b: bool) -> None:
        """Sets busy state with reference counting."""

        if b:
            self._busy_count += 1

        else:
            self._busy_count = max(0, self._busy_count - 1)

        busy_now = self._busy_count > 0

        self._is_busy = busy_now

        self._update_busy_ui(busy_now)

        if busy_now:
            if hasattr(self, "status_label"):
                self.status_label.setText("Computing...")

            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, 0)

        else:
            if hasattr(self, "status_label"):
                self.status_label.setText("Ready")

            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, 100)

                self.progress_bar.setValue(0)

    def _force_idle(self) -> None:
        """Force-reset busy counter and UI state to idle."""

        self._busy_count = 0

        self._is_busy = False

        self._update_busy_ui(False)

        if hasattr(self, "status_label"):
            self.status_label.setText("Ready")

        if hasattr(self, "progress_bar") and self.progress_bar:
            if hasattr(self.progress_bar, "reset"):
                self.progress_bar.reset()
            elif hasattr(self.progress_bar, "setRange"):
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)

    def _on_error(self, error_msg: object, generation_id: int | None = None) -> None:
        """Slot for ``WorkerSignals.error`` (EvalWorker, REWorker, DESIGN optimization, etc.)."""

        msg = error_msg if isinstance(error_msg, str) else str(error_msg)

        logging.error("Worker error:\n%s", msg)

        try:
            short = msg.strip().replace("\n", " ")

            if len(short) > 900:
                short = short[:900] + "..."

            self.log(short, "ERROR")

        except NUMERICAL_FAULT_EXCEPTIONS:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self._set_busy(False)

        if getattr(self, "_re_mode_active", False):
            self._re_mode_active = False

            clr = getattr(self, "_re_clear_re_nk_preview", None)

            if callable(clr):
                clr()

        pw = getattr(self, "progress_widget", None)

        if pw is not None:
            try:
                pw.stop("Error")

            except NUMERICAL_FAULT_EXCEPTIONS:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _update_busy_ui(self, busy: bool) -> None:
        """Hook for subclasses to update specific button states."""

        pass

    #: The attributes that hold a module's computation threads when it does not register them with `worker_manager`
    #: (D41): INDEX, INDEX SPLINE, RE, METAL and DESIGN closed a running computation without a question. A tuple of
    #: names, NOT annotated: under Python 3.14 an annotation gives the mixin its own `__annotate_func__`, which the
    #: window would resolve to another mixin's (test_the_base_app_split_keeps_every_window_method_where_it_resolves).
    _COMPUTATION_THREADS = ()

    def running_worker_count(self) -> int:
        """Background threads ACTUALLY running right now.

        worker_manager.active_count() counts REGISTRATIONS, and a worker that has
        finished may still be registered. The close guard has to be precise
        rather than merely cautious: a false positive freezes a window with
        nothing to lose, and tests/unit/test_gui_apps_smoke.py closes eleven.
        """
        # Only the manager's own registrations. An earlier version also walked
        # findChildren(QThread): that traversal reached objects whose C++ side was
        # already gone during teardown and crashed the interpreter outright -
        # "Windows fatal exception: access violation", which no except clause can
        # catch. Measured 2026-09-05: tests/unit/test_gui_apps_smoke.py went from
        # 5 passed in 4 s to a hard crash, and back once the traversal was
        # dropped.
        manager = getattr(self, "worker_manager", None)
        workers = getattr(manager, "_active_workers", None) or []

        running = 0
        for candidate in list(workers):
            try:
                if candidate.isRunning():
                    running += 1
            except RuntimeError, AttributeError:  # wrapper outlived the C++ object
                continue
        for name in self._COMPUTATION_THREADS:
            thread = getattr(self, name, None)
            try:
                if thread is not None and thread not in workers and thread.isRunning():
                    running += 1
            except RuntimeError, AttributeError:  # wrapper outlived the C++ object
                continue
        return running

    def confirm_close_during_run(self, event) -> bool:
        """Ask before a close throws a running computation away.

        Until 2026-09-05 closeEvent called _stop_all_workers() and never asked,
        and STRAT's own override ended with `finally: event.accept()`. Clicking
        the window's X during a STRAT run - up to 2 h 39 - discarded it with no
        question and no undo.

        Returns True when the close may proceed.
        """
        running = self.running_worker_count()
        if not running:
            return True
        if self.confirm_destructive(
            "Close while a computation is running?",
            f"{running} background task(s) are still running in this window.",
            detail="Closing now discards the current run. A STRAT run takes up to 2 h 39.",
            confirm_label="Close and discard",
            cancel_label="Keep running",
        ):
            return True
        event.ignore()
        return False

    def _stop_all_workers(self) -> None:
        """Stop all active workers."""
        self.worker_manager.stop_all()

    def _on_worker_finished(self, worker: QThread) -> None:
        """Called when a worker finishes."""
        self.worker_manager.unregister_worker(worker)

    #: What loads a dropped file, by kind: a configuration (.json) or a data file (spectrum, workbook, table).
    _CONFIG_LOADERS = ("load_configuration", "load_config", "load_design")
    _DATA_LOADERS = ("load_file", "_on_load", "load_target_file", "load_reverse_engineering_from_path")

    def _handle_dropped_file(self, file_path: str) -> None:
        """Universal router for loading a dropped file: a configuration (.json) or a data file.

        The kind of file picks the loader, not the mere existence of a method: a spectrum dropped on a window that
        also reads configurations used to go to the configuration reader. A loader returns True once the file is
        loaded (see ``open_dropped_file``).
        """
        from pathlib import Path

        path = Path(file_path)
        names = self._CONFIG_LOADERS if path.suffix.lower() == ".json" else self._DATA_LOADERS
        loader = next((getattr(self, n) for n in names if callable(getattr(self, n, None))), None)
        if loader is None:
            kind = path.suffix.lower() or "such"
            show_toast(self, f"Cannot open {path.name}: this window does not read {kind} files", "error")
            return
        open_dropped_file(self, file_path, loader)
