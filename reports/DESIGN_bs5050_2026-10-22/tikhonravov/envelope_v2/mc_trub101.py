"""Thickness errors on Trubetskov's 101-layer design, as re-created and after the pole charge (2026-11-01 night, method
paper, Sec. "Relevance for fabricated coatings"): threeline_mc_resolved.mc -- 300 draws of independent optical-thickness
errors sigma_OT = 0.2 and 0.5 nm (seed 1 per sigma), each judged on the nominal grid and on 0.001 nm steps; the root of
the mean squared MF of the draws. Also the fraction of draws whose resolved MF exceeds twice their nominal one.
usage: SEARCH_TARGET=threeline python mc_trub101.py
"""

from __future__ import annotations

import csv

import grid_study as gs
import numpy as np
import search as s
import threeline_mc_resolved as mcr

r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
c = list(csv.DictReader(open("threeline_track_height_trub101.csv", encoding="utf-8")))[-1]
for name, row in (("as re-created", r), ("after the pole charge", c)):
    seq, d = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
    vals = mcr.mc((seq, d))
    print(f"{name}: " + ", ".join(f"sigma {sg}: nominal {vals[2 * i]:.4f} %, resolved {vals[2 * i + 1]:.4f} %"
                                  for i, sg in enumerate(mcr.SIGMAS)), flush=True)
    for sg in mcr.SIGMAS:
        rng = np.random.default_rng(1)
        alpha = sg / np.array([s.N_IDX[m] for m in seq])
        worse = 0
        for _ in range(mcr.DRAWS):
            x = np.maximum(d + rng.normal(0.0, alpha), 0.0)
            worse += gs.mf(seq, x, gs.GRIDS["resolved"]) > 2 * gs.mf(seq, x, gs.GRIDS["nominal"])
        print(f"   sigma {sg}: draws with resolved MF > 2 x nominal: {worse}/{mcr.DRAWS}", flush=True)
