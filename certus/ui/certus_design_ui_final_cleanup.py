"""Apply the final layer cleanup to the DESIGN window."""

from __future__ import annotations

import numpy as np

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS


class FinalCleanupMixin:
    def _final_cleanup(self) -> int | None:
        """Clean the final design: each thin layer removed or raised to its floor, then a last polish.

        Owner's request of 2026-11-13, automatic. The thinnest variable layer under its floor (the window's
        `Min. Layer`, or the file's optical floor) is tried removed and raised, each polished, and the better is
        kept (certus/core/certus_design_final_cleanup.py); the design is then polished above its floors. Returns
        how many layers the design lost, or None when the cleanup does not run here: oblique incidence (its cost
        kernel is the normal-incidence one), `final_cleanup: false` in the file, or nothing to judge the design by.
        The caller then applies the 5 nm rule, so a thin layer never stays unnoticed.
        """
        if not self._optional_step("final_cleanup") or getattr(self.ui, "oblique_mode", False):
            return None
        state = self._save_table_state()
        ep0 = np.asarray(self.ui.ep_current, dtype=np.float64) if self.ui.ep_current is not None else np.zeros(0)
        if len(state) == 0 or len(ep0) != len(state):
            return None
        try:
            from certus.core.certus_design_cost_context import prepare_design_cost_context
            from certus.core.certus_design_final_cleanup import design_cost_factory, final_cleanup
            from certus.core.certus_design_worker_utils import optim_backside_flags_from_cfg

            wls = np.asarray(self.ui._get_optim_wls(), dtype=np.float64)
            tgts = [t for t in self.ui._get_tgts() if t.valid()]
            if len(wls) == 0 or not tgts:
                return None
            has_back_stack, has_back_calc, back_stack = optim_backside_flags_from_cfg(
                {
                    "back": self.ui.back_check.isChecked(),
                    "use_back_coat": self.ui.back_coat_check.isChecked(),
                    "stack_back": self.ui._get_back_stack(),
                }
            )
            ep_back = np.asarray(self.ui.ep_back_current) if self.ui.ep_back_current is not None else np.array([])
            context = prepare_design_cost_context(
                self.ui._get_materials(), self.ui._get_front_stack(), wls, tgts,
                stack_back=back_stack, ep_back=ep_back, has_back_stack=has_back_stack, has_back_calc=has_back_calc,
            )
            names = [row["mat"] for row in state]
            floors = {name: float(self._min_layer_thickness([name])[0]) for name in set(names)}
            result = final_cleanup(
                names, ep0, [bool(row["var"]) for row in state], floors.__getitem__,
                design_cost_factory(context),
            )
        except (*NUMERICAL_FAULT_EXCEPTIONS, KeyError, TypeError, AttributeError, ValueError) as exc:
            self.ui.log(f"[FINAL CLEANUP] Not run ({type(exc).__name__}: {exc}); the 5 nm rule applies", "WARNING")
            return None

        def rmse(cost: float | None) -> str:
            return "n/a" if cost is None else f"{float(np.sqrt(max(cost, 0.0))):.6f}"

        for step in result.steps:
            other = (f"raised to its floor: {rmse(step.cost_raised)}" if step.action == "removed"
                     else f"removed: {rmse(step.cost_removed)}")
            kept = step.cost_removed if step.action == "removed" else step.cost_raised
            self.ui.log(
                f"[FINAL CLEANUP] {step.material} layer of {step.thickness:.2f} nm {step.action}: "
                f"RMSE {rmse(step.cost_before)} -> {rmse(kept)} ({other})",
                "INFO",
            )
        if result.kept_fixed:
            self.ui.log(
                f"[FINAL CLEANUP] Keeping {len(result.kept_fixed)} fixed layers under their floor: the operator fixed them",
                "WARNING",
            )
        removed = len(state) - len(result.materials)
        new_state = [dict(state[o], var=v) for o, v in zip(result.origin, result.var, strict=True)]
        if new_state != state:
            self._restore_table_state(new_state)
        # Same order as _revert_to_checkpoint: table, QWOT from the exact thicknesses, display, then ep_current.
        self.ui._update_qwot_from_ep(result.ep)
        self.ui._update_thickness_display()
        self.ui.ep_current = result.ep.copy()
        self.ui._use_exact_ep = True
        self.ui._update_layer_count()
        self.ui.orchestrator._target_layer_count = self.ui.front_table.rowCount()
        # The RMSE of THIS design: the topology may have changed, the earlier value would name another one.
        self.ui._workflow_best_rmse = float(np.sqrt(max(result.cost, 0.0)))
        self.ui.log(
            f"[FINAL CLEANUP] {len(state)} -> {len(result.materials)} layers, thinnest "
            f"{float(np.min(result.ep)):.2f} nm, RMSE {rmse(result.cost_start)} -> {rmse(result.cost)}",
            "SUCCESS",
        )
        return removed
