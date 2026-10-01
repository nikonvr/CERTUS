"""The undo stack and the evaluation scheduling of a CERTUS window (moved out of certus_base_app.py, S5.3)."""

import logging

from PyQt6.QtCore import QTimer

from certus.utils.certus_copy_utils import copy_optimization_result


class CertusAppUndoMixin:
    """The undo stack and the evaluation scheduling of a CERTUS window (moved out of certus_base_app.py, S5.3)."""

    def _save_undo_state(self, force: bool = False) -> None:
        """Saves current state for undo"""

        # Guard on the CAPABILITY to replay, not on the presence of a button.
        # Measured 2026-09-05: undo_stack, _get_front_stack, _add_front_row and
        # _undo are inherited by ALL six modules, so none of them discriminates;
        # front_table is owned only by RE and DESIGN. RE owns the entire undo
        # machinery and this single `hasattr(self, "undo_btn")` neutralised it -
        # nothing was ever pushed, so Ctrl+Z had nothing to pop. Conversely,
        # pushing on FIELD or INDEX would build a stack whose replay raises on
        # self.front_table at the first press.
        if not hasattr(self, "undo_stack") or not hasattr(self, "front_table"):
            return

        stack = self._get_front_stack()

        if stack or force:
            self.undo_stack.append(stack)

            # DESIGN is the only module with the button; the rest reach undo by
            # keyboard alone.
            if getattr(self, "undo_btn", None) is not None:
                self.undo_btn.setEnabled(True)

            self.log(f"State saved (Undo stack: {len(self.undo_stack)})", "INFO")

    def _undo(self) -> None:
        """Undoes last action"""

        if not hasattr(self, "undo_stack") or not self.undo_stack:
            return

        # Same capability test as _save_undo_state: everything below addresses
        # self.front_table, which four of the six modules do not own.
        if not hasattr(self, "front_table"):
            return

        self.log("Undo...", "INFO")

        state = self.undo_stack.pop()

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for layer in state:
            # mat, qwot, var, del_checked

            self._add_front_row(layer.mat, layer.qwot, layer.var)

        self.front_table.blockSignals(False)

        self._update_layer_count()

        if not self.undo_stack and getattr(self, "undo_btn", None) is not None:
            self.undo_btn.setEnabled(False)

        self._trigger_post_undo_action()

    def _trigger_post_undo_action(self) -> None:
        """Hook for post-undo actions (like re-running optimization or evaluation)."""

        pass

    def _schedule_eval(self, instant: bool = False) -> None:
        """Schedules evaluation"""

        logging.debug(f"[EVAL] _schedule_eval called (instant={instant})")

        self._update_thickness_display()

        if self.eval_timer is not None:
            self.eval_timer.stop()

        self.eval_timer = QTimer(self)

        self.eval_timer.setSingleShot(True)

        self.eval_timer.timeout.connect(self.run_eval)

        self.eval_timer.start(0 if instant else 400)

        logging.debug(f"[EVAL] Timer started with delay={0 if instant else 400}ms")

    def _store_best_eval_snapshot(self, data: dict) -> None:
        """Store immutable snapshot of the best evaluated spectrum/result."""

        rmse = data.get("rmse")

        if not self._is_valid_rmse_value(rmse):
            return

        if rmse <= self._best_eval_rmse + 1e-12:
            self._best_eval_rmse = float(rmse)

            self._best_eval_result = copy_optimization_result(data)
