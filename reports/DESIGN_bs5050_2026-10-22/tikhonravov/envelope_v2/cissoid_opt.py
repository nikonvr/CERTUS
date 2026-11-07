"""OIC 2016 design problem B1 (cissoid of Diocles), CERTUS needle optimization with nine materials (2026-10-28).

Problem (OIC_2016_Design_Problems.pdf, Problem B.1; Kruschwitz et al., AO 56, C151, 2017): reflectance at normal
incidence, 301 points 400-700 nm, tolerance 0.01, MF = sqrt(mean(((R - R') / 0.01)^2)); substrate 1.52, air;
materials F 1.38, L 1.45, B 1.65, M 1.8, T 2.15, H 2.45, Ag 0.12 - 3.45i, Au 0.306 - 2.88i, Ni 1.8 - 3.33i
(n - ik, k >= 0); at most 50 layers, each >= 3 nm. Results to beat: Trubetskov 0.0139 (contest winner, 3 dielectrics
and 2 metals), Trubetskov AO 59 A75 (2020) deep search 0.0238.
Target R': `cissoid_target_b1.csv`, exact: cissoid of Diocles with its cusps at the R = 0.5 crossings (400, 500,
600, 700 nm), (0.5 - R)^2 = k^2 s^3 / (2a - s), s the distance in nm to the crossing, 2a = 100 nm, k such that
|R - 0.5| = 0.3 at s = 50 nm (R = 0.2 at 450 and 650 nm, 0.8 at 550 nm), rounded to 4 decimals. Found by fitting the
vector polyline of Fig. B.1 of the problem statement (rms 1.0e-4), confirmed by the example design of their
Appendix B: MF 0.89721320429466 on this target, the published value to all 14 digits.

R and dR/dd: CERTUS `compute_oblique_rt_and_grads_analytic` at 0 deg (no new transfer-matrix code).
Method: needle steps over all nine materials (P-function = gradient at zero-thickness layers inserted every STEP nm
and at every interface, one kernel call per material), the K best insertions polished in parallel (trf, d >= 0),
layers under 0.05 nm dropped; then the design cleaner of Trubetskov 2020 (remove each layer in turn, re-polish, keep
the best) until N <= 50, and a last polish with d >= 3 nm.

usage: python cissoid_opt.py MINUTES START   (START: example | H | Ag | csv file of an earlier result)
outputs: cissoid_opt_{start}.csv (every stage), cissoid_opt_{start}.log
"""

from __future__ import annotations

import csv
import functools
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid as c
import numpy as np
import search as s  # noqa: F401  (puts the repository and the oracle on sys.path)
import tmm_reference as oracle
from scipy.optimize import least_squares

from certus.physics.gradient_oblique import compute_oblique_rt_and_grads_analytic

MATS = {"F": 1.38, "L": 1.45, "B": 1.65, "M": 1.8, "T": 2.15, "H": 2.45,
        "A": 0.12 - 3.45j, "U": 0.306 - 2.88j, "N": 1.8 - 3.33j}  # A = Ag, U = Au, N = Ni
def exact_target(w):
    """The contest's target at any wavelength (module docstring): |R - 0.5| = k s^1.5 / sqrt(2a - s), s the distance in
    nm to the nearest R = 0.5 crossing (400, 500, 600, 700 nm), 2a = 100 nm, k = 0.3 / 50, R above 0.5 between 500 and
    600 nm; on the 1 nm points it matches cissoid_target_b1.csv within its 4-decimal rounding (4.9e-5)."""
    w = np.asarray(w, dtype=float)
    s = np.abs(w[..., None] - np.array([400.0, 500.0, 600.0, 700.0])).min(axis=-1)
    mag = 0.3 / 50.0 * s ** 1.5 / np.sqrt(100.0 - s)
    return np.where((w > 500.0) & (w < 600.0), 0.5 + mag, 0.5 - mag)


W_CONTEST = c.WLS
TGT_CONTEST = np.loadtxt(s.HERE / "cissoid_target_b1.csv", delimiter=",", skiprows=1)[:, 1]
W, TGT = W_CONTEST, TGT_CONTEST
#: env CISSOID_JUDGE (2026-11-01, owner: each problem optimized on its nominal grid and on a resolved one; unset = the
#: contest's 301 points and its 4-decimal target): "exactK" puts K points per nm from 400 to 700 nm, against
#: `exact_target`, in place of the 301 points everywhere (search, polish_full, oracle_mf, the campaigns' judge).
JUDGE = os.environ.get("CISSOID_JUDGE", "")
if JUDGE:
    W = np.linspace(400.0, 700.0, 300 * int(re.fullmatch(r"exact(\d+)", JUDGE).group(1)) + 1)
    TGT = exact_target(W)
