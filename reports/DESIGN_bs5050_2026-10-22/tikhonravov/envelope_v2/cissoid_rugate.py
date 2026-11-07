"""OIC 2016 B1 (cissoid): pseudo-rugate conversion to fewer dielectrics, then reduction to 50 layers (2026-11-01, owner).

Each dielectric layer whose material is not kept becomes symmetric cells of the two kept dielectrics that bracket
its index, fitted to its characteristic matrix (cissoid_herpin.py, "fit"), periods of about RUGATE_PERIOD nm.
Metals are unchanged. The converted stack is polished on the 301 points (sub-layers under 3 nm allowed), then layers
are removed one at a time (removal_thin: among the RUGATE_CANDIDATES thinnest) until N <= 50, then needle-removal
cycles, a feasible polish (d >= 3 nm) and the oracle.
Run with CISSOID_DIELECTRICS set to the kept dielectrics, so that needles and cycles use only them.
usage: python cissoid_rugate.py IN.csv KEPT OUT.csv   e.g. KEPT = FH, FMH, FBH
"""

from __future__ import annotations

import csv
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_herpin as hp
import cissoid_opt as co
import numpy as np

PERIOD = float(os.environ.get("RUGATE_PERIOD", "30"))


CANDIDATES = int(os.environ.get("RUGATE_CANDIDATES", "40"))  # removals tried per step: the thinnest layers (OT)


def removal_thin(m, d, pool):
    """Remove one layer among the CANDIDATES optically thinnest (all ~380 would cost hours per step): each removal
    polished 30 iterations, the 6 best fully, the best kept."""
    ot = [abs(co.MATS[x]) * t for x, t in zip(m, d, strict=True)]
    idx = np.argsort(ot)[:CANDIDATES]
    tasks = [(*co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0), 0.0) for i in idx]
    quick = sorted(pool.map(co.polish, [(*t, 30) for t in tasks]), key=lambda t: t[2])
    return min(pool.map(co.polish, [(mm, x, 0.0) for mm, x, _r in quick[:6]]), key=lambda t: t[2])


def main() -> None:
    src, kept, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    # env RUGATE_FROM (2026-11-01): resume from the row of IN whose "step" is this (e.g. "stage 75"), no conversion
    resume = os.environ.get("RUGATE_FROM", "")
    all_rows = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    r0 = next(r for r in all_rows if r["step"] == resume) if resume else all_rows[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    rows = []

    def keep_row(tag, m, d, f):
        o = co.oracle_mf(m, d) if len(m) <= 400 else float("nan")
        rows.append({"step": tag, "layers": len(m), "mf_full": f, "mf_oracle": o, "mats": " ".join(m),
                     "d_nm": " ".join(f"{v:.4f}" for v in d)})
        with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{tag}: N {len(m)}, MF {f:.5f}, oracle {o:.5f} ({time.time() - t0:.0f} s)", flush=True)

    with ProcessPoolExecutor(co.WORKERS) as pool:
        # 2026-11-01 (owner): each layer replaced by symmetric cells whose characteristic matrix is fitted to the
        # layer's (cissoid_herpin.py: unpolished MF 0.143 at 30 nm periods, against 3.95 for the plain mixture)
        if not resume:
            m, d = hp.convert(m, d, kept, "fit", PERIOD)
            keep_row("converted", m, d, co.mf_full(m, d))
        m, d, f = co.polish_full((m, d, 0.0))  # sub-layers under 3 nm stay until the reduction
        keep_row("resumed+polish" if resume else "converted+polish", m, d, f)
        k = 0
        # env RUGATE_STAGES (2026-11-01, owner: the straight reduction lost everything): layer counts where the
        # reduction pauses for up to 5 needle-removal cycles at that count, e.g. "200,140,100,75"; empty = straight
        for target in [int(v) for v in os.environ.get("RUGATE_STAGES", "").split(",") if v] + [co.N_MAX]:
            while len(m) > target:
                m, d, f = removal_thin(m, d, pool)
                k += 1
                if k % 10 == 0 or len(m) <= target:
                    print(f"  removal {k}: N {len(m)}, MF {f:.5f} ({time.time() - t0:.0f} s)", flush=True)
            if target == co.N_MAX:
                break
            keep_n, co.N_MAX = co.N_MAX, target  # the cycles grow a needle then remove back to this count
            for c in range(5):
                got = fx.cycle(m, d, pool)
                if got is None or got[2] >= f * (1 - 1e-4):
                    break
                m, d, f = got
                print(f"  stage {target}, cycle {c + 1}: N {len(m)}, MF {f:.5f} ({time.time() - t0:.0f} s)", flush=True)
            co.N_MAX = keep_n
            keep_row(f"stage {target}", m, d, f)
        m, d, f = fx.feasible(m, d)
        keep_row("reduced to <= 50", m, d, f)
        for c in range(10):
            got = fx.cycle(m, d, pool)
            if got is None or got[2] >= f * (1 - 1e-4):
                break
            m, d, f = got
            print(f"  cycle {c + 1}: N {len(m)}, MF {f:.5f} ({time.time() - t0:.0f} s)", flush=True)
        m, d, f = co.polish_full((m, d, co.FLOOR))
        keep_row("final", m, d, f)
        print(f"done: materials {sorted(set(m))}, record to beat 0.012869", flush=True)


if __name__ == "__main__":
    main()
