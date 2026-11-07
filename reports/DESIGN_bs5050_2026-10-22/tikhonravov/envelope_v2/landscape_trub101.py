"""Does a hidden resonance hold the optimization? The merit landscape along lines through Trubetskov's 101-layer design
(re-created, fig4_2020_designs.csv row 'deep') (2026-11-01 evening, owner's hypothesis for the method paper: on an
unresolved grid the peaks hold the design). Two directions, d = d0 (1 + s u): u = 1 (all layers scaled: the spectrum
shifts by s lambda) and u = random normal per layer (seed 1). Along each: the nominal MF (277 points) every 2e-6 in s, the
resolved MF (0.001 nm) every 40 steps, and the wavelength and height of the strongest stop-band resonance in 400-412 nm
(T every 0.0005 nm, CERTUS no-backside TMM) every 10 steps. Expected if the hypothesis holds: a narrow wall of the
nominal MF each time the resonance crosses an integer wavelength (a grid point), none in the resolved MF.
usage: SEARCH_TARGET=threeline python landscape_trub101.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import grid_study as gs
import matplotlib
import numpy as np
import search as s

import certus.physics.certus_tmm_core as tmm_core

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
SEQ, D0 = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
NL = np.array([s.N_IDX[m] for m in SEQ], dtype=complex)
WW = np.arange(400.0, 412.0 + 1e-9, 0.0005)
SS = np.round(np.arange(-0.004, 0.004 + 1e-12, 2e-6), 9)


def resonance(d):
    nl = np.ascontiguousarray(np.tile(NL, (len(WW), 1)))
    _r, t = tmm_core.calculate_RT_no_backside(np.ascontiguousarray(d), nl, np.full(len(WW), 1.52 + 0j), WW)
    k = int(np.argmax(t))
    return float(WW[k]), float(t[k])


def main() -> None:
    out = Path(sys.argv[1])
    dirs = {"scale": np.ones(len(D0)), "random": np.random.default_rng(1).normal(size=len(D0))}
    rows = []
    for name, u in dirs.items():
        for i, sv in enumerate(SS):
            d = D0 * (1.0 + sv * u)
            row = {"direction": name, "s": sv, "mf_nominal": gs.mf(SEQ, d, gs.GRIDS["nominal"])}
            if i % 10 == 0:
                row["res_nm"], row["res_T"] = resonance(d)
            if i % 40 == 0:
                row["mf_resolved"] = gs.mf(SEQ, d, gs.GRIDS["resolved"])
            rows.append(row)
        print(name, "done", flush=True)
    keys = ["direction", "s", "mf_nominal", "mf_resolved", "res_nm", "res_T"]
    with open("landscape_trub101.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    fig, ax = plt.subplots(2, 2, figsize=(10, 6), sharex="col")
    for j, name in enumerate(dirs):
        rr = [x for x in rows if x["direction"] == name]
        sv = np.array([x["s"] for x in rr]) * 1e3
        ax[0, j].semilogy(sv, [x["mf_nominal"] for x in rr], lw=0.8, label="nominal grid (277 points)")
        rs = [x for x in rr if "mf_resolved" in x]
        ax[0, j].semilogy(np.array([x["s"] for x in rs]) * 1e3, [x["mf_resolved"] for x in rs], "o", ms=3,
                          label="resolved (0.001 nm)")
        ax[0, j].set_title({"scale": "all layers scaled by 1 + s", "random": "random direction (seed 1)"}[name])
        ax[0, j].set_ylabel("MF (%)")
        rp = [x for x in rr if "res_nm" in x]
        ax[1, j].plot(np.array([x["s"] for x in rp]) * 1e3, [x["res_nm"] for x in rp], ".", ms=2)
        lo, hi = min(x["res_nm"] for x in rp), max(x["res_nm"] for x in rp)
        for g in range(int(np.ceil(lo)), int(np.floor(hi)) + 1):
            ax[1, j].axhline(g, color="0.7", lw=0.6)
        ax[1, j].set_ylabel("strongest resonance (nm)")
        ax[1, j].set_xlabel(r"$s\ (10^{-3})$")
    ax[0, 0].legend(fontsize=8)
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "landscape.pdf")
    fig.savefig(out / "landscape.png", dpi=150)


if __name__ == "__main__":
    main()
