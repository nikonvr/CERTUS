"""OIC 2016 B1 (cissoid): remove the middle dielectric M, leaving Ni, Ag, F, H (2026-10-31, owner).

The owner: replace M by H or F, testing both at each step. Each step tries every remaining M layer as F and as H, at
constant optical thickness, polishes each candidate, and keeps the best one; one layer at a time (replacing them all
at once gave MF 0.21-1.08 in cissoid_three_diel.py).
usage: python cissoid_drop_m.py FILE.csv [K [OUT.csv]]; output: OUT.csv (default cissoid_drop_m.csv), one row per step.
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def candidate(m, d, i, y):
    d2 = d.copy()
    d2[i] *= co.MATS[m[i]] / co.MATS[y]
    return co.normalize([*m[:i], y, *m[i + 1:]], d2, 0.0)


def row(step, choice, m, d, r):
    return {"step": step, "choice": choice, "layers": len(m), "mf_kernel": r, "mf_oracle": co.oracle_mf(m, d),
            "m_left": m.count("M"), "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
            "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}


def main() -> None:
    name = sys.argv[1]
    rows = sorted(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")),
                  key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))
    r0 = rows[int(sys.argv[2]) if len(sys.argv) > 2 else 0]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    out_path = co.s.HERE / (sys.argv[3] if len(sys.argv) > 3 else "cissoid_drop_m.csv")
    out = [row(0, "start", m, d, co.mf(m, d))]
    print(f"start {name}:{r0.get('rank', 0)} N {len(m)} M {m.count('M')} MF {out[0]['mf_kernel']:.5f}", flush=True)
    with ProcessPoolExecutor(co.WORKERS) as pool:
        step = 0
        while "M" in m:
            step += 1
            t0 = time.time()
            tries = [(i, y) for i, x in enumerate(m) if x == "M" for y in "FH"]
            results = list(pool.map(co.polish, [(*candidate(m, d, i, y), co.FLOOR) for i, y in tries]))
            k = int(np.argmin([r for _, _, r in results]))
            (i, y), (m, d, r) = tries[k], results[k]
            scores = " ".join(f"{t[0]}{t[1]}:{res[2]:.4f}" for t, res in zip(tries, results, strict=True))
            print(f"step {step}: layer {i} M -> {y}, N {len(m)}, M left {m.count('M')}, MF {r:.5f} "
                  f"({time.time() - t0:.0f} s; {scores})", flush=True)
            out.append(row(step, f"{i}:M->{y}", m, d, r))
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(out[0]))
                w.writeheader()
                w.writerows(out)
    # the M-free design alone, as a seed ("FILE.csv:0" sorts by MF, which would pick the start, still with M)
    with out_path.with_name(out_path.stem + "_final.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[-1]))
        w.writeheader()
        w.writerow(out[-1])


if __name__ == "__main__":
    main()
