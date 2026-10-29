"""Which wavelength grid did Tikhonravov & Trubetskov (AO 51, 7319, 2012) use for the three-line filter? (2026-10-29)

The ten 51-layer designs of Fig. 3 (raw bars, `fig3_2012_designs.csv`, column ot_raw) are judged on four grids that
differ only at the band edges: 277 points (every band [a, b]), 270 ([a, b) or (a, b]) and 263 ((a, b)). For each grid:
the raw MF, then the MF after a bounded polish (OT 100-350 nm) on that same grid. The right grid reproduces Table 1
design by design. Designs are matched to Table 1 by TOT.

usage: python grid_test.py   -> grid_test.csv and stdout
"""

from __future__ import annotations

import csv
import os

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from constrained import local  # noqa: E402

TABLE1 = [(0.526, 9212.7), (0.524, 9363.9), (0.516, 9409.7), (0.479, 9422.8), (0.571, 9202.9), (0.599, 9391.2),
          (0.570, 9665.9), (0.464, 9371.8), (0.524, 9226.7), (0.496, 9382.7)]
BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
         (650, 700, 0.0)]
GRIDS = {"277 [a,b]": (0, 0), "270 [a,b)": (0, 1), "270 (a,b]": (1, 0), "263 (a,b)": (1, 1)}


def set_grid(cut_lo: int, cut_hi: int) -> None:
    """Point the search module globals at one grid (every kernel call reads them)."""
    wls = np.concatenate([np.arange(a + cut_lo, b + 1 - cut_hi, dtype=float) for a, b, _t in BANDS])
    s.WLS, s.K0 = wls, 2.0 * np.pi / wls
    s.TGT = np.concatenate([np.full(b + 1 - cut_hi - a - cut_lo, t) for a, b, t in BANDS])
    s.SQW = np.full(len(wls), np.sqrt(1.0 / len(wls)))
    s.NSUB, s.ZB, s.OB = np.full(len(wls), s.N_SUB), np.zeros(len(wls)), np.ones(len(wls))


def main() -> None:
    rows = list(csv.DictReader((s.HERE / "fig3_2012_designs.csv").open(encoding="utf-8")))
    out = []
    for label, cut in GRIDS.items():
        set_grid(*cut)
        errs = []
        for r in rows:
            seq, ot_raw = r["seq"], np.array([float(v) for v in r["ot_raw"].split()])
            n = np.array([s.N_IDX[m] for m in seq])
            raw = 100 * s.oracle_rmse(seq, ot_raw / n)
            _rk, d = local((seq, ot_raw))
            pol = 100 * s.oracle_rmse(seq, d)
            tot = s.total_ot(seq, d)
            j = min(range(10), key=lambda i: abs(TABLE1[i][1] - tot))
            errs.append(pol - TABLE1[j][0])
            out.append({"grid": label, "points": len(s.WLS), "design": j + 1, "table1_mf": TABLE1[j][0],
                        "table1_tot": TABLE1[j][1], "mf_raw": raw, "mf_polished": pol, "tot_polished": tot})
        e = np.array(errs)
        print(f"{label}: {len(s.WLS)} pts, polished - Table 1: mean {e.mean():+.4f} rms {np.sqrt((e * e).mean()):.4f} "
              f"max |.| {np.abs(e).max():.4f}", flush=True)
    for o in out:
        print(f"{o['grid']} D{o['design']:>2} T1 {o['table1_mf']:.3f} raw {o['mf_raw']:.4f} pol {o['mf_polished']:.4f} "
              f"TOT {o['tot_polished']:.1f} (T1 {o['table1_tot']})")
    with (s.HERE / "grid_test.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
