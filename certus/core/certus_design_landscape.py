"""Distance between two designs and merit-function barrier between them (2026-10-29).

Ported from the study scripts ``reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_v2/design_distance.py`` and
``barrier.py``; nothing here runs unless the user asks for it (no effect on the optimization path).

``align_designs``: a design is the sequence of its layers (material, optical thickness), layer 0 next to the substrate.
Two designs, with any numbers of layers, are aligned by dynamic programming (Needleman-Wunsch, J. Mol. Biol. 48, 443,
1970, semi-global) with the moves that keep the index profile continuous:
  - match: a layer of A against a layer of B of the same material, cost |t_a - t_b|;
  - gap: a layer present in one design only, cost its optical thickness;
  - merge: three layers m, x, m of one design against one layer m of the other (x is a needle), cost
    |t1 + t3 - u| + t_x;
  - unmatched ends (e.g. an impedance-matching section at the substrate or at the air side): the first ``free_nm`` of
    optical thickness of each unmatched end are free, the rest costs its optical thickness. With ``free_nm`` = 0 the
    cost is a distance between index profiles up to merges; ``free_nm`` > 0 measures the similarity of the cores.
The distance is the cost in nm of optical thickness; ``fraction`` divides it by the mean TOT of the two designs.

``aligned_path`` writes both designs in one superset sequence: a matched pair is one layer going from t_a to t_b, a
gap layer shrinks to (or grows from) zero, a merge keeps its two outer layers (their sum going to u, in proportion) and
shrinks the needle to zero. Zero-thickness layers and adjacent layers of one material change nothing optically, so
the superset at s = 0 is design A and at s = 1 design B.

``mf_barrier``: the straight path between the two ends gives an upper bound of the RMSE barrier; the simplified string
method (E, Ren, Vanden-Eijnden, J. Chem. Phys. 126, 164103, 2007) relaxes it towards the minimum-energy path: every
interior image takes a gradient step on the MSE, then the images are redistributed at equal arc length; the ends stay
fixed. The highest RMSE on the relaxed path is an upper bound of the true pass height (one class of paths only).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

LayerOT = tuple[str, float]  # (material, optical thickness in nm)


@dataclass(frozen=True)
class Alignment:
    """Best alignment of two designs: cost (nm of optical thickness), cost / mean TOT, moves, first aligned layers.

    ``moves`` holds (kind, a_from, a_to, b_from, b_to), kind in "match", "gap A", "gap B", "merge A", "merge B"; the
    layers a[a_from:a_to] are paired with b[b_from:b_to]. ``start`` = (i0, j0): a[:i0] and b[:j0] are the unmatched
    substrate-side sections.
    """

    cost_nm: float
    fraction: float
    moves: tuple[tuple[str, int, int, int, int], ...]
    start: tuple[int, int]


def optical_layers(materials: Sequence[str], ep: np.ndarray, n_real: np.ndarray) -> list[LayerOT]:
    """(material, optical thickness n_i * d_i) of each layer; ``n_real``: real index of each layer at the reference
    wavelength."""
    ep = np.asarray(ep, dtype=np.float64)
    n_real = np.asarray(n_real, dtype=np.float64)
    if not len(materials) == ep.size == n_real.size:
        raise ValueError("one material, one thickness and one index per layer")
    return [(str(m), float(n * d)) for m, d, n in zip(materials, ep, n_real, strict=True)]


def align_designs(a: Sequence[LayerOT], b: Sequence[LayerOT], free_nm: float = 0.0) -> Alignment:
    """Best alignment of designs ``a`` and ``b``; dp[i, j] is the cost of aligning a[:i] with b[:j]."""
    na, nb = len(a), len(b)
    inf = float("inf")
    dp = np.full((na + 1, nb + 1), inf)
    back: dict[tuple[int, int], tuple[int, int, str]] = {}
    ca = np.concatenate([[0.0], np.cumsum([t for _m, t in a])])
    cb = np.concatenate([[0.0], np.cumsum([t for _m, t in b])])
    dp[0, :] = np.maximum(0.0, cb - free_nm)  # a substrate-side section of B without counterpart
    dp[:, 0] = np.maximum(0.0, ca - free_nm)
    for i in range(1, na + 1):
        ma, ta = a[i - 1]
        for j in range(1, nb + 1):
            mb, tb = b[j - 1]
            best, how = inf, None
            if ma == mb and dp[i - 1, j - 1] + abs(ta - tb) < best:
                best, how = dp[i - 1, j - 1] + abs(ta - tb), (i - 1, j - 1, "match")
            if dp[i - 1, j] + ta < best:
                best, how = dp[i - 1, j] + ta, (i - 1, j, "gap A")
            if dp[i, j - 1] + tb < best:
                best, how = dp[i, j - 1] + tb, (i, j - 1, "gap B")
            if i >= 3 and a[i - 3][0] == ma == mb != a[i - 2][0]:
                c = dp[i - 3, j - 1] + abs(a[i - 3][1] + ta - tb) + a[i - 2][1]
                if c < best:
                    best, how = c, (i - 3, j - 1, "merge A")
            if j >= 3 and b[j - 3][0] == mb == ma != b[j - 2][0]:
                c = dp[i - 1, j - 3] + abs(b[j - 3][1] + tb - ta) + b[j - 2][1]
                if c < best:
                    best, how = c, (i - 1, j - 3, "merge B")
            dp[i, j] = best
            if how is not None:
                back[(i, j)] = how
    # the air-side section of either design may stay unmatched, its first free_nm free
    ends = [(dp[i, nb] + max(0.0, ca[na] - ca[i] - free_nm), i, nb) for i in range(na + 1)]
    ends += [(dp[na, j] + max(0.0, cb[nb] - cb[j] - free_nm), na, j) for j in range(nb + 1)]
    cost, i, j = min(ends)
    moves = []
    while i > 0 and j > 0:
        pi, pj, kind = back[(i, j)]
        moves.append((kind, pi, i, pj, j))
        i, j = pi, pj
    tot = 0.5 * (ca[na] + cb[nb])
    return Alignment(cost_nm=float(cost), fraction=float(cost / tot) if tot > 0 else 0.0, moves=tuple(moves[::-1]),
                     start=(i, j))


@dataclass(frozen=True)
class AlignedPath:
    """Both designs on one superset sequence of materials, in physical thickness (nm).

    ``matched``: the layer is a one-to-one match of the two designs (False for gap layers and the three layers of a
    merge); a thickness box, if any, applies to these layers only.
    """

    materials: tuple[str, ...]
    ep_a: np.ndarray
    ep_b: np.ndarray
    matched: np.ndarray


def aligned_path(a: Sequence[LayerOT], b: Sequence[LayerOT], alignment: Alignment,
                 n_of: Callable[[str], float]) -> AlignedPath:
    """Superset sequence of ``a`` and ``b`` from their ``alignment``; ``n_of(material)`` is the real index used for the
    optical thicknesses (physical thickness = optical / n)."""
    mats: list[str] = []
    xa: list[float] = []
    xb: list[float] = []
    matched: list[bool] = []

    def put(m: str, ta: float, tb: float, both: bool = False) -> None:
        n = float(n_of(m))
        mats.append(m)
        xa.append(ta / n)
        xb.append(tb / n)
        matched.append(both)

    i0, j0 = alignment.start
    for m, t in a[:i0]:  # unmatched substrate-side sections, A then B
        put(m, t, 0.0)
    for m, t in b[:j0]:
        put(m, 0.0, t)
    i, j = i0, j0
    for kind, pi, ci, pj, cj in alignment.moves:
        if kind == "match":
            put(a[pi][0], a[pi][1], b[pj][1], True)
        elif kind == "gap A":
            put(a[pi][0], a[pi][1], 0.0)
        elif kind == "gap B":
            put(b[pj][0], 0.0, b[pj][1])
        elif kind == "merge A":
            (m, t1), (x, tx), (_m, t3) = a[pi:ci]
            u = b[pj][1]
            put(m, t1, u * t1 / (t1 + t3) if t1 + t3 > 0 else 0.5 * u)
            put(x, tx, 0.0)
            put(m, t3, u * t3 / (t1 + t3) if t1 + t3 > 0 else 0.5 * u)
        else:  # merge B
            (m, u1), (x, ux), (_m, u3) = b[pj:cj]
            t = a[pi][1]
            put(m, t * u1 / (u1 + u3) if u1 + u3 > 0 else 0.5 * t, u1)
            put(x, 0.0, ux)
            put(m, t * u3 / (u1 + u3) if u1 + u3 > 0 else 0.5 * t, u3)
        i, j = ci, cj
    for m, t in a[i:]:  # unmatched air-side sections
        put(m, t, 0.0)
    for m, t in b[j:]:
        put(m, 0.0, t)
    return AlignedPath(materials=tuple(mats), ep_a=np.array(xa), ep_b=np.array(xb), matched=np.array(matched))


@dataclass(frozen=True)
class Barrier:
    """RMSE along the straight path and along the relaxed string, from design A (s = 0) to design B (s = 1).

    ``rmse_straight`` and ``rmse_string`` are sampled ``fine`` times per segment between images. ``barrier`` is the
    highest RMSE on the string minus the higher end; ``total_variation`` sums every climb and descent along the string;
    ``local_minima`` counts the interior minima of the sampled string profile. All are upper bounds of the true
    values for the class of paths explored.
    """

    rmse_a: float
    rmse_b: float
    rmse_straight: np.ndarray
    rmse_string: np.ndarray
    path: np.ndarray
    barrier: float
    total_variation: float
    local_minima: int
    iterations: int


def _reparametrize(path: np.ndarray) -> np.ndarray:
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    if arc[-1] <= 0.0:
        return path
    arc /= arc[-1]
    tgt = np.linspace(0.0, 1.0, len(path))
    return np.array([np.interp(tgt, arc, path[:, k]) for k in range(path.shape[1])]).T


def mf_barrier(
    residual_jacobian: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]],
    ep_a: np.ndarray,
    ep_b: np.ndarray,
    *,
    images: int = 33,
    iterations: int = 3000,
    step_nm: float = 0.5,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    fine: int = 8,
    progress: Callable[[int, int], None] | None = None,
    stop: Callable[[], bool] | None = None,
) -> Barrier:
    """RMSE barrier between ``ep_a`` and ``ep_b`` (physical nm, same superset sequence).

    ``residual_jacobian(ep)`` returns the weighted residual vector r (|r|^2 is the MSE) and its Jacobian. Each
    iteration moves every interior image by at most ``step_nm`` along -grad MSE (the step decays by 0.7 every 500
    iterations, down to 0.05 nm), clipped to [lower, upper] (default [0, inf)), then redistributes the images at equal
    arc length.
    """
    ep_a, ep_b = np.asarray(ep_a, dtype=np.float64), np.asarray(ep_b, dtype=np.float64)
    lo = np.zeros(ep_a.size) if lower is None else np.asarray(lower, dtype=np.float64)
    hi = np.full(ep_a.size, np.inf) if upper is None else np.asarray(upper, dtype=np.float64)

    def rmse(x: np.ndarray) -> float:
        r = residual_jacobian(x)[0]
        return float(np.sqrt(r @ r))

    def profile(p: np.ndarray) -> np.ndarray:
        out = [rmse(np.clip((1.0 - f) * p[k] + f * p[k + 1], lo, hi))
               for k in range(len(p) - 1) for f in np.linspace(0.0, 1.0, fine, endpoint=False)]
        out.append(rmse(p[-1]))
        return np.array(out)

    path = np.linspace(ep_a, ep_b, max(3, images))
    straight = profile(path)
    h, done = step_nm, 0
    for it in range(iterations):
        if stop is not None and stop():
            break
        grads = []
        for x in path[1:-1]:
            r, jac = residual_jacobian(x)
            grads.append(2.0 * jac.T @ r)
        g = np.array(grads)
        gmax = float(np.abs(g).max()) if g.size else 0.0
        if gmax > 0.0:
            path[1:-1] = np.clip(path[1:-1] - (h / gmax) * g, lo, hi)
        path = _reparametrize(path)
        done = it + 1
        if done % 500 == 0:
            h = max(0.05, 0.7 * h)
        if progress is not None:
            progress(done, iterations)
    string = profile(path)
    ra, rb = rmse(ep_a), rmse(ep_b)
    inner = string[1:-1]
    minima = int(np.sum((inner < string[:-2]) & (inner < string[2:]))) if string.size > 2 else 0
    return Barrier(rmse_a=ra, rmse_b=rb, rmse_straight=straight, rmse_string=string, path=path,
                   barrier=float(string.max() - max(ra, rb)), total_variation=float(np.abs(np.diff(string)).sum()),
                   local_minima=minima, iterations=done)


def design_residual_jacobian(mats: dict, materials: Sequence[str], wls: np.ndarray,
                             tgts: list) -> Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """Weighted residuals sqrt(w_j / sum w) (T_j - target_j) of DESIGN's cost (front face, normal incidence) and their
    Jacobian for the layer sequence ``materials``.

    Lossless stacks (k = 0 for every layer and the substrate) use the exact analytic Jacobian of the Gauss-Newton
    kernel (``_res_jac_lossless_normal_kernel``); otherwise central differences of 1e-3 nm of
    ``design_residual_function``.
    """
    from certus.core.certus_design_tolerance import design_residual_function
    from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel
    from certus_physics import Layer, prepare_targets_vectorized

    wls = np.ascontiguousarray(np.asarray(wls, dtype=np.float64))
    nk = {name: np.asarray(m.get_nk(wls), dtype=np.complex128) for name, m in mats.items()}
    sub_key = "Substrate" if "Substrate" in nk else next(k for k in nk if k.lower() == "substrate")
    n_layers = np.array([nk[m] for m in materials], dtype=np.complex128).T.reshape(len(wls), len(materials))
    lossless = not np.any(n_layers.imag) and not np.any(nk[sub_key].imag)
    if not lossless:
        residual = design_residual_function(mats, [Layer(m, 0.0) for m in materials], wls, tgts)

        def numeric(ep: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            ep = np.asarray(ep, dtype=np.float64)
            r0 = residual(ep)
            jac = np.empty((r0.size, ep.size))
            for k in range(ep.size):
                e = np.zeros(ep.size)
                e[k] = 1e-3
                jac[:, k] = (residual(ep + e) - residual(np.maximum(ep - e, 0.0))) / (ep[k] + 1e-3 - max(ep[k] - 1e-3, 0.0))
            return r0, jac

        return numeric

    tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
    tgt_vals, tgt_weights = np.asarray(tgt_vals, dtype=np.float64), np.asarray(tgt_weights, dtype=np.float64)
    valid = (tgt_weights > 0) & np.isfinite(tgt_vals)
    w = np.where(valid, tgt_weights, 0.0)
    sqrt_w = np.ascontiguousarray(np.sqrt(w / max(float(w.sum()), 1e-300)))
    tgt = np.ascontiguousarray(np.where(valid, tgt_vals, 0.0))
    n_real = np.ascontiguousarray(n_layers.real)
    inv_n = np.ascontiguousarray(1.0 / n_real)
    n_sub = np.ascontiguousarray(nk[sub_key].real)
    k0 = np.ascontiguousarray(2.0 * np.pi / wls)
    zeros, ones = np.zeros(len(wls)), np.ones(len(wls))
    var_idx = np.arange(len(materials), dtype=np.int64)

    def exact(ep: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        res, jac, _cost = _res_jac_lossless_normal_kernel(
            np.ascontiguousarray(ep, dtype=np.float64), n_real, inv_n, n_sub, k0, False, zeros, ones, tgt, sqrt_w,
            var_idx)
        return res, jac

    return exact