SCALE = 1.0 / (0.01 * np.sqrt(len(W)))
NSUB = np.full(len(W), 1.52 + 0j)
W_FULL, TGT_FULL, NSUB_FULL, SCALE_FULL = W, TGT, NSUB, SCALE  # the judge: the contest's 301 points or CISSOID_JUDGE
SCALE_J = SCALE


def search_grid(spec: str):
    """Indices of the 301-point grid kept for the search, and the number of 301-grid points each one stands for.

    env CISSOID_GRID (2026-10-30, owner: search on a reduced, logarithmic grid, then a fine polish on the true grid):
    "full" (default) or "logKcC", K points uniform in 1/lambda from 400 to 700 nm snapped to the 1 nm grid, plus every
    point within C nm of the corners 450, 550 and 650 nm (a spline in 1/lambda cannot follow the V of a corner: without
    them the error reached 300 %). log130c8 keeps 159 points: on 15 designs of campaigns 28-29 its MF is within 0.5 %
    (median, 1.6 % max) of the 301-point MF, and the record repolished on it gives 0.03244 on the full grid (0.03212).
    """
    if spec == "full":
        return np.arange(len(W_FULL)), np.ones(len(W_FULL))
    k, cn = (int(v) for v in re.fullmatch(r"log(\d+)c(\d+)", spec).groups())
    x = 1.0 / np.linspace(1.0 / 700.0, 1.0 / 400.0, k)
    corners = np.concatenate([np.arange(cc - cn, cc + cn + 1.0) for cc in (450.0, 550.0, 650.0)])
    sel = np.unique(np.clip(np.round(np.concatenate([x, corners]) - W_FULL[0]).astype(int), 0, len(W_FULL) - 1))
    owner = sel[np.argmin(np.abs(sel[None, :] - np.arange(len(W_FULL))[:, None]), axis=1)]
    return sel, np.array([np.sum(owner == j) for j in sel], dtype=float)


GRID = os.environ.get("CISSOID_GRID", "full")
if GRID.startswith("over"):
    # "overK" (2026-10-31, owner): K points per nm, target interpolated linearly between the 1 nm points; a deformed
    # landscape for the search, judged later on the 301 points (polishing on it alone worsens the 301-point MF)
    W = np.linspace(400.0, 700.0, 300 * int(GRID[4:]) + 1)
    TGT, NSUB = np.interp(W, W_FULL, TGT_FULL), np.full(len(W), 1.52 + 0j)
    SCALE = 1.0 / (0.01 * np.sqrt(len(W)))
    SCALE_J = SCALE
elif GRID != "full":
    _sel, _weight = search_grid(GRID)
    W, TGT, NSUB = W_FULL[_sel], TGT_FULL[_sel], NSUB_FULL[_sel]
    SCALE = np.sqrt(_weight / len(W_FULL)) / 0.01
    SCALE_J = SCALE[:, None]
# env CISSOID_WEIGHT (2026-10-31, owner; empty by default): "LO-HI:W,..." multiplies by W the weight of the search
# points from LO to HI nm (the squared residual by W), to push the search where the error sits; SCALE_FULL, the
# judge, is never weighted.
WEIGHT = os.environ.get("CISSOID_WEIGHT", "")
if WEIGHT:
    _w = np.ones(len(W))
    for part in WEIGHT.split(","):
        span, wt = part.split(":")
        lo, hi = (float(v) for v in span.split("-"))
        _w[(W >= lo) & (W <= hi)] *= float(wt)
    SCALE = SCALE * np.sqrt(_w)
    SCALE_J = SCALE[:, None]
STEP, DROP, FLOOR, N_MAX = 2.0, 0.05, 3.0, 50
HI_METAL, HI_DIEL = 100.0, 3000.0  # a metal above 100 nm is opaque; bounds keep the kernel finite
K = int(os.environ.get("CISSOID_K", "7"))
WORKERS = int(os.environ.get("CISSOID_WORKERS", "7"))
#: 2026-10-29 (owner's strategy, `cissoid_grow.py`): materials tried as needles, and the most metal layers a design may
#: hold (None = no cap). Defaults keep the 2026-10-28 behaviour: every material, no cap.
NEEDLE_MATS = list(MATS)
MAX_METALS: int | None = None


#: env CISSOID_OTMAX (2026-11-01, owner: the record with a dielectric optical thickness of at most OTMAX nm; unset or
#: 0 = off, the residuals unchanged): one more residual, OTMAX_W * max(0, OT_d - OTMAX) / OTMAX with OT_d the sum of
#: n d over the dielectric layers, so that every polish, swap and screen of the study works under the cap. The judge
#: (`oracle_mf`) ignores it.
OTMAX = float(os.environ.get("CISSOID_OTMAX", "0") or 0.0)
OTMAX_W = 100.0


