"""Quarter-wave starts at imposed TOT for the three-line filter (2026-10-29, AUDIT section 6 point 1(b)).

Trubetskov 2020's deep design (Fig. 4, `fig4_2020_designs.csv`) is a quasi quarter-wave stack at 550 nm (median optical
thickness 139 nm, 1 layer under 20 nm) cut by a few near half-wave layers (coupled cavities); 101 x 137.5 nm is about
its TOT. Our needle trajectories never start there. Here every start is a quarter-wave stack of N layers at QW nm
(optical thickness), each layer multiplied by (1 + sigma * g), g standard normal, rescaled to TOT, then settled,
needled and cleaned at that TOT with `gradual.py`'s functions (env GRAD_DEEP, GRAD_CLEAN apply).

usage: python qwstart.py MINUTES TOT   (env QW_N "99,101,103", QW_SIGMAS "0.1,0.3,0.6", QW_NM 137.5, QW_WORKERS 7)
outputs: qwstart_{TOT}.csv (every finished start), qwstart_{TOT}.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("SEARCH_TARGET", "threeline")
import gradual as g  # noqa: E402
import numpy as np  # noqa: E402
import search as s  # noqa: E402

NS = [int(v) for v in os.environ.get("QW_N", "99,101,103").split(",")]
SIGMAS = [float(v) for v in os.environ.get("QW_SIGMAS", "0.1,0.3,0.6").split(",")]
QW = float(os.environ.get("QW_NM", "137.5"))
WORKERS = int(os.environ.get("QW_WORKERS", "7"))


def run(task):
    k, n, first, sigma, tot, deadline = task
    rng = np.random.default_rng(k)  # the start depends on its index only
    seq = "".join(first if i % 2 == 0 else s.other(first) for i in range(n))
    ot = QW * np.maximum(0.05, 1.0 + sigma * rng.standard_normal(n))
    ot *= tot / ot.sum()
    d = ot / np.array([s.N_IDX[m] for m in seq])
    seq, d, r = g.settle(seq, d, tot)
    seq, d, r = g.needles(seq, d, r, deadline, tot)
    seq, d, r = g.clean(seq, d, r, deadline, tot)
    return {"start": k, "n0": n, "first": first, "sigma": sigma, "total_ot_nm": s.total_ot(seq, d), "layers": len(seq),
            "mf_kernel": 100 * r, "mf_oracle": 100 * s.oracle_rmse(seq, d), "seq": seq,
            "d_nm": " ".join(f"{v:.6f}" for v in d)}


def main() -> None:
    minutes, tot = float(sys.argv[1]), float(sys.argv[2])
    deadline = time.time() + 60.0 * minutes
    tag = f"qwstart_{tot:.0f}"
    log = (s.HERE / f"{tag}.log").open("w", encoding="utf-8")
    combos = [(n, f, sg) for sg in SIGMAS for n in NS for f in "HL"]
    rows, best = [], None
    with ProcessPoolExecutor(WORKERS) as pool:
        k = 0
        while time.time() < deadline:
            tasks = []
            for _ in range(WORKERS):
                n, f, sg = combos[k % len(combos)]
                tasks.append((k, n, f, sg, tot, deadline))
                k += 1
            for row in pool.map(run, tasks):
                rows.append(row)
                if best is None or row["mf_oracle"] < best["mf_oracle"]:
                    best = row
                log.write(f"{time.strftime('%H:%M:%S')} start {row['start']} N0 {row['n0']} {row['first']} "
                          f"sigma {row['sigma']} -> N {row['layers']} MF {row['mf_oracle']:.4f} "
                          f"(best {best['mf_oracle']:.4f})\n")
                log.flush()
            with (s.HERE / f"{tag}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    log.write("written\n")
    log.close()


if __name__ == "__main__":
    main()
