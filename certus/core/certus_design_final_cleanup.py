"""Final cleanup of a DESIGN result: no thin layer is left, and the design is polished above its floors.

The 5 nm rule removed every layer under its floor at once, without re-optimizing: one layer lost took a 34-layer
design from RMSE 0.000161 to 0.001035 (reports/DESIGN_bs5050_2026-10-22/journal.md). Here each thin layer is
treated alone, the thinnest first: the design is polished with the layer REMOVED (neighbours of one material
merged) and with the layer RAISED to its floor, and the better of the two is kept. When no variable layer is under
its floor, the whole design is polished once more with the floors as lower bounds.

No Qt, no window: the cost comes from a factory, `make_cost(materials)`, which returns
`cost_and_grad(ep, var_idx) -> (cost, gradient over var_idx)`. `design_cost_factory` builds the one of DESIGN.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from certus.core.certus_design_cost_context import DesignCostContext, design_layer_indices

#: Lower bound of a layer still under its floor while another is treated: it will have its own turn.
FREE_LOWER_BOUND_NM = 0.05
#: The thinnest a layer may be for the cost kernel (below it the kernel returns its cliff value).
KERNEL_MIN_THICKNESS_NM = 0.01

CostAndGrad = Callable[[np.ndarray, np.ndarray], tuple[float, np.ndarray]]


@dataclass(frozen=True)
class CleanupStep:
    """What happened to one thin layer: `removed` or `raised`, and what each choice cost after its polish."""

    action: str
    material: str
    thickness: float
    cost_before: float
    cost_removed: float | None  # None: the layer could not be removed (the last layer of the stack)
    cost_raised: float


@dataclass
class CleanupResult:
    materials: list[str]
    ep: np.ndarray
    var: list[bool]
    #: For each final layer, the index it had in the stack given at the start (a merged layer keeps the first).
    origin: list[int]
    cost_start: float
    cost: float
    steps: list[CleanupStep] = field(default_factory=list)
    #: Final indices of the layers under their floor that the operator fixed: they are left as they are.
    kept_fixed: list[int] = field(default_factory=list)


def _polish(
    cost_and_grad: CostAndGrad, ep: np.ndarray, var: Sequence[bool], lower: np.ndarray, max_iter: int
) -> tuple[np.ndarray, float]:
    """L-BFGS-B over the variable layers, each at or above `lower`; never returns a design worse than `ep`."""
    import scipy.optimize

    var_idx = np.array([i for i, v in enumerate(var) if v], dtype=np.int64)
    full = np.asarray(ep, dtype=np.float64).copy()
    if len(var_idx) == 0:
        return full, float(cost_and_grad(full, var_idx)[0])
    full[var_idx] = np.maximum(full[var_idx], lower[var_idx])
    start = full.copy()
    cost_start = float(cost_and_grad(start, var_idx)[0])
    bounds = [(float(lower[i]), float(max(2.0 * start[i], 2000.0))) for i in var_idx]

    def objective(x_var: np.ndarray) -> tuple[float, np.ndarray]:
        full[var_idx] = x_var
        cost, grad = cost_and_grad(full, var_idx)
        return float(cost), np.asarray(grad, dtype=np.float64)

    result = scipy.optimize.minimize(
        objective, start[var_idx], method="L-BFGS-B", jac=True, bounds=bounds,
        options={"maxiter": int(max_iter), "ftol": 1e-15, "gtol": 1e-12},
    )
    if not np.isfinite(result.fun) or result.fun >= cost_start:
        return start, cost_start
    polished = start.copy()
    polished[var_idx] = result.x
    return polished, float(result.fun)


def _without_layer(
    materials: list[str], ep: np.ndarray, var: list[bool], origin: list[int], index: int
) -> tuple[list[str], np.ndarray, list[bool], list[int]]:
    """The stack without layer `index`; its two neighbours become one layer when they are of one material."""
    mats = materials[:index] + materials[index + 1:]
    d = np.delete(ep, index)
    v = var[:index] + var[index + 1:]
    o = origin[:index] + origin[index + 1:]
    if 0 < index < len(mats) and mats[index - 1] == mats[index]:
        d[index - 1] += d[index]
        # A merged layer is variable only when both halves were: the operator's fixed thickness is not re-optimized.
        v[index - 1] = v[index - 1] and v[index]
        mats.pop(index)
        d = np.delete(d, index)
        v.pop(index)
        o.pop(index)
    return mats, d, v, o


def _lower_bounds(ep: np.ndarray, floor: np.ndarray) -> np.ndarray:
    """A layer at or above its floor stays there; one still under it moves freely until its own turn."""
    return np.where(ep >= floor, floor, FREE_LOWER_BOUND_NM)


def final_cleanup(
    materials: Sequence[str],
    ep: np.ndarray,
    var: Sequence[bool],
    floor_of: Callable[[str], float],
    make_cost: Callable[[Sequence[str]], CostAndGrad],
    *,
    max_iter: int = 500,
) -> CleanupResult:
    """Remove or raise every variable layer under its floor, the thinnest first, then polish above the floors.

    `floor_of(material)` is the least final thickness of a layer of that material, in nm. A layer the operator
    fixed (`var` False) is never touched. Each step leaves one thin layer fewer, and a layer at or above its floor
    never goes back under it (it is a lower bound of every polish): the loop ends.
    """
    mats, d, v = list(materials), np.asarray(ep, dtype=np.float64).copy(), [bool(x) for x in var]
    origin = list(range(len(mats)))
    all_idx = np.arange(len(d), dtype=np.int64)
    cost_start = float(make_cost(mats)(d, all_idx[:0])[0]) if len(d) else 0.0
    cost = cost_start
    steps: list[CleanupStep] = []

    for _ in range(len(mats)):  # at most one step per layer of the start
        floor = np.array([float(floor_of(m)) for m in mats])
        thin = [i for i in range(len(d)) if v[i] and d[i] < floor[i]]
        if not thin:
            break
        i = min(thin, key=lambda k: d[k])

        raised = d.copy()
        raised[i] = floor[i]
        raised, cost_raised = _polish(make_cost(mats), raised, v, _lower_bounds(raised, floor), max_iter)

        cost_removed = None
        if len(mats) > 1:
            r_mats, r_d, r_v, r_o = _without_layer(mats, d, v, origin, i)
            r_floor = np.array([float(floor_of(m)) for m in r_mats])
            r_d, cost_removed = _polish(make_cost(r_mats), r_d, r_v, _lower_bounds(r_d, r_floor), max_iter)

        remove = cost_removed is not None and cost_removed <= cost_raised  # a tie goes to the fewer layers
        steps.append(CleanupStep("removed" if remove else "raised", mats[i], float(d[i]), cost, cost_removed, cost_raised))
        if remove:
            mats, d, v, origin, cost = r_mats, r_d, r_v, r_o, float(cost_removed)
        else:
            d, cost = raised, cost_raised

    floor = np.array([float(floor_of(m)) for m in mats])
    if len(d):
        d, cost = _polish(make_cost(mats), d, v, _lower_bounds(d, floor), max_iter)
    kept_fixed = [i for i in range(len(d)) if not v[i] and d[i] < floor[i]]
    return CleanupResult(mats, d, v, origin, cost_start, cost, steps, kept_fixed)


def design_cost_factory(context: DesignCostContext) -> Callable[[Sequence[str]], CostAndGrad]:
    """The cost of DESIGN at normal incidence (its analytic gradient kernel) for any layout of the same materials."""
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

    values, weights = context.normal_targets()

    def make_cost(materials: Sequence[str]) -> CostAndGrad:
        n_layers_t = design_layer_indices(context.mats_nk, materials)

        def cost_and_grad(ep: np.ndarray, var_idx: np.ndarray) -> tuple[float, np.ndarray]:
            cost, grad = compute_gradient_all_layers_analytic(
                np.ascontiguousarray(ep, dtype=np.float64), n_layers_t, context.n_sub, context.wls, values, weights,
                KERNEL_MIN_THICKNESS_NM, context.has_back_calc, context.n_back, context.d_back,
                np.asarray(var_idx, dtype=np.int64), substrate_thickness_nm=context.substrate_thickness_nm,
            )
            return float(cost), np.asarray(grad, dtype=np.float64)

        return cost_and_grad

    return make_cost


def lbfgsb_polish(
    ep_full: np.ndarray,
    var_idx: np.ndarray,
    x0: np.ndarray,
    bounds: Sequence[tuple[float, float]],
    context: DesignCostContext,
    *,
    maxiter: int,
    ftol: float,
) -> tuple[object, CostAndGrad]:
    """L-BFGS-B on the thicknesses ``var_idx`` of ``ep_full`` with DESIGN's analytic gradient at normal incidence.

    Moved out of the DESIGN window (CLAUDE.md section 8): the re-polish after the 5 nm rule and the trial polish of a
    pruned layer. Returns the SciPy result and the cost function, whose ``(cost, gradient)`` the caller may evaluate
    again (for the start point, say). ``ep_full`` is copied; the copy carries the fixed thicknesses.
    """
    import scipy.optimize

    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

    tgt_vals, tgt_weights = context.normal_targets()
    full = np.array(ep_full, dtype=np.float64, copy=True)

    def cost_and_grad(x_var: np.ndarray) -> tuple[float, np.ndarray]:
        full[var_idx] = x_var
        c, g = compute_gradient_all_layers_analytic(
            full, context.n_front, context.n_sub, context.wls, tgt_vals, tgt_weights, KERNEL_MIN_THICKNESS_NM,
            context.has_back_calc, context.n_back, context.d_back, var_idx,
            substrate_thickness_nm=context.substrate_thickness_nm,
        )
        return float(c), np.asarray(g, dtype=np.float64)

    res = scipy.optimize.minimize(
        cost_and_grad, x0, method="L-BFGS-B", jac=True, bounds=bounds, options={"maxiter": maxiter, "ftol": ftol}
    )
    return res, cost_and_grad
