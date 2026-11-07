"""OIC 2016 B1 (cissoid): give M back to the best Ni, Ag, F, H designs (2026-10-31, owner).

The owner: allow M to be inserted (needles or otherwise) into the most promising four-material designs. Each step tries
M needles at the K most negative P-function points (polished, then cleaned to N <= 50, d >= 3 nm) and every F or H
layer swapped for M at constant optical thickness (polished); the best candidate is kept if it gains, else stop.
The inverse of cissoid_drop_m.py, which showed 2 to 4 M layers carry the quintet basin.
usage: python cissoid_add_m.py FILE.csv [COUNT [OUT.csv]]: the COUNT best distinct designs of FILE.csv (default 3);
output OUT.csv (default cissoid_add_m.csv), one row per design and step.
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def swap(m, d, i):
    d2 = d.copy()
    d2[i] *= co.MATS[m[i]] / co.MATS["M"]
    return co.normalize([*m[:i], "M", *m[i + 1:]], d2, 0.0)


def needle_tasks(m, d):
    co.NEEDLE_MATS = ["M"]
    cands, used = [], set()
    for g, cand, i, z in sorted(co.p_function(m, d)):
        if g >= 0 or len(cands) >= co.K:
            break
        if (cand, i) not in used:
            used.add((cand, i))
            cands.append((*co.insert(m, d, cand, i, z), 0.0))
    return cands


def row(src, step, choice, m, d, r):
    return {"source": src, "step": step, "choice": choice, "layers": len(m), "mf_kernel": r,
            "mf_oracle": co.oracle_mf(m, d), "m_count": m.count("M"), "metals": "".join(x for x in m if x in "AUN"),
            "physical_nm": float(d.sum()), "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}


def main() -> None:
    name, count = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
    out_path = co.s.HERE / (sys.argv[3] if len(sys.argv) > 3 else "cissoid_add_m.csv")
    rows = sorted(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")),
                  key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))
    starts, seen = [], set()
    for r in rows:
        if r["mats"] not in seen and len(starts) < count:
            seen.add(r["mats"])
            starts.append((r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])))
    out = []
    with ProcessPoolExecutor(co.WORKERS) as pool:
        for k, (m, d) in enumerate(starts):
            src = f"{name}:{k}"
            m, d, r = co.polish((m, d, co.FLOOR))
            out.append(row(src, 0, "start", m, d, r))
            print(f"{src} start N {len(m)} MF {r:.5f}", flush=True)
            step = 0
            while True:
                step += 1
                t0 = time.time()
                found = []
                for t in pool.map(co.polish, needle_tasks(m, d)):
                    m2, d2, r2 = co.clean(*t, pool, t0 + 600, lambda s: None)
                    if len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9:
                        found.append(("needle", m2, d2, r2))
                swaps = [i for i, x in enumerate(m) if x in "FH"]
                for i, (m2, d2, r2) in zip(swaps, pool.map(co.polish, [(*swap(m, d, i), co.FLOOR) for i in swaps]),
                                           strict=True):
                    found.append((f"swap {i}{m[i]}", m2, d2, r2))
                if not found:
                    break
                choice, m2, d2, r2 = min(found, key=lambda f: f[3])
                gain = r2 < r * (1 - 1e-3)
                print(f"{src} step {step}: best {choice} N {len(m2)} M {m2.count('M')} MF {r2:.5f} vs {r:.5f} "
                      f"({len(found)} candidates, {time.time() - t0:.0f} s){'' if gain else ', stop'}", flush=True)
                if not gain:
                    break
                m, d, r = m2, d2, r2
                out.append(row(src, step, choice, m, d, r))
                with out_path.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(out[0]))
                    w.writeheader()
                    w.writerows(out)


if __name__ == "__main__":
    main()
