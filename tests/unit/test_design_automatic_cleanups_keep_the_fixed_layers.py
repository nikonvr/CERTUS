"""The automatic cleanups of DESIGN never delete a layer whose thickness the operator fixed.

`_apply_5nm_minimum` removed every layer under 5 nm, and `smart_cleanup` every layer under its adaptive threshold, whatever
the `var` flag: a fixed 2 nm layer disappeared at the end of a workflow (D08 and U01, UX-03 in docs/AUDITS.md). A layer the
operator fixed is a constraint of the design, not an artefact of the optimisation.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from certus.ui.certus_design_ui_optimization import OptimizationManager


def _ui(thicknesses: list[float], variable: list[bool]) -> MagicMock:
    """A window double with a front table of `len(thicknesses)` rows, the `variable` flags saying which may be optimised."""
    ui = MagicMock()
    ui.ep_current = np.asarray(thicknesses, dtype=float)
    ui._get_front_stack.return_value = [SimpleNamespace(mat="H", qwot=1.0, var=v) for v in variable]
    ui.front_table.rowCount.return_value = len(thicknesses)
    ui._workflow_best_rmse = 1.0
    ui._cleanup_threshold_multiplier = 150.0
    return ui


def _removed_rows(ui: MagicMock) -> list[int]:
    return [call.args[0] for call in ui.front_table.removeRow.call_args_list]


def test_the_5nm_rule_keeps_a_fixed_layer_thinner_than_5nm() -> None:
    ui = _ui([2.0, 5.0, 3.0], [False, True, True])

    OptimizationManager(ui)._apply_5nm_minimum()

    assert _removed_rows(ui) == [2]


def test_the_5nm_rule_still_removes_thin_variable_layers() -> None:
    ui = _ui([2.0, 6.0, 3.0], [True, True, True])

    OptimizationManager(ui)._apply_5nm_minimum()

    assert _removed_rows(ui) == [2, 0]


def test_smart_cleanup_keeps_a_fixed_layer_under_the_threshold() -> None:
    ui = _ui([0.5, 10.0, 0.8, 12.0], [False, True, True, True])

    OptimizationManager(ui).smart_cleanup()

    assert _removed_rows(ui) == [2]


def test_smart_cleanup_still_removes_thin_variable_layers() -> None:
    ui = _ui([0.5, 10.0, 0.8, 12.0], [True, True, True, True])

    OptimizationManager(ui).smart_cleanup()

    assert _removed_rows(ui) == [2, 0]


def test_the_5nm_rule_reoptimizes_the_remaining_variable_layers_after_removing_a_thin_one() -> None:
    """ALG-19: removing a thin (< 5 nm) layer at the end must re-polish the remaining variable layers above 5 nm."""
    import sys
    from pathlib import Path

    from certus_physics import Material, Target, prepare_targets_vectorized

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
    import tmm_reference as oracle

    mats = {"H": Material(2.35, 2.35), "L": Material(1.45, 1.45), "Substrate": Material(1.52, 1.52)}
    wls = np.linspace(450.0, 750.0, 31)
    full_layers = [("H", 55.0), ("L", 88.0), ("H", 52.0), ("L", 84.0), ("H", 3.5)]

    def spectrum(layers: list[tuple[str, float]]) -> np.ndarray:
        n_lay = np.array([mats[m].get_nk(wls) for m, _ in layers]).T
        n_sub = mats["Substrate"].get_nk(wls)
        d = [t for _, t in layers]
        return np.array([oracle.rt_stack(float(wl), n_lay[i], d, n_inc=1.0 + 0.0j, n_sub=n_sub[i])[1] for i, wl in enumerate(wls)])

    tgts = [Target(float(wl), float(wl), float(t), float(t)) for wl, t in zip(wls, spectrum(full_layers), strict=True)]
    vals, weights = prepare_targets_vectorized(wls, tgts)

    def rmse_of(layers: list[tuple[str, float]]) -> float:
        err = spectrum(layers) - vals
        return float(np.sqrt(np.sum(weights * err**2) / np.sum(weights)))

    unpolished_4layer_rmse = rmse_of(full_layers[:-1])

    stack = [SimpleNamespace(mat=m, qw=1.0, qwot=1.0, var=True) for m, _ in full_layers]
    ep = np.array([t for _, t in full_layers], dtype=float)

    class _Win:
        def __init__(self) -> None:
            self.ep_current = ep.copy()
            self.oblique_mode = False
            self.ep_back_current = None
            self.back_check = SimpleNamespace(isChecked=lambda: False)
            self.back_coat_check = SimpleNamespace(isChecked=lambda: False)
            self.orchestrator = SimpleNamespace(_target_layer_count=len(stack))
            self._workflow_best_rmse = 0.0
            self._design_optional_steps = {"polish_after_5nm_rule": True}  # optional step, off by default
            self.front_table = SimpleNamespace(
                rowCount=lambda: len(stack),
                removeRow=self._remove_row,
                blockSignals=lambda b: None,
            )

        def _remove_row(self, r: int) -> None:
            del stack[r]
            self.ep_current = np.delete(self.ep_current, r)

        def _merge_adjacent_layers(self) -> None:
            i = 1
            while i < len(stack):
                if stack[i].mat == stack[i - 1].mat:
                    self.ep_current[i - 1] += self.ep_current[i]
                    del stack[i]
                    self.ep_current = np.delete(self.ep_current, i)
                else:
                    i += 1

        def _get_front_stack(self):
            return list(stack)

        def _get_materials(self):
            return mats

        def _get_optim_wls(self):
            return wls

        def _get_tgts(self):
            return tgts

        def _get_back_stack(self):
            return []

        def _update_layer_count(self) -> None:
            pass

        def _update_thickness_display(self) -> None:
            pass

        def _update_qwot_from_ep(self, new_ep: np.ndarray) -> None:
            self.ep_current = np.asarray(new_ep, dtype=float).copy()

        def log(self, msg: str, level: str = "INFO") -> None:
            pass

    win = _Win()
    removed = OptimizationManager(win)._apply_5nm_minimum()

    assert removed == 1
    assert len(stack) == 4
    assert np.all(win.ep_current >= 5.0)
    polished_rmse = rmse_of([(layer.mat, float(d)) for layer, d in zip(stack, win.ep_current, strict=True)])
    assert polished_rmse < 0.7 * unpolished_4layer_rmse
