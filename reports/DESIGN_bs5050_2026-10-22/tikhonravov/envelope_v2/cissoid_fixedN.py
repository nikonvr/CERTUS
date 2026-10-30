"""OIC 2016 B1 (cissoid) under the contest rules at every step: needle-removal cycles at N <= 50, d >= 3 nm (2026-10-30).

Growing then cleaning (`cissoid_grow.py`, `cissoid_clean50.py`) lets N reach 90-140 before the cut to 50; here every
accepted design obeys the rules (<= 50 layers, each >= 3 nm, at most MAX_METALS metal layers). One cycle:
  1. P-function over the allowed materials (`cissoid_opt.p_function`), the K best insertions polished in parallel;
  2. for the two best, if N + 1 > 50, the cleaner's removal step (each layer removed in turn, re-polished, best kept);
  3. a last polish with d >= 3 nm; the cycle is accepted if the MF drops.
When a cycle fails, a kick (basin hopping, accept if better): every thickness scaled by 1 + 0.05 g (g normal), or one
dielectric layer changed to another allowed dielectric, or one metal layer moved by one position; then cycles again.
Draws come from a generator seeded per start (reproducible for one start list).

Starts (STARTS, comma-separated): `example` (their 43-layer design), a csv of `cissoid_clean50.py` or of
`cissoid_grow.py` (`file.csv:k`, the k-th lowest-MF row with at most 50 layers; metals are added by the first
cycles). MINUTES are shared equally.

usage: python cissoid_fixedN.py MINUTES STARTS   (env CISSOID_DIELECTRICS, default FMH; CISSOID_MAX_METALS, default 2)
outputs: cissoid_fixedN.csv (best design of each start, oracle MF), cissoid_fixedN.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np

_DIEL = os.environ.get("CISSOID_DIELECTRICS", "FMH")
DIELECTRICS = [m for m, n in co.MATS.items() if not np.iscomplex(n) and (_DIEL == "all" or m in _DIEL)]
# env CISSOID_METALS (letters A Ag, U Au, N Ni), default all three; the owner (2026-10-30): restrict to Au and Ni if
# the searches confirm them
_MET = os.environ.get("CISSOID_METALS", "AUN")
METALS = [m for m, n in co.MATS.items() if np.iscomplex(n) and m in _MET]
co.NEEDLE_MATS = DIELECTRICS + METALS
co.MAX_METALS = int(os.environ.get("CISSOID_MAX_METALS", "2"))
KICK_SIGMA = 0.05


def is_metal(m: str) -> bool:
    return bool(np.iscomplex(co.MATS[m]))


def feasible(mats, d):
    """Polish with d >= 3 nm; the design must already hold <= 50 layers."""
    m2, d2 = co.normalize(mats, np.maximum(d, co.FLOOR), 0.0)
    return co.polish((m2, d2, co.FLOOR))


def removal(mats, d, pool):
    tasks = [(*co.normalize(mats[:i] + mats[i + 1:], np.delete(d, i), 0.0), 0.0) for i in range(len(mats))]
    return min(pool.map(co.polish, tasks), key=lambda t: t[2])


def _p_one(task):
    """P-function of one material, in a worker (the main process stays free; same list as `co.p_function`)."""
    mats, d, cand = task
    keep = co.NEEDLE_MATS
    co.NEEDLE_MATS = [cand]
    try:
        return co.p_function(mats, d)
    finally:
        co.NEEDLE_MATS = keep


def cycle(mats, d, pool):
    """One needle-removal cycle; returns the best feasible design it reached (may be worse than the input)."""
    p = sorted(g for part in pool.map(_p_one, [(mats, d, c) for c in co.NEEDLE_MATS]) for g in part)
    # a needle inside a metal layer splits it in two metal layers (2026-10-30: "ANN" under MAX_METALS 2, "NNNUNAN"
    # under 6): count the metal layers after the insertion
    base = sum(map(is_metal, mats))
    cands, used = [], set()
    for g, cand, i, z in p:
        if g >= 0 or len(cands) >= co.K:
            break
        split = z > 0 and i < len(mats) and is_metal(mats[i]) and mats[i] != cand
        if co.MAX_METALS is not None and base + is_metal(cand) + split > co.MAX_METALS:
            continue
        if (cand, i) not in used:
            used.add((cand, i))
            cands.append((cand, i, z))
    if not cands:
        return None
    grown = sorted(pool.map(co.polish, [(*co.insert(mats, d, c, i, z), 0.0) for c, i, z in cands]),
                   key=lambda t: t[2])[:2]
    out = []
    for m2, d2, _r in grown:
        while len(m2) > co.N_MAX:
            m2, d2, _r = removal(m2, d2, pool)
        out.append((m2, d2))
    return min(pool.map(feasible, [m for m, _ in out], [x for _, x in out]), key=lambda t: t[2])


def kick(mats, d, rng):
    mats, d = list(mats), d.copy()
    kind = rng.integers(3)
    diel = [i for i, m in enumerate(mats) if not is_metal(m)]
    metal = [i for i, m in enumerate(mats) if is_metal(m)]
    if kind == 1 and diel and len(DIELECTRICS) > 1:
        i = int(rng.choice(diel))
        mats[i] = str(rng.choice([m for m in DIELECTRICS if m != mats[i]]))
    elif kind == 2 and metal and len(mats) > 2:
        i = int(rng.choice(metal))
        j = int(np.clip(i + rng.choice([-1, 1]), 0, len(mats) - 1))
        mats[i], mats[j], d[i], d[j] = mats[j], mats[i], d[j], d[i]
    else:
        d = d * (1.0 + KICK_SIGMA * rng.standard_normal(len(d)))
    return co.normalize(mats, np.maximum(d, co.FLOOR), 0.0)


def start_design(spec: str):
    if spec == "example":
        return co.start_design("example")
    name, _, k = spec.partition(":")
    rows = list(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")))
    rows = sorted((r for r in rows if int(r["layers"]) <= co.N_MAX), key=lambda r: float(r["mf_kernel"]))
    r = rows[int(k or 0)]
    return r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])


def main() -> None:
    minutes, starts = float(sys.argv[1]), sys.argv[2].split(",")
    t_end = time.time() + 60 * minutes
    logf = (co.s.HERE / "cissoid_fixedN.log").open("a", encoding="utf-8")
    out = []

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    log(f"start: {minutes} min, starts {starts}, dielectrics {DIELECTRICS}, metals <= {co.MAX_METALS}, K {co.K}")
    pool = ProcessPoolExecutor(co.WORKERS)
    for n, spec in enumerate(starts):
        deadline = t_end - (t_end - time.time()) * (len(starts) - n - 1) / (len(starts) - n)
        rng = np.random.default_rng(1000 + n)
        mats, d = start_design(spec)
        while len(mats) > co.N_MAX:
            mats, d, _r = removal(mats, d, pool)
        mats, d, r = feasible(mats, d)
        log(f"[{spec}] feasible start: N {len(mats)} metals {sum(map(is_metal, mats))} MF {r:.5f}")
        best = (mats, d, r)
        cur = best
        kicks = 0
        while time.time() < deadline:
            got = cycle(cur[0], cur[1], pool)
            if got is not None and got[2] < cur[2] * (1 - 1e-4):
                cur = got
                if cur[2] < best[2]:
                    best = cur
                    log(f"[{spec}] cycle -> N {len(best[0])} metals {sum(map(is_metal, best[0]))} MF {best[2]:.5f}")
                continue
            kicks += 1
            cur = feasible(*kick(best[0], best[1], rng))
        m, x, r = best
        out.append({"start": spec, "layers": len(m), "metals": sum(map(is_metal, m)), "mf_kernel": r,
                    "mf_oracle": co.oracle_mf(m, x), "thinnest_nm": float(x.min()), "physical_nm": float(x.sum()),
                    "kicks": kicks, "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in x)})
        log(f"[{spec}] best: N {len(m)} MF {r:.5f} oracle {out[-1]['mf_oracle']:.5f} thinnest {x.min():.2f} "
            f"physical {x.sum():.0f} nm, {kicks} kicks")
        with (co.s.HERE / "cissoid_fixedN.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
    pool.shutdown()


if __name__ == "__main__":
    main()
