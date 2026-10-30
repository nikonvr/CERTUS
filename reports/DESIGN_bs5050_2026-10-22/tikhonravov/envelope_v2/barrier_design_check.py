"""Does DESIGN's module (certus/core/certus_design_landscape.py) reproduce the study's barrier? (2026-10-29)

Same pair as `barrier_best_D8_12k.out` (our 51-layer 0.4597 against D8 of 2012), same residuals (the study's kernel
call through `search.Stack`), same box (matched layers within 100-350 nm OT), 12 000 string iterations, 33 images.
The study printed MF = 100 x RMSE: string max 29.5694, straight max 35.6288, total variation 89.9804, 26 minima.

usage: python barrier_design_check.py   -> barrier_design_check.out
"""

from __future__ import annotations

import os
import time

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from design_distance import layers, load  # noqa: E402

from certus.core.certus_design_landscape import align_designs, aligned_path, mf_barrier  # noqa: E402

a = layers(*load("constrained_threeline_N51_lbfgsb_mix_resume.csv:0"))
b = layers(*load("fig3_2012_designs.csv:5"))
t0 = time.time()
al = align_designs(a, b, 0.0)
t_align = time.time() - t0
path = aligned_path(a, b, al, s.N_IDX.get)
seq = "".join(path.materials)
st = s.Stack.of(seq)
n = np.array([s.N_IDX[m] for m in seq])
lo = np.where(path.matched, 100.0 / n, 0.0)
hi = np.where(path.matched, 350.0 / n, np.inf)


def rj(x):
    r, j, _c = st.res_jac(x)
    return r, j


t0 = time.time()
bar = mf_barrier(rj, path.ep_a, path.ep_b, images=33, iterations=12000, lower=lo, upper=hi)
t_bar = time.time() - t0
with open(s.HERE / "barrier_design_check.out", "w", encoding="utf-8") as f:
    f.write(f"alignment {t_align:.3f} s, cost {al.cost_nm:.1f} nm ({100 * al.fraction:.1f} % TOT), superset N "
            f"{len(seq)}\n")
    f.write(f"MF (100 x RMSE): A {100 * bar.rmse_a:.4f} B {100 * bar.rmse_b:.4f}; straight max "
            f"{100 * bar.rmse_straight.max():.4f}; string max {100 * bar.rmse_string.max():.4f}; total variation "
            f"{100 * bar.total_variation:.4f}; local minima {bar.local_minima}; {bar.iterations} iterations in "
            f"{t_bar:.0f} s\n")
    f.write("study (barrier_best_D8_12k.out): A 0.4597 B 0.4646; straight max 35.6288; string max 29.5694; total "
            "variation 89.9804; local minima 26\n")
