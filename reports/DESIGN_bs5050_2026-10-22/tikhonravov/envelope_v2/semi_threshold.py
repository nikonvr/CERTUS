"""Hidden resonances against the number of layers and the optical thickness (2026-11-01 evening, owner: "show that from
about 50 layers there are peaks, once the optical thickness is large"). For every design of the half-circle search
(curve_semi_free_s1.csv: best of each N; front_semi_free_s1.csv: the MF-OT front), the MF on the nominal grid (1 nm) and
on 0.001 nm steps, the resonances found from the complex plane (threeline_track.poles) and the optical thickness; the
three-line envelope (threeline_mc_resolved.csv) for comparison. Figure: resolved / nominal MF against OT, with the
estimate OT_c of the method paper, Sec. "critical optical thickness":
OT_c = M (lambda / 2) ln(0.424 lambda / (dlambda sqrt(r / h))) / ln(nH / nL), M = ln(700/400) / ln(1.335), lambda = 400,
h = 0.5, r = the nominal RMS residual of each design.
usage: SEARCH_TARGET=semicircle|mshape TRACK_DETECT=complex python semi_threshold.py OUT_DIR
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import grid_study as gs
import matplotlib
import numpy as np
import search as s
import threeline_track as tt

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

#: materials of the search (SEARCH_NH changes n_H): contrast, Fabry-Perot constant C = 2 (n0 + ns)(nH - nL) / (pi nH nL)
#: and the wavelength ratio covered by one quarter-wave mirror, (1 + dg) / (1 - dg), dg = (2/pi) asin((nH-nL)/(nH+nL))
NH, NL = s.N_IDX["H"], s.N_IDX["L"]
RHO = NH / NL
C_FP = 2 * (1.0 + 1.52) * (NH - NL) / (np.pi * NH * NL)
_DG = 2 / np.pi * np.arcsin((NH - NL) / (NH + NL))
MIRROR = (1 + _DG) / (1 - _DG)
#: env THRESH_SEED: the search seed whose curve/front files are read (default 1; seed 2: the thin designs, 2026-11-02)
SEED = int(os.environ.get("THRESH_SEED", "1"))
SUFFIX = "" if SEED == 1 else f"_s{SEED}"
#: M: quarter-wave mirrors (wavelength ratio 1.335 each with these materials) needed to cover the span of the target's
#: stop bands (2026-11-01 night: a fixed 400-700 nm span was wrong for the long-wave pass, 400-540 nm)
_STOP = [(a, b) for a, b, t in s._bands if t == 0.0]
M = np.log(max(b for _a, b in _STOP) / min(a for a, _b in _STOP)) / np.log(MIRROR)


def ot_c(r, lam=400.0, dlam=1.0, h=0.5):
    return M * lam / 2 * np.log(C_FP * lam / (dlam * np.sqrt(r / h))) / np.log(RHO)


def judge(rows, kind):
    out = []
    for r in rows:
        seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
        nom, res = gs.mf(seq, d, gs.GRIDS["nominal"]), gs.mf(seq, d, gs.GRIDS["resolved"])
        p = tt.poles(seq, d)
        ot = float(s.total_ot(seq, d))
        out.append({"kind": kind, "layers": len(seq), "ot_nm": ot, "mf_nominal": nom, "mf_resolved": res,
                    "poles": len(p), "highest": max((q[2] for q in p), default=0.0),
                    "ot_c": ot_c(nom / 100.0)})
        print(f"{kind} N {len(seq):3d} OT {ot:7.0f} nominal {nom:.4f} % resolved {res:.4f} % ratio {res / nom:5.2f} "
              f"poles {len(p)} highest {100 * out[-1]['highest']:.2f} % OT_c {out[-1]['ot_c']:.0f}", flush=True)
    return out


def main() -> None:
    out = Path(sys.argv[1])
    rows = judge(list(csv.DictReader(open(f"curve_{s.TAG}free_s{SEED}.csv", encoding="utf-8"))), "curve")
    rows += judge(list(csv.DictReader(open(f"front_{s.TAG}free_s{SEED}.csv", encoding="utf-8"))), "front")
    with open(f"{s.TAG}threshold{SUFFIX}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tl = list(csv.DictReader(open("threeline_mc_resolved.csv", encoding="utf-8")))
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    for kind, mk in (("curve", "o"), ("front", "s")):
        q = [r for r in rows if r["kind"] == kind]
        ax[0].semilogy([r["ot_nm"] for r in q], [r["mf_resolved"] / r["mf_nominal"] for r in q], mk, ms=4,
                       label=f"{s.TARGET} ({kind})")
        ax[1].semilogy([r["layers"] for r in q], [r["mf_resolved"] / r["mf_nominal"] for r in q], mk, ms=4,
                       label=f"{s.TARGET} ({kind})")
    ax[0].semilogy([float(r["tot"]) for r in tl], [float(r["mf_resolved"]) / float(r["mf_nominal"]) for r in tl], "^",
                   ms=4, label="three-line filter")
    ax[1].semilogy([int(r["layers"]) for r in tl], [float(r["mf_resolved"]) / float(r["mf_nominal"]) for r in tl], "^",
                   ms=4, label="three-line filter")
    for a in ax:
        a.axhline(1.0, color="0.6", lw=0.8)
        a.set_ylabel("resolved MF / nominal MF")
        a.legend(fontsize=7)
    cs = sorted(r["ot_c"] for r in rows if r["kind"] == "curve")
    ax[0].axvspan(cs[0], cs[-1], color="C3", alpha=0.12, label="OT_c estimate")
    ax[0].set_xlabel("optical thickness (nm)")
    ax[1].set_xlabel("number of layers")
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"threshold_{s.TAG.rstrip("_")}{SUFFIX}.pdf")
    fig.savefig(out / f"threshold_{s.TAG.rstrip("_")}{SUFFIX}.png", dpi=150)


if __name__ == "__main__":
    main()
