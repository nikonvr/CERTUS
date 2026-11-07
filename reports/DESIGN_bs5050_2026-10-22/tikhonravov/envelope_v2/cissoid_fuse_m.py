"""OIC 2016 B1 (cissoid): grow a Ni, Ag, F, H design to many layers, then come back to 50 by fusing F/H blocks into M.

The owner (2026-10-31): solve with four materials at about 80 layers, then fuse some H F H sequences into M. Herpin's
equivalence read backwards: a block of thin F and H layers acts as one intermediate index, here M (1.8).
1. grow: F and H needles (P-function, K best points, polished) until N >= N_GROW or no gain;
2. come back to N <= 50, d >= 3 nm two ways, from the same grown design, one layer at a time:
   - "remove": Trubetskov's cleaner (`cissoid_opt.clean`), the reference;
   - "fuse": the same removals plus every block of 2 to 4 consecutive dielectric layers fused into one M layer of the
     same optical thickness; the best polished candidate is kept.
usage: python cissoid_fuse_m.py FILE.csv [N_GROW [OUT.csv]] (default 80, cissoid_fuse_m.csv); one row per stage.
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np

N_FINAL = co.N_MAX


def row(stage, m, d, r):
    return {"stage": stage, "layers": len(m), "mf_kernel": r, "mf_oracle": co.oracle_mf(m, d), "m_count": m.count("M"),
            "thinnest_nm": float(d.min()), "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
            "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}


def grow(m, d, r, pool, n_grow):
    co.NEEDLE_MATS = ["F", "H"]
    while len(m) < n_grow:
        cands, used = [], set()
        for g, cand, i, z in sorted(co.p_function(m, d)):
            if g >= 0 or len(cands) >= co.K:
                break
            if (cand, i) not in used:
                used.add((cand, i))
                cands.append((*co.insert(m, d, cand, i, z), 0.0))
        if not cands:
            break
        best = min(pool.map(co.polish, cands), key=lambda t: t[2])
        if best[2] > r * (1 - 1e-3):
            break
        m, d, r = best
        print(f"grow -> N {len(m)} MF {r:.5f}", flush=True)
    return m, d, r


def fusions(m, d):
    out = []
    for i in range(len(m)):
        for w in (2, 3, 4):
            block = m[i:i + w]
            if len(block) < w or any(x in "AUN" for x in block):
                continue
            opt = sum(co.MATS[x] * t for x, t in zip(block, d[i:i + w], strict=True))
            out.append(co.normalize([*m[:i], "M", *m[i + w:]], np.concatenate([d[:i], [opt / co.MATS["M"]], d[i + w:]]),
                                    0.0))
    return out


def fuse_down(m, d, r, pool):
    while len(m) > N_FINAL or d.min() < co.FLOOR:
        t0 = time.time()
        tasks = [(*co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0), 0.0) for i in range(len(m))]
        tasks += [(*f, 0.0) for f in fusions(m, d)]
        m, d, r = min(pool.map(co.polish, tasks), key=lambda t: t[2])
        print(f"fuse -> N {len(m)} M {m.count('M')} MF {r:.5f} thinnest {d.min():.2f} ({len(tasks)} candidates, "
              f"{time.time() - t0:.0f} s)", flush=True)
        if len(m) <= N_FINAL:
            m2, d2, r2 = co.polish((m, d, co.FLOOR))
            if len(m2) <= N_FINAL and d2.min() >= co.FLOOR - 1e-9:
                return m2, d2, r2
    return m, d, r


def main() -> None:
    name = sys.argv[1]
    n_grow = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    out_path = co.s.HERE / (sys.argv[3] if len(sys.argv) > 3 else "cissoid_fuse_m.csv")
    r0 = sorted(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")),
                key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))[0]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    out = []

    def save(stage, m, d, r):
        out.append(row(stage, m, d, r))
        print(f"{stage}: N {len(m)} M {m.count('M')} MF {r:.5f} oracle {out[-1]['mf_oracle']:.5f}", flush=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)

    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, r = co.polish((m, d, co.FLOOR))
        save("start", m, d, r)
        mg, dg, rg = grow(m, d, r, pool, n_grow)
        save("grown", mg, dg, rg)
        save("remove", *co.clean(mg, dg, rg, pool, time.time() + 3600, print))
        save("fuse", *fuse_down(mg, dg, rg, pool))


if __name__ == "__main__":
    main()
