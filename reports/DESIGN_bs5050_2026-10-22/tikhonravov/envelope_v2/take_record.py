"""OIC 2016 B1 (cissoid): make a candidate csv the record if the independent oracle says it is better (2026-11-01).

Checks N <= 50, every layer >= 3 nm, allowed materials, and oracle MF < record * (1 - 1e-4); then writes
cissoid_record_0pXXXXX.csv and cissoid_record_best.csv and a line in campaign.log. Prints TAKEN or KEPT.
usage: python take_record.py CANDIDATE.csv "how it was found"
"""

from __future__ import annotations

import csv
import sys
import time

import cissoid_opt as co
import numpy as np


def main() -> None:
    src, note = sys.argv[1], sys.argv[2]
    r = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r["mats"].split(), np.array([float(v) for v in r["d_nm"].split()])
    best = next(csv.DictReader((co.s.HERE / "cissoid_record_best.csv").open(encoding="utf-8")))
    o, o_best = co.oracle_mf(m, d), float(best["mf_oracle"])
    valid = len(m) <= co.N_MAX and d.min() >= co.FLOOR - 1e-9 and all(x in co.MATS for x in m)
    if not (valid and o < o_best * (1 - 1e-4)):
        print(f"KEPT {o_best:.6f} (candidate {o:.6f}, valid {valid})")
        return
    row = {"how": r.get("how", note), "layers": len(m), "mf_kernel": co.mf_full(m, d), "mf_full": co.mf_full(m, d),
           "mf_oracle": o, "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
           "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}
    name = "cissoid_record_0p" + f"{o:.5f}"[2:]
    path, k = co.s.HERE / f"{name}.csv", 1
    while path.exists():
        path, k = co.s.HERE / f"{name}_{k}.csv", k + 1
    for p in (path, co.s.HERE / "cissoid_record_best.csv"):
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row))
            w.writeheader()
            w.writerow(row)
    with (co.s.HERE / "campaign.log").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M')} {note}: {o_best:.6f} -> {o:.6f} oracle = NEW RECORD "
                 f"({row['how']}), {path.name}\n")
    print(f"TAKEN {o:.6f} (was {o_best:.6f}) -> {path.name}")


if __name__ == "__main__":
    main()
