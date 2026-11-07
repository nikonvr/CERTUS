"""50/50 beamsplitter: does the wavelength grid hide errors between its points, as at the cissoid's corners?
(2026-11-01, owner's question)

RMSE of the published design (Tikhonravov et al. 1996, judged by them on 80 points), and of our 35- and 37-layer
envelope designs (optimized on 1601 points), on three grids: 80, 1601 and 16 001 wavelengths of 400-1200 nm. Then each
of our designs is re-polished on the 80-point grid alone (same kernel, same trust-region polish) and judged again on
the three grids: a coarse grid lets the optimizer trade the points it sees against the wavelengths it does not.
usage: SEARCH_TARGET=bs5050 python bs5050_grid.py
"""

from __future__ import annotations

import csv
import json

import numpy as np
import search as s
from scipy.optimize import least_squares

from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel

N_SUB = 1.52


def kernel_grid(n_points):
    wls = np.linspace(400.0, 1200.0, n_points)
    return {"k0": 2.0 * np.pi / wls, "tgt": np.full(n_points, 0.5), "sqw": np.full(n_points, np.sqrt(1.0 / n_points)),
            "nsub": np.full(n_points, N_SUB), "zb": np.zeros(n_points), "ob": np.ones(n_points)}


def res_jac(seq, d, g):
    n = np.array([s.N_IDX[m] for m in seq])
    n_real = np.ascontiguousarray(np.tile(n, (len(g["k0"]), 1)))
    return _res_jac_lossless_normal_kernel(np.ascontiguousarray(d, dtype=np.float64), n_real, 1.0 / n_real, g["nsub"],
                                           g["k0"], False, g["zb"], g["ob"], g["tgt"], g["sqw"],
                                           np.arange(len(seq), dtype=np.int64))


def rmse(seq, d, g) -> float:
    r = res_jac(seq, d, g)[0]
    return float(np.sqrt(r @ r))


def polish(seq, d, g):
    sol = least_squares(lambda x: res_jac(seq, x, g)[0], d, jac=lambda x: res_jac(seq, x, g)[1], bounds=(0.0, np.inf),
                        method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=2000)
    return sol.x


def main() -> None:
    grids = {n: kernel_grid(n) for n in (80, 1601, 16001)}
    cfg = json.load((s.ROOT / "example" / "example_design"
                     / "JSON-design-reference-tikhonravov-1996-published-design.json").open(encoding="utf-8"))
    designs = [("published, 34 layers", "".join(x["mat"] for x in cfg["front"]),
                np.array([x["qw"] * float(cfg["l0"]) / 4.0 / s.N_IDX[x["mat"]] for x in cfg["front"]]))]
    rows = csv.DictReader(open("curve_mono_free.csv", encoding="utf-8"))
    designs += [(f"ours, {r['layers']} layers", r["seq"], np.array([float(v) for v in r["d_nm"].split()]))
                for r in rows if int(r["layers"]) in (20, 35, 37)]
    print("RMSE on 80 | 1601 | 16001 wavelengths (400-1200 nm)")
    for label, seq, d in designs:
        print(f"  {label:22s} " + " | ".join(f"{rmse(seq, d, g):.3e}" for g in grids.values()), flush=True)
        if label.startswith("ours"):
            d80 = polish(seq, d, grids[80])
            print(f"  {label + ', polished on 80':22s} " + " | ".join(f"{rmse(seq, d80, g):.3e}" for g in grids.values()),
                  flush=True)


if __name__ == "__main__":
    main()
