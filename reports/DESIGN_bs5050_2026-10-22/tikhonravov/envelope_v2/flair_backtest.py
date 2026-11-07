"""OIC 2016 B1 (cissoid): backtest of cheap predictors of a material-swap gain on the record chain of 2026-10-31.

For each past transition whose winning swaps are known (pre-design -> swaps, layer index from 0 = substrate side), every
candidate of the same kind is scored on the pre-design by
  raw   MF of the swapped design (optical thicknesses kept, as cissoid_multiswap.apply), not polished;
  gn    one Gauss-Newton step on the thicknesses (unbounded): || r - J lstsq(J, r) ||;
  spK   polish_full with max_nfev K (K in NFEVS);
and singles also by the full polish (max_nfev 300, the search's judge). Prints the rank of the winner under each score.
usage: python flair_backtest.py [OUT_DIR]   (OUT_DIR: one csv of all scores per transition; default: none)
"""

from __future__ import annotations

import csv
import itertools
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cissoid_multiswap as ms
import cissoid_opt as co
import numpy as np
from scipy.stats import spearmanr

DIEL = "FLBMTH"
NFEVS = (10, 30)
TRANSITIONS = [
    ("E", "cissoid_record_0p01375.csv", [(10, "L"), (11, "T")], "pair"),
    ("G", "cissoid_record_0p01316.csv", [(46, "L"), (49, "L")], "pair"),
    ("I", "cissoid_record_0p01299.csv", [(24, "M"), (26, "T")], "pair"),
    ("J", "recon_0p01289", [(40, "L"), (43, "B")], "pair"),
    ("D", "cissoid_record_0p01379.csv", [(14, "T"), (42, "F"), (43, "H")], "combo"),
    ("C", "cissoid_record_force2.csv", [(10, "M"), (22, "B"), (42, "L"), (43, "T")], "combo"),
    ("F", "cissoid_record_exhaustive.csv", [(33, "H")], "single"),
    ("A", "cissoid_record_0p01633.csv", [(1, "T"), (15, "L"), (18, "B"), (28, "L"), (33, "T")], "single"),
]


def load(name: str):
    r = list(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")))[-1]
    return r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])


def score(task):
    m, d, swaps, nfevs = task
    m2, d2 = ms.apply(m, d, swaps)
    r, jac = co.res_jac_full(m2, d2)
    x, *_ = np.linalg.lstsq(jac, r, rcond=None)
    return [float(np.linalg.norm(r)), float(np.linalg.norm(r - jac @ x))] + [
        co.polish_full((m2, d2, co.FLOOR, n))[2] for n in nfevs]


def rank_of(values: np.ndarray, k: int) -> int:
    return int(np.sum(values < values[k])) + 1


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    rng = random.Random(7)
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        for tag, src, win, kind in TRANSITIONS:
            if src == "recon_0p01289":  # the pre-design of dig round 3 was overwritten: undo its pair on the record
                m, d = load("cissoid_record_best.csv")
                m, d = ms.apply(m, d, [(40, "F"), (43, "H")])
            else:
                m, d = load(src)
            m, d, base = co.polish_full((m, d, co.FLOOR))
            assert all(m[i] != y and m[i] in DIEL for i, y in win), (tag, [(i, m[i], y) for i, y in win])
            singles = [(i, y) for i, x in enumerate(m) if x in DIEL for y in DIEL if y != x]
            s_scores = np.array(list(pool.map(score, [(m, d, [c], (*NFEVS, 300)) for c in singles], chunksize=4)))
            names = ["raw", "gn", *[f"sp{n}" for n in NFEVS], "full"]
            rho = {nm: spearmanr(s_scores[:, k], s_scores[:, -1])[0] for k, nm in enumerate(names[:-1])}
            line = " ".join(f"{nm} {v:.2f}" for nm, v in rho.items())
            print(f"[{tag}] {src} base {base:.6f} N {len(m)}; {len(singles)} singles, Spearman vs full: {line}", flush=True)
            for c in win:
                k = singles.index(c)
                ranks = " ".join(f"{nm} {rank_of(s_scores[:, j], k)}" for j, nm in enumerate(names))
                print(f"  single {c[0]}{c[1]} (from {m[c[0]]}, OT {co.MATS[m[c[0]]] * d[c[0]]:.0f}): full MF "
                      f"{s_scores[k, -1]:.5f}; rank among {len(singles)}: {ranks}", flush=True)
            best = int(np.argmin(s_scores[:, -1]))
            print(f"  best single {singles[best][0]}{singles[best][1]} full {s_scores[best, -1]:.5f}", flush=True)
            rows = [(f"{i}{y}", *v) for (i, y), v in zip(singles, s_scores, strict=True)]
            if kind in ("pair", "combo"):
                size = len(win)
                if kind == "pair":
                    cands = [p for p in itertools.combinations(singles, 2) if p[0][0] != p[1][0]]
                else:  # a random sample of the same size, plus the winner
                    cands, seen = [], set()
                    while len(cands) < 20000:
                        p = tuple(sorted(rng.sample(singles, size)))
                        if len({i for i, _ in p}) == size and p not in seen:
                            seen.add(p)
                            cands.append(p)
                wt = tuple(sorted(win))
                if wt not in cands:
                    cands.append(wt)
                c_scores = np.array(list(pool.map(score, [(m, d, list(p), NFEVS) for p in cands], chunksize=16)))
                k = cands.index(wt)
                single_full = {c: v[-1] for c, v in zip(singles, s_scores, strict=True)}
                additive = np.array([sum(single_full[c] - base for c in p) for p in cands])
                ranks = " ".join(f"{nm} {rank_of(c_scores[:, j], k)}" for j, nm in enumerate(names[:-1]))
                print(f"  winner {' '.join(f'{i}{y}' for i, y in win)}: rank among {len(cands)} size-{size} "
                      f"candidates: {ranks} additive-singles {rank_of(additive, k)} ({time.time() - t0:.0f} s)", flush=True)
                rows += [(" ".join(f"{i}{y}" for i, y in p), *v) for p, v in zip(cands, c_scores, strict=True)]
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                with (out_dir / f"flair_{tag}.csv").open("w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(["swaps", *names[: len(rows[0]) - 1]])
                    w.writerows(rows)


if __name__ == "__main__":
    main()
