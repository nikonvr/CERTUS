"""Gradual evolution with needle optimization from the bare substrate, for the three-line filter.

Problem: Tikhonravov & Trubetskov, AO 51, 7319 (2012), Eq. 1 and Sec. 3, as in `search.py` (SEARCH_TARGET=threeline):
T = 100 % at 445-455, 505-515, 635-645 nm, 0 % at 400-440, 460-500, 520-630, 650-700 nm, 1 nm step, tolerance 1 %,
nH = 2.35, nL = 1.45, substrate 1.52, air, normal incidence; MF = RMS deviation in %. Compared with Trubetskov,
AO 59, A75 (2020), Fig. 5 (MF against total optical thickness TOT, classical and deep search).

Method (classical needle optimization and gradual evolution, Tikhonravov et al., AO 35, 5493 (1996)):
1. polish all thicknesses (trf, exact CERTUS Jacobian, d >= 0), drop layers under 0.3 nm, merge equal neighbours;
2. needle step: the exact P-function is the gradient of the MSE with respect to zero-thickness layers of the other
   material inserted every STEP nm inside every layer, obtained from ONE call of the CERTUS Jacobian kernel (no new
   transfer-matrix code); insert a needle at the most negative P and go to 1;
3. when no needle lowers MF (P >= 0 everywhere, or the gain is under 0.1 %), the design is converged at its TOT: record
   (TOT, N, MF), raise the imposed TOT by GRAD_DTOT (stretching the design, or adding a layer of the other material on
   the air side, the better after convergence) and go to 1 (evolution step). Polishes run at imposed TOT (one extra
   residual row): without it the optimizer absorbs every added layer and TOT never grows.
Deep search (env GRAD_DEEP=K): the K most negative P minima (in distinct layers) are each inserted and polished, the
best result is kept; the evolution step also tries a new layer on the substrate side.

usage: python gradual.py MINUTES TOT_MAX   (env GRAD_DEEP=1 classical, K > 1 deep)
outputs: gradual_{tag}.csv (every converged design, oracle MF on the last column), gradual_{tag}.log
"""

from __future__ import annotations

import csv
import os
import sys
import time

os.environ.setdefault("SEARCH_TARGET", "threeline")  # 2026-10-28: SEARCH_TARGET=bs5050 runs the 50/50 splitter
import numpy as np
import search as s

STEP = 2.0  # nm physical, spacing of the P-function samples
THIN = 0.3  # nm, layers below are dropped
DEEP = int(os.environ.get("GRAD_DEEP", "1"))
TAG = ("" if s.TARGET == "threeline" else f"{s.TARGET}_") + ("classic" if DEEP == 1 else f"deep{DEEP}")
#: env GRAD_RESUME=gradual_X.csv: continue from the last design of an earlier run (outputs tagged _cont)
RESUME = os.environ.get("GRAD_RESUME", "")
if RESUME:
    TAG += "_cont"
DTOT = float(os.environ.get("GRAD_DTOT", "100"))  # nm, TOT increment of each evolution step
#: env GRAD_FIRST (2026-10-28): material of the first layer on the bare substrate, "H" or "L" (default: the better one);
#: env GRAD_TAG: suffix of the output names (several trajectories side by side)
FIRST = os.environ.get("GRAD_FIRST", "")
TAG += os.environ.get("GRAD_TAG", "")
#: env GRAD_WORKERS (2026-10-28): processes settling the K deep-search candidates in parallel; 1 = serial (same result)
WORKERS = int(os.environ.get("GRAD_WORKERS", "1"))
POOL = None  # created in main() when WORKERS > 1
#: env GRAD_CLEAN (2026-10-29): physical thickness in nm; after each convergence, layers thinner than this are removed
#: (all at once, or the thinnest alone), the design re-settled and re-needled, and kept if MF is not worse. 0 = off.
CLEAN = float(os.environ.get("GRAD_CLEAN", "0"))
if CLEAN > 0:
    TAG += f"_clean{CLEAN:g}"
#: env GRAD_GROW=1 (2026-10-29): evolution step of Trubetskov 2020 (one layer thickened to the next minimum of the
#: one-parameter MF, see grow()) instead of the stretch / outer layer at TOT + DTOT; 0 = off.
GROW = os.environ.get("GRAD_GROW", "0") == "1"
GROW_STEP, GROW_MAX = 2.0, 400.0  # nm optical: scan step and largest thickness increase of one layer
if GROW:
    TAG += "_grow"


