"""OIC 2016 B1 (cissoid), gradual evolution with needles over nine materials, then the cleaner (2026-10-29).

`cissoid_opt.py` (needles, then cleaner) stalled: 0.182 from the example design, 11.6 from a single H layer, against
0.0238 for Trubetskov's deep gradual evolution (AO 59 A75, 2020, Fig. 7) and 0.0139 for the contest winner. Same
problem, kernel, polish, needles and cleaner as `cissoid_opt.py`; added: the evolution step of Trubetskov 2020 (Sec. 2):
each layer alone is thickened until the next local minimum of the one-parameter MF, and a new layer of each dielectric
is tried on top of the stack and next to the substrate in the same way; the DEEP candidates with the lowest MF are
polished in parallel, the best two get needles, the best result is kept (deep search).

Phases, after the owner's manual strategy (2026-10-29: "solve the problem in dielectrics, and at the end allow one or
two metal layers"):
  1. DIEL_SHARE of the time: gradual evolution and needles with the dielectrics only (F, M, H by default);
  2. METAL_SHARE: from the three best dielectric designs with at most N_CLEAN layers, needles over all nine materials
     (same dielectrics) with at most 1, then at most MAX_METALS (env CISSOID_MAX_METALS, default 2) metal layers;
  3. the rest: the three best designs (any phase, at most N_CLEAN layers) cleaned to <= 50 layers of >= 3 nm (the
     contest rules) and judged by the oracle.
Every converged design is recorded.

usage: python cissoid_grow.py MINUTES START   (START: H | example | csv of cissoid_opt; env CISSOID_DEEP, default 7)
outputs: cissoid_grow_{start}.csv, cissoid_grow_{start}.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np

DEEP = int(os.environ.get("CISSOID_DEEP", "7"))
DIEL_SHARE, METAL_SHARE, N_CLEAN = 0.5, 0.2, 90
MAX_METALS = int(os.environ.get("CISSOID_MAX_METALS", "2"))
# owner, 2026-10-30: three dielectrics are enough, the two of highest index contrast (F, H) and a middle one (M,
# nearest to their geometric mean); env CISSOID_DIELECTRICS (letters) to change, 'all' for the six
_DIEL = os.environ.get("CISSOID_DIELECTRICS", "FMH")
DIELECTRICS = [m for m, n in co.MATS.items() if not np.iscomplex(n) and (_DIEL == "all" or m in _DIEL)]
METALS = [m for m, n in co.MATS.items() if np.iscomplex(n)]


def _first_minimum(mats, d, i, new: str | None = None, where: str = "top"):
    """MF at the first local minimum when layer i (or a new layer `new` on top / at the substrate) is thickened."""
    if new is None:
        metal = np.iscomplex(co.MATS[mats[i]])
    else:
        metal = False
        mats = [*mats, new] if where == "top" else [new, *mats]
        d = np.append(d, 0.0) if where == "top" else np.insert(d, 0, 0.0)
        i = len(mats) - 1 if where == "top" else 0
    step, top = (0.5, 40.0) if metal else (2.0, 300.0)
    vals = []
    for k, dz in enumerate(np.arange(step, top + step / 2, step)):
        x = d.copy()
        x[i] += dz
        vals.append((co.mf(mats, x), x))
        if k >= 2 and vals[-2][0] < vals[-3][0] and vals[-2][0] <= vals[-1][0]:
            return vals[-2][0], list(mats), vals[-2][1]
    return None


def grow(mats, d):
    cands = [_first_minimum(mats, d, i) for i in range(len(mats))]
    for m in DIELECTRICS:
        if m != mats[-1]:
            cands.append(_first_minimum(mats, d, None, m, "top"))
        if m != mats[0]:
            cands.append(_first_minimum(mats, d, None, m, "bottom"))
    cands = sorted((c for c in cands if c is not None), key=lambda c: c[0])
    return [(m, x) for _r, m, x in cands[:DEEP]]


def main() -> None:
    minutes, start = float(sys.argv[1]), sys.argv[2]
    t_end = time.time() + 60 * minutes
    t_grow = time.time() + DIEL_SHARE * 60 * minutes
    t_metal = t_grow + METAL_SHARE * 60 * minutes
    tag = start.replace(".csv", "")
    logf = (co.s.HERE / f"cissoid_grow_{tag}.log").open("a", encoding="utf-8")
    rows = []

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    def record(stage, mats, d, r, oracle=False):
        rows.append({"stage": stage, "layers": len(mats), "mf_kernel": r,
                     "mf_oracle": co.oracle_mf(mats, d) if oracle else "", "thinnest_nm": float(d.min()),
                     "physical_nm": float(d.sum()), "metals": sum(np.iscomplex(co.MATS[m]) for m in mats),
                     "mats": " ".join(mats), "d_nm": " ".join(f"{v:.4f}" for v in d)})
        with (co.s.HERE / f"cissoid_grow_{tag}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        log(f"{stage}: N {len(mats)} physical {d.sum():.0f} nm MF {r:.5f}"
            + (f" oracle {rows[-1]['mf_oracle']:.5f}" if oracle else ""))

    pool = ProcessPoolExecutor(co.WORKERS)
    co.NEEDLE_MATS, co.MAX_METALS = list(DIELECTRICS), 0  # phase 1: dielectrics only
    mats, d = co.start_design(start)
    mats, d, r = co.polish((mats, d, 0.0))
    mats, d, r = co.needles(mats, d, r, pool, t_grow, log)
    record("start", mats, d, r)
    step = 0
    while time.time() < t_grow:
        cands = grow(mats, d)
        if not cands:
            log("no layer has a next minimum: stop")
            break
        polished = sorted(pool.map(co.polish, [(m, x, 0.0) for m, x in cands]), key=lambda t: t[2])
        best = None
        for m2, d2, r2 in polished[:2]:
            m2, d2, r2 = co.needles(m2, d2, r2, pool, t_grow, log)
            if best is None or r2 < best[2]:
                best = (m2, d2, r2)
        mats, d, r = best
        step += 1
        record(f"grow {step}", mats, d, r)
    # phase 2: metals at the end, at most 1 then at most MAX_METALS metal layers
    co.NEEDLE_MATS = DIELECTRICS + METALS
    seeds = sorted((row for row in rows if row["layers"] <= N_CLEAN), key=lambda row: row["mf_kernel"])[:3]
    for row in seeds:
        m1, d1, r1 = row["mats"].split(), np.array([float(v) for v in row["d_nm"].split()]), row["mf_kernel"]
        for cap in range(1, MAX_METALS + 1):
            if time.time() >= t_metal:
                break
            co.MAX_METALS = cap
            m1, d1, r1 = co.needles(m1, d1, r1, pool, t_metal, log)
            record(f"metals <= {cap} from '{row['stage']}'", m1, d1, r1)
    usable = sorted((row for row in rows if row["layers"] <= N_CLEAN), key=lambda row: row["mf_kernel"])[:3]
    for k, row in enumerate(usable):
        if time.time() >= t_end:
            break
        m0, d0 = row["mats"].split(), np.array([float(v) for v in row["d_nm"].split()])
        share = t_end - (t_end - time.time()) * (len(usable) - k - 1) / (len(usable) - k)
        m2, d2, r2 = co.clean(m0, d0, row["mf_kernel"], pool, share, log)
        ok = len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9
        record(f"clean of '{row['stage']}'" + ("" if ok else " (unfinished)"), m2, d2, r2, oracle=True)
    pool.shutdown()


if __name__ == "__main__":
    main()
