"""OIC 2016 B1 (cissoid): how the winning designs evolved from 0.02407 to the record (2026-11-01, owner's question).

For every saved record, in time order: layers and thickness of each material, metal layers, total thickness, mean
dielectric index weighted by thickness, share of the dielectric thickness in the intermediate indices L B M T, thin
layers (< 20 nm), thick layers (> 500 nm), and where each material sits (mean layer index, 0 = substrate side).
usage: python cissoid_evolution.py
"""

from __future__ import annotations

import collections
import csv

import cissoid_opt as co

CHAIN = ["cissoid_quintet.csv", "cissoid_record_0p01839.csv", "cissoid_record_0p01786.csv", "cissoid_record_0p01633.csv",
         "cissoid_record_0p01577.csv", "cissoid_record_0p01493.csv", "cissoid_record_0p01448.csv",
         "cissoid_record_0p01419.csv", "cissoid_record_force2.csv", "cissoid_record_0p01379.csv",
         "cissoid_record_0p01375.csv", "cissoid_record_exhaustive.csv", "cissoid_record_0p01316.csv",
         "cissoid_record_0p01308.csv", "cissoid_record_0p01299.csv", "dig_reduce.csv:0", "cissoid_record_0p01271.csv",
         "cissoid_record_0p01268.csv", "cissoid_record_0p01228.csv", "cissoid_record_0p01221.csv",
         "cissoid_record_0p01089.csv", "cissoid_record_0p01040.csv", "cissoid_record_0p01015.csv",
         "cissoid_record_0p01011_2.csv", "cissoid_record_0p00935.csv", "cissoid_record_0p00928.csv",
         "cissoid_record_0p00927_1.csv", "cissoid_record_0p00921.csv"]
DIEL = "FLBMTH"


def load(spec):
    name, _, row = spec.partition(":")
    rows = list(csv.DictReader((co.s.HERE / name).open(encoding="utf-8")))
    r = rows[int(row)] if row else rows[-1]
    return r["mats"].split(), [float(v) for v in r["d_nm"].split()], co.oracle_mf(r["mats"].split(),
                                                                                     [float(v) for v in r["d_nm"].split()])


def main() -> None:
    print("   MF     N  " + " ".join(f"{x:>8}" for x in DIEL) + "  Ag Ni Au   total  n_mean  inter  thin thick")
    for spec in CHAIN:
        m, d, o = load(spec)
        n, t, pos = collections.Counter(m), collections.Counter(), collections.defaultdict(list)
        for i, (x, v) in enumerate(zip(m, d, strict=True)):
            t[x] += v
            pos[x].append(i)
        dt = sum(t[x] for x in DIEL)
        n_mean = sum(co.MATS[x].real * t[x] for x in DIEL) / dt
        inter = sum(t[x] for x in "LBMT") / dt
        thin = sum(v < 20 for x, v in zip(m, d, strict=True) if x in DIEL)
        thick = sum(v > 500 for x, v in zip(m, d, strict=True) if x in DIEL)
        print(f"{o:.5f} {len(m):2d}  " + " ".join(f"{n[x]:2d}/{t[x]:5.0f}" for x in DIEL)
              + f"  {n['A']:2d} {n['N']:2d} {n['U']:2d}  {sum(d):6.0f}  {n_mean:.3f}  {inter:.2f}  {thin:3d}  {thick:3d}")
    print("\nmean position (layer index, 0 = substrate) of each dielectric, first / middle / last record:")
    for spec in (CHAIN[0], CHAIN[len(CHAIN) // 2], CHAIN[-1]):
        m, d, o = load(spec)
        line = []
        for x in DIEL:
            idx = [i for i, y in enumerate(m) if y == x]
            line.append(f"{x}:{sum(idx) / len(idx):4.1f}" if idx else f"{x}:  - ")
        print(f"  {o:.5f}  " + "  ".join(line))


if __name__ == "__main__":
    main()
