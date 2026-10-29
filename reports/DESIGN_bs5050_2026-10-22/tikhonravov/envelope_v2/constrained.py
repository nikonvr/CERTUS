"""Fixed N with bounded layer optical thicknesses: the two constrained problems of Tikhonravov & Trubetskov,
AO 51, 7319 (2012), Sec. 2 (2026-10-28).

- three-line filter (SEARCH_TARGET=threeline), N = 51, optical thicknesses in [100, 350] nm: their 10 solutions
  (Table 1) have MF 0.464-0.599 at TOT 9202.9-9665.9 nm;
- hot mirror (SEARCH_TARGET=hotmirror), N = 40, same bounds: Design A MF 0.865 (TOT 9046.1 nm), Design B 0.913.

Their method (Sec. 2): M0 = 3000 random starts (layer optical thickness of mean TOT/N), then K = 6 series of 1000
starts drawn around the best design with relative sigma 3 %, the series centre moving to any better design; repeated
several times. Here the same procedure, local optimizations by `scipy.optimize.least_squares` (trf, box bounds,
exact CERTUS Jacobian), in parallel; both alternations (H or L next to the substrate).

usage: python constrained.py N OT_MEAN RUNS MINUTES   (env CONSTRAINED_WORKERS, default 7)
outputs: constrained_{target}_N{N}.csv (best design of each run, oracle MF) and .log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import search as s
from scipy.optimize import least_squares, minimize

OT_LO, OT_HI = 100.0, 350.0
M0, K, M1, SIGMA = int(os.environ.get("CONSTRAINED_M0", "3000")), 6, int(os.environ.get("CONSTRAINED_M1", "1000")), 0.03
WORKERS = int(os.environ.get("CONSTRAINED_WORKERS", "7"))
#: local optimizer (2026-10-29): trf (default, Gauss-Newton with box bounds) or lbfgsb (L-BFGS-B on MF^2 with the exact
#: gradient 2 J^T r, then 200 trf evaluations). From random 51-layer starts the residuals are large, the Gauss-Newton
#: Hessian J^T J misses the residual term and trf crawls: on 10 starts trf (3000 nfev) ends at 1.76-20, L-BFGS-B at
#: 0.73-19 (`campaign.log`, 2026-10-29 02:00).
LOCAL = os.environ.get("CONSTRAINED_LOCAL", "trf")
#: H|L next to the substrate: both in turn (default) or H only (the ten 2012 designs of Fig. 3 all start with H)
FIRST = os.environ.get("CONSTRAINED_FIRST", "alt")
#: random starts: uniform (default, mean OT_MEAN) or qw: every layer at q (1 + 0.1 N(0, 1)), q = OT_MEAN U(0.9, 1.1),
#: and 6-12 random layers doubled (half-wave cavities), the structure of the ten 2012 designs of Fig. 3 (most layers
#: 110-170 nm, 6-10 layers at 250-350 nm; fig3_2012_designs.csv)
STARTS = os.environ.get("CONSTRAINED_STARTS", "uniform")
#: mix: each start drawn from one of three kinds: uniform over the whole box [100, 350], uniform around OT_MEAN,
#: or a stack of base U(110, 220) nm (+-10 % per layer) with 0-16 random layers doubled. Wide search, no narrow prior.
#: refinement series: relative sigmas cycled per series (default 0.03 only, as in 2012) and their number K
SIGMAS = [float(v) for v in os.environ.get("CONSTRAINED_SIGMAS", str(SIGMA)).split(",")]
K = int(os.environ.get("CONSTRAINED_K", str(K)))
#: resume (2026-10-29): csv of a previous run; run r starts from its row r (no M0 phase), unset = random starts
RESUME = os.environ.get("CONSTRAINED_RESUME", "")


def local(task):
    """One bounded local optimization; returns (rmse, physical thicknesses)."""
    seq, ot = task
    n = np.array([s.N_IDX[m] for m in seq])
    lo, hi = OT_LO / n, OT_HI / n
    st = s.Stack.of(seq)
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            r, j, _c = st.res_jac(x)
            memo[key] = (r, j)
        return memo[key]

    x0 = np.clip(ot / n, lo, hi)
    if LOCAL == "lbfgsb":

        def fg(x):
            r, j = both(x)
            return float(r @ r), 2.0 * j.T @ r

        x0 = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=list(zip(lo, hi, strict=True)),
                      options={"maxiter": 5000, "maxfun": 10000, "ftol": 1e-15, "gtol": 1e-12}).x
    sol = least_squares(lambda x: both(x)[0], x0, jac=lambda x: both(x)[1], bounds=(lo, hi), method="trf",
                        x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=200)
    x = np.clip(sol.x, lo, hi)
    return s.rmse(seq, x), x


def main() -> None:
    n_layers, ot_mean, runs, minutes = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
    deadline = time.time() + 60 * minutes
    rng = np.random.default_rng(20261028)
    pool = ProcessPoolExecutor(WORKERS)
    name = f"constrained_{s.TARGET}_N{n_layers}" + ("" if LOCAL == "trf" else f"_{LOCAL}") + (
        "" if STARTS == "uniform" else f"_{STARTS}") + ("_resume" if RESUME else "")
    log = (s.HERE / f"{name}.log").open("w", encoding="utf-8")
    best_rows = []
    resumed = list(csv.DictReader((s.HERE / RESUME).open(encoding="utf-8"))) if RESUME else []
    for run in range(runs):
        if time.time() >= deadline:
            break
        shift = 0 if FIRST == "H" else run  # alternation changes with the run unless CONSTRAINED_FIRST=H
        seq = "".join("HL"[(i + shift) % 2] for i in range(n_layers))
        n = np.array([s.N_IDX[m] for m in seq])
        if resumed:
            row = resumed[run % len(resumed)]
            seq, x0 = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
            n = np.array([s.N_IDX[m] for m in seq])
            r0 = s.rmse(seq, x0)
            log.write(f"{time.strftime('%H:%M:%S')} run {run} {seq[0]}.. resumed from {RESUME}: MF {100 * r0:.4f}\n")
        elif STARTS == "mix":
            starts = np.empty((M0, n_layers))
            for row in starts:
                kind = rng.integers(3)
                if kind == 0:
                    row[:] = rng.uniform(OT_LO, OT_HI, n_layers)
                elif kind == 1:
                    width = min(ot_mean - OT_LO, OT_HI - ot_mean)
                    row[:] = rng.uniform(ot_mean - width, ot_mean + width, n_layers)
                else:
                    row[:] = rng.uniform(110.0, 220.0) * (1 + 0.1 * rng.standard_normal(n_layers))
                    row[rng.choice(n_layers, rng.integers(0, 17), replace=False)] *= 2.0
            starts = np.clip(starts, OT_LO, OT_HI)
        elif STARTS == "qw":
            base = ot_mean * rng.uniform(0.9, 1.1, (M0, 1)) * (1 + 0.1 * rng.standard_normal((M0, n_layers)))
            for row in base:
                row[rng.choice(n_layers, rng.integers(6, 13), replace=False)] *= 2.0
            starts = np.clip(base, OT_LO, OT_HI)
        else:
            width = min(ot_mean - OT_LO, OT_HI - ot_mean)
            starts = rng.uniform(ot_mean - width, ot_mean + width, (M0, n_layers))
        if not resumed:
            res = list(pool.map(local, [(seq, x) for x in starts], chunksize=8))
            r0, x0 = min(res, key=lambda t: t[0])
            log.write(f"{time.strftime('%H:%M:%S')} run {run} {seq[0]}.. M0: MF {100 * r0:.4f}\n")
        log.flush()
        for k in range(K):
            if time.time() >= deadline:
                break
            ot0 = x0 * n
            starts = ot0 * (1 + SIGMAS[k % len(SIGMAS)] * rng.standard_normal((M1, n_layers)))
            r1, x1 = min(pool.map(local, [(seq, x) for x in starts], chunksize=8), key=lambda t: t[0])
            if r1 < r0:
                r0, x0 = r1, x1
            log.write(f"{time.strftime('%H:%M:%S')} run {run} series {k + 1}: MF {100 * r0:.4f}\n")
            log.flush()
        ro = s.oracle_rmse(seq, x0)
        best_rows.append({"run": run, "layers": n_layers, "mf_kernel": 100 * r0, "mf_oracle": 100 * ro,
                          "total_ot_nm": s.total_ot(seq, x0), "ot_min": float((x0 * n).min()),
                          "ot_max": float((x0 * n).max()), "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in x0)})
        log.write(f"run {run} best: MF oracle {100 * ro:.4f} TOT {s.total_ot(seq, x0):.1f}\n")
        log.flush()
        with (s.HERE / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(best_rows[0]))
            w.writeheader()
            w.writerows(best_rows)
    pool.shutdown()


if __name__ == "__main__":
    main()
