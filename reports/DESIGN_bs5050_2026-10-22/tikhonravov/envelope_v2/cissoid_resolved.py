"""OIC 2016 B1 (cissoid) optimized on a resolved wavelength grid (2026-11-01, owner: every problem optimized on its
nominal grid and on a resolved one, each design re-optimized on the grid that judges it).

Resolved grid: CISSOID_JUDGE=exact10, 3001 points from 400 to 700 nm against the exact cissoid (cissoid_opt.exact_target).
The record 0.009210 (301 points) gives 0.021876 there and 0.021877 on 6001 points: 0.1 nm resolves it, the 301 points do
not (80 % of its MF^2 within 1 nm of the corners 450, 550 and 650 nm, which they sample only at the corner itself).
repolish: every design of the study (article_figures_cissoid.designs: N <= 50, d >= 3 nm) polished on the resolved grid,
same layers and materials; MF on both grids before and after, by the oracle, to resolved_cissoid_repolish.csv (a name
outside the cissoid_*.csv archive, which stays the nominal grid's).
descend IN OUT HOURS: from the last row of IN, polished on the resolved grid, then descents of flair_campaign (N1, metal
trades, ADD, N2; BEAM when they stall) until nothing gains or HOURS; every gain appended to OUT (last row = best).
usage: CISSOID_JUDGE=exact10 python cissoid_resolved.py repolish
       CISSOID_JUDGE=exact10 python cissoid_resolved.py descend IN.csv OUT.csv HOURS
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import article_figures_cissoid as af
import cissoid_opt as co
import flair_campaign as fc
import numpy as np

NFEV = 600


def nominal(m, d) -> float:
    """MF on the contest's 301 points against its 4-decimal target, by the oracle."""
    return co.oracle_mf(m, d, co.W_CONTEST, co.TGT_CONTEST)


def judged(task) -> tuple[float, float]:
    m, d = task
    return nominal(m, d), co.oracle_mf(m, d)


def repolish() -> None:
    src = af.designs()
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        before = list(pool.map(judged, [(m, d) for m, d, _f in src]))
        res = list(pool.map(co.polish_full, [(m, d, co.FLOOR, NFEV) for m, d, _f in src]))
        after = list(pool.map(judged, [(m, d) for m, d, _f in res]))
    rows = [{"source": f, "layers": len(m2), "ot_d_before": f"{af.ot_d(m, d):.1f}", "ot_d_after": f"{af.ot_d(m2, d2):.1f}",
             "mf_nominal_before": f"{b[0]:.6f}", "mf_resolved_before": f"{b[1]:.6f}",
             "mf_nominal_after": f"{a[0]:.6f}", "mf_resolved_after": f"{a[1]:.6f}",
             "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)}
            for (m, d, f), (m2, d2, _f2), b, a in zip(src, res, before, after, strict=True)]
    with (co.s.HERE / "resolved_cissoid_repolish.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} designs repolished on {len(co.W_FULL)} points ({time.time() - t0:.0f} s)", flush=True)
    for key in ("mf_nominal_before", "mf_resolved_after"):
        b = min(rows, key=lambda r: float(r[key]))
        print(f"  best by {key}: N {b['layers']}, nominal {b['mf_nominal_before']} -> {b['mf_nominal_after']}, "
              f"resolved {b['mf_resolved_before']} -> {b['mf_resolved_after']} ({b['source']})", flush=True)


def save(dst, m, d, f, how) -> None:
    path = co.s.HERE / dst
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["how", "layers", "ot_d_nm", "mf_full", "mf_oracle", "mf_nominal", "mats",
                                           "d_nm"])
        if new:
            w.writeheader()
        w.writerow({"how": how, "layers": len(m), "ot_d_nm": f"{af.ot_d(m, d):.1f}", "mf_full": f"{f:.6f}",
                    "mf_oracle": f"{co.oracle_mf(m, d):.6f}", "mf_nominal": f"{nominal(m, d):.6f}",
                    "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)})


def descend(src, dst, hours) -> None:
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, co.FLOOR, NFEV))
        save(dst, m, d, f, f"polished on {len(co.W_FULL)} points from {src}")
        fc.log(f"start {f:.6f} (resolved), nominal {nominal(m, d):.6f}, N {len(m)}")
        while time.time() < t0 + 3600.0 * hours:
            m2, d2, f2, steps = fc.descend(pool, m, d, f, names=("N1", "MT", "ADD", "N2"), rounds=1)
            if not steps:
                got = fc.stage(pool, "BEAM", m, d, f)
                if not (fc.ok(got[1], got[2]) and got[0] < f * (1 - 1e-4)):
                    break
                m2, d2, f2, steps = got[1], got[2], got[0], [f"beam {got[3]}"]
            m, d, f = m2, d2, f2
            save(dst, m, d, f, steps[0])
            fc.log(f"gain {f:.6f} (resolved), nominal {nominal(m, d):.6f} [{steps[0]}]")
    fc.log(f"done: resolved {co.oracle_mf(m, d):.6f}, nominal {nominal(m, d):.6f} -> {dst}")


if __name__ == "__main__":
    assert co.JUDGE, "set CISSOID_JUDGE (e.g. exact10)"
    if sys.argv[1] == "repolish":
        repolish()
    else:
        descend(sys.argv[2], sys.argv[3], float(sys.argv[4]))
