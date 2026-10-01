"""The two ends of `compute_profiled_corridors_by_d` are functions of their own (audit v2, plan S5.2).

`compute_profiled_corridors_by_d` walks the corridor towards larger d and towards smaller d, merges what the two walks found, checks it, and hands back a context. That was 373 lines; the merge (86
lines) and the final rebuild of the context (62 lines) come out. Pinned here without a fit: the walks are dictionaries, the context is a namespace.

    _merge_the_two_walks_into_the_context     the larger-d walk is appended before the smaller-d walk, the counters are added (the centre's seed-gate counts too), the seed-gate verdict is
                                              "saturated" only above 50 % kept on at least 5 evaluations, and the number of valid points of each side is handed back
    _context_of_the_accepted_corridor         a new `CorridorProfileContext` that carries every field of the old one, by reference
"""

from __future__ import annotations

import dataclasses
import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.spline import spline_profile_corridors as module
from certus.spline.certus_corridor_orchestrator_utils import CorridorProfileContext
from certus.spline.spline_profile_corridors import (
    _context_of_the_accepted_corridor,
    _merge_the_two_walks_into_the_context,
)

LISTS = ("d_vals", "n_curves", "k_curves", "x_curves", "rmse_vals", "chi2_vals", "fit_nfev_values", "fit_nit_values", "fit_try_values", "fit_fail_values")


def walk(tag: str, **changes) -> dict:
    base = {name: [f"{tag}-{name}-1", f"{tag}-{name}-2"] for name in LISTS}
    base.update(n_valid_side=3, n_refines=2, seed_gate_eval_count=4, seed_gate_kept_count=3, seed_gate_delta_refit_minus_seed=[0.1, 0.2])
    base.update(changes)
    return base


def context(**changes) -> SimpleNamespace:
    ctx = SimpleNamespace(
        **{name: [f"centre-{name}"] for name in LISTS},
        boundary_refine_calls=0,
        seed_gate_eval_count=0,
        seed_gate_kept_count=0,
        seed_gate_deltas=None,
        seed_gate_saturated_global=None,
        seed_gate_auto_escalated_global=None,
        center_seed_gate_eval_count=1,
        center_seed_gate_kept_count=1,
        center_seed_gate_delta_refit_minus_seed=0.3,
    )
    for key, value in changes.items():
        setattr(ctx, key, value)
    return ctx


def merge(ctx, r_plus=None, r_minus=None):
    return _merge_the_two_walks_into_the_context(ctx, r_minus or walk("minus"), r_plus or walk("plus"))


@pytest.mark.parametrize("name", LISTS)
def test_the_larger_d_walk_is_appended_before_the_smaller_d_walk(name):
    ctx = context()
    merge(ctx)
    assert getattr(ctx, name) == [f"centre-{name}", f"plus-{name}-1", f"plus-{name}-2", f"minus-{name}-1", f"minus-{name}-2"]


def test_the_valid_points_of_each_side_are_handed_back_as_integers():
    neg_valid, pos_valid = merge(context(), walk("plus", n_valid_side=7.0), walk("minus", n_valid_side=2.0))
    assert (neg_valid, pos_valid) == (2, 7)
    assert isinstance(neg_valid, int)
    assert isinstance(pos_valid, int)


def test_the_boundary_refinements_are_added():
    ctx = context()
    merge(ctx, walk("plus", n_refines=2), walk("minus", n_refines=5))
    assert ctx.boundary_refine_calls == 7


def test_the_seed_gate_counts_include_the_centre_and_default_to_zero_when_a_walk_has_none():
    ctx = context(center_seed_gate_eval_count=2, center_seed_gate_kept_count=1)
    merge(ctx, walk("plus", seed_gate_eval_count=4, seed_gate_kept_count=3), walk("minus", seed_gate_eval_count=5, seed_gate_kept_count=2))
    assert (ctx.seed_gate_eval_count, ctx.seed_gate_kept_count) == (11, 6)
    bare = context(center_seed_gate_eval_count=2, center_seed_gate_kept_count=1)
    plus, minus = walk("plus"), walk("minus")
    for key in ("seed_gate_eval_count", "seed_gate_kept_count"):
        plus.pop(key)
        minus.pop(key)
    merge(bare, plus, minus)
    assert (bare.seed_gate_eval_count, bare.seed_gate_kept_count) == (2, 1)