def _ot_cap(mats, d, r, j):
    if not OTMAX:
        return r, j
    n = np.array([0.0 if np.iscomplex(MATS[m]) else float(np.real(MATS[m])) for m in mats])
    excess = float(n @ d) - OTMAX
    row = OTMAX_W * n / OTMAX if excess > 0.0 else np.zeros(len(d))
    return np.append(r, OTMAX_W * max(excess, 0.0) / OTMAX), np.vstack([j, row])


def res_jac(mats: list[str], d: np.ndarray):
    nm = np.column_stack([np.full(len(W), MATS[m], dtype=complex) for m in mats])
    r, _t, dr, _dt = compute_oblique_rt_and_grads_analytic(d, nm, NSUB, W, np.arange(len(d)), 0.0, True)
    return _ot_cap(mats, d, (r - TGT) * SCALE, dr * SCALE_J)


def res_jac_full(mats: list[str], d: np.ndarray):
    """`res_jac` on the contest's 301 points, whatever CISSOID_GRID."""
    nm = np.column_stack([np.full(len(W_FULL), MATS[m], dtype=complex) for m in mats])
    r, _t, dr, _dt = compute_oblique_rt_and_grads_analytic(d, nm, NSUB_FULL, W_FULL, np.arange(len(d)), 0.0, True)
    return _ot_cap(mats, d, (r - TGT_FULL) * SCALE_FULL, dr * SCALE_FULL)


def mf(mats, d) -> float:
    return float(np.linalg.norm(res_jac(mats, d)[0]))


def mf_full(mats, d) -> float:
    return float(np.linalg.norm(res_jac_full(mats, d)[0]))


def oracle_mf(mats, d, w=None, tgt=None) -> float:
    """The independent oracle's MF on the judge's grid, or on the wavelengths ``w`` against ``tgt``."""
    w, tgt = (W_FULL, TGT_FULL) if w is None else (w, tgt)
    n = [complex(MATS[m]) for m in mats]
    r = np.array([oracle.rt_stack(x, n, np.asarray(d), complex(1.0), complex(1.52))[0] for x in w])
    return float(np.sqrt(np.mean(((r - tgt) / 0.01) ** 2)))


def normalize(mats: list[str], d: np.ndarray, drop: float):
    m2, d2 = [], []
    for m, x in zip(mats, d, strict=True):
        if x < drop:
            continue
        if m2 and m2[-1] == m:
            d2[-1] += x
        else:
            m2.append(m)
            d2.append(float(x))
    return m2, np.array(d2)


def polish(task, rj=None):
    """task (mats, d, lo) or (mats, d, lo, max_nfev); max_nfev defaults to 300. ``rj`` (default `res_jac`, the search
    grid) gives the residuals; `polish_full` polishes on the contest's 301 points."""
    mats, d, lo, *rest = task
    max_nfev = rest[0] if rest else 300
    res = rj or res_jac
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = res(mats, x)
            r, jac = memo[key]
            if not (np.isfinite(r).all() and np.isfinite(jac).all()):
                print(f"non-finite kernel output: {''.join(mats)} {np.round(x, 3).tolist()}", file=sys.stderr, flush=True)
                memo[key] = (np.full_like(r, 1e3, dtype=float), np.zeros_like(jac, dtype=float))
        return memo[key]

    hi = np.array([HI_METAL if np.iscomplex(MATS[m]) else HI_DIEL for m in mats])
    sol = least_squares(lambda x: both(x)[0], np.clip(d, lo, hi), jac=lambda x: both(x)[1], bounds=(lo, hi),
                        method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=max_nfev)
    x = np.maximum(sol.x, lo)
    if lo < FLOOR:
        mats, x = normalize(mats, x, DROP)
    return mats, x, (mf(mats, x) if rj is None else float(np.linalg.norm(rj(mats, x)[0])))


polish_full = functools.partial(polish, rj=res_jac_full)


def p_function(mats, d):
    """[(dMF^2/d(delta), material, layer, z)] for zero layers of every material, z from the substrate-side face."""
    out = []
    metals = sum(np.iscomplex(MATS[m]) for m in mats)
    for cand in NEEDLE_MATS:
        if MAX_METALS is not None and np.iscomplex(MATS[cand]) and metals >= MAX_METALS:
            continue
        m2, d2, where = [], [], []
        for i, m in enumerate(mats):
            zs = [0.0, *list(np.arange(STEP / 2, d[i], STEP))] if m != cand else [0.0]
            last = 0.0
            for z in zs:
                m2 += [m, cand]
                d2 += [z - last, 0.0]
                where.append((len(m2) - 1, i, float(z)))
                last = z
            m2.append(m)
            d2.append(d[i] - last)
        m2.append(cand)  # on top of the stack
        d2.append(0.0)
        where.append((len(m2) - 1, len(mats), 0.0))
        res, jac = res_jac(m2, np.array(d2))  # zero layers: res is the residual of the design itself
        grad = 2.0 * (jac.T @ res)
        out += [(float(grad[k]), cand, i, z) for k, i, z in where]
    return out


