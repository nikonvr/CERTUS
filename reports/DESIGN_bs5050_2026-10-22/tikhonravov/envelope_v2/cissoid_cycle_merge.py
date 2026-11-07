"""OIC 2016 B1 (cissoid): needle-removal cycles at 50 layers whose removal step may also MERGE (2026-11-01 audit).

Why: reducing the F+H pseudo-rugates, merging 2-4 consecutive dielectric layers into one layer of the six dielectrics
fitted to their characteristic matrix cost less than deleting a layer (0.0112 against 0.0133 at 58 layers,
cissoid_collapse.py). The classic cycle (cissoid_fixedN.cycle) inserts a needle and gets back to 50 by deleting.
Here each of the K best needles (P-function, every allowed material) is inserted and polished, then the design gets
back to 50 by the best of: deleting any layer, or merging any window of 2-3 consecutive dielectric layers into one
fitted layer; screened by a 30-iteration polish, the 6 best polished fully. Repeats while it gains.
usage: python cissoid_cycle_merge.py IN.csv OUT.csv [ROUNDS]
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_collapse as cc
import cissoid_fixedN as fx
import cissoid_opt as co
import numpy as np


def back_to_50(m, d, pool):
    cands = [(f"delete {i}{m[i]}", *co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0)) for i in range(len(m))]
    for k in (2, 3):
        for i in range(len(m) - k + 1):
            if all(x in cc.DIEL for x in m[i:i + k]):
                y, t, _e = cc.single_for(m[i:i + k], d[i:i + k])
                cands.append((f"merge {i}-{i + k - 1}->{y}",
                              *co.normalize([*m[:i], y, *m[i + k:]], np.concatenate([d[:i], [t], d[i + k:]]), 0.0)))
    cands = [c for c in cands if len(c[1]) <= co.N_MAX]
    quick = list(pool.map(co.polish_full, [(cm, cd, co.FLOOR, 30) for _h, cm, cd in cands], chunksize=4))
    order = np.argsort([q[2] for q in quick])[:6]
    full = list(pool.map(co.polish_full, [(cands[k][1], cands[k][2], co.FLOOR) for k in order]))
    j = int(np.argmin([q[2] for q in full]))
    return (*full[j], cands[order[j]][0])


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, co.FLOOR))
        print(f"start {f:.6f}, N {len(m)}", flush=True)
        for rnd in range(rounds):
            p = sorted(g for part in pool.map(fx._p_one, [(m, d, c) for c in co.NEEDLE_MATS]) for g in part)
            needles, used = [], set()
            for g, cand, i, z in p:
                if g >= 0 or len(needles) >= co.K:
                    break
                if (cand, i) not in used:
                    used.add((cand, i))
                    needles.append((cand, i, z))
            grown = list(pool.map(co.polish_full, [(*co.insert(m, d, c, i, z), 0.0) for c, i, z in needles]))
            best = None
            for (c, i, _z), (gm, gd, gf) in zip(needles, grown, strict=True):
                if len(gm) <= co.N_MAX:
                    got = (*co.polish_full((gm, gd, co.FLOOR)), "no removal needed")
                else:
                    got = back_to_50(gm, gd, pool)
                print(f"  round {rnd + 1}: needle {c}@{i} -> N {len(gm)} MF {gf:.5f}; back to {len(got[0])}: "
                      f"{got[2]:.5f} [{got[3]}] ({time.time() - t0:.0f} s)", flush=True)
                if best is None or got[2] < best[2]:
                    best = (*got[:3], f"needle {c}@{i} + {got[3]}")
            if best is None or best[2] >= f * (1 - 1e-4):
                print(f"round {rnd + 1}: no gain (best {best[2] if best else float('nan'):.6f} vs {f:.6f})", flush=True)
                break
            m, d, f = best[0], best[1], best[2]
            o = co.oracle_mf(m, d)
            print(f"round {rnd + 1}: {f:.6f} oracle {o:.6f} [{best[3]}]", flush=True)
            with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["how", "layers", "mf_full", "mf_oracle", "mats", "d_nm"])
                w.writeheader()
                w.writerow({"how": best[3], "layers": len(m), "mf_full": f, "mf_oracle": o, "mats": " ".join(m),
                            "d_nm": " ".join(f"{v:.4f}" for v in d)})


if __name__ == "__main__":
    main()
