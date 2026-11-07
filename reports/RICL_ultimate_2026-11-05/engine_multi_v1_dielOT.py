"""Memetic engine for the OIC 2016 B1 cissoid (RICL 2026-11-05): nine materials, three of them absorbing metals.

Residuals, Jacobian and P-function come from `envelope_v2/cissoid_opt.py` (CERTUS kernel
`compute_oblique_rt_and_grads_analytic` at 0 deg, contest grid of 301 points, MF = sqrt(mean(((R - R')/0.01)^2)));
the judge is the independent oracle through `cissoid_opt.oracle_mf`. No CERTUS source is modified.
Contest rules: at most 50 layers, every layer >= 3 nm. Optional equality on the dielectric optical thickness
(sum of n d over the dielectric layers; metals excluded), for the dense curve along that axis.
A design is a string of material codes, layer 0 on the substrate: F L B M T H (dielectrics), A = Ag, U = Au, N = Ni.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ENV = HERE.parent / "DESIGN_bs5050_2026-10-22" / "tikhonravov" / "envelope_v2"
sys.path.insert(0, str(ENV))

import cissoid_opt as co  # noqa: E402

MATS = co.MATS
METALS = "AUN"
DIELS = "FLBMTH"
HI_METAL, HI_DIEL = 100.0, 3000.0


def is_metal(m: str) -> bool:
    return m in METALS


def otvec(seq: str) -> np.ndarray:
    return np.array([0.0 if is_metal(m) else float(np.real(MATS[m])) for m in seq])


def diel_ot(seq: str, d: np.ndarray) -> float:
    return float(otvec(seq) @ d)


def res_jac(seq: str, d: np.ndarray):
    r, j = co.res_jac(list(seq), np.ascontiguousarray(d, dtype=np.float64))
    return r, j


def mf(seq: str, d: np.ndarray) -> float:
    r, _j = res_jac(seq, d)
    return float(math.sqrt(r @ r))


def oracle_mf(seq: str, d: np.ndarray) -> float:
    return co.oracle_mf(list(seq), np.asarray(d, dtype=np.float64))


def upper(seq: str) -> np.ndarray:
    return np.array([HI_METAL if is_metal(m) else HI_DIEL for m in seq])


def _fix_tot(x, n, tot, lb, ub):
    for _ in range(4):
        gap = tot - float(n @ x)
        if abs(gap) <= 1e-9 * tot:
            break
        inner = (x > lb + 1e-12) & (x < ub - 1e-12) & (n > 0)
        if not inner.any():
            break
        w = np.where(inner, n, 0.0)
        x = np.clip(x + gap * w / float(w @ n), lb, ub)
    return x


def lm(seq: str, d: np.ndarray, tot: float | None = None, floor: float = 0.0, iters: int = 300,
       ftol: float = 1e-12):
    """Levenberg-Marquardt with box bounds [floor, upper] and an optional exact equality on the dielectric OT."""
    m = len(seq)
    n = otvec(seq)
    lb = np.full(m, floor)
    ub = upper(seq)
    x = np.clip(np.asarray(d, dtype=np.float64).copy(), lb, ub)
    if tot is not None and n.any():
        x = _fix_tot(x, n, tot, lb, ub)
    r, jac = res_jac(seq, x)
    if not (np.isfinite(r).all() and np.isfinite(jac).all()):
        return x, float("inf"), 0
    f = float(r @ r)
    mu, nu, small, it = 1e-3, 2.0, 0, 0
    use_tot = tot is not None and n.any()
    for it in range(1, iters + 1):  # noqa: B007
        g = jac.T @ r
        a = jac.T @ jac
        da = np.diag(a).copy()
        dmax = float(da.max()) if da.size else 1.0
        free = ~(((x <= lb + 1e-12) & (g > 0.0)) | ((x >= ub - 1e-12) & (g < 0.0)))
        fi = np.flatnonzero(free)
        if fi.size == 0:
            break
        b = a[np.ix_(fi, fi)].copy()
        b[np.diag_indices_from(b)] += mu * (da[fi] + 1e-12 * dmax)
        try:
            nf = n[fi]
            if use_tot and fi.size > 1 and nf.any():
                k = np.zeros((fi.size + 1, fi.size + 1))
                k[:-1, :-1] = b
                k[:-1, -1] = nf
                k[-1, :-1] = nf
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
        if use_tot:
            xn = _fix_tot(xn, n, tot, lb, ub)
        dx = xn - x
        pred = -(2.0 * float(dx @ g) + float(dx @ a @ dx))
        rn, jn = res_jac(seq, xn)
        fn = float(rn @ rn) if np.isfinite(rn).all() and np.isfinite(jn).all() else float("inf")
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


def normalize(seq: str, d: np.ndarray, thin: float = 1e-3):
    s, x = [], []
    for m, v in zip(seq, np.asarray(d, dtype=np.float64), strict=True):
        if v < thin:
            continue
        if s and s[-1] == m:
            x[-1] += v
        else:
            s.append(m)
            x.append(float(v))
    if not s:
        return seq[:1], np.array([max(float(d[0]), 3.0)])
    return "".join(s), np.array(x)


def remove_layer(seq: str, d: np.ndarray, i: int):
    """Delete layer i (a dielectric gives its optical thickness to a dielectric neighbour), merge equal neighbours."""
    d = np.asarray(d, dtype=np.float64).copy()
    if not is_metal(seq[i]):
        ot = float(np.real(MATS[seq[i]])) * d[i]
        nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(seq) and not is_metal(seq[j])]
        if nbs:
            j = min(nbs, key=lambda q: d[q])
            d[j] += ot / float(np.real(MATS[seq[j]]))
    return normalize(seq[:i] + seq[i + 1:], np.delete(d, i), 1e-6)


@dataclass
class Rules:
    nmax: int = 50
    floor: float = 3.0
    tot: float | None = None  # dielectric OT equality
    iters: int = 250


def settle(rules: Rules, seq: str, d: np.ndarray):
    x, r, _ = lm(seq, d, rules.tot, 0.0, rules.iters)
    seq, x = normalize(seq, x, 1e-3)
    for _ in range(80):
        thin = np.flatnonzero(x < rules.floor * 0.999)
        if thin.size == 0 or len(seq) <= 1:
            break
        seq, x = remove_layer(seq, x, int(thin[np.argmin(x[thin])]))
        x, r, _ = lm(seq, x, rules.tot, 0.0, rules.iters)
        seq, x = normalize(seq, x, 1e-3)
    x, r, _ = lm(seq, x, rules.tot, rules.floor, rules.iters)
    return seq, x, r


def cap(rules: Rules, seq: str, d: np.ndarray, r: float, rng: np.random.Generator, width: int = 10):
    """Deep cleaner: while N > nmax, the best of several single removals after a short refinement."""
    while len(seq) > rules.nmax:
        order = list(np.argsort(d)[:width])
        extra = rng.choice(len(seq), size=min(4, len(seq)), replace=False)
        best = None
        for i in dict.fromkeys([int(v) for v in order] + [int(v) for v in extra]):
            s2, d2 = remove_layer(seq, d, i)
            x, r2, _ = lm(s2, d2, rules.tot, 0.0, 40)
            if best is None or r2 < best[2]:
                best = (s2, x, r2)
        seq, d, r = settle(rules, best[0], best[1])
    return seq, d, r


def needle_step(rules: Rules, seq: str, d: np.ndarray, rng: np.random.Generator, choices: int = 10,
                mats: str | None = None):
    old = co.NEEDLE_MATS
    if mats:
        co.NEEDLE_MATS = list(mats)
    try:
        p = sorted(co.p_function(list(seq), d))
    finally:
        co.NEEDLE_MATS = old
    cands, used = [], set()
    for g, cand, i, z in p:
        if g >= 0.0 or len(cands) >= choices:
            break
        if (cand, i) not in used:
            used.add((cand, i))
            cands.append((cand, i, z))
    if not cands:
        return None
    k = min(int(len(cands) * rng.random() ** 2), len(cands) - 1)
    cand, i, z = cands[k]
    m2, d2 = co.insert(list(seq), d, cand, i, z)
    s2, x2, r2 = settle(rules, "".join(m2), np.asarray(d2, dtype=np.float64))
    return cap(rules, s2, x2, r2, rng)


def mutate(rules: Rules, parents, move: str, rng: np.random.Generator):
    seq, d = parents[0]
    d = np.asarray(d, dtype=np.float64).copy()
    m = len(seq)
    if move == "jitter":
        sig = float(rng.choice([0.005, 0.02, 0.05, 0.1, 0.2]))
        mask = np.ones(m, dtype=bool)
        if rng.random() < 0.5 and m > 6:
            a = int(rng.integers(0, m))
            mask[:] = False
            mask[a:a + int(rng.integers(2, max(3, m // 3)))] = True
        d = np.where(mask, d * (1.0 + sig * rng.standard_normal(m)), d)
        d = np.maximum(d, 0.2)
    elif move == "needle":
        return needle_step(rules, seq, d, rng)
    elif move == "needle_diel":
        return needle_step(rules, seq, d, rng, mats=DIELS)
    elif move == "substitute":
        i = int(rng.integers(0, m))
        old = seq[i]
        if is_metal(old):
            new = str(rng.choice([c for c in METALS if c != old] + (["M", "T", "H"] if rng.random() < 0.2 else [])))
        else:
            pool = [c for c in DIELS if c != old] + (list(METALS) if rng.random() < 0.15 else [])
            new = str(rng.choice(pool))
        if is_metal(new) and not is_metal(old):
            d[i] = float(rng.uniform(4.0, 20.0))
        elif not is_metal(new) and not is_metal(old):
            d[i] *= float(np.real(MATS[old])) / float(np.real(MATS[new]))
        elif not is_metal(new):
            d[i] = float(rng.uniform(40.0, 150.0)) / float(np.real(MATS[new]))
        seq = seq[:i] + new + seq[i + 1:]
        seq, d = normalize(seq, d, 1e-6)
    elif move == "remove":
        i = int(rng.integers(0, m))
        seq, d = remove_layer(seq, d, i)
        seq, d, r = settle(rules, seq, d)
        out = needle_step(rules, seq, d, rng)
        return out if out is not None else (seq, d, r)
    elif move == "swap":
        if m < 2:
            return None
        i = int(rng.integers(0, m - 1))
        seq = seq[:i] + seq[i + 1] + seq[i] + seq[i + 2:]
        d[i], d[i + 1] = d[i + 1], d[i]
        seq, d = normalize(seq, d, 1e-6)
    elif move == "block":
        w = int(rng.integers(2, max(3, min(12, m // 2))))
        a = int(rng.integers(0, max(1, m - w)))
        for k in range(a, min(m, a + w)):
            d[k] = float(rng.uniform(4.0, 30.0)) if is_metal(seq[k]) else float(rng.uniform(30.0, 300.0)) / float(
                np.real(MATS[seq[k]]))
    elif move == "cross" and len(parents) > 1:
        s_b, d_b = parents[1]
        d_b = np.asarray(d_b, dtype=np.float64)
        ca, cb = np.cumsum(d), np.cumsum(d_b)
        f = float(rng.uniform(0.15, 0.85))
        ia = int(np.searchsorted(ca, f * ca[-1]))
        ib = int(np.searchsorted(cb, f * cb[-1]))
        seq = seq[:ia + 1] + s_b[ib + 1:]
        d = np.concatenate([d[:ia + 1], d_b[ib + 1:]])
        seq, d = normalize(seq, d, 1e-6)
    else:
        return None
    if rules.tot is not None and otvec(seq).any():
        d = d * np.where(otvec(seq) > 0, rules.tot / max(diel_ot(seq, d), 1e-9), 1.0)
    s2, x2, r2 = settle(rules, seq, d)
    return cap(rules, s2, x2, r2, rng)


def admissible(rules: Rules, seq: str, d: np.ndarray) -> bool:
    if len(seq) > rules.nmax or np.min(d) < rules.floor * (1 - 1e-9) or np.any(d > upper(seq) * (1 + 1e-9)):
        return False
    return not (rules.tot is not None and abs(diel_ot(seq, d) - rules.tot) > 1e-6 * rules.tot)
