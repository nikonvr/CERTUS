"""Three-line filter under random thickness errors, judged on the resolved grid (2026-11-01, owner: the article's
robustness of the three-line filter came from the 277 nominal points, which its grid section shows blind to the
resonances hidden between them).

For every design of the nominal N envelope (best MF on the 277 points among the designs of exactly N layers, kept where
it improves on all smaller N, as in article_figures.py), the root of the mean squared MF over DRAWS Monte Carlo draws of
independent optical-thickness errors sigma_OT (alpha_i = sigma / n_i, one generator of seed 1 per sigma, the draws of
article_figures.monte_carlo), each draw judged on the nominal grid and on 0.001 nm steps (grid_study.GRIDS). The
nominal column must give back the numbers of the article's figure (threeline_envelope.csv).
usage: SEARCH_TARGET=threeline python threeline_mc_resolved.py OUT.csv
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import grid_study as gs
import numpy as np
import search as s

SIGMAS, DRAWS = (0.2, 0.5), 300
WORKERS = int(os.environ.get("MC_WORKERS", "2"))


def mc(task) -> list[float]:
    seq, d = task
    out = []
    for sg in SIGMAS:
        rng = np.random.default_rng(1)
        alpha = sg / np.array([s.N_IDX[m] for m in seq])
        nom, res = [], []
        for _ in range(DRAWS):
            x = np.maximum(d + rng.normal(0.0, alpha), 0.0)
            nom.append(gs.mf(seq, x, gs.GRIDS["nominal"]) ** 2)
            res.append(gs.mf(seq, x, gs.GRIDS["resolved"]) ** 2)
        out += [float(np.sqrt(np.mean(nom))), float(np.sqrt(np.mean(res)))]
    return out


def main() -> None:
    rows = list(csv.DictReader(open("grid_threeline_judged.csv", encoding="utf-8")))
    env, best = [], np.inf
    for n in range(1, 121):
        cand = [r for r in rows if int(r["layers"]) == n]
        if cand:
            b = min(cand, key=lambda r: float(r["mf_nominal"]))
            if float(b["mf_nominal"]) < best:
                best = float(b["mf_nominal"])
                env.append(b)
    env.sort(key=lambda r: -int(r["layers"]))
    t0 = time.time()
    print(f"{len(env)} designs of the nominal N envelope, {DRAWS} draws per sigma", flush=True)
    with ProcessPoolExecutor(WORKERS) as pool:
        res = list(pool.map(mc, [(r["seq"], np.array([float(v) for v in r["d_nm"].split()])) for r in env]))
    out = sorted(({"layers": r["layers"], "tot": r["tot"], "mf_nominal": r["mf_nominal"], "mf_resolved": r["mf_resolved"],
                   **{f"mc_{g}_sigma{sg}": f"{v:.6e}"
                      for (sg, g), v in zip([(sg, g) for sg in SIGMAS for g in ("nominal", "resolved")], vals,
                                            strict=True)}}
                  for r, vals in zip(env, res, strict=True)), key=lambda r: int(r["layers"]))
    with open(sys.argv[1], "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"done ({time.time() - t0:.0f} s) -> {sys.argv[1]}", flush=True)


if __name__ == "__main__":
    main()
