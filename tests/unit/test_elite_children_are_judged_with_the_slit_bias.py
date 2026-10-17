"""Every strategy that is evaluated carries the slit-bias profile of its own blocks, the children of ELITE and of the local search included.

`_prepare_robustness_inputs` attached the profile to the plans it was given, and ELITE and the local search build their children
after it, from the blocks of their parent: the children were simulated with no bias while their parents and every other plan of the
run carried it. 📏 `35c` in `fast`, `scripts`-side trace of the calls of the task: 2 926 of the 3 013 ELITE evaluations had no profile.
The bias is largest at the band edge, where the winners of the juge de paix monitor their first block (544 nm): a plan judged without
it looks better than the same plan judged like the others.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import numpy as np
import pytest

import certus.core.certus_strat_robustness as robustness

CONSENSUS = Path(__file__).resolve().parents[2] / "certus" / "core" / "certus_strat_consensus.py"
LOG = logging.getLogger("test_slit_children")


@pytest.fixture
def profiles(monkeypatch):
    """A stand-in for the profile: it records the strategy, the slit it was asked for, and returns an array that names both."""
    asked: list[tuple[dict, float]] = []

    def fake(strategy, p_thick_nominal, params, resolution_nm):
        asked.append((strategy, resolution_nm))
        return np.full(3, float(resolution_nm))

    monkeypatch.setattr(robustness, "_slit_bias_profiles", fake)
    return asked


def _plan(blocks_wl: float, **extra) -> dict:
    return {"blocks": [{"start": 0, "end": 4, "wavelength": blocks_wl}], **extra}


def test_each_strategy_gets_the_profile_of_its_own_blocks_at_its_own_slit(profiles) -> None:
    plans = [_plan(544.0), _plan(550.0, monochromator_resolution_nm=1.0), _plan(560.0, monochromator_resolution_nm=5.0)]

    robustness._attach_slit_profiles(plans, [100.0] * 4, {"monochromator_resolution_nm": 2.0}, LOG)

    assert [float(p["slit_profile"][0]) for p in plans] == [2.0, 1.0, 5.0]
    assert [s for _, s in profiles] == [2.0, 1.0, 5.0]


def test_a_child_that_inherited_its_slit_gets_a_profile_at_that_slit(profiles) -> None:
    """The children keep the slit of their parent (`test_elite_children_keep_what_their_parent_carries.py`): the profile follows."""
    child = _plan(545.0, monochromator_resolution_nm=1.0, rate_layers=[3])

    robustness._attach_slit_profiles([child], [100.0] * 4, {"monochromator_resolution_nm": 2.0}, LOG)

    assert float(child["slit_profile"][0]) == 1.0


def test_nothing_is_attached_when_the_bias_is_switched_off(profiles) -> None:
    plans = [_plan(544.0)]

    robustness._attach_slit_profiles(plans, [100.0] * 4, {"slit_bias_enabled": False}, LOG)

    assert "slit_profile" not in plans[0]
    assert profiles == []


def test_a_profile_that_cannot_be_computed_disables_the_bias_for_that_strategy_alone(monkeypatch) -> None:
    def broken(strategy, *_args):
        if strategy["blocks"][0]["wavelength"] == 1.0:
            raise ValueError("no curvature here")
        return np.zeros(3)

    monkeypatch.setattr(robustness, "_slit_bias_profiles", broken)
    plans = [_plan(1.0), _plan(2.0)]

    robustness._attach_slit_profiles(plans, [100.0] * 4, {}, LOG)

    assert plans[0]["slit_profile"] is None
    assert plans[1]["slit_profile"] is not None


@pytest.mark.parametrize("function", ["_apply_elite_refinement_if_enabled", "_apply_local_search_p_conforme"])
def test_the_children_are_given_their_profile_before_they_are_evaluated(function: str) -> None:
    tree = ast.parse(CONSENSUS.read_text(encoding="utf-8"))
    (node,) = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
    attach = [c.lineno for c in ast.walk(node) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_attach_slit_profiles"]
    evaluate = [n.lineno for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == "_test_strategy_robustness_task"]

    assert attach, f"{function} never attaches the slit profile to the children it builds"
    assert evaluate
    assert min(attach) < min(evaluate), f"{function} evaluates a child before it has its slit profile"
