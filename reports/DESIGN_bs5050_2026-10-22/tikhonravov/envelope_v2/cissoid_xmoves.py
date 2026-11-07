"""OIC 2016 B1 (cissoid): two moves the searches never made, on the record (2026-11-01 afternoon, push below 0.009268).

CROSS: the record with a block of 2-12 consecutive layers (materials and thicknesses) taken from a design of the elite
pool (cissoid_elites.csv) at the same positions; the pool's designs descend from the same 50-layer skeleton, so the
blocks line up. HOP: each dielectric layer thicker than 400 nm moved by k = -2, -1, 1, 2 interference orders
(k * 550 / (2 n) nm), which a polish never crosses. Every candidate is polished on the 301 points; the best 8 distinct
ones get a quick descent (N1, metal trades, ADD; 2 rounds), the best 2 the full descent (with N2, 4 rounds); every
descended design goes to the elite pool; a design under the record is written to OUT at once.
usage: python cissoid_xmoves.py OUT.csv
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

BLOCKS = (2, 3, 4, 6, 8, 12)


def candidates(m, d):
    out = []
    pool_rows = sorted(csv.DictReader(ss.ELITES.open(encoding="utf-8")), key=lambda r: float(r["mf"]))
    seen = set()
    for r in pool_rows:
        em, ed = r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])
        if len(em) != len(m) or r["mats"] in seen or em == m:
            continue
        seen.add(r["mats"])
        for size in BLOCKS:
            for a in range(len(m) - size + 1):
                if em[a:a + size] == m[a:a + size] and np.allclose(ed[a:a + size], d[a:a + size], atol=1.0):
                    continue
                cm = [*m[:a], *em[a:a + size], *m[a + size:]]
                cd = np.concatenate([d[:a], ed[a:a + size], d[a + size:]])
                out.append((f"cross {float(r['mf']):.6f} [{a}-{a + size - 1}]", *co.normalize(cm, cd, 0.0)))
    for i, x in enumerate(m):
        if x in "FLBMTH" and d[i] > 400.0:
            for k in (-2, -1, 1, 2):
                cd = d.copy()
                cd[i] += k * 550.0 / (2.0 * co.MATS[x].real)
                if cd[i] > co.FLOOR:
                    out.append((f"hop {i}{x} {k:+d}", list(m), cd))
    return out


def main() -> None:
    dst = sys.argv[1]
    best_row = next(csv.DictReader((co.s.HERE / "cissoid_record_best.csv").open(encoding="utf-8")))
    record = float(best_row["mf_oracle"])
    m, d = best_row["mats"].split(), np.array([float(v) for v in best_row["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, base = co.polish_full((m, d, co.FLOOR))
        cands = [c for c in candidates(m, d) if len(c[1]) <= co.N_MAX]
        res = list(pool.map(co.polish_full, [(cm, cd, co.FLOOR) for _h, cm, cd in cands], chunksize=4))
        vals = [q[2] if fc.ok(q[0], q[1]) else np.inf for q in res]
        order = np.argsort(vals)
        kinds = {"cross": 0, "hop": 0}
        for k in order:
            kinds[cands[k][0].split()[0]] += vals[k] < base * (1 - 1e-4)
        print(f"base {base:.6f}; {len(cands)} candidates ({time.time() - t0:.0f} s); better than the base: {kinds}",
              flush=True)
        picked, seen = [], set()
        for k in order:
            key = " ".join(res[k][0])
            if np.isfinite(vals[k]) and key not in seen:
                seen.add(key)
                picked.append(int(k))
                print(f"  {cands[k][0]}: N {len(res[k][0])}, MF {vals[k]:.6f} ({100 * (vals[k] / base - 1):+.2f} %)",
                      flush=True)
            if len(picked) == 8:
                break
        quick = []
        for k in picked:
            mm, dd, ff, steps = fc.descend(pool, *res[k], names=("N1", "MT", "ADD"), rounds=2)
            how = cands[k][0] + (" + " + " + ".join(steps) if steps else "")
            print(f"  quick: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
            quick.append((ff, mm, dd, how))
            if fc.ok(mm, dd):
                ss.keep_elite(ff, "xmoves", "quick " + how, mm, dd)
            if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                record = st.save(dst, mm, dd, ff, how)
                print(f"GAIN (quick): {record:.6f} -> {dst}", flush=True)
        for ff, mm, dd, how in sorted(quick, key=lambda t: t[0])[:2]:
            mm, dd, ff, steps = fc.descend(pool, mm, dd, ff, names=("N1", "MT", "ADD", "N2"), rounds=4)
            how = how + (" + " + " + ".join(steps) if steps else "")
            print(f"  full: {how} -> {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
            if fc.ok(mm, dd):
                ss.keep_elite(ff, "xmoves", "full " + how, mm, dd)
            if ff < record * (1 - 1e-4) and fc.ok(mm, dd):
                record = st.save(dst, mm, dd, ff, how)
                print(f"GAIN: {record:.6f} -> {dst}", flush=True)
    print(f"done: best {record:.6f}", flush=True)


if __name__ == "__main__":
    main()
