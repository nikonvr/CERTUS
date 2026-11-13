"""Levenberg-Marquardt polisher with Nielsen damping and box bounds, for DESIGN's least-squares merit.

Measured on 2026-11-13 (reports/audits_2026-11-13/bilan.md §3.2): on the 50/50 beamsplitter of Tikhonravov et al.
(33 layers, 1 601 wavelengths), started 1 % or 5 % away from a record, it reached the local optimum in 22 to 48
evaluations of residuals and Jacobian, every time; L-BFGS-B never did in 800 to 2 700, stopping 20 % to 60 % above it.
On the 101-layer three-line filter it was slower than L-BFGS-B: it is an option, not a replacement.

The damping follows Nielsen (1999), as the RICL engine does (reports/RICL_ultimate_2026-11-05/engine.py::lm): the
ratio of the actual to the predicted decrease scales mu; a refused step doubles the growth factor. Bounds are handled
by an active set: a variable on a bound whose gradient pushes it out is held there for the iteration, and the step is
clipped into the box. A step is taken only when it lowers the cost, so the result is never worse than the start.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

ResJac = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]

#: Three accepted steps in a row that lower the cost by less than this fraction end the polish.
FTOL = 1e-13


def lm_nielsen(
    res_jac: ResJac,
    x0: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    max_iter: int = 300,
    ftol: float = FTOL,
) -> tuple[np.ndarray, float, int]:
    """Polish `x0` inside [lower, upper]; return (x, cost = r @ r, number of residual evaluations).

    `res_jac(x)` returns the residuals r (m,) and their Jacobian (m, n). `max_iter` bounds the iterations, each of
    which evaluates the residuals once.
    """
    lo = np.asarray(lower, dtype=np.float64)
    hi = np.asarray(upper, dtype=np.float64)
    x = np.clip(np.asarray(x0, dtype=np.float64), lo, hi)
    r, jac = res_jac(x)
    f = float(r @ r)
    n_eval = 1
    if not np.isfinite(f):
        return x, f, n_eval
    mu, nu, small = 1e-3, 2.0, 0
    n = len(x)
    for _ in range(int(max_iter)):
        g = jac.T @ r
        a = jac.T @ jac
        da = np.diag(a).copy()
        held = ((x <= lo + 1e-12) & (g > 0.0)) | ((x >= hi - 1e-12) & (g < 0.0))
        free = np.flatnonzero(~held)
        if free.size == 0:
            break
        b = a[np.ix_(free, free)].copy()
        b[np.diag_indices_from(b)] += mu * (da[free] + 1e-12 * max(float(da.max()), 1e-300))
        try:
            step_free = np.linalg.solve(b, -g[free])
        except np.linalg.LinAlgError:
            mu *= nu
            nu *= 2.0
            continue
        step = np.zeros(n)
        step[free] = step_free
        xn = np.clip(x + step, lo, hi)
        dx = xn - x
        if not np.any(dx):
            break
        predicted = -(2.0 * float(dx @ g) + float(dx @ a @ dx))
        rn, jn = res_jac(xn)
        n_eval += 1
        fn = float(rn @ rn)
        if np.isfinite(fn) and fn < f and predicted > 0.0:
            rho = (f - fn) / predicted
            gain = (f - fn) / f if f > 0.0 else 0.0
            x, r, jac, f = xn, rn, jn, fn
            mu *= max(1.0 / 3.0, 1.0 - (2.0 * rho - 1.0) ** 3)
            nu = 2.0
            small = small + 1 if gain < ftol else 0
            if small >= 3 or f == 0.0:
                break
        else:
            mu *= nu
            nu *= 2.0
            if mu > 1e16:
                break
    return x, f, n_eval


#: Iterations granted to one polish of the memetic stage (the 50/50 beamsplitter needed 22 to 182).
MEMETIC_LM_MAX_ITER = 300
#: The residuals must reproduce the memetic cost to this relative precision, or the polisher is not used.
COST_AGREEMENT_RTOL = 1e-8

Polisher = Callable[[np.ndarray, int], tuple[np.ndarray, float]]


def build_memetic_lm_polisher(
    cost_and_grad: Callable[[np.ndarray], tuple[float, np.ndarray]],
    *,
    fast_ctx: dict | None,
    ep_full: np.ndarray,
    var_idx: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    bounds: np.ndarray,
    min_d: float,
    probe: np.ndarray,
    qwot_max: float | None = None,
    q_per_nm: np.ndarray | None = None,
    qwot_penalty: float = 0.0,
    after_lbfgs: bool = False,
) -> tuple[Polisher | None, str]:
    """The polisher of the memetic stage of DESIGN by Levenberg-Marquardt, or (None, why it cannot be used).

    The residuals come from the normal-incidence lossless kernel of the Gauss-Newton refinement (ALG-07), with one
    more residual for the ceiling on total QWOT. They are trusted only if, at `probe`, their squared sum equals the
    memetic cost `cost_and_grad` to COST_AGREEMENT_RTOL: otherwise the two would optimize different merits. Each
    polish returns the memetic cost of its result, so the population is judged as before.

    `after_lbfgs` (choice `lbfgs_then_lm`): L-BFGS-B first, as before, then Levenberg-Marquardt from its result. Never
    worse than L-BFGS-B alone; measured on 2026-11-13 it was the only choice at least as good as L-BFGS-B on both the
    50/50 beamsplitter and the three-line filter (audits 2026-11-13 §3.2).
    """
    from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel

    if fast_ctx is None or not fast_ctx.get("use_real_approx"):
        return None, "it needs normal incidence and real indices (the fast lossless context)"
    lo = np.asarray(bounds, dtype=np.float64)[:, 0]
    hi = np.asarray(bounds, dtype=np.float64)[:, 1]
    if np.any(lo < min_d):
        return None, f"a layer may go under {min_d:g} nm, where the memetic cost counts it as absent"
    tv = np.asarray(tgt_vals, dtype=np.float64)
    tw = np.asarray(tgt_weights, dtype=np.float64)
    valid = (tw > 0.0) & np.isfinite(tv)
    w_sum = float(np.sum(tw[valid]))
    if w_sum <= 0.0 or len(tv) != len(fast_ctx["k0_wls"]):
        return None, "its targets do not match the fast context"
    sqrt_w = np.zeros(len(tw))
    sqrt_w[valid] = np.sqrt(tw[valid] / w_sum)
    tv = np.where(valid, tv, 0.0)
    idx = np.asarray(var_idx, dtype=np.int64)
    base = np.asarray(ep_full, dtype=np.float64).copy()
    root_p = float(np.sqrt(qwot_penalty)) if qwot_max is not None else 0.0

    def res_jac(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ep = base.copy()
        ep[idx] = x
        r, j, _c = _res_jac_lossless_normal_kernel(
            ep, fast_ctx["n_layers_real"], fast_ctx["inv_n_layers_real"], fast_ctx["n_sub_real"], fast_ctx["k0_wls"],
            bool(fast_ctx.get("has_back_calc", False)), fast_ctx["rb_prime"], fast_ctx["tb"], tv, sqrt_w, idx)
        if qwot_max is None:
            return r, j
        excess = float(q_per_nm @ x) - float(qwot_max)
        on = excess > 0.0
        return (np.append(r, root_p * excess if on else 0.0),
                np.vstack((j, (root_p * q_per_nm if on else np.zeros(len(x)))[None, :])))

    p = np.clip(np.asarray(probe, dtype=np.float64), lo, hi)
    r0, _j0 = res_jac(p)
    c0 = float(cost_and_grad(p)[0])
    if not np.isclose(float(r0 @ r0), c0, rtol=COST_AGREEMENT_RTOL, atol=0.0):
        return None, f"its residuals give {float(r0 @ r0):.10e} where the memetic cost is {c0:.10e}"

    def polisher(x: np.ndarray, maxiter: int) -> tuple[np.ndarray, float]:
        if after_lbfgs:
            import scipy.optimize

            res = scipy.optimize.minimize(lambda v: cost_and_grad(np.ascontiguousarray(v, dtype=np.float64)),
                                          np.clip(x, lo, hi), jac=True, method="L-BFGS-B",
                                          bounds=list(zip(lo, hi, strict=True)),
                                          options={"maxiter": int(maxiter), "ftol": 1e-15, "gtol": 1e-12})
            x = np.asarray(res.x, dtype=np.float64)
        xs, _f, _n = lm_nielsen(res_jac, x, lo, hi, max_iter=min(int(maxiter), MEMETIC_LM_MAX_ITER))
        return xs, float(cost_and_grad(xs)[0])

    return polisher, ""
