"""The exchange method as a reference for the method paper (2026-11-02 night): Trubetskov's 101-layer design (re-created)
polished in ROUNDS bursts of 30 trust-region iterations on the 277 nominal points plus a growing set of extra points: at
each round a scan of the bands every 0.0002 nm (threeline_refine_probe.peaks: maxima of |T - T'| above 1 %) finds the
peaks, and their wavelengths join the set (exchange methods of minimax filter design add the extrema found by sampling).
Judged each round on the nominal grid and on 0.001 nm steps, with the time.
env EXCHANGE_OUT=FILE.csv (2026-11-02, Dataset 1 of the method paper): the design of the last round (round, extra
points, seq, d_nm); unset, nothing is written.
usage: SEARCH_TARGET=threeline python exchange_trub101.py ROUNDS
"""

from __future__ import annotations

import csv
import os
import sys
import time

import bs5050_grid as bg
import grid_study as gs
import numpy as np
import search as s
from scipy.optimize import least_squares
from threeline_refine_probe import peaks

ROUNDS = int(sys.argv[1])
W0, T0 = gs.band_grid(1.0)


def target(x: float) -> float:
    for a, b, t in s._bands:
        if a <= x <= b:
            return float(s.band_values(np.array([x]), t)[0])
    return 0.0


def main() -> None:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    extra: list[float] = []
    t0 = time.time()
    #: 2026-11-03 (Visualization 1 of the OE paper): EXCHANGE_TRACE=FILE.csv writes every round (design and extra
    #: points); unset, nothing more is written
    trace = []
    for rnd in range(ROUNDS + 1):
        pk = peaks(seq, d)
        nom, res = gs.mf(seq, d, gs.GRIDS["nominal"]), gs.mf(seq, d, gs.GRIDS["resolved"])
        trace.append({"round": rnd, "mf_nominal": f"{nom:.6e}", "mf_resolved": f"{res:.6e}",
                      "extra_nm": " ".join(f"{e:.4f}" for e in extra), "seq": seq,
                      "d_nm": " ".join(f"{v:.6f}" for v in d)})
        print(f"round {rnd}: {len(pk)} peaks, highest {100 * pk[0][0] if pk else 0:.2f} %, extra points {len(extra)}; "
              f"MF nominal {nom:.4f} %, 0.001 nm {res:.4f} % ({time.time() - t0:.0f} s)", flush=True)
        if rnd == ROUNDS:
            if os.environ.get("EXCHANGE_TRACE"):
                with open(os.environ["EXCHANGE_TRACE"], "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(trace[0]))
                    w.writeheader()
                    w.writerows(trace)
            if os.environ.get("EXCHANGE_OUT"):
                with open(os.environ["EXCHANGE_OUT"], "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=["round", "extra_points", "seq", "d_nm"])
                    w.writeheader()
                    w.writerow({"round": rnd, "extra_points": len(extra), "seq": seq,
                                "d_nm": " ".join(f"{v:.6f}" for v in d)})
            break
        for _h, x, _fw in pk:
            if all(abs(x - e) > 1e-4 for e in extra):
                extra.append(x)
        w = np.concatenate([W0, np.array(extra)])
        tg = np.concatenate([T0, np.array([target(x) for x in extra])])
        g = gs.kernel_grid(w, tg)
        g["sqw"] = np.full(len(w), np.sqrt(1.0 / len(W0)))
        sol = least_squares(lambda x, g=g: bg.res_jac(seq, x, g)[0], d, jac=lambda x, g=g: bg.res_jac(seq, x, g)[1],
                            bounds=(gs.FLOOR, np.inf), method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15,
                            gtol=1e-15, max_nfev=30)
        d = np.maximum(sol.x, gs.FLOOR)


if __name__ == "__main__":
    main()
