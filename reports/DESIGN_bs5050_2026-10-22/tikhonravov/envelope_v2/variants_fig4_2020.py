"""Hidden resonances of the variants of Trubetskov's Fig. 4 designs (2026-11-01 evening, owner: the method paper takes
his 101-layer design, re-created; does the conclusion depend on the re-creation?). For the deep (101 layers) and the
classical (104 layers) designs of fig4_2020_designs.csv, as read from the image (ot_raw, before refinement) and as
refined on the 277 points (d_nm): MF on 1, 0.001 and 0.0002 nm and the peaks of |T - T'| above 1 % on 0.0002 nm.
usage: SEARCH_TARGET=threeline python variants_fig4_2020.py
"""

from __future__ import annotations

import csv

import grid_study as gs
import numpy as np
import search as s
from threeline_refine_probe import peaks

for r in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")):
    seq = r["seq"]
    raw = np.array([float(v) for v in r["ot_raw"].split()]) / np.array([s.N_IDX[m] for m in seq])
    for tag, d in (("as read", raw), ("refined", np.array([float(v) for v in r["d_nm"].split()]))):
        vals = [gs.mf(seq, d, gs.kernel_grid(*gs.band_grid(h))) for h in (1.0, 0.001, 0.0002)]
        print(f"{r['design']} N{len(seq)} {tag}: MF 1 nm {vals[0]:.4f} %, 0.001 nm {vals[1]:.4f} %, "
              f"0.0002 nm {vals[2]:.4f} %", flush=True)
        for h, x, fw in peaks(seq, d)[:5]:
            print(f"    peak {x:9.4f} nm  {100 * h:6.2f} %  FWHM {fw:.4f} nm", flush=True)