def insert(mats, d, cand, i, z, delta=None):
    # a metal needle is strongly non-linear (0.001 nm of Ag already reverses the first-order gain): 0.01 nm
    delta = delta if delta is not None else (0.01 if cand in "AUN" else 0.5)
    if i == len(mats):
        return [*mats, cand], np.append(d, delta)
    return [*mats[:i], mats[i], cand, mats[i], *mats[i + 1:]], np.concatenate([d[:i], [z, delta, d[i] - z], d[i + 1:]])


def needles(mats, d, r, pool, deadline, log):
    while time.time() < deadline:
        p = sorted(p_function(mats, d))
        cands, used = [], set()
        for g, cand, i, z in p:
            if g >= 0 or len(cands) >= K:
                break
            if (cand, i) not in used:
                used.add((cand, i))
                cands.append((cand, i, z))
        if not cands:
            return mats, d, r
        tasks = [(*insert(mats, d, cand, i, z), 0.0) for cand, i, z in cands]
        best = min(pool.map(polish, tasks), key=lambda t: t[2])
        if best[2] > r * (1 - 1e-3):
            return mats, d, r
        mats, d, r = best
        log(f"needle -> N {len(mats)} MF {r:.5f}")
    return mats, d, r


def clean(mats, d, r, pool, deadline, log):
    """Trubetskov's cleaner: remove each layer in turn, re-polish, keep the best, until N <= N_MAX and d >= FLOOR."""
    while (len(mats) > N_MAX or d.min() < FLOOR) and time.time() < deadline:
        tasks = []
        for i in range(len(mats)):
            m2, d2 = normalize(mats[:i] + mats[i + 1:], np.delete(d, i), 0.0)
            tasks.append((m2, d2, 0.0))
        mats, d, r = min(pool.map(polish, tasks), key=lambda t: t[2])
        log(f"clean -> N {len(mats)} MF {r:.5f} thinnest {d.min():.2f}")
        if len(mats) <= N_MAX:
            mats2, d2, r2 = polish((mats, d, FLOOR))
            if len(mats2) <= N_MAX and d2.min() >= FLOOR - 1e-9:
                return mats2, d2, r2
    return mats, d, r


def start_design(name: str):
    if name == "example":
        return ["H" if i % 2 == 0 else "L" for i in range(len(c.EXAMPLE))], np.array(c.EXAMPLE)
    if name in MATS:
        return [name], np.array([60.0 if name in "FLBMTH" else 20.0])
    rows = list(csv.DictReader((s.HERE / name).open(encoding="utf-8")))
    return rows[-1]["mats"].split(), np.array([float(v) for v in rows[-1]["d_nm"].split()])


def main() -> None:
    minutes, start = float(sys.argv[1]), sys.argv[2]
    deadline = time.time() + 60 * minutes
    tag = start.replace(".csv", "")
    logf = (s.HERE / f"cissoid_opt_{tag}.log").open("a", encoding="utf-8")
    rows = []

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    def record(stage, mats, d, r):
        rows.append({"stage": stage, "layers": len(mats), "mf_kernel": r, "mf_oracle": oracle_mf(mats, d),
                     "thinnest_nm": float(d.min()), "physical_nm": float(d.sum()),
                     "metals": sum(m in "AUN" for m in mats), "mats": " ".join(mats),
                     "d_nm": " ".join(f"{v:.4f}" for v in d)})
        with (s.HERE / f"cissoid_opt_{tag}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        log(f"record {stage}: N {len(mats)} MF kernel {r:.5f} oracle {rows[-1]['mf_oracle']:.5f}")

    pool = ProcessPoolExecutor(WORKERS)
    mats, d = start_design(start)
    mats, d, r = polish((mats, d, 0.0))
    record("start", mats, d, r)
    budget_needles = time.time() + 0.75 * (deadline - time.time())
    mats, d, r = needles(mats, d, r, pool, budget_needles, log)
    record("needles", mats, d, r)
    mats, d, r = clean(mats, d, r, pool, deadline, log)
    record("clean", mats, d, r)
    pool.shutdown()


if __name__ == "__main__":
    main()
