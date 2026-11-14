"""The compute engine of a CERTUS window: Numba warm-up, its signals, the logger and the log queue (moved out of certus_base_app.py, S5.3)."""

import logging
import threading
from typing import Any

from PyQt6.QtCore import pyqtSlot

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, certus_timestamp_display
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_utils import process_log_queue_standard, show_toast
from certus.ui.certus_ui_widgets_utils import CertusLogPanel


class CertusAppEngineMixin:
    """The compute engine of a CERTUS window: Numba warm-up, its signals, the logger and the log queue (moved out of certus_base_app.py, S5.3)."""

    def _setup_logger(self, name: str) -> Any:
        """

        Setup GUI logger with the given name.

        Args:

            name: Logger name (typically self.APP_NAME)

        Returns:

            Configured logger instance

        """

        from certus.core.certus_core import setup_gui_logger

        self.logger = setup_gui_logger(self.log_queue, name)
        self.logger.info("[%s] Show Details logger attached", name)

        return self.logger

    def _warmup_numba(self) -> None:
        """
        Override in subclass to perform JIT precompilation.
        Call self.numba_manager.start_warmup() when done.
        """
        self.numba_manager.start_warmup(None)

    # --- Threaded warm-up, shared by INDEX, INDEX SPLINE, METAL and STRAT -----------
    #
    # A window that compiles its kernels in the background overrides _warmup_numba to call
    # _start_numba_warmup_thread and writes _compile_numba_kernels, the calls its kernels
    # need. The daemon thread emits sig_numba_ready or sig_numba_error; the connection is
    # queued, so the slots run in the GUI thread. A window closed before the end of the
    # warm-up has a deleted C++ object: the emission raises RuntimeError and is dropped.

    #: Attribute name of the label the warm-up writes its state to; skipped when missing.
    WARMUP_STATUS_LABEL = "status_label"
    #: Exceptions of _compile_numba_kernels handed to _on_numba_warmup_failure; others propagate.
    WARMUP_FAULTS: tuple[type[BaseException], ...] | type[BaseException] = NUMERICAL_FAULT_EXCEPTIONS

    def _warmup_status_label(self) -> Any:
        return getattr(self, self.WARMUP_STATUS_LABEL, None)

    def _start_numba_warmup_thread(self) -> None:
        """Connect the warm-up signals to the window's slots and compile its kernels on a daemon thread."""
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        label = self._warmup_status_label()
        if label is not None:
            label.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _compile_numba_kernels(self) -> None:
        """Call once, on dummy data, each Numba kernel the window needs (runs on the warm-up thread)."""
        raise NotImplementedError

    def _warmup_numba_thread_runner(self) -> None:
        """Body of the warm-up thread: compile, then emit sig_numba_ready, or report the failure."""
        try:
            self._compile_numba_kernels()
            self._emit_warmup_signal(self.sig_numba_ready)
        except self.WARMUP_FAULTS as e:
            self._on_numba_warmup_failure(e)

    @staticmethod
    def _emit_warmup_signal(signal: Any) -> None:
        """Emit from the warm-up thread; a window already destroyed drops the emission."""
        try:
            signal.emit()
        except (RuntimeError, AttributeError):
            return

    def _on_numba_warmup_failure(self, exc: BaseException) -> None:
        """Log the failure and emit sig_numba_error (warm-up thread, inside the except block)."""
        self.logger.error(f"✗ Numba warmup failed: {exc}", exc_info=True)
        self._emit_warmup_signal(self.sig_numba_error)

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:
        label = self._warmup_status_label()
        if label is not None:
            label.setText("Ready (JIT Compiled)")
        self._on_numba_ready()  # Mark as ready
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        label = self._warmup_status_label()
        if label is not None:
            label.setText("JIT Init Error")

    def _on_numba_ready_from_manager(self) -> None:
        self.numba_ready = True

    def _on_numba_error_from_manager(self, message: str) -> None:
        self.numba_ready = False

    def _on_numba_ready(self) -> None:
        """Called when Numba warmup completes."""
        self.numba_manager.on_warmup_done()

    def _on_warmup_done(self) -> None:
        """Slot when ``WarmupWorker.finished`` fires (CERTUS_DESIGN / CERTUS_RE)."""
        self._warmup_done = True
        self._spectrum_eval_jit_wait_logged = False
        sl = getattr(self, "status_label", None)
        if sl is not None:
            sl.setText("Ready")
        logging.info("[WARMUP] JIT warmup finished; spectrum eval may proceed.")
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        self._on_numba_ready()

    def _on_warmup_error(self, message: str) -> None:
        self.numba_manager.on_warmup_error(message)

    def _process_log_queue(self) -> None:
        """Process pending log messages."""

        log_widget = self._get_log_widget()

        if log_widget and self.log_queue:
            process_log_queue_standard(self.log_queue, log_widget)

    def log(self, msg: str, lvl: str = "INFO") -> None:
        """Adds message to log.

        P0.5 integration: mirrors ``SUCCESS`` / ``ERROR`` / ``WARNING``
        messages to the stacked toast notifications so user-facing state
        changes are visible even when the log panel is collapsed. ``INFO``
        stays log-only (too noisy for toasts).
        """

        colors = {
            "SUCCESS": CertusTheme.SUCCESS,
            "ERROR": CertusTheme.ERROR,
            "WARNING": CertusTheme.WARNING,
        }

        c = colors.get(lvl, CertusTheme.TEXT_SUB)

        # Show elapsed time if workflow is running

        elapsed_str = ""

        is_top_start = (
            (
                ("Starting" in msg or "STARTING" in msg)
                and "optimization" in msg
                and not any(
                    sub in msg for sub in ("Auto-Restart", "PGLOBAL Global", "iterative", "local re-optimization")
                )
            )
            or "Creating REWorker" in msg
            or "Calling worker.start()" in msg
        )

        if is_top_start:
            import time as _time

            self._workflow_wall_start = _time.time()

        t0 = getattr(self, "_workflow_wall_start", None)

        if t0 is not None:
            import time as _time

            elapsed = _time.time() - t0

            m, s = divmod(int(elapsed), 60)

            elapsed_str = f" <b>({m}m{s:02d}s)</b>"

        if hasattr(self, "log_text"):
            self.log_text.append(
                f"<span style='color:{c}'><b>[{certus_timestamp_display()}]</b>{elapsed_str} {msg}</span>"
            )

        # P0.5 - Mirror to stacked toasts for important levels only
        self._mirror_log_to_toast(msg, lvl)

    def _mirror_log_to_toast(self, msg: str, lvl: str) -> None:
        """Best-effort mirror of a log line to the toast stack.

        Silently ignored on INFO level or if the toast module is
        unavailable. Strips HTML tags from ``msg`` before display.
        """
        lvl_norm = str(lvl).strip().upper()
        if lvl_norm not in ("SUCCESS", "ERROR", "WARNING"):
            return
        try:
            import re

            from certus.ui.certus_toast_stack import show_toast_stack

            variant = {"SUCCESS": "success", "ERROR": "error", "WARNING": "warning"}[lvl_norm]
            clean = re.sub(r"<[^>]+>", "", str(msg)).strip()
            if clean:
                show_toast_stack(self, clean[:200], variant=variant, duration_ms=3500)
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _get_log_widget(self) -> Any:
        """Override base class: log widget is self.log_text (set by _build_log_container)."""

        return getattr(self, "log_text", None)

    def _build_log_container(self) -> Any:
        """Constructs log container using shared CertusLogPanel."""

        panel = CertusLogPanel(title="LOGS", visible=True, height=120)

        self.log_text = panel.log_text

        def _on_logs_copied() -> None:

            sl = getattr(self, "status_label", None)

            if sl is not None and hasattr(sl, "setText"):
                sl.setText("Logs copied to clipboard.")

        panel.copied.connect(_on_logs_copied)

        self._log_panel = panel

        return panel

    def toggle_logs(self, checked: bool) -> None:
        """Toggle logs visibility"""

        self.log_container.setVisible(checked)
