"""OIC 2016 B1 (cissoid): every combination of 2 then 3 material swaps among the dielectric layers of optical thickness
below OTMAX nm (2026-10-31, owner), to any of the six dielectrics, each polished on the 301 points. Runs in chunks,
prints progress and writes the best design to OUT as soon as it beats the start (judged by the oracle).
usage: python cissoid_otswaps.py IN.csv OUT.csv OTMAX [SIZES]   (SIZES default "2,3")
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


def main() -> None:
    src, dst, otmax = sys.argv[1], sys.argv[2], float(sys.argv[3])
    sizes = [int(v) for v in (sys.argv[4] if len(sys.argv) > 4 else "2,3").split(",")]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    thin = [i for i, x in enumerate(m) if x in "FLBMTH" and co.MATS[x] * d[i] < otmax]
    singles = [(i, y) for i in thin for y in "FLBMTH" if y != m[i]]
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, best = co.polish_full((m, d, co.FLOOR))
        start = best
        print(f"start {best:.5f}; {len(thin)} layers OT < {otmax:g} nm, {len(singles)} single swaps", flush=True)
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
                    how = " ".join(f"{i + 1}{y}" for i, y in chunk[k])
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