def p_function(seq: str, d: np.ndarray):
    """Exact P-function: dMSE/d(delta) of a needle of the other material at every STEP nm inside every layer.

    Returns [(p, layer, z)], z the distance from the substrate-side face of the layer."""
    seq2, d2, where = [], [], []
    for i, m in enumerate(seq):
        zs = np.arange(STEP / 2, d[i], STEP)
        last = 0.0
        for z in zs:
            seq2 += [m, s.other(m)]
            d2 += [z - last, 0.0]
            where.append((len(seq2) - 1, i, float(z)))
            last = z
        seq2.append(m)
        d2.append(d[i] - last)
    if not where:
        return []
    st = s.Stack("".join(seq2))  # not cached: one-off sequence
    res, jac, _c = st.res_jac(np.array(d2))
    grad = 2.0 * (jac.T @ res)
    return [(float(grad[k]), i, z) for k, i, z in where]


def insert(seq: str, d: np.ndarray, i: int, z: float, delta: float = 0.5):
    return seq[:i + 1] + s.other(seq[i]) + seq[i:], np.concatenate([d[:i], [z, delta, d[i] - z], d[i + 1:]])


TOT_W = 100.0  # weight of the TOT constraint row: a relative TOT error of 1e-4 costs as much as an RMSE of 1e-2


def polish_tot(seq: str, d: np.ndarray, tot: float, max_nfev: int = 300):
    """Least-squares polish at imposed total optical thickness (gradual evolution grows TOT step by step; without
    the constraint the optimizer absorbs every added layer). d >= 0."""
    st = s.Stack.of(seq)
    n = np.array([s.N_IDX[m] for m in seq])
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            r, j, _c = st.res_jac(x)
            memo[key] = (np.append(r, TOT_W * (n @ x - tot) / tot), np.vstack([j, TOT_W * n / tot]))
        return memo[key]

    sol = s.least_squares(lambda x: both(x)[0], np.maximum(d, 0.0), jac=lambda x: both(x)[1], bounds=(0.0, np.inf),
                          method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=max_nfev)
    x = np.maximum(sol.x, 0.0)
    return x, s.rmse(seq, x)


def settle(seq: str, d: np.ndarray, tot: float):
    """Polish at imposed TOT, drop thin layers, re-polish until the sequence is stable."""
    for _ in range(6):
        d, r = polish_tot(seq, d, tot)
        seq2, d2 = s.normalize(seq, d, THIN)
        if seq2 == seq:
            return seq, d, r
        seq, d = seq2, d2
    d, r = polish_tot(seq, d, tot)
    return seq, d, r


def settle_task(task):
    return settle(*task)


def needles(seq: str, d: np.ndarray, r: float, deadline: float, tot: float):
    """Needle steps at imposed TOT until no needle helps; returns the converged design."""
    while time.time() < deadline:
        p = sorted(p_function(seq, d), key=lambda t: t[0])
        cands, used = [], set()
        for g, i, z in p:
            if g >= 0.0 or len(cands) >= DEEP:
                break
            if i not in used:
                used.add(i)
                cands.append((i, z))
        best = None
        tasks = [(*insert(seq, d, i, z), tot) for i, z in cands]
        for s2, d2, r2 in (POOL.map(settle_task, tasks) if POOL else map(settle_task, tasks)):
            if best is None or r2 < best[2]:
                best = (s2, d2, r2)
        if best is None or best[2] > r * (1.0 - 1e-3):
            return seq, d, r
        seq, d, r = best
    return seq, d, r


def grow(seq: str, d: np.ndarray):
    """Evolution step of Trubetskov, AO 59, A75 (2020), Sec. 2: the thickness of each layer alone is increased until
    the next local minimum of the one-parameter MF; the DEEP candidates with the lowest MF (at least 1) are returned
    as (seq, d, TOT), each at its own new TOT (the TOT step is not fixed). Empty when no layer has such a minimum."""
    out = []
    for i, m in enumerate(seq):
        steps = np.arange(GROW_STEP, GROW_MAX + GROW_STEP / 2, GROW_STEP) / s.N_IDX[m]
        mf = []
        for dz in steps:
            x = d.copy()
            x[i] += dz
            mf.append(s.rmse(seq, x))
            # the first local minimum along the layer thickness (MF has risen, then turns up again)
            if len(mf) >= 3 and mf[-2] < mf[-3] and mf[-2] <= mf[-1]:
                x[i] -= GROW_STEP / s.N_IDX[m]
                out.append((mf[-2], seq, x))
                break
    out.sort(key=lambda t: t[0])
    return [(q, x, s.total_ot(q, x)) for _r, q, x in out[: max(1, DEEP)]]


