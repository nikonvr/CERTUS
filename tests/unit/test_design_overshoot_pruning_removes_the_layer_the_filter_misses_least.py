"""Overshoot & Prune removes the layer the filter misses least, not simply the thinnest one (ALG-02, designargon section 6.3).

`OptimizationManager._prune_to_target` is meant to try the removal of each of the 20 % thinnest layers, merge the layers that
become adjacent, polish the thicknesses with the analytic gradient and remove the layer that leaves the lowest RMSE. The
evaluator of those trials could not run: it unpacked `optim_prepare_stack_nk_back` in the wrong order and read `t.val` and
`t.weight`, which a `Target` does not have, and `except Exception: return float("inf")` hid both. No candidate was ever scored,
so the first one, the thinnest layer, always went, whatever it did to the spectrum.

The stack below is built so that the thinnest layer is the wrong answer. Row 0, next to the substrate (index 0 of every kernel),
has the index of the substrate: it is invisible whatever its thickness, so removing it leaves the spectrum as it is. Row 9, on
the air side, is a thin layer of high index: the thinnest of the stack, and the one the filter feels. The target is the
spectrum of the full stack, so the stack sits on the minimum of its own merit and any removal that moves the spectrum is an error.
The spectra come from `tests/oracle/tmm_reference.py`, which shares no code with `certus.physics`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui.certus_design_ui_optimization import OptimizationManager
from certus_physics import Material, Target, prepare_targets_vectorized

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

#: Constant indices (n4 = n7). "S" has the index of the substrate, which makes it invisible next to it.
INDEX = {"H": 2.30, "L": 1.46, "S": 1.52, "Substrate": 1.52}
MATERIALS = {name: Material(n, n) for name, n in INDEX.items()}
WLS = np.linspace(450.0, 750.0, 31)

#: (material, thickness in nm), row 0 next to the substrate. Row 9 is the thinnest layer and the one the filter feels;
#: row 0, the second thinnest, cannot be felt at all. No two neighbours share a material, so no removal merges anything.
STACK = [
    ("S", 24.0),
    ("H", 58.0),
    ("L", 92.0),
    ("H", 61.0),
    ("L", 90.0),
    ("H", 55.0),
    ("L", 94.0),
    ("H", 60.0),
    ("L", 96.0),
    ("H", 18.0),
]


def _layer(name: str) -> SimpleNamespace:
    return SimpleNamespace(mat=name, qwot=1.0, var=True)


def _transmittance(layers: list[tuple[str, float]]) -> np.ndarray:
    """T of the stack in air on the substrate at each wavelength of `WLS`, by the oracle (index 0 next to the substrate)."""
    n_layers = np.array([MATERIALS[name].get_nk(WLS) for name, _ in layers]).T  # (wavelengths, layers)
    n_sub = MATERIALS["Substrate"].get_nk(WLS)
    thicknesses = [d for _, d in layers]
    return np.array(
        [
            oracle.rt_stack(float(wl), n_layers[i], thicknesses, n_inc=1.0 + 0.0j, n_sub=n_sub[i])[1]
            for i, wl in enumerate(WLS)
        ]
    )


def _targets(layers: list[tuple[str, float]]) -> list[Target]:
    """One target per wavelength of `WLS`, equal to the transmittance of `layers` there: the stack sits on its own minimum."""
    return [Target(float(wl), float(wl), float(t), float(t)) for wl, t in zip(WLS, _transmittance(layers), strict=True)]


def _rmse(layers: list[tuple[str, float]]) -> float:
    """RMSE of `layers` against the full stack as DESIGN weighs it: oracle spectrum, `prepare_targets_vectorized` weights."""
    values, weights = prepare_targets_vectorized(WLS, _targets(STACK))
    error = _transmittance(layers) - values
    return float(np.sqrt(np.sum(weights * error**2) / np.sum(weights)))


class _Window:
    """The part of the DESIGN window that `_prune_to_target` reads and writes, over a real list of layers."""

    def __init__(self, layers: list[tuple[str, float]]) -> None:
        self.stack = [_layer(name) for name, _ in layers]
        self.ep_current = np.array([d for _, d in layers], dtype=float)
        self.targets = _targets(layers)
        self.materials = dict(MATERIALS)
        self.oblique_mode = False
        self.ep_back_current = None
        self.back_check = SimpleNamespace(isChecked=lambda: False)
        self.back_coat_check = SimpleNamespace(isChecked=lambda: False)
        self.front_table = SimpleNamespace(
            rowCount=lambda: len(self.stack), removeRow=self._remove_row, blockSignals=lambda blocked: None
        )
        self.removed_rows: list[int] = []
        self.messages: list[tuple[str, str]] = []

    def _remove_row(self, row: int) -> None:
        self.removed_rows.append(row)
        del self.stack[row]
        self.ep_current = np.delete(self.ep_current, row)

    def _merge_adjacent_layers(self) -> None:
        row = 1
        while row < len(self.stack):
            if self.stack[row].mat == self.stack[row - 1].mat:
                self.ep_current[row - 1] += self.ep_current[row]
                del self.stack[row]
                self.ep_current = np.delete(self.ep_current, row)
            else:
                row += 1

    def _get_front_stack(self) -> list[SimpleNamespace]:
        return list(self.stack)

    def _get_materials(self) -> dict[str, Material]:
        return self.materials

    def _get_optim_wls(self) -> np.ndarray:
        return WLS

    def _get_tgts(self) -> list[Target]:
        return self.targets

    def _get_back_stack(self) -> list[SimpleNamespace]:
        return []

    def _update_layer_count(self) -> None:
        pass

    def _update_thickness_display(self) -> None:
        pass

    def log(self, message: str, level: str = "INFO") -> None:
        self.messages.append((message, level))


def test_overshoot_pruning_removes_the_layer_the_filter_misses_least_not_the_thinnest() -> None:
    window = _Window(STACK)

    OptimizationManager(window)._prune_to_target(9)

    assert window.removed_rows == [0], "the thinnest layer (row 9) went: no trial removal was scored"
    assert [layer.mat for layer in window.stack] == [name for name, _ in STACK[1:]]
    assert window.ep_current.tolist() == [d for _, d in STACK[1:]]


def test_overshoot_pruning_still_removes_the_thinnest_layer_when_it_is_the_one_the_filter_misses_least() -> None:
    layers = [("S", 14.0), *STACK[1:]]
    window = _Window(layers)

    OptimizationManager(window)._prune_to_target(9)

    assert window.removed_rows == [0]


def test_overshoot_pruning_logs_the_rmse_the_removal_leaves() -> None:
    window = _Window(STACK)

    OptimizationManager(window)._prune_to_target(9)

    said = [message for message, _level in window.messages if "RMSE after removal" in message]
    assert len(said) == 1
    assert float(re.search(r"RMSE after removal ([0-9.]+)", said[0]).group(1)) == pytest.approx(0.0, abs=1e-6)


def test_a_trial_removal_is_scored_with_a_finite_rmse_after_the_polish() -> None:
    manager = OptimizationManager(_Window(STACK))
    air_side_removed = STACK[:-1]
    invisible_removed = STACK[1:]

    polished = manager._prune_trial_rmse(
        np.array([d for _, d in air_side_removed]), [_layer(name) for name, _ in air_side_removed]
    )
    invisible = manager._prune_trial_rmse(
        np.array([d for _, d in invisible_removed]), [_layer(name) for name, _ in invisible_removed]
    )

    assert np.isfinite(polished)
    assert 0.0 < polished < _rmse(air_side_removed)  # the polish ran, and it cannot give the lost layer back
    assert invisible == pytest.approx(0.0, abs=1e-6)  # the invisible layer costs nothing
    assert invisible < polished


def test_a_trial_that_cannot_be_evaluated_is_reported_with_its_cause() -> None:
    window = _Window(STACK)
    window.materials = {}  # no substrate: every trial raises a KeyError

    OptimizationManager(window)._prune_to_target(9)

    assert window.removed_rows == [9]  # nothing could be ranked: the thinnest layer goes, as it always did
    warnings = [message for message, level in window.messages if level == "WARNING"]
    assert any("KeyError" in message for message in warnings), warnings