def test_the_seed_gate_deltas_are_the_plus_then_the_minus_then_the_centre_when_it_is_finite():
    ctx = context(center_seed_gate_delta_refit_minus_seed=0.3)
    merge(ctx, walk("plus", seed_gate_delta_refit_minus_seed=[0.1]), walk("minus", seed_gate_delta_refit_minus_seed=[0.2, 0.25]))
    np.testing.assert_allclose(ctx.seed_gate_deltas, [0.1, 0.2, 0.25, 0.3])
    nan_centre = context(center_seed_gate_delta_refit_minus_seed=float("nan"))
    merge(nan_centre, walk("plus", seed_gate_delta_refit_minus_seed=[0.1]), walk("minus", seed_gate_delta_refit_minus_seed=[]))
    np.testing.assert_allclose(nan_centre.seed_gate_deltas, [0.1])


@pytest.mark.parametrize(
    ("plus", "minus", "centre", "saturated"),
    [
        ((4, 4), (4, 4), (0, 0), True),
        ((3, 2), (3, 1), (0, 0), False),
        ((2, 2), (2, 1), (0, 0), False),
        ((0, 0), (0, 0), (0, 0), False),
        ((2, 2), (2, 2), (1, 0), True),
        ((2, 2), (2, 2), (0, 0), False),
    ],
    ids=["all kept", "exactly half", "three quarters but four evaluations", "no evaluation", "the centre's evaluation makes it five", "four evaluations"],
)
def test_the_seed_gate_is_saturated_above_half_kept_on_five_evaluations_or_more(plus, minus, centre, saturated):
    ctx = context(center_seed_gate_eval_count=centre[0], center_seed_gate_kept_count=centre[1])
    merge(
        ctx,
        walk("plus", seed_gate_eval_count=plus[0], seed_gate_kept_count=plus[1]),
        walk("minus", seed_gate_eval_count=minus[0], seed_gate_kept_count=minus[1]),
    )
    assert bool(ctx.seed_gate_saturated_global) is saturated


@pytest.fixture
def warnings(monkeypatch):
    """The module's logger replaced by a recorder (the application's own logger does not propagate to pytest's handler)."""
    seen: list[str] = []
    monkeypatch.setattr(module, "log", SimpleNamespace(warning=lambda fmt, *args, **kwargs: seen.append(fmt % args if args else fmt)))
    return seen


def test_a_saturated_seed_gate_warns_with_the_share_kept(warnings):
    ctx = context(center_seed_gate_eval_count=0, center_seed_gate_kept_count=0)
    merge(ctx, walk("plus", seed_gate_eval_count=4, seed_gate_kept_count=4), walk("minus", seed_gate_eval_count=4, seed_gate_kept_count=4))
    assert len(warnings) == 1
    assert "SATURATED (100% kept" in warnings[0]


def test_an_unsaturated_seed_gate_does_not_warn(warnings):
    ctx = context()
    merge(ctx, walk("plus", seed_gate_eval_count=4, seed_gate_kept_count=1), walk("minus", seed_gate_eval_count=4, seed_gate_kept_count=1))
    assert warnings == []


@pytest.mark.parametrize(("plus", "minus", "expected"), [(True, False, True), (False, True, True), (False, False, False), (True, True, True)])
def test_the_global_auto_escalation_is_either_walks(plus, minus, expected):
    ctx = context()
    merge(ctx, walk("plus", seed_gate_auto_escalated=plus), walk("minus", seed_gate_auto_escalated=minus))
    assert ctx.seed_gate_auto_escalated_global is expected


def test_the_corridor_function_hands_the_merge_its_two_walks():
    assert "neg_valid, pos_valid = _merge_the_two_walks_into_the_context(ctx, r_minus, r_plus)" in inspect.getsource(module.compute_profiled_corridors_by_d)


# --- the rebuild ---------------------------------------------------------------------------------------------------------------------


def filled_context() -> CorridorProfileContext:
    """A real context whose every field is a distinct object, so that a missed or crossed field shows."""
    return CorridorProfileContext(**{field.name: object() for field in dataclasses.fields(CorridorProfileContext)})


def test_the_rebuilt_context_is_a_new_object_that_carries_every_field_by_reference():
    old = filled_context()
    new = _context_of_the_accepted_corridor(old)
    assert new is not old
    assert isinstance(new, CorridorProfileContext)
    for field in dataclasses.fields(CorridorProfileContext):
        assert getattr(new, field.name) is getattr(old, field.name), field.name


def test_the_corridor_function_ends_with_the_rebuilt_context():
    source = inspect.getsource(module.compute_profiled_corridors_by_d)
    assert "ctx = _context_of_the_accepted_corridor(ctx)" in source
    assert source.index("ctx = _context_of_the_accepted_corridor(ctx)") < source.index("return _package_corridor_results(ctx)")