def clean(seq: str, d: np.ndarray, r: float, deadline: float, tot: float):
    """Remove thin layers (all under CLEAN at once, then the thinnest alone), re-settle and re-needle at the same TOT;
    keep the result when MF is not worse. Repeats while it helps."""
    while CLEAN > 0 and time.time() < deadline:
        thin = np.flatnonzero(d < CLEAN)
        if thin.size == 0:
            return seq, d, r
        best = None
        for drop in ({*thin.tolist()}, {int(thin[np.argmin(d[thin])])}):
            d2 = d.copy()
            d2[list(drop)] = 0.0
            s2, d2 = s.normalize(seq, d2, THIN)
            s2, d2, r2 = settle(s2, d2, tot)
            s2, d2, r2 = needles(s2, d2, r2, deadline, tot)
            if best is None or r2 < best[2]:
                best = (s2, d2, r2)
        if best[2] > r or (best[0] == seq and np.array_equal(best[1], d)):
            return seq, d, r
        seq, d, r = best
    return seq, d, r


def main() -> None:
    global POOL
    minutes, tot_max = float(sys.argv[1]), float(sys.argv[2])
    if WORKERS > 1:
        from concurrent.futures import ProcessPoolExecutor
        POOL = ProcessPoolExecutor(WORKERS)
    deadline = time.time() + 60.0 * minutes
    log = (s.HERE / f"gradual_{TAG}.log").open("w", encoding="utf-8")
    rows: list[dict] = []

    def record(seq: str, d: np.ndarray, r: float) -> None:
        tot = s.total_ot(seq, d)
        rows.append({"total_ot_nm": tot, "layers": len(seq), "mf_kernel": 100 * r, "mf_oracle": "",
                     "thinnest_nm": float(np.min(d)), "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
        log.write(f"{time.strftime('%H:%M:%S')} TOT {tot:8.1f} N {len(seq):3d} MF {100 * r:.4f}\n")
        log.flush()
        # every design is kept as soon as it is found (an interrupted run loses nothing)
        with (s.HERE / f"gradual_{TAG}_partial.csv").open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[-1]))
            if f.tell() == 0:
                w.writeheader()
            w.writerow(rows[-1])

    # bare substrate: the first layer is the better of H or L at TOT = DTOT
    if RESUME:
        with (s.HERE / RESUME).open(encoding="utf-8") as f:
            last = list(csv.DictReader(f))[-1]
        seq, d = last["seq"], np.array([float(v) for v in last["d_nm"].split()])
        tot = DTOT * round(s.total_ot(seq, d) / DTOT)
        seq, d, r = settle(seq, d, tot)
    else:
        tot = DTOT
        seq, d, r = min((settle(m, np.array([tot / s.N_IDX[m]]), tot) for m in (FIRST or "HL")), key=lambda t: t[2])
    seq, d, r = needles(seq, d, r, deadline, tot)
    seq, d, r = clean(seq, d, r, deadline, tot)
    record(seq, d, r)
    while time.time() < deadline and tot < tot_max:
        if GROW:
            best = None
            for s2, d2, t2 in grow(seq, d):
                s2, d2, r2 = settle(s2, d2, t2)
                s2, d2, r2 = needles(s2, d2, r2, deadline, t2)
                if best is None or r2 < best[2]:
                    best = (s2, d2, r2, t2)
            if best is None:
                break
            tot = best[3]
            seq, d, r = clean(*best[:3], deadline, tot)
            record(seq, d, r)
            continue
        tot0, tot = tot, tot + DTOT
        starts = [(seq, d * (tot / tot0))]  # stretch only
        top = s.other(seq[-1])
        starts.append((seq + top, np.concatenate([d, [DTOT / s.N_IDX[top]]])))  # new layer on the air side
        if DEEP > 1:
            bot = s.other(seq[0])
            starts.append((bot + seq, np.concatenate([[DTOT / s.N_IDX[bot]], d])))  # new layer on the substrate
        best = None
        for s2, d2 in starts:
            s2, d2, r2 = settle(s2, d2, tot)
            s2, d2, r2 = needles(s2, d2, r2, deadline, tot)
            if best is None or r2 < best[2]:
                best = (s2, d2, r2)
        seq, d, r = clean(*best, deadline, tot)
        record(seq, d, r)
    for row in rows:
        dd = np.array([float(v) for v in row["d_nm"].split()])
        row["mf_oracle"] = 100 * s.oracle_rmse(row["seq"], dd)
    with (s.HERE / f"gradual_{TAG}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log.write("written\n")
    log.close()


if __name__ == "__main__":
    main()
