"""Do hidden resonances keep a designer from cleaning a design? (2026-11-01 evening, owner: "from experience these peaks
keep the designer from cleaning a design at the end -- removing layers, refining it".) Two versions of Trubetskov's
101-layer design: 'resonant' as re-created (fig4_2020_designs.csv, 0.348 % resolved, peaks 61 and 6 %) and 'cured'
after the pole charge (last round of threeline_track_height_trub101.csv, 0.0189 % resolved). For each, each of its
LAYERS thinnest layers is removed (its two neighbours, of the same material, merge; an outer layer is dropped), then the
design is polished again with ROUNDS bursts of 30 trust-region iterations, either on the 277 nominal points ('nominal')
or with the resonances charged by their height ('pole'). Judged on the nominal and on the resolved (0.001 nm) grid, with
the highest resonance found from the complex plane. Rows to cleaning_test_trub101.csv.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex python cleaning_test_trub101.py LAYERS ROUNDS WORKERS
"""

from __future__ import annotations

import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import grid_study as gs
import numpy as np
import threeline_track as tt

LAYERS, ROUNDS, WORKERS = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
#: env CLEAN_CURED, CLEAN_OUT (2026-11-03, the detector redo): the charge run whose last round is the 'cured' design,
#: and the output file; unset, as before
CURED = os.environ.get("CLEAN_CURED", "threeline_track_height_trub101.csv")
OUT = os.environ.get("CLEAN_OUT", "cleaning_test_trub101.csv")


def designs() -> dict:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    c = list(csv.DictReader(open(CURED, encoding="utf-8")))[-1]
    return {"resonant": (r["seq"], r["d_nm"]), "cured": (c["seq"], c["d_nm"])}


def remove(seq, d, j):
    if j == 0 or j == len(seq) - 1:
        keep = [k for k in range(len(seq)) if k != j]
        return "".join(seq[k] for k in keep), d[keep]
    return seq[:j - 1] + seq[j - 1] + seq[j + 2:], np.concatenate([d[:j - 1], [d[j - 1] + d[j + 1]], d[j + 2:]])


def judge(seq, d) -> dict:
    p = tt.poles(seq, d)
    return {"mf_nominal": gs.mf(seq, d, gs.GRIDS["nominal"]), "mf_resolved": gs.mf(seq, d, gs.GRIDS["resolved"]),
            "highest": max((q[2] for q in p), default=0.0)}


def run(task) -> dict:
    name, j, method = task
    seq, dt = designs()[name]
    d0 = np.array([float(v) for v in dt.split()])
    seq, d = remove(seq, d0, j)
    before = judge(seq, d)
    for _ in range(ROUNDS):
        d = tt.polish("height", seq, d, tt.poles(seq, d) if method == "pole" else [])
    after = judge(seq, d)
    return {"design": name, "removed": j, "removed_nm": f"{d0[j]:.2f}", "method": method, "layers": len(seq),
            **{f"{k}_cut": f"{v:.6e}" for k, v in before.items()}, **{k: f"{v:.6e}" for k, v in after.items()}}


def main() -> None:
    tasks = []
    for name, (_seq, dt) in designs().items():
        d0 = np.array([float(v) for v in dt.split()])
        for j in np.argsort(d0)[:LAYERS]:
            tasks += [(name, int(j), m) for m in ("nominal", "pole")]
    rows = []
    with ProcessPoolExecutor(WORKERS) as pool:
        for r in pool.map(run, tasks):
            rows.append(r)
            print(f"{r['design']:8s} -layer {r['removed']:3d} ({r['removed_nm']:>6s} nm) {r['method']:7s}: nominal "
                  f"{float(r['mf_nominal']):.4f} %, resolved {float(r['mf_resolved']):.4f} %, highest "
                  f"{100 * float(r['highest']):.2f} %", flush=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
