"""Seed of a high-performance design (2026-10-29, AUDIT_2026-10-28.md section 6 point 7).

A seed of S* is a design with fewer layers whose redeployment by needle optimization leads back to the basin of S*.
  reduce: from S*, remove one layer at a time (an interior removal merges the two neighbours, N - 2; an end layer,
          N - 1), polish (free thicknesses >= 0, free TOT), keep a beam of the BEAM best distinct designs; the best
          design of every N in TARGETS is written to seed_<name>_N<n>.csv (format of gradual.py, GRAD_RESUME).
  judge:  after the redeployments (gradual.py with GRAD_RESUME=seed_...csv: needles at the seed TOT), the MF and the
          alignment distance (`design_distance.py`) of each redeployed design to S*.

usage: python seed.py reduce CSV:ROW NAME MINUTES      (env SEED_BEAM, default 3; SEED_WORKERS, default 7)
       python seed.py judge CSV:ROW NAME
"""

from __future__ import annotations

import csv
import glob
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from design_distance import align, layers, load  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

BEAM = int(os.environ.get("SEED_BEAM", "3"))
WORKERS = int(os.environ.get("SEED_WORKERS", "7"))
TARGETS = (90, 80, 70, 60, 50, 40, 30, 20)
THIN = 0.3  # nm, thinner layers are dropped (as in gradual.py)


SCREEN = 60  # evaluations of the screening polish of every removal; the 2 BEAM best get FULL
FULL = 300


def polish(task):
    seq, d, nfev = task
    st = s.Stack.of(seq)
    sol = least_squares(lambda x: st.res_jac(x)[0], np.maximum(d, 0.0), jac=lambda x: st.res_jac(x)[1],
                        bounds=(0.0, np.inf), method="trf", x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12,
                        max_nfev=nfev)
    seq2, d2 = s.normalize(seq, np.maximum(sol.x, 0.0), THIN)
    return seq2, d2, s.rmse(seq2, d2)


def removals(seq: str, d: np.ndarray):
    out, n = [], len(seq)
    for i in range(n):
        if 0 < i < n - 1:
            out.append((seq[: i - 1] + seq[i - 1] + seq[i + 2:],
                        np.concatenate([d[: i - 1], [d[i - 1] + d[i + 1]], d[i + 2:]])))
        else:
            out.append((seq[:i] + seq[i + 1:], np.delete(d, i)))
    return out


def write(path, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def row(seq, d, r, **extra):
    return {**extra, "total_ot_nm": s.total_ot(seq, d), "layers": len(seq), "mf_kernel": 100 * r,
            "mf_oracle": 100 * s.oracle_rmse(seq, d), "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)}


def reduce(spec: str, name: str, minutes: float) -> None:
    deadline = time.time() + 60 * minutes
    seq, d = load(spec)
    d = np.array(d)
    log = (s.HERE / f"seed_{name}.log").open("w", encoding="utf-8")
    pool = ProcessPoolExecutor(WORKERS)
    beam = [(s.rmse(seq, d), seq, d)]
    log.write(f"{time.strftime('%H:%M:%S')} S* N {len(seq)} MF {100 * beam[0][0]:.4f} TOT {s.total_ot(seq, d):.1f}\n")
    log.flush()
    done = set()
    while beam and len(beam[0][1]) > min(TARGETS) and time.time() < deadline:
        tasks = [(*t, SCREEN) for _r, q, x in beam for t in removals(q, x)]
        res = sorted(pool.map(polish, tasks, chunksize=4), key=lambda t: t[2])
        res = sorted(pool.map(polish, [(q, x, FULL) for q, x, _r in res[: 2 * BEAM]]), key=lambda t: t[2])
        nxt, seen = [], set()
        for q, x, r in res:
            key = (q, tuple(np.round(x * np.array([s.N_IDX[m] for m in q]), 0)))
            if key in seen:
                continue
            seen.add(key)
            nxt.append((r, q, x))
            if len(nxt) == BEAM:
                break
        # the beam keeps a common N: designs one layer longer than the shortest wait one step
        beam = sorted(nxt, key=lambda t: t[0])
        r, q, x = beam[0]
        log.write(f"{time.strftime('%H:%M:%S')} N {len(q)} MF {100 * r:.4f} TOT {s.total_ot(q, x):.1f} "
                  f"(beam {' '.join(f'{len(b[1])}:{100 * b[0]:.4f}' for b in beam)})\n")
        log.flush()
        for tgt in TARGETS:
            if tgt not in done and len(q) <= tgt:
                done.add(tgt)
                write(s.HERE / f"seed_{name}_N{tgt}.csv", [row(q, x, r, target=tgt)])
    pool.shutdown()


def judge(spec: str, name: str) -> None:
    star = load(spec)
    a = layers(*star)
    mf_star = 100 * s.oracle_rmse(star[0], np.array(star[1]))
    print(f"S*: N {len(star[0])} MF {mf_star:.4f}")
    out = []
    for path in sorted(glob.glob(str(s.HERE / f"gradual_classic_cont_seed_{name}_N*.csv"))):
        if path.endswith("_partial.csv"):
            continue
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        last = rows[-1]
        seq, d = last["seq"], np.array([float(v) for v in last["d_nm"].split()])
        seed_path = s.HERE / os.path.basename(path).split("gradual_classic_cont_")[1]
        seed = next(csv.DictReader(open(seed_path, encoding="utf-8"))) if seed_path.exists() else None
        dist = align(a, layers(seq, d), 0.0)[0]
        tot = 0.5 * (sum(t for _m, t in a) + s.total_ot(seq, d))
        out.append({"seed": os.path.basename(path), "seed_layers": seed["layers"] if seed else "",
                    "seed_mf": seed["mf_oracle"] if seed else "", "final_layers": len(seq),
                    "final_mf": 100 * s.oracle_rmse(seq, d), "final_tot": s.total_ot(seq, d),
                    "distance_to_star_pct": 100 * dist / tot})
        print(" ".join(f"{k} {v}" if isinstance(v, str) else f"{k} {v:.4f}" for k, v in out[-1].items()))
    if out:
        write(s.HERE / f"seed_{name}_judge.csv", out)


if __name__ == "__main__":
    (reduce if sys.argv[1] == "reduce" else judge)(*sys.argv[2:4], *([float(sys.argv[4])] if sys.argv[1] == "reduce" else []))
