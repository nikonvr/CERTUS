"""Injecting a small artificial absorption to kill the hidden resonances: same as the pole charge, or worse? (2026-11-01
evening, owner, method paper). Trubetskov's 101-layer design (re-created, fig4_2020_designs.csv row 'deep') is polished
on the 277 nominal points with k_H = k_L = K (n_hat = n - iK, CERTUS no-backside TMM, finite-difference Jacobian, trf,
floor 0.1 nm), then judged LOSSLESS: MF on 1 nm, on 0.001 nm, and the peaks of |T - T'| on 0.0002 nm.
Sanity: K = 0 must give back 0.0128 % nominal.
env INJECT_OUT=FILE.csv (2026-11-02, Dataset 1 of the method paper): the polished designs (k, seq, d_nm); unset, nothing
is written.
usage: SEARCH_TARGET=threeline python inject_k_trub101.py K [K ...]
"""

from __future__ import annotations

import csv
import os
import sys
import time

import grid_study as gs
import numpy as np
import search as s
from scipy.optimize import least_squares
from threeline_refine_probe import peaks

import certus.physics.certus_tmm_core as tmm_core

W, TGT = gs.band_grid(1.0)
r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
SEQ, D0 = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
NSUB = np.full(len(W), complex(s.N_SUB)) if hasattr(s, "N_SUB") else np.full(len(W), 1.52 + 0j)


def residual(d, k):
    n = np.array([s.N_IDX[m] - 1j * k for m in SEQ])
    nl = np.ascontiguousarray(np.tile(n, (len(W), 1)))
    _r, t = tmm_core.calculate_RT_no_backside(np.ascontiguousarray(d), nl, NSUB, W)
    return (t - TGT) / np.sqrt(len(W))


def lossless(tag, d, t0):
    nom = gs.mf(SEQ, d, gs.GRIDS["nominal"])
    res = gs.mf(SEQ, d, gs.GRIDS["resolved"])
    print(f"{tag}: lossless MF 1 nm {nom:.4f} %, 0.001 nm {res:.4f} % ({time.time() - t0:.0f} s)", flush=True)
    for h, x, fw in peaks(SEQ, d)[:4]:
        print(f"    peak {x:9.4f} nm  {100 * h:6.2f} %  FWHM {fw:.4f} nm", flush=True)


t0 = time.time()
print(f"check K=0: {100 * np.sqrt(np.sum(residual(D0, 0.0) ** 2)):.4f} % (expected 0.0128)", flush=True)
lossless("start", D0, t0)
OUT = []
for k in map(float, sys.argv[1:]):
    print(f"K {k:g}: lossy MF at start {100 * np.sqrt(np.sum(residual(D0, k) ** 2)):.4f} %", flush=True)
    sol = least_squares(residual, D0, args=(k,), jac="2-point", bounds=(0.1, np.inf), method="trf", x_scale="jac",
                        ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=300)
    print(f"K {k:g}: lossy MF after polish {100 * np.sqrt(2 * sol.cost):.4f} %, nfev {sol.nfev}, max shift "
          f"{np.max(np.abs(sol.x - D0)):.2f} nm", flush=True)
    lossless(f"K {k:g} polished, judged lossless", sol.x, t0)
    OUT.append({"k": k, "seq": SEQ, "d_nm": " ".join(f"{v:.6f}" for v in sol.x)})
if os.environ.get("INJECT_OUT"):
    with open(os.environ["INJECT_OUT"], "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["k", "seq", "d_nm"])
        w.writeheader()
        w.writerows(OUT)
