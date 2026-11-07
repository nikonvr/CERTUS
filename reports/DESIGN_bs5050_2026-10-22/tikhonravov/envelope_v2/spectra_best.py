"""Spectral responses of the arbitrary targets for the method paper (2026-11-02, owner: "the spectral responses of all
the filters are needed"). For the target of SEARCH_TARGET: the design of least nominal MF among the searches of seeds 1
and 2 (curve_{TAG}free_s{1,2}.csv, oracle RMSE), judged on the grid and on 0.001 nm steps, then 20 rounds of the charge
by height (threeline_track.track, complex detection), the round of least tracked MF kept. Both designs to
{TAG}spectra_designs.csv for oe_spectra_figure.py.
usage: SEARCH_TARGET=semicircle TRACK_DETECT=complex python spectra_best.py
"""

from __future__ import annotations

import csv
import os

import grid_study as gs
import numpy as np
import search as s
import threeline_track as tt

rows = []
for sd in tuple(int(v) for v in os.environ.get("SPECTRA_SEEDS", "1,2").split(",")):  # 2026-11-02: SPECTRA_SEEDS
    f = f"curve_{s.TAG}free_s{sd}.csv"
    if os.path.exists(f):
        rows += list(csv.DictReader(open(f, encoding="utf-8")))
#: env SPECTRA_FIRST_H=1 (2026-11-02, owner: no thick low-index layer next to the substrate, it does nothing): only
#: designs whose substrate-side layer is H and at least 10 nm thick
if os.environ.get("SPECTRA_FIRST_H", "0") == "1":
    rows = [r for r in rows if r["seq"][0] == "H" and float(r["d_nm"].split()[0]) >= 10.0]
best = min(rows, key=lambda r: float(r["rmse_1601_oracle"]))
seq, d = best["seq"], np.array([float(v) for v in best["d_nm"].split()])
out = tt.track("height", seq, d, rounds=20)
b = min(out, key=lambda q: float(q["mf_tracked"]))
res = []
for tag, row in (("grid", out[0]), ("charged", b)):
    dd = np.array([float(v) for v in row["d_nm"].split()])
    res.append({"which": tag, "layers": len(seq), "ot_nm": f"{s.total_ot(seq, dd):.1f}",
                "mf_nominal": row["mf_nominal"], "mf_resolved": row["mf_resolved"], "highest": row["highest"],
                "seq": seq, "d_nm": row["d_nm"]})
    print(f"{s.TARGET} {tag}: N {len(seq)}, OT {s.total_ot(seq, dd):.0f}, nominal {float(row['mf_nominal']):.4f} %, "
          f"resolved {float(row['mf_resolved']):.4f} %, highest {100 * float(row['highest']):.2f} %", flush=True)
with open(f"{s.TAG}spectra_designs.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(res[0]))
    w.writeheader()
    w.writerows(res)
