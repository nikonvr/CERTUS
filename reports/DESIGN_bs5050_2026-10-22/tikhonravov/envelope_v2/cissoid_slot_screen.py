"""OIC 2016 B1 (cissoid): slot trades from several designs, screened by a quick descent (2026-11-01, push under 0.01).

Why: in slot-loop round 1 the trade that became the record (0.010148) was only second by its own MF (+7.2 % against
+6.4 %), and the record 0.009349 came from 0.010396, a design that had lost, whose slots were cheaper than the record's:
the MF of a trade predicts its descent badly, and the best start is not always the best design.
For each start design: cissoid_slot_trade.trades (12 needles, up to 3 of the 8 cheapest freeings); the best trades of 5
distinct needle layers get a quick descent (N1, metal trades, ADD; 2 rounds); the 3 best of all then get the full
descent (N1, metal trades, ADD, N2; 4 rounds). Every descended design goes to the elite pool cissoid_elites.csv; a start
written ELITES:K takes the K best distinct designs of the pool other than the record. Any design under the record
(cissoid_record_best.csv, oracle) is written to OUT at once.
usage: python cissoid_slot_screen.py OUT.csv START1.csv [START2.csv | ELITES:K ...]
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import cissoid_slot_trade as st
import flair_campaign as fc
import numpy as np

ELITES = co.s.HERE / "cissoid_elites.csv"


def keep_elite(mf, origin, how, m, d) -> None:
    new = not ELITES.exists()
    with ELITES.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["mf", "origin", "how", "mats", "d_nm"])
        w.writerow([f"{mf:.6f}", origin, how, " ".join(m), " ".join(f"{v:.4f}" for v in d)])


MIN_DIFF = 8  # positions where two material sequences must differ for a second start to be worth it


def differ(a, b) -> int:
    a, b = a.split(), b.split()
    return sum(x != y for x, y in zip(a, b, strict=False)) + abs(len(a) - len(b))


def elites(k, record_mats):
    """The k best designs of the pool that differ from the record and from each other in at least MIN_DIFF positions
    (2026-11-01: the best other designs are the record's close relatives; 0.009349 came from a design 0.3 % worse but
    structurally different, whose slots were cheaper)."""
    if not ELITES.exists():
        return []
    rows = sorted(csv.DictReader(ELITES.open(encoding="utf-8")), key=lambda r: float(r["mf"]))
    out, chosen = [], [record_mats]
    for r in rows:
        if all(differ(r["mats"], c) >= MIN_DIFF for c in chosen):
            chosen.append(r["mats"])
            out.append((f"elite {float(r['mf']):.6f}", r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])))
        if len(out) == k:
            break
    return out


def load(src):
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    return src, r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])


def main() -> None:
    dst, specs = sys.argv[1], sys.argv[2:]
    best_row = next(csv.DictReader((co.s.HERE / "cissoid_record_best.csv").open(encoding="utf-8")))
    record = float(best_row["mf_oracle"])
    starts = []
    for spec in specs:  # a suffix @S skips the S best distinct trades (the trades are deterministic: already screened)
        spec, skip = (spec.split("@")[0], int(spec.split("@")[1])) if "@" in spec else (spec, 0)
        got = elites(int(spec.split(":")[1]), best_row["mats"]) if spec.startswith("ELITES:") else [load(spec)]
        starts += [(*g, skip) for g in got]
    t0, pool_of = time.time(), []
    with ProcessPoolExecutor(co.WORKERS) as pool:
        for src, m, d, skip in starts:
            m, d, base = co.polish_full((m, d, co.FLOOR))
            print(f"== {src}: {base:.6f} (skipping {skip} trades)", flush=True)
            _designs, hows, res, vals = st.trades(pool, m, d, base, t0, n_needles=12)
            for k in st.distinct_needles(hows, vals, 5 + skip)[skip:]:
                mm, dd, ff, steps = fc.descend(pool, *res[k], names=("N1", "MT", "ADD"), rounds=2)
                how = f"{hows[k]}" + (" + " + " + ".join(steps) if steps else "")
                print(f"  quick: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
                pool_of.append((ff, mm, dd, f"{src}: {how}"))
                if fc.ok(mm, dd):
                    keep_elite(ff, src, "quick " + how, mm, dd)
                if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                    record = st.save(dst, mm, dd, ff, pool_of[-1][3])
                    print(f"GAIN (quick): {record:.6f} -> {dst}", flush=True)
        pool_of.sort(key=lambda t: t[0])
        for ff, mm, dd, how in pool_of[:3]:
            mm, dd, ff, steps = fc.descend(pool, mm, dd, ff, names=("N1", "MT", "ADD", "N2"), rounds=4)
            how = how + (" + " + " + ".join(steps) if steps else "")
            print(f"  full: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
            if fc.ok(mm, dd):
                keep_elite(ff, how.split(":")[0], "full " + how, mm, dd)
            if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                record = st.save(dst, mm, dd, ff, how)
                print(f"GAIN: {record:.6f} -> {dst}", flush=True)
    print(f"done: best {record:.6f}", flush=True)


if __name__ == "__main__":
    main()
