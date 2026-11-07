"""DRAFT (2026-11-05 night) of the headless core of DESIGN's future "Resources" tool, to move to
certus/core/certus_design_resources.py after the 48 h campaign (owner's decision), with its worker, tab and tests.

Scope: lossless layers at normal incidence, any number of materials with real dispersion n(lambda), optional
incoherent back surface, DESIGN targets (linear between tmin at lmin and tmax at lmax, weight w), through the
existing kernel `design_fast_gauss_newton._res_jac_lossless_normal_kernel` (residuals and exact Jacobian): no new
transfer-matrix formula. Optical thickness uses the real index at the reference wavelength, as the Compare tab.

Provides: refinement with bounds and an exact total-optical-thickness equality (Levenberg-Marquardt with one
Lagrange multiplier), exact perturbation function, needle insertion, removal with optical thickness kept, cleaning
to a floor, deep cleaner to a layer cap, the evolution step of Trubetskov (AO 59, A75, 2020), and the dense sweeps
over total optical thickness (dynamic programme) and over the number of layers. Every long routine takes a stop
callable and a progress callable; nothing runs at import.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel


@dataclass
class ResourceProblem:
    """Frozen spectral problem: wavelengths, target, weights, material indices and substrate terms."""

    wls: np.ndarray
    target: np.ndarray
    weights: np.ndarray
    indices: dict[str, np.ndarray]  # real index of each material on wls
    ref_index: dict[str, float]  # real index at the reference wavelength (optical thickness)
    n_sub: np.ndarray
    has_back: bool = False
    rb_prime: np.ndarray | None = None
    tb: np.ndarray | None = None
    k0: np.ndarray = field(init=False)
    sqrt_w: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.wls = np.ascontiguousarray(self.wls, dtype=np.float64)
        self.target = np.ascontiguousarray(self.target, dtype=np.float64)
        w = np.asarray(self.weights, dtype=np.float64)
        if w.shape != self.wls.shape or np.any(w < 0) or w.sum() <= 0:
            raise ValueError("weights must be non-negative, one per wavelength, with a positive sum")
        self.sqrt_w = np.ascontiguousarray(np.sqrt(w / w.sum()))
        self.k0 = np.ascontiguousarray(2.0 * np.pi / self.wls)
        self.n_sub = np.ascontiguousarray(self.n_sub, dtype=np.float64)
        if self.rb_prime is None:
            self.rb_prime = np.zeros(len(self.wls))
        if self.tb is None:
            self.tb = np.ones(len(self.wls))
        for name, n in self.indices.items():
            if np.shape(n) != self.wls.shape or not np.all(np.isfinite(n)) or np.any(np.asarray(n) <= 0):
                raise ValueError(f"{name}: one positive real index per wavelength is required")

    def _arrays(self, seq: Sequence[str]):
        n_real = np.ascontiguousarray(np.column_stack([self.indices[m] for m in seq]))
        return n_real, np.ascontiguousarray(1.0 / n_real)

    def res_jac(self, seq: Sequence[str], d: np.ndarray):
        n_real, inv_n = self._arrays(seq)
        r, j, _c = _res_jac_lossless_normal_kernel(np.ascontiguousarray(d, dtype=np.float64), n_real, inv_n,
                                                   self.n_sub, self.k0, self.has_back, self.rb_prime, self.tb,
                                                   self.target, self.sqrt_w, np.arange(len(seq), dtype=np.int64))
        return r, j

    def rmse(self, seq: Sequence[str], d: np.ndarray) -> float:
        r, _j = self.res_jac(seq, d)
        return math.sqrt(float(r @ r))

    def ot_vector(self, seq: Sequence[str]) -> np.ndarray:
        return np.array([self.ref_index[m] for m in seq])

    def total_ot(self, seq: Sequence[str], d: np.ndarray) -> float:
        return float(self.ot_vector(seq) @ np.asarray(d))


def target_samples(bands: Sequence[tuple[float, float, float, float, float]], step_nm: float):
    """Wavelengths, target values and weights of DESIGN targets (lmin, lmax, tmin, tmax, w), linear in each band,
    sampled every step_nm with both ends included; equal weight per point within a band."""
    wl, tg, wt = [], [], []
    for lmin, lmax, tmin, tmax, w in bands:
        if not (np.isfinite(lmin) and np.isfinite(lmax) and lmax >= lmin and w >= 0):
            raise ValueError("invalid target band")
        n = max(1, round((lmax - lmin) / step_nm)) + 1 if lmax > lmin else 1
        x = np.linspace(lmin, lmax, n)
        wl.append(x)
        tg.append(np.interp(x, [lmin, lmax], [tmin, tmax]) if lmax > lmin else np.full(1, tmin))
        wt.append(np.full(n, float(w)))
    return np.concatenate(wl), np.concatenate(tg), np.concatenate(wt)


# --------------------------------------------------------------------------------------------- refinement


def _fix_tot(x, n, tot, lb, ub):
    for _ in range(4):
        gap = tot - float(n @ x)
        if abs(gap) <= 1e-9 * tot:
            break
        inner = (x > lb + 1e-12) & (x < ub - 1e-12)
        if not inner.any():
            inner = np.ones(len(x), dtype=bool)
        w = np.where(inner, n, 0.0)
        x = np.clip(x + gap * w / float(w @ n), lb, ub)
    return x


def refine(problem: ResourceProblem, seq: Sequence[str], d: np.ndarray, *, tot: float | None = None, lower=0.0,
           upper=np.inf, variable: np.ndarray | None = None, max_iter: int = 400, ftol: float = 1e-13,
           stop: Callable[[], bool] | None = None):
    """Levenberg-Marquardt with Marquardt scaling, active-set bounds and, when tot is given, the exact equality
    sum(n_ref d) = tot (augmented system with one multiplier). Locked layers (variable False) keep their thickness.
    Returns (d, rmse, iterations)."""
    m = len(seq)
    n = problem.ot_vector(seq)
    lb = np.broadcast_to(np.asarray(lower, dtype=np.float64), (m,)).copy()
    ub = np.broadcast_to(np.asarray(upper, dtype=np.float64), (m,)).copy()
    var = np.ones(m, dtype=bool) if variable is None else np.asarray(variable, dtype=bool)
    x = np.clip(np.asarray(d, dtype=np.float64).copy(), lb, ub)
    nv = np.where(var, n, 0.0)  # only variable layers move to meet the imposed total optical thickness
    tot_var = None if tot is None else tot - float(n[~var] @ x[~var])
    if tot_var is not None:
        x = _fix_tot(x, nv, tot_var, np.where(var, lb, x), np.where(var, ub, x))
    r, jac = problem.res_jac(seq, x)
    f = float(r @ r)
    mu, nu, small, it = 1e-3, 2.0, 0, 0
    for it in range(1, max_iter + 1):  # noqa: B007
        if stop is not None and stop():
            break
        g = jac.T @ r
        a = jac.T @ jac
        da = np.diag(a).copy()
        dmax = float(da.max()) if da.size else 1.0
        free = var & ~(((x <= lb + 1e-12) & (g > 0.0)) | ((x >= ub - 1e-12) & (g < 0.0)))
        fi = np.flatnonzero(free)
        if fi.size == 0:
            break
        b = a[np.ix_(fi, fi)].copy()
        b[np.diag_indices_from(b)] += mu * (da[fi] + 1e-12 * dmax)
        try:
            if tot is not None and fi.size > 1:
                k = np.zeros((fi.size + 1, fi.size + 1))
                k[:-1, :-1] = b
                k[:-1, -1] = n[fi]
                k[-1, :-1] = n[fi]
                sf = np.linalg.solve(k, np.concatenate([-g[fi], [0.0]]))[:-1]
            else:
                sf = np.linalg.solve(b, -g[fi])
        except np.linalg.LinAlgError:
            mu *= nu
            nu *= 2.0
            continue
        step = np.zeros(m)
        step[fi] = sf
        xn = np.clip(x + step, lb, ub)
        if tot_var is not None:
            xn = _fix_tot(xn, nv, tot_var, np.where(var, lb, xn), np.where(var, ub, xn))
        dx = xn - x
        pred = -(2.0 * float(dx @ g) + float(dx @ a @ dx))
        rn, jn = problem.res_jac(seq, xn)
        fn = float(rn @ rn)
        if fn < f and pred > 0.0:
            rho = (f - fn) / pred
            gain = (f - fn) / f
            x, r, jac, f = xn, rn, jn, fn
            mu *= max(1.0 / 3.0, 1.0 - (2.0 * rho - 1.0) ** 3)
            nu = 2.0
            small = small + 1 if gain < ftol else 0
            if small >= 3:
                break
        else:
            mu *= nu
            nu *= 2.0
            if mu > 1e16:
                break
    return x, math.sqrt(f), it


# --------------------------------------------------------------------------------------------- structure


def perturbation_function(problem: ResourceProblem, seq: Sequence[str], d: np.ndarray, candidates: Sequence[str],
                          step_nm: float = 2.0):
    """Exact needle perturbation function: d(MSE)/d(delta) of a zero-thickness layer of each candidate material
    every step_nm inside each layer of another material, plus a new layer at either end. One Jacobian call per
    candidate material. Returns [(p, material, layer, z)], layer -1 = substrate side, len(seq) = air side."""
    out = []
    for cand in candidates:
        s2: list[str] = []
        d2: list[float] = []
        where = []
        if seq[0] != cand:
            s2.append(cand)
            d2.append(0.0)
            where.append((0, -1, 0.0))
        for i, mat in enumerate(seq):
            last = 0.0
            if mat != cand:
                for z in np.arange(step_nm / 2, d[i], step_nm):
                    s2 += [mat, cand]
                    d2 += [float(z - last), 0.0]
                    where.append((len(s2) - 1, i, float(z)))
                    last = float(z)
            s2.append(mat)
            d2.append(float(d[i] - last))
        if seq[-1] != cand:
            s2.append(cand)
            d2.append(0.0)
            where.append((len(s2) - 1, len(seq), 0.0))
        if not where:
            continue
        n_real, inv_n = problem._arrays(s2)
        var = np.array([k for k, _i, _z in where], dtype=np.int64)
        r, jac, _c = _res_jac_lossless_normal_kernel(np.array(d2), n_real, inv_n, problem.n_sub, problem.k0,
                                                     problem.has_back, problem.rb_prime, problem.tb, problem.target,
                                                     problem.sqrt_w, var)
        grad = 2.0 * (jac.T @ r)
        out += [(float(grad[q]), cand, i, z) for q, (_k, i, z) in enumerate(where)]
    return out


def insert_needle(seq: Sequence[str], d: np.ndarray, mat: str, i: int, z: float, delta: float):
    seq = list(seq)
    if i == -1:
        return [mat, *seq], np.concatenate([[delta], d])
    if i == len(seq):
        return [*seq, mat], np.concatenate([d, [delta]])
    return [*seq[:i + 1], mat, *seq[i:]], np.concatenate([d[:i], [z, delta, d[i] - z], d[i + 1:]])


def remove_layer(problem: ResourceProblem, seq: Sequence[str], d: np.ndarray, i: int):
    """Remove layer i; its optical thickness goes to a neighbour (the thinner one when both exist), then equal
    neighbours merge. The total optical thickness is kept (Tikhonravov et al., AO 46, 704, 2007)."""
    seq, d = list(seq), np.asarray(d, dtype=np.float64).copy()
    if len(seq) <= 1:
        return seq, d
    ot = problem.ref_index[seq[i]] * d[i]
    nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(seq)]
    j = min(nbs, key=lambda q: d[q])
    d[j] += ot / problem.ref_index[seq[j]]
    del seq[i]
    d = np.delete(d, i)
    return merge(seq, d)


def merge(seq: Sequence[str], d: np.ndarray, thin: float = 0.0):
    s, x = [], []
    for mat, v in zip(seq, np.asarray(d, dtype=np.float64), strict=True):
        if v <= thin and s:
            continue
        if s and s[-1] == mat:
            x[-1] += float(v)
        else:
            s.append(mat)
            x.append(float(v))
    return s, np.array(x)


@dataclass
class Resources:
    """Resource limits of one search: layer cap, imposed total optical thickness (None = free), physical floor."""

    max_layers: int
    tot: float | None = None
    floor_nm: float = 5.0
    max_iter: int = 200


def settle(problem: ResourceProblem, res: Resources, seq, d, stop=None):
    """Refine without floor, remove layers that fall under the floor one at a time (thinnest optical thickness first),
    then refine at the floor."""
    x, r, _ = refine(problem, seq, d, tot=res.tot, max_iter=res.max_iter, stop=stop)
    seq, x = merge(seq, x, 1e-6)
    for _ in range(500):
        thin = np.flatnonzero(x < res.floor_nm * 0.999)
        if thin.size == 0 or len(seq) <= 2 or (stop is not None and stop()):
            break
        k = int(thin[np.argmin(x[thin] * problem.ot_vector(seq)[thin])])
        seq, x = remove_layer(problem, seq, x, k)
        x, r, _ = refine(problem, seq, x, tot=res.tot, max_iter=res.max_iter, stop=stop)
        seq, x = merge(seq, x, 1e-6)
    x, r, _ = refine(problem, seq, x, tot=res.tot, lower=res.floor_nm, max_iter=res.max_iter, stop=stop)
    return list(seq), x, r


def clean_to_cap(problem: ResourceProblem, res: Resources, seq, d, r, rng: np.random.Generator, width: int = 12,
                 stop=None):
    """Deep cleaner (Trubetskov 2020): while N exceeds the cap, the best single removal after a short refinement."""
    while len(seq) > res.max_layers and not (stop is not None and stop()):
        order = list(np.argsort(problem.ot_vector(seq) * d)[:width])
        extra = rng.choice(len(seq), size=min(4, len(seq)), replace=False)
        best = None
        for i in dict.fromkeys([int(v) for v in order] + [int(v) for v in extra]):
            s2, d2 = remove_layer(problem, seq, d, i)
            x, r2, _ = refine(problem, s2, d2, tot=res.tot, max_iter=60, stop=stop)
            if best is None or r2 < best[2]:
                best = (s2, x, r2)
        seq, d, r = settle(problem, res, best[0], best[1], stop)
    return seq, d, r


def growth_step(problem: ResourceProblem, res: Resources, seq, d, new_tot: float, materials: Sequence[str],
                rng: np.random.Generator, top: int = 4, stop=None):
    """Evolution step of Trubetskov (AO 59, A75, 2020) to an imposed total optical thickness: one layer is thickened
    (or an outer layer of each other material added) by the missing optical thickness; the `top` candidates with the
    lowest unrefined error are refined at new_tot and the best is returned (None if new_tot is not larger)."""
    missing = new_tot - problem.total_ot(seq, d)
    if missing <= 0:
        return None
    cands = []
    for i, mat in enumerate(seq):
        x = d.copy()
        x[i] += missing / problem.ref_index[mat]
        cands.append((problem.rmse(seq, x), list(seq), x))
    for mat in materials:
        if mat != seq[-1]:
            s2, x = [*seq, mat], np.concatenate([d, [missing / problem.ref_index[mat]]])
            cands.append((problem.rmse(s2, x), s2, x))
        if mat != seq[0]:
            s2, x = [mat, *seq], np.concatenate([[missing / problem.ref_index[mat]], d])
            cands.append((problem.rmse(s2, x), s2, x))
    cands.sort(key=lambda t: t[0])
    sub = Resources(res.max_layers, new_tot, res.floor_nm, res.max_iter)
    best = None
    for _e, s2, x in cands[:top]:
        out = clean_to_cap(problem, sub, *settle(problem, sub, s2, x, stop), rng, stop=stop)
        if best is None or out[2] < best[2]:
            best = out
    return best


# --------------------------------------------------------------------------------------------- moves and sweeps


def needle_move(problem: ResourceProblem, res: Resources, seq, d, materials: Sequence[str], rng: np.random.Generator,
                choices: int = 8, stop=None):
    """Insert a needle at one of the deepest minima of the perturbation function (distinct layers, random choice
    biased to the deepest), then settle and clean to the layer cap. None when no needle lowers the error."""
    p = sorted(perturbation_function(problem, seq, d, materials))
    cands, used = [], set()
    for g, mat, i, z in p:
        if g >= 0.0 or len(cands) >= choices:
            break
        if (mat, i) not in used:
            used.add((mat, i))
            cands.append((mat, i, z))
    if not cands:
        return None
    mat, i, z = cands[min(int(len(cands) * rng.random() ** 2), len(cands) - 1)]
    s2, d2 = insert_needle(seq, d, mat, i, z, 0.5)
    return clean_to_cap(problem, res, *settle(problem, res, s2, d2, stop), rng, stop=stop)


def random_move(problem: ResourceProblem, res: Resources, seq, d, materials: Sequence[str], rng: np.random.Generator,
                stop=None):
    """One structural move: needle (+ cleaning), removal then needle, thickness jitter or half-wave change."""
    kind = rng.choice(["needle", "remove", "jitter", "halfwave"], p=[0.4, 0.25, 0.25, 0.1])
    seq, d = list(seq), np.asarray(d, dtype=np.float64).copy()
    if kind == "needle":
        return needle_move(problem, res, seq, d, materials, rng, stop=stop)
    if kind == "remove":
        s2, d2 = remove_layer(problem, seq, d, int(rng.integers(0, len(seq))))
        s2, d2, r2 = settle(problem, res, s2, d2, stop)
        return needle_move(problem, res, s2, d2, materials, rng, stop=stop) or (s2, d2, r2)
    if kind == "jitter":
        d = np.maximum(d * (1.0 + float(rng.choice([0.01, 0.03, 0.1])) * rng.standard_normal(len(d))), 0.1)
    else:
        i = int(rng.integers(0, len(seq)))
        d[i] += 0.5 * float(rng.uniform(problem.wls.min(), problem.wls.max())) / problem.ref_index[seq[i]]
    if res.tot is not None:
        d *= res.tot / problem.total_ot(seq, d)
    return clean_to_cap(problem, res, *settle(problem, res, seq, d, stop), rng, stop=stop)


def sweep_tot(problem: ResourceProblem, grid: Sequence[float], seeds, materials: Sequence[str], *, max_layers: int,
              floor_nm: float, executor, rounds: int = 10, grow_from=(1, 2, 3, 5, 8), grow_top: int = 4,
              moves_per_point: int = 2, seed: int = 0, stop=None, progress=None):
    """Dense curve over total optical thickness: best design with TOT exactly equal to each grid value, N <= cap.
    Each round feeds every point with rescaled neighbours, the evolution step from lower points and random moves.
    `executor` runs the tasks (a thread pool in DESIGN: the kernels release the GIL). Returns {tot: (rmse, seq, d)}."""
    keys = [float(t) for t in grid]
    rng = np.random.default_rng(seed)
    best: dict = {}
    tried: set = set()

    def res_at(t):
        return Resources(max_layers, t, floor_nm)

    def file(out, t) -> bool:
        if out is None:
            return False
        s, x, r = out
        if abs(problem.total_ot(s, x) - t) > 1e-6 * t or np.min(x) < floor_nm * (1 - 1e-9) or len(s) > max_layers:
            return False
        if t not in best or r < best[t][0] * (1 - 1e-10):
            best[t] = (r, list(s), x)
            return True
        return False

    def transfer(s, x, t, sub_seed):
        g = np.random.default_rng(sub_seed)
        x = np.asarray(x) * (t / problem.total_ot(s, x))
        return clean_to_cap(problem, res_at(t), *settle(problem, res_at(t), s, x, stop), g, stop=stop)

    jobs = []
    for s, x in seeds:
        tot = problem.total_ot(s, x)
        near = min(keys, key=lambda k: abs(k - tot))
        jobs.append((near, executor.submit(transfer, list(s), np.asarray(x, dtype=np.float64), near,
                                           int(rng.integers(1 << 31)))))
    for t, f in jobs:
        file(f.result(), t)
    for rnd in range(rounds):
        if stop is not None and stop():
            break
        jobs = []
        for i, t in enumerate(keys):
            for off in (1, -1, 2, -2, 3, -3):
                if 0 <= i + off < len(keys) and keys[i + off] in best:
                    src = keys[i + off]
                    sig = ("t", t, src, best[src][0])
                    if sig not in tried:
                        tried.add(sig)
                        jobs.append((t, executor.submit(transfer, best[src][1], best[src][2], t,
                                                        int(rng.integers(1 << 31)))))
            for off in grow_from:
                if i - off >= 0 and keys[i - off] in best:
                    src = keys[i - off]
                    sig = ("g", t, src, best[src][0])
                    if sig not in tried:
                        tried.add(sig)
                        jobs.append((t, executor.submit(growth_step, problem, Resources(max_layers, None, floor_nm),
                                                        best[src][1], best[src][2], t, materials,
                                                        np.random.default_rng(int(rng.integers(1 << 31))), grow_top,
                                                        stop)))
            if t in best:
                for _ in range(moves_per_point):
                    jobs.append((t, executor.submit(random_move, problem, res_at(t), best[t][1], best[t][2],
                                                    materials, np.random.default_rng(int(rng.integers(1 << 31))),
                                                    stop)))
        improved = sum(file(f.result(), t) for t, f in jobs)
        if progress is not None:
            progress(rnd + 1, improved, dict(best))
    return best


def to_layer_count(problem: ResourceProblem, res: Resources, seq, d, n: int, materials: Sequence[str],
                   rng: np.random.Generator, stop=None):
    """Bring a design to exactly n layers (or as close as the floor allows): needles while too few, deep cleaner
    while too many, each followed by a settle. The result is filed under its actual layer count."""
    free = Resources(10**6, res.tot, res.floor_nm, res.max_iter)
    out = settle(problem, free, list(seq), np.asarray(d, dtype=np.float64), stop)
    for _ in range(12):
        if len(out[0]) >= n or (stop is not None and stop()):
            break
        nxt = needle_move(problem, free, out[0], out[1], materials, rng, stop=stop)
        if nxt is None:
            break
        out = nxt
    cap = Resources(n, res.tot, res.floor_nm, res.max_iter)
    return clean_to_cap(problem, cap, *out, rng, stop=stop)


def sweep_layers(problem: ResourceProblem, counts: Sequence[int], seeds, materials: Sequence[str], *,
                 tot_cap: float | None, floor_nm: float, executor, rounds: int = 10, moves_per_point: int = 2,
                 seed: int = 0, stop=None, progress=None):
    """Dense curve over the number of layers: best design with exactly N layers for every N of `counts`, total
    optical thickness at most tot_cap (refined free, then at the cap when exceeded). Returns {N: (rmse, seq, d)}."""
    keys = [int(k) for k in counts]
    rng = np.random.default_rng(seed)
    best: dict = {}
    tried: set = set()

    def capped(s, x, r, g):
        if tot_cap is not None and problem.total_ot(s, x) > tot_cap * (1 + 1e-9):
            res = Resources(len(s), tot_cap, floor_nm)
            s, x, r = settle(problem, res, s, x * (tot_cap / problem.total_ot(s, x)), stop)
        return s, x, r

    def to_n(s, x, n, sub_seed):
        g = np.random.default_rng(sub_seed)
        return capped(*to_layer_count(problem, Resources(n, None, floor_nm), s, x, n, materials, g, stop), g)

    def move(s, x, n, sub_seed):
        g = np.random.default_rng(sub_seed)
        out = random_move(problem, Resources(n, None, floor_nm), s, x, materials, g, stop)
        return None if out is None else capped(*out, g)

    def file(out) -> bool:
        if out is None:
            return False
        s, x, r = out
        n = len(s)
        if n not in keys or np.min(x) < floor_nm * (1 - 1e-9):
            return False
        if tot_cap is not None and problem.total_ot(s, x) > tot_cap * (1 + 1e-6):
            return False
        if n not in best or r < best[n][0] * (1 - 1e-10):
            best[n] = (r, list(s), x)
            return True
        return False

    jobs = [executor.submit(to_n, list(s), np.asarray(x, dtype=np.float64), min(max(len(s), keys[0]), keys[-1]),
                            int(rng.integers(1 << 31))) for s, x in seeds]
    for f in jobs:
        file(f.result())
    for rnd in range(rounds):
        if stop is not None and stop():
            break
        jobs = []
        for i, n in enumerate(keys):
            for off in (1, -1, 2, -2):
                if 0 <= i + off < len(keys) and keys[i + off] in best:
                    src = keys[i + off]
                    sig = (n, src, best[src][0])
                    if sig not in tried:
                        tried.add(sig)
                        jobs.append(executor.submit(to_n, best[src][1], best[src][2], n, int(rng.integers(1 << 31))))
            if n in best:
                for _ in range(moves_per_point):
                    jobs.append(executor.submit(move, best[n][1], best[n][2], n, int(rng.integers(1 << 31))))
        improved = sum(file(f.result()) for f in jobs)
        if progress is not None:
            progress(rnd + 1, improved, dict(best))
    return best
