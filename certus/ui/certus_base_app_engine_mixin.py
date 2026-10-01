"""The compute engine of a CERTUS window: Numba warm-up, its signals, the logger and the log queue (moved out of certus_base_app.py, S5.3)."""

import logging
from typing import Any

from certus.core.certus_core import certus_timestamp_display
from certus.ui.certus_ui_utils import show_toast, process_log_queue_standard
from certus.ui.certus_ui_widgets_utils import CertusLogPanel
from certus.ui.certus_theme import CertusTheme


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
