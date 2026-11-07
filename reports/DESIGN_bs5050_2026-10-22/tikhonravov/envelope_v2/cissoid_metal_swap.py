"""OIC 2016 B1 (cissoid): swap metal layers for another metal, one at a time, best kept while it gains (2026-10-31, owner).

The owner: see whether changing one or several Ag layers into Au helps. Each step tries every metal layer of a
material in FROM as each material of TO (constant thickness), polishes every candidate on the 301 points, prints every
score, and keeps the best while it gains 1e-3 relative.
usage: python cissoid_metal_swap.py FILE.csv FROM TO [OUT.csv]   e.g. cissoid_islands_swapA.csv A U
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def main() -> None:
    name, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = co.s.HERE / (sys.argv[4] if len(sys.argv) > 4 else "cissoid_metal_swap.csv")
    r0 = sorted(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")),
                key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))[0]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    out = []
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, r = co.polish_full((m, d, co.FLOOR))
        print(f"start N {len(m)} MF {r:.5f} oracle {co.oracle_mf(m, d):.5f}", flush=True)
        step = 0
        while True:
            step += 1
            t0 = time.time()
            tries = [(i, y) for i, x in enumerate(m) if x in src for y in dst if y != x]
            if not tries:
                break
            tasks = [(*co.normalize([*m[:i], y, *m[i + 1:]], d.copy(), 0.0), co.FLOOR) for i, y in tries]
            res = list(pool.map(co.polish_full, tasks))
            print(f"step {step} ({time.time() - t0:.0f} s): " + " ".join(
                f"{i}{m[i]}->{y}:{q[2]:.5f}" for (i, y), q in zip(tries, res, strict=True)), flush=True)
            k = int(np.argmin([q[2] for q in res]))
            if res[k][2] >= r * (1 - 1e-3):
                print(f"stop: best {res[k][2]:.5f} vs {r:.5f}", flush=True)
                break
            (i, y), (m, d, r) = tries[k], res[k]
            o = co.oracle_mf(m, d)
            print(f"step {step}: keep layer {i} -> {y}, MF {r:.5f}, oracle {o:.5f}", flush=True)
            out.append({"step": step, "choice": f"{i}->{y}", "layers": len(m), "mf_full": r, "mf_oracle": o,
                        "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
                        "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)})
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(out[0]))
                w.writeheader()
                w.writerows(out)


if __name__ == "__main__":
    main()
