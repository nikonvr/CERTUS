"""Memetic search engine for the RICL article (2026-11-05): two-material lossless coatings at normal incidence.

Residuals and exact Jacobian: CERTUS kernel `design_fast_gauss_newton._res_jac_lossless_normal_kernel` (no new
transfer-matrix code, no CERTUS source modified). Records are judged by the independent oracle
`tests/oracle/tmm_reference.py` (Macleod, chap. 2).

Conventions: layer 0 is on the substrate side; thicknesses are physical (nm); OT = n d. Air, normal incidence,
substrate 1.52 without back side, nH = 2.35, nL = 1.45 (problems of Tikhonravov et al. 1996, 2012; Trubetskov 2020).

Local refinement: Levenberg-Marquardt with Marquardt scaling, box bounds by active set and an exact equality on the
total optical thickness (TOT) through a KKT system. Structural moves: needles at the minima of the exact P-function,
removal of a layer (it takes the index of its neighbour, OT kept, Tikhonravov et al. 2007), thin-layer cleaning,
deep cleaner (best removal after refinement, Trubetskov 2020), half-wave changes, crossover, thickness jitter.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "oracle")]

import tmm_reference as oracle  # noqa: E402

from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel  # noqa: E402

N_IDX = {"H": 2.35, "L": 1.45}
N_SUB = 1.52


def other(m: str) -> str:
    return "L" if m == "H" else "H"


THREELINE_BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0),
                   (520, 630, 0.0), (650, 700, 0.0)]


@dataclass
class Problem:
    """Wavelengths, transmittance target and uniform weights; MF scale factor for reports."""

    name: str
    wls: np.ndarray
    tgt: np.ndarray
    scale: float = 100.0
    k0: np.ndarray = field(init=False)
    sqw: np.ndarray = field(init=False)
    nsub: np.ndarray = field(init=False)
    zb: np.ndarray = field(init=False)
    ob: np.ndarray = field(init=False)
    _cache: dict = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.wls = np.ascontiguousarray(self.wls, dtype=np.float64)
        self.tgt = np.ascontiguousarray(self.tgt, dtype=np.float64)
        self.k0 = 2.0 * np.pi / self.wls
        self.sqw = np.full(len(self.wls), math.sqrt(1.0 / len(self.wls)))
        self.nsub = np.full(len(self.wls), N_SUB)
        self.zb = np.zeros(len(self.wls))
        self.ob = np.ones(len(self.wls))

    def arrays(self, seq: str):
        hit = self._cache.get(seq)
        if hit is None:
            if len(self._cache) > 256:  # 2026-11-05 22:00: memory cap (0.5 MB per 120-layer entry, 15 workers)
                self._cache.clear()
            n = np.array([N_IDX[m] for m in seq])
            n_real = np.ascontiguousarray(np.tile(n, (len(self.wls), 1)))
            hit = (n_real, np.ascontiguousarray(1.0 / n_real), np.arange(len(seq), dtype=np.int64))
            self._cache[seq] = hit
        return hit

    def res_jac(self, seq: str, d: np.ndarray):
        n_real, inv_n, var = self.arrays(seq)
        r, j, _c = _res_jac_lossless_normal_kernel(np.ascontiguousarray(d, dtype=np.float64), n_real, inv_n, self.nsub,
                                                   self.k0, False, self.zb, self.ob, self.tgt, self.sqw, var)
        return r, j

    def rmse(self, seq: str, d: np.ndarray) -> float:
        r, _j = self.res_jac(seq, d)
        return float(math.sqrt(r @ r))

    def oracle_rmse(self, seq: str, d: np.ndarray, wls=None, tgt=None) -> float:
        wls = self.wls if wls is None else wls
        tgt = self.tgt if tgt is None else tgt
        n = [complex(N_IDX[m], 0.0) for m in seq]
        t = np.array([oracle.rt_stack(float(w), n, list(map(float, d)), complex(1.0), complex(N_SUB))[1]
                      for w in wls])
        return float(np.sqrt(np.mean((t - tgt) ** 2)))


def threeline(step: float = 1.0) -> Problem:
    """Tikhonravov & Trubetskov 2012 Eq. 1 / Trubetskov 2020: 277 points at 1 nm, band edges included."""
    xs = [np.linspace(a, b, round((b - a) / step) + 1) for a, b, _t in THREELINE_BANDS]
    return Problem("threeline", np.concatenate(xs), np.concatenate([np.full(len(x), t) for x, (_a, _b, t) in
                                                                     zip(xs, THREELINE_BANDS, strict=True)]), 100.0)


def bs5050(points: int = 1601) -> Problem:
    return Problem("bs5050", np.linspace(400.0, 1200.0, points), np.full(points, 0.5), 1.0)


def make_problem(name: str, **kw) -> Problem:
    if name == "threeline":
        return threeline(kw.get("step", 1.0))
    if name == "threeline_fine":  # same bands and targets, resolved grid (0.1 nm: 2761 points), 2026-11-06
        return threeline(kw.get("step", 0.1))
    if name == "bs5050":
        return bs5050(int(kw.get("points", 1601)))
    raise ValueError(name)


def nvec(seq: str) -> np.ndarray:
    return np.array([N_IDX[m] for m in seq])


def total_ot(seq: str, d: np.ndarray) -> float:
    return float(nvec(seq) @ d)


# ----------------------------------------------------------------------------------------------- local refinement


def _fix_tot(x: np.ndarray, n: np.ndarray, tot: float, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:
    """Restore n.x = tot after a clip, moving only the layers strictly inside their bounds (additive along n)."""
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


def lm(prob: Problem, seq: str, d: np.ndarray, tot: float | None = None, lb=None, ub=None, iters: int = 400,
       ftol: float = 1e-13):
    """Levenberg-Marquardt polish. tot: exact equality on the total optical thickness (None = free).
    lb/ub: physical bounds (scalars or arrays). Returns (x, rmse, iterations)."""
    m = len(seq)
    n = nvec(seq)
    lb = np.broadcast_to(np.asarray(0.0 if lb is None else lb, dtype=np.float64), (m,)).copy()
    ub = np.broadcast_to(np.asarray(np.inf if ub is None else ub, dtype=np.float64), (m,)).copy()
    x = np.clip(np.asarray(d, dtype=np.float64).copy(), lb, ub)
    if tot is not None:
        x = _fix_tot(x, n, tot, lb, ub)
    r, jac = prob.res_jac(seq, x)
    f = float(r @ r)
    mu, nu, small = -1.0, 2.0, 0
    it = 0
    for it in range(1, iters + 1):  # noqa: B007
        g = jac.T @ r
        a = jac.T @ jac
        da = np.diag(a).copy()
        dmax = float(da.max()) if da.size else 1.0
        if mu < 0.0:
            mu = 1e-3
        free = ~(((x <= lb + 1e-12) & (g > 0.0)) | ((x >= ub - 1e-12) & (g < 0.0)))
        fi = np.flatnonzero(free)
        if fi.size == 0:
            break
        b = a[np.ix_(fi, fi)].copy()
        b[np.diag_indices_from(b)] += mu * (da[fi] + 1e-12 * dmax)
        try:
            if tot is not None and fi.size > 1:
                nf = n[fi]
                k = np.zeros((fi.size + 1, fi.size + 1))
                k[:-1, :-1] = b
                k[:-1, -1] = nf
                k[-1, :-1] = nf
                sol = np.linalg.solve(k, np.concatenate([-g[fi], [0.0]]))
                sf = sol[:-1]
            else:
                sf = np.linalg.solve(b, -g[fi])
        except np.linalg.LinAlgError:
            mu *= nu
            nu *= 2.0
            continue
        step = np.zeros(m)
        step[fi] = sf
        xn = np.clip(x + step, lb, ub)
        if tot is not None:
            xn = _fix_tot(xn, n, tot, lb, ub)
        dx = xn - x
        pred = -(2.0 * float(dx @ g) + float(dx @ a @ dx))
        rn, jn = prob.res_jac(seq, xn)
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


# ----------------------------------------------------------------------------------------------- structural moves


def p_function(prob: Problem, seq: str, d: np.ndarray, step: float = 2.0):
    """Exact P-function: d(MSE)/d(delta) for a zero-thickness needle of the other material every `step` nm inside each
    layer, plus a new layer at each end (one call of the CERTUS Jacobian kernel). Returns [(p, layer, z)] where layer
    -1 means a new substrate-side layer and len(seq) a new air-side layer."""
    seq2: list[str] = [other(seq[0])]
    d2: list[float] = [0.0]
    where = [(0, -1, 0.0)]
    for i, m in enumerate(seq):
        zs = np.arange(step / 2, d[i], step)
        last = 0.0
        for z in zs:
            seq2 += [m, other(m)]
            d2 += [float(z - last), 0.0]
            where.append((len(seq2) - 1, i, float(z)))
            last = float(z)
        seq2.append(m)
        d2.append(float(d[i] - last))
    seq2.append(other(seq[-1]))
    d2.append(0.0)
    where.append((len(seq2) - 1, len(seq), 0.0))
    s2 = "".join(seq2)
    n = nvec(s2)
    n_real = np.ascontiguousarray(np.tile(n, (len(prob.wls), 1)))
    var = np.array([k for k, _i, _z in where], dtype=np.int64)
    r, jac, _c = _res_jac_lossless_normal_kernel(np.array(d2), n_real, np.ascontiguousarray(1.0 / n_real), prob.nsub,
                                                 prob.k0, False, prob.zb, prob.ob, prob.tgt, prob.sqw, var)
    grad = 2.0 * (jac.T @ r)
    return [(float(grad[q]), i, z) for q, (_k, i, z) in enumerate(where)]


def insert_needle(seq: str, d: np.ndarray, i: int, z: float, delta: float = 0.5):
    if i == -1:
        return other(seq[0]) + seq, np.concatenate([[delta], d])
    if i == len(seq):
        return seq + other(seq[-1]), np.concatenate([d, [delta]])
    return seq[:i + 1] + other(seq[i]) + seq[i:], np.concatenate([d[:i], [z, delta, d[i] - z], d[i + 1:]])


def remove_layer(seq: str, d: np.ndarray, i: int):
    """Remove layer i keeping the total optical thickness: it takes the index of its neighbour (OT kept), then equal
    neighbours merge (Tikhonravov et al., AO 46, 704, 2007)."""
    if len(seq) <= 1:
        return seq, d
    ot = N_IDX[seq[i]] * d[i]
    if i == 0:
        nb = seq[1]
        dd = np.concatenate([[d[1] + ot / N_IDX[nb]], d[2:]])
        return seq[1:], dd
    if i == len(seq) - 1:
        nb = seq[-2]
        dd = np.concatenate([d[:-2], [d[-2] + ot / N_IDX[nb]]])
        return seq[:-1], dd
    nb = seq[i - 1]  # == seq[i + 1] for alternating designs
    if seq[i + 1] != nb:  # not alternating: give the OT to the thinner neighbour side
        dd = d.copy()
        dd[i - 1] += ot / N_IDX[nb]
        return seq[:i] + seq[i + 1:], np.delete(dd, i)
    merged = d[i - 1] + ot / N_IDX[nb] + d[i + 1]
    return seq[:i - 1] + nb + seq[i + 2:], np.concatenate([d[:i - 1], [merged], d[i + 2:]])


def normalize(seq: str, d: np.ndarray, thin: float = 1e-6):
    """Remove layers thinner than `thin` (OT kept by the neighbour) and merge equal neighbours."""
    s, x = seq, np.asarray(d, dtype=np.float64).copy()
    changed = True
    while changed and len(s) > 1:
        changed = False
        k = np.flatnonzero(x < thin)
        if k.size:
            s, x = remove_layer(s, x, int(k[np.argmin(x[k])]))
            changed = True
            continue
        for i in range(len(s) - 1):
            if s[i] == s[i + 1]:
                x = np.concatenate([x[:i], [x[i] + x[i + 1]], x[i + 2:]])
                s = s[:i] + s[i] + s[i + 2:]
                changed = True
                break
    return s, x


@dataclass
class Rules:
    """Resources of a run. tot: imposed TOT (nm) or None; nmax: layer cap; floor: physical minimum (nm);
    otlo/othi: per-layer optical-thickness bounds (fixed-N constrained problem), fixed_seq: alternation imposed."""

    nmax: int = 101
    tot: float | None = None
    floor: float = 5.0
    otlo: float | None = None
    othi: float | None = None
    fixed_seq: str | None = None
    iters: int = 400
    tot_le: bool = False  # True: tot is a cap (refine free, re-refine at the cap only if exceeded)

    def bounds(self, seq: str):
        n = nvec(seq)
        lb = np.full(len(seq), self.floor)
        ub = np.full(len(seq), np.inf)
        if self.otlo is not None:
            lb = np.maximum(lb, self.otlo / n)
        if self.othi is not None:
            ub = self.othi / n
        return lb, ub


def settle(prob: Problem, rules: Rules, seq: str, d: np.ndarray, iters: int | None = None):
    """Refine without floor, remove the layers that fall under the floor one by one (thinnest first, OT kept),
    then refine at the floor: the result respects the floor, the TOT and the per-layer bounds (not yet nmax).
    With rules.tot_le the TOT is a cap: free refinement, then refinement at the cap if the cap is exceeded."""
    if rules.tot_le and rules.tot is not None:
        free = Rules(rules.nmax, None, rules.floor, rules.otlo, rules.othi, rules.fixed_seq, rules.iters)
        s2, x2, r2 = settle(prob, free, seq, d, iters)
        if total_ot(s2, x2) <= rules.tot * (1 + 1e-9):
            return s2, x2, r2
        eq = Rules(rules.nmax, rules.tot, rules.floor, rules.otlo, rules.othi, rules.fixed_seq, rules.iters)
        s3, x3, r3 = settle(prob, eq, s2, x2 * (rules.tot / total_ot(s2, x2)), iters)
        return s3, x3, r3
    iters = iters or rules.iters
    if rules.fixed_seq is not None:
        lb, ub = rules.bounds(seq)
        x, r, _ = lm(prob, seq, d, rules.tot, lb, ub, iters)
        return seq, x, r
    x, r, _ = lm(prob, seq, d, rules.tot, 0.0, None, iters)
    seq, x = normalize(seq, x, 1e-3)
    for _ in range(200):
        thin = np.flatnonzero(x < rules.floor * 0.999)
        if thin.size == 0 or len(seq) <= 2:
            break
        seq, x = remove_layer(seq, x, int(thin[np.argmin(x[thin] * nvec(seq)[thin])]))
        seq, x = normalize(seq, x, 1e-3)
        x, r, _ = lm(prob, seq, x, rules.tot, 0.0, None, iters)
        seq, x = normalize(seq, x, 1e-3)
    lb, ub = rules.bounds(seq)
    x, r, _ = lm(prob, seq, x, rules.tot, lb, ub, iters)
    return seq, x, r


def cap(prob: Problem, rules: Rules, seq: str, d: np.ndarray, r: float, rng: np.random.Generator, width: int = 12):
    """Deep cleaner (Trubetskov 2020): while N > nmax, try removing each candidate layer (the `width` thinnest in OT
    and a few random ones), refine each shortly, keep the best, then settle."""
    while len(seq) > rules.nmax:
        ot = nvec(seq) * d
        order = list(np.argsort(ot)[:width])
        extra = rng.choice(len(seq), size=min(4, len(seq)), replace=False)
        cands = list(dict.fromkeys([int(v) for v in order] + [int(v) for v in extra]))
        best = None
        for i in cands:
            s2, d2 = remove_layer(seq, d, i)
            s2, d2 = normalize(s2, d2, 1e-3)
            x, r2, _ = lm(prob, s2, d2, rules.tot, 0.0, None, 60)
            if best is None or r2 < best[2]:
                best = (s2, x, r2)
        seq, d, r = settle(prob, rules, best[0], best[1])
    return seq, d, r


def needle_step(prob: Problem, rules: Rules, seq: str, d: np.ndarray, rng: np.random.Generator, choices: int = 8):
    """Insert a needle at one of the most negative P-function minima (distinct layers), chosen at random with a bias
    to the deepest, then settle and cap."""
    p = sorted(p_function(prob, seq, d), key=lambda t: t[0])
    cands, used = [], set()
    for g, i, z in p:
        if g >= 0.0 or len(cands) >= choices:
            break
        if i not in used:
            used.add(i)
            cands.append((i, z))
    if not cands:
        return None
    k = min(int(len(cands) * rng.random() ** 2), len(cands) - 1)
    i, z = cands[k]
    s2, d2 = insert_needle(seq, d, i, z, 0.5)
    s2, d2, r2 = settle(prob, rules, s2, d2)
    return cap(prob, rules, s2, d2, r2, rng)


def scale_tot(seq: str, d: np.ndarray, tot: float | None, le: bool = False):
    if tot is None:
        return d
    t = total_ot(seq, d)
    if le and t <= tot:
        return d
    return d * (tot / t)


def mutate(prob: Problem, rules: Rules, parents, move: str, rng: np.random.Generator):
    """One child from one or two parents (seq, d). Returns (seq, d, rmse) admissible, or None."""
    seq, d = parents[0]
    d = d.copy()
    m = len(seq)
    if move == "jitter":
        sig = float(rng.choice([0.005, 0.02, 0.05, 0.12, 0.25]))
        if rng.random() < 0.5 or m < 8:
            mask = np.ones(m, dtype=bool)
        else:
            a = int(rng.integers(0, m))
            w = int(rng.integers(3, max(4, m // 3)))
            mask = np.zeros(m, dtype=bool)
            mask[a:a + w] = True
        d = np.where(mask, d * (1.0 + sig * rng.standard_normal(m)), d)
        d = np.maximum(d, 0.1)
        d = scale_tot(seq, d, rules.tot)
        s2, d2, r2 = settle(prob, rules, seq, d)
        if rules.fixed_seq is not None:
            return s2, d2, r2
        return cap(prob, rules, s2, d2, r2, rng)
    if rules.fixed_seq is not None:
        if move == "swap":
            i, j = rng.choice(m, size=2, replace=False)
            if seq[i] == seq[j]:
                d[i], d[j] = d[j], d[i]
            else:
                d[i] = d[j] * N_IDX[seq[j]] / N_IDX[seq[i]]
            return settle(prob, rules, seq, scale_tot(seq, d, rules.tot))
        if move == "cross" and len(parents) > 1:
            s_b, d_b = parents[1]
            a = int(rng.integers(1, m - 1))
            w = int(rng.integers(2, max(3, m // 2)))
            d[a:a + w] = d_b[a:a + w]
            return settle(prob, rules, seq, scale_tot(seq, d, rules.tot))
        if move == "block":  # a block re-drawn inside the optical-thickness bounds
            n = nvec(seq)
            lo_ot = rules.otlo if rules.otlo is not None else 40.0
            hi_ot = rules.othi if rules.othi is not None else 320.0
            w = int(rng.integers(2, max(3, min(16, m // 3))))
            a = int(rng.integers(0, max(1, m - w)))
            d[a:a + w] = rng.uniform(lo_ot, hi_ot, size=len(d[a:a + w])) / n[a:a + w]
            return settle(prob, rules, seq, scale_tot(seq, d, rules.tot))
        if move == "reverse":
            w = int(rng.integers(1, max(2, min(12, m // 3)))) * 2 + 1
            if w >= m:
                return None
            a = int(rng.integers(0, m - w + 1))
            d[a:a + w] = d[a:a + w][::-1].copy()
            return settle(prob, rules, seq, scale_tot(seq, d, rules.tot))
        return None
    if move == "needle":
        return needle_step(prob, rules, seq, d, rng)
    if move == "remove":
        ot = nvec(seq) * d
        pr = 1.0 / (ot + 20.0)
        i = int(rng.choice(m, p=pr / pr.sum()))
        s2, d2 = remove_layer(seq, d, i)
        s2, d2 = normalize(s2, d2, 1e-3)
        s2, d2, r2 = settle(prob, rules, s2, d2)
        out = needle_step(prob, rules, s2, d2, rng)
        return out if out is not None else (s2, d2, r2)
    if move == "halfwave":
        i = int(rng.integers(0, m))
        lam = float(rng.uniform(400.0, 700.0))
        dd = 0.5 * lam / N_IDX[seq[i]] * (1 if rng.random() < 0.5 or d[i] * N_IDX[seq[i]] < 0.5 * lam + 20 else -1)
        d[i] = max(d[i] + dd, 0.5)
        d = scale_tot(seq, d, rules.tot)
        s2, d2, r2 = settle(prob, rules, seq, d)
        return cap(prob, rules, s2, d2, r2, rng)
    if move == "cross" and len(parents) > 1:
        s_b, d_b = parents[1]
        ca = np.cumsum(nvec(seq) * d)
        cb = np.cumsum(nvec(s_b) * d_b)
        f = float(rng.uniform(0.15, 0.85))
        ia = int(np.searchsorted(ca, f * ca[-1]))
        ib = int(np.searchsorted(cb, f * cb[-1]))
        s2 = seq[:ia + 1] + s_b[ib + 1:]
        d2 = np.concatenate([d[:ia + 1], d_b[ib + 1:]])
        s2, d2 = normalize(s2, d2, 1e-3)
        d2 = scale_tot(s2, d2, rules.tot)
        s2, d2, r2 = settle(prob, rules, s2, d2)
        return cap(prob, rules, s2, d2, r2, rng)
    if move == "swap":
        same = [k for k in range(m) if seq[k] == seq[0]] if rng.random() < 0.5 else [k for k in range(m) if
                                                                                       seq[k] != seq[0]]
        if len(same) < 2:
            return None
        i, j = rng.choice(same, size=2, replace=False)
        d[i], d[j] = d[j], d[i]
        s2, d2, r2 = settle(prob, rules, seq, d)
        return cap(prob, rules, s2, d2, r2, rng)
    if move == "rescharge" and prob.name == "threeline":
        # owner's idea (2026-11-05 22:00): charge the hidden resonances found from the complex plane (native DESIGN
        # tool, method of the companion paper) for a few rounds, then release: settle on the nominal 277 points.
        from kick import resonance_kick  # noqa: PLC0415  (this folder; native DESIGN resonance tool)
        d = resonance_kick(seq, d, int(rng.integers(2, 9)), rules.floor, rules.tot)
        d = scale_tot(seq, d, rules.tot)
        s2, d2, r2 = settle(prob, rules, seq, d)
        return cap(prob, rules, s2, d2, r2, rng)
    if move == "block":  # large neighbourhood: a block of layers re-drawn at random, its optical thickness kept
        w = int(rng.integers(4, max(5, min(24, m // 2))))
        a = int(rng.integers(0, max(1, m - w)))
        n = nvec(seq)
        ot_block = float(n[a:a + w] @ d[a:a + w])
        new = rng.uniform(40.0, 320.0, size=w)
        new *= ot_block / new.sum()
        d[a:a + w] = new / n[a:a + w]
        s2, d2, r2 = settle(prob, rules, seq, d)
        return cap(prob, rules, s2, d2, r2, rng)
    if move == "reverse":  # mirror an odd block (same material at both ends keeps the alternation)
        w = int(rng.integers(1, max(2, min(20, m // 3)))) * 2 + 1
        if w >= m:
            return None
        a = int(rng.integers(0, m - w + 1))
        if seq[a] != seq[a + w - 1]:
            return None
        d[a:a + w] = d[a:a + w][::-1].copy()
        s2, d2, r2 = settle(prob, rules, seq, d)
        return cap(prob, rules, s2, d2, r2, rng)
    return None


def admissible(rules: Rules, seq: str, d: np.ndarray, tol: float = 1e-6) -> bool:
    if len(seq) > rules.nmax or np.min(d) < rules.floor * (1 - 1e-9):
        return False
    if rules.tot is not None and total_ot(seq, d) > rules.tot * (1 + tol):
        return False
    if rules.fixed_seq is not None and seq != rules.fixed_seq:
        return False
    lb, ub = rules.bounds(seq)
    return bool(np.all(d >= lb * (1 - 1e-9)) and np.all(d <= ub * (1 + 1e-9)))
