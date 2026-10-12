"""D96, D97 and D98 are settled (ETAT section 3, 2026-10-12): production runs STRAT with POEM's anchors at the extremum, the stop on the
exact signal, and an OMS that waits for ever on a level crossed before the last extremum is declared.

The kernels keep their historical path as the default of their own signature (proved to the bit by `scripts/c1_diff.py`). What makes it
the stop model of PRODUCTION is that every production entry into them asks for it: Phase A (the candidates and the propagated states) and
Phase B (the growth of the robustness batch) read the SAME three values from `stop_model_flags`. A caller that forgot it would grow with
the old model and be judged with the new one, and nothing would fail.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from certus.physics.certus_strat_readings import ARMING_NEVER_STOPS, stop_model_flags

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "certus" / "utils" / "certus_strat_service.py"
TASK = ROOT / "certus" / "core" / "certus_strat_robustness_task.py"


class _Dto:
    """A parameter set that is not a dict: `get` works, `setdefault` does not (CLAUDE.md, section 6)."""

    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _calls(path: Path, names: set[str]) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in names:
                found.append(node)
    return found


def _passes_the_stop_model(call: ast.Call) -> bool:
    """The call hands `stop_model_flags(params)` over, spread (`*`) or as one value (the bridge takes it as one)."""
    for arg in call.args:
        value = arg.value if isinstance(arg, ast.Starred) else arg
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "stop_model_flags":
            return True
    return False


def test_the_decided_stop_model_is_the_default() -> None:
    assert stop_model_flags({}) == (True, True, ARMING_NEVER_STOPS)
    assert stop_model_flags(_Dto()) == (True, True, ARMING_NEVER_STOPS)


def test_a_parameter_set_can_ask_for_the_old_model_for_a_baseline() -> None:
    old = {"exact_inversion": False, "exact_anchors": False, "oms_arming": 0}

    assert stop_model_flags(old) == (False, False, 0)
    assert stop_model_flags(_Dto(**old)) == (False, False, 0)


@pytest.mark.parametrize(
    ("path", "names"),
    [(SERVICE, {"validate_wavelengths", "update_run_states"}), (TASK, {"simulate_stack_robustness_batch"})],
    ids=["phase A", "phase B"],
)
def test_every_production_entry_into_the_growth_kernels_asks_for_the_stop_model(path: Path, names: set[str]) -> None:
    calls = _calls(path, names)

    assert calls, f"no call of {sorted(names)} found in {path.name}: the search is broken"
    for call in calls:
        assert _passes_the_stop_model(call), f"{path.name}, line {call.lineno}: a call into the growth kernels without `*stop_model_flags(params)`"


def test_the_bridge_forwards_the_three_values_to_the_kernels() -> None:
    for kernel in ("validate_wavelengths_batch", "update_run_states_kernel"):
        (call,) = _calls(SERVICE, {kernel})
        spread = {arg.value.id for arg in call.args if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name)}

        assert spread == {"stop_model"}, kernel
