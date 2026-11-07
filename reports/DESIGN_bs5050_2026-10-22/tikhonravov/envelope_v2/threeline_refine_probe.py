"""Three-line filter: does a finer grid resolve the optimum, or does the optimizer hide narrower resonances? (2026-11-01)

Our best design (109 layers, 0.0145 % on the 277 nominal points, 0.378 % resolved) is polished on uniform band grids of
0.005 then 0.001 nm, each result judged on 1, 0.005, 0.001 and 0.0002 nm, with the peaks of |T - T'| above 1 % on the
0.0002 nm scan (position, height, FWHM). A grid resolves the problem if the design optimized on it keeps its MF on the
finer ones. Designs to threeline_refine_probe.csv.
usage: SEARCH_TARGET=threeline python threeline_refine_probe.py [IN.csv OUT.csv]   (default: our design; 2026-11-01
evening, owner: the method paper uses Trubetskov's 101-layer design alone, IN = fig4_2020_designs.csv)
"""

from __future__ import annotations

import csv
import sys
import time

import bs5050_grid as bg
import grid_study as gs
import numpy as np

STEPS = (1.0, 0.005, 0.001, 0.0002)
SRC, DST = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("gradual_deep2_cont_seed89_clean2.csv",
                                                                 "threeline_refine_probe.csv")


def peaks(seq, d, step=0.0002, thr=0.01):
    w, tgt = gs.band_grid(step)
    out = []
    for idx in np.array_split(np.arange(len(w)), -(-len(w) // gs.CHUNK)):
        g = gs.kernel_grid(w[idx], tgt[idx])
        a = np.abs(bg.res_jac(seq, d, g)[0] / g["sqw"])
        for k in np.where((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr))[0] + 1:
            lo, hi = k, k
            while lo > 0 and a[lo] > a[k] / 2:
                lo -= 1
            while hi < len(a) - 1 and a[hi] > a[k] / 2:
                hi += 1
            out.append((float(a[k]), float(w[idx][k]), float(w[idx][hi] - w[idx][lo])))
    return sorted(out, reverse=True)


def report(tag, seq, d, t0) -> None:
    vals = [gs.mf(seq, d, gs.kernel_grid(*gs.band_grid(h))) for h in STEPS]
    print(f"{tag}: " + ", ".join(f"{h:g} nm {v:.4f} %" for h, v in zip(STEPS, vals, strict=True))
          + f" ({time.time() - t0:.0f} s)", flush=True)
    for h, x, fw in peaks(seq, d)[:6]:
        print(f"    peak {x:9.4f} nm  {100 * h:6.2f} %  FWHM {fw:.4f} nm", flush=True)


def main() -> None:
    r = min(csv.DictReader(open(SRC, encoding="utf-8")),
            key=lambda r: float(r["mf_oracle"]))
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    t0 = time.time()
    report("nominal design", seq, d, t0)
    rows = []
    for h in (0.005, 0.001):
        d = gs.polish(seq, d, gs.kernel_grid(*gs.band_grid(h)))
        report(f"polished on {h:g} nm", seq, d, t0)
        rows.append({"grid_nm": h, "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
    with open(DST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
