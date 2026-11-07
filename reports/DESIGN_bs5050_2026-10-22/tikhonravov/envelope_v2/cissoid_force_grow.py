"""OIC 2016 B1 (cissoid): forced growth, then reduction (2026-10-31, owner: let the stack grow, then reduce).

On the 0.01633 record no needle gains, so the overshoot never grows (grow 55-70 gave the record back bit for bit).
Here the growth is forced: each trial inserts FORCE_SIZES needles (2, 3 or 4) drawn among the 30 best P-function points, gaining or
not, in distinct layers (dielectric 15 nm, metal 3 nm), polishes them with d >= 3 nm so they stay, removes layers
back to 50 (`cissoid_fixedN.removal`), then cycles and swap rounds; judged by the 301-point polish and the oracle.
A new best becomes the start of the next trials.
usage: python cissoid_force_grow.py IN.csv OUT.csv TRIALS   (env as cissoid_islands.py: dielectrics, metals, grid)
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_islands as ci
import cissoid_opt as co
import numpy as np

# needles inserted per trial (2026-10-31: 2 won at once on the 0.01448, 8 gave 0.0548)
SIZES = [int(v) for v in os.environ.get("FORCE_SIZES", "2,3,4").split(",")]


def main() -> None:
    src, dst, trials = sys.argv[1], sys.argv[2], int(sys.argv[3])
    r0 = next(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    m0, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    rng = np.random.default_rng(57)
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, best = co.polish_full((m0, d0, co.FLOOR))
        print(f"start: 301-point MF {best:.5f}; needles {co.NEEDLE_MATS}", flush=True)
        def needle_points(m, d):
            cands, used = [], set()
            for g, cand, i, z in sorted(co.p_function(m, d)):
                if i not in used and len(cands) < 30:
                    used.add(i)
                    cands.append((g, cand, i, z))
            return cands

        cands = needle_points(m0, d0)
        print("best needles: " + " ".join(f"{c}@{i}:{g:.2e}" for g, c, i, _z in cands[:10]), flush=True)
        for t in range(trials):
            n_ins = int(rng.choice(SIZES))
            pick = sorted(rng.choice(len(cands), size=n_ins, replace=False), key=lambda k: -cands[k][2])
            m, d = list(m0), d0.copy()
            for k in pick:  # from the substrate side, so the earlier layer indices stay valid
                _g, cand, i, z = cands[k]
                m, d = co.insert(m, d, cand, i, z, 3.0 if fx.is_metal(cand) else 15.0)
            m, d, _r = co.polish((m, d, co.FLOOR))
            n_up = len(m)
            while len(m) > co.N_MAX:
                m, d, _r = fx.removal(m, d, pool)
            m, d, r = fx.feasible(m, d)
            for _ in range(5):
                got = fx.cycle(m, d, pool)
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, d, r = got
            m, d, r, kept = ci.swap_round(m, d, r, pool)
            m, d, f = co.polish_full((m, d, co.FLOOR))
            ok = len(m) <= co.N_MAX and d.min() >= co.FLOOR - 1e-9
            tag = ""
            if ok and f < best * (1 - 1e-4):
                best, o = f, co.oracle_mf(m, d)
                # 2026-10-31 (owner: start again from the current winner): the next trials grow the new best
                m0, d0 = list(m), d.copy()
                cands = needle_points(m0, d0)
                tag = f"  NEW BEST, oracle {o:.5f}"
                row = {"how": f"force {n_ins} needles", "layers": len(m), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
                       "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
                       "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}
                with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(row))
                    w.writeheader()
                    w.writerow(row)
            print(f"trial {t}: {n_ins} needles -> N {n_up}, back to {len(m)}, {kept} swaps, 301-point {f:.5f}"
                  f"{tag} ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
