"""OIC 2016 B1: finish the cleaning of `cissoid_grow.py` designs to the contest rules (2026-10-30).

`cissoid_grow.py` shares its last phase between three designs; a removal costs about one minute (each layer removed in
turn, all re-polished), so the cleaning of 90-layer designs may stop above 50 layers ("unfinished" rows). This script
takes the unfinished rows of a `cissoid_grow` csv (else its three best rows with at most N_CLEAN layers) and continues
the same cleaner (`cissoid_opt.clean`) with an equal share of MINUTES each; every result is judged by the oracle.

usage: python cissoid_clean50.py MINUTES CSV   -> cissoid_clean50_{csv stem}.csv, .log
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def main() -> None:
    minutes, name = float(sys.argv[1]), sys.argv[2]
    t_end = time.time() + 60 * minutes
    stem = name.replace(".csv", "")
    rows = list(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")))
    starts = [r for r in rows if "unfinished" in r["stage"]]
    if not starts:
        starts = sorted((r for r in rows if int(r["layers"]) <= 90), key=lambda r: float(r["mf_kernel"]))[:3]
    logf = (co.s.HERE / f"cissoid_clean50_{stem}.log").open("a", encoding="utf-8")

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    out = []
    pool = ProcessPoolExecutor(co.WORKERS)
    for k, row in enumerate(starts):
        m0, d0 = row["mats"].split(), np.array([float(v) for v in row["d_nm"].split()])
        r0 = co.mf(m0, d0)
        log(f"from '{row['stage']}': N {len(m0)} MF {r0:.5f}")
        share = t_end - (t_end - time.time()) * (len(starts) - k - 1) / (len(starts) - k)
        m2, d2, r2 = co.clean(m0, d0, r0, pool, share, log)
        ok = len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9
        out.append({"from": row["stage"], "finished": ok, "layers": len(m2), "mf_kernel": r2,
                    "mf_oracle": co.oracle_mf(m2, d2), "thinnest_nm": float(d2.min()),
                    "physical_nm": float(d2.sum()), "metals": sum(np.iscomplex(co.MATS[m]) for m in m2),
                    "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)})
        log(f"result: N {len(m2)} MF {r2:.5f} oracle {out[-1]['mf_oracle']:.5f} finished {ok}")
        with (co.s.HERE / f"cissoid_clean50_{stem}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
    pool.shutdown()


if __name__ == "__main__":
    main()
