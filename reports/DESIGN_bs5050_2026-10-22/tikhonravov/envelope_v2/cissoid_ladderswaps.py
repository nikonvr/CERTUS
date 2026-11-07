"""OIC 2016 B1 (cissoid): every combination of 1..k material swaps among ALL dielectric layers, each layer going only to
its neighbour on the index ladder F < L < B < M < T < H (2026-11-01: 25 of the 28 winning swaps of 2026-10-31 were
ladder neighbours), each polished on the 301 points. Same chunks, progress and output as cissoid_otswaps.py, but layer
labels count from 0 (as cissoid_exhaustive.py), index 0 = substrate side.
usage: python cissoid_ladderswaps.py IN.csv OUT.csv [SIZES]   (SIZES default "1,2,3")
"""

from __future__ import annotations

import csv
import itertools
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_multiswap as ms
import cissoid_opt as co
import numpy as np

LADDER = "FLBMTH"


def neighbours(x: str) -> list[str]:
    k = LADDER.index(x)
    return [LADDER[j] for j in (k - 1, k + 1) if 0 <= j < len(LADDER)]


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    sizes = [int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "1,2,3").split(",")]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    singles = [(i, y) for i, x in enumerate(m) if x in LADDER for y in neighbours(x)]
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, best = co.polish_full((m, d, co.FLOOR))
        start = best
        print(f"start {best:.5f}; {sum(x in LADDER for x in m)} dielectric layers, {len(singles)} ladder swaps", flush=True)
        for n in sizes:
            combos = [c for c in itertools.combinations(singles, n) if len({i for i, _ in c}) == n]
            done = 0
            for lo in range(0, len(combos), 3000):
                chunk = combos[lo:lo + 3000]
                res = list(pool.map(co.polish_full, [(*ms.apply(m, d, c), co.FLOOR) for c in chunk], chunksize=8))
                done += len(chunk)
                k = int(np.argmin([q[2] for q in res]))
                m2, d2, f = res[k]
                if f < best * (1 - 1e-4) and len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9:
                    best, o = f, co.oracle_mf(m2, d2)
                    how = " ".join(f"{i}{y}" for i, y in chunk[k])
                    print(f"NEW BEST size {n} [{how}]: oracle {o:.5f}", flush=True)
                    row = {"how": how, "layers": len(m2), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
                           "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)}
                    with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                        w = csv.DictWriter(fh, fieldnames=list(row))
                        w.writeheader()
                        w.writerow(row)
                print(f"size {n}: {done}/{len(combos)}, best {best:.5f} (start {start:.5f}, {time.time() - t0:.0f} s)",
                      flush=True)


if __name__ == "__main__":
    main()
