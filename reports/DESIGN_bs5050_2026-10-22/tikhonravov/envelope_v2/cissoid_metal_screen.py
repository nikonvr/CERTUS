"""OIC 2016 B1 (cissoid): metal trades judged after a quick descent, not after a polish (2026-11-01, trend analysis).

Why (cissoid_evolution.py): along the 28 records the Ag layers went from 10 to 6, each removal or conversion a gain
(Ag 27 -> H, Ag 18 -> F, the Ag needle 2 -> M); Ni stayed at 6; T and M receded, B and L grew. The metal trades of the
descents (flair_campaign MT) are judged by a polish alone, which misses a trade that loses a little but opens a cascade,
as the slot trades showed (a +7 % trade became the record after its descent).
For each start (the record and the K most different elites, cissoid_slot_screen.elites): every metal layer deleted,
turned into each of the six dielectrics (same physical thickness) or into the other metal, polished; the best 8
distinct trades get a quick descent (N1, metal trades, ADD; 2 rounds), the best 2 of all the full descent; descended
designs go to the elite pool; a design under the record is written to OUT at once.
usage: python cissoid_metal_screen.py OUT.csv K
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import cissoid_slot_screen as ss
import cissoid_slot_trade as st
import flair_campaign as fc
import numpy as np


def main() -> None:
    dst, k_elites = sys.argv[1], int(sys.argv[2])
    best_row = next(csv.DictReader((co.s.HERE / "cissoid_record_best.csv").open(encoding="utf-8")))
    record = float(best_row["mf_oracle"])
    starts = [ss.load("cissoid_record_best.csv"), *ss.elites(k_elites, best_row["mats"])]
    t0, quick = time.time(), []
    with ProcessPoolExecutor(co.WORKERS) as pool:
        for src, m, d in starts:
            m, d, base = co.polish_full((m, d, co.FLOOR))
            trades = fc.metal_trades(m, d)
            res = list(pool.map(co.polish_full, [(tm, td, co.FLOOR) for _h, tm, td in trades], chunksize=2))
            vals = [q[2] if fc.ok(q[0], q[1]) else np.inf for q in res]
            order = np.argsort(vals)
            print(f"== {src}: {base:.6f}; {len(trades)} metal trades; best "
                  + ", ".join(f"{trades[k][0]} {100 * (vals[k] / base - 1):+.1f} %" for k in order[:5]), flush=True)
            picked, seen = [], set()
            for k in order:
                key = " ".join(res[k][0])
                if np.isfinite(vals[k]) and key not in seen:
                    seen.add(key)
                    picked.append(int(k))
                if len(picked) == 8:
                    break
            for k in picked:
                mm, dd, ff, steps = fc.descend(pool, *res[k], names=("N1", "MT", "ADD"), rounds=2)
                how = f"{src}: {trades[k][0]}" + (" + " + " + ".join(steps) if steps else "")
                print(f"  quick: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
                quick.append((ff, mm, dd, how))
                if fc.ok(mm, dd):
                    ss.keep_elite(ff, "metal screen", "quick " + how, mm, dd)
                if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                    record = st.save(dst, mm, dd, ff, how)
                    print(f"GAIN (quick): {record:.6f} -> {dst}", flush=True)
        for ff, mm, dd, how in sorted(quick, key=lambda t: t[0])[:2]:
            mm, dd, ff, steps = fc.descend(pool, mm, dd, ff, names=("N1", "MT", "ADD", "N2"), rounds=6)
            how = how + (" + " + " + ".join(steps) if steps else "")
            print(f"  full: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
            if fc.ok(mm, dd):
                ss.keep_elite(ff, "metal screen", "full " + how, mm, dd)
            if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                record = st.save(dst, mm, dd, ff, how)
                print(f"GAIN: {record:.6f} -> {dst}", flush=True)
    print(f"done: best {record:.6f}", flush=True)


if __name__ == "__main__":
    main()
