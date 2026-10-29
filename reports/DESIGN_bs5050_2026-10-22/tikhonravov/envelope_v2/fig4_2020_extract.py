"""Layer optical thicknesses of the two three-line designs of Trubetskov, AO 59, A75 (2020), Fig. 4 (classical, top;
deep search, bottom), read from the raster image embedded in the PDF (page 3, 1614 x 2106 px), 2026-10-29.

Purpose: judge their designs with our merit function (277 points, `grid_test.py`), then compare CERTUS at the same
number of layers and total optical thickness. Bars: magenta = L, yellow = H, layer 1 next to the substrate. The OT
scale is fitted on the dashed grid lines (50-250 nm, about 3 px per nm); a bar top is its fill top minus half the
outline. The reading error (about 0.5 nm) is absorbed by a polish.

usage: python fig4_2020_extract.py PDF   -> fig4_2020_designs.csv (raw OT, polished design, oracle MF)
"""

from __future__ import annotations

import csv
import io
import os
import sys

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import pypdf  # noqa: E402
import search as s  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

#: (name, first and last image row of the plot area, grid line rows of 250, 200, 150, 100, 50 nm, last legend row)
PANELS = [("classical", 20, 912, [168.5, 318.5, 468.0, 616.5, 766.5], 155),
          ("deep", 1102, 1998, [1251.5, 1401.5, 1551.5, 1699.5, 1849.5], 1240)]
OUTLINE = 1.5  # px, half the black bar outline
LEGEND_COLS = slice(1400, 1530)  # the legend boxes sit above the bars of layers 92-97


def bars(img: np.ndarray, top: int, bottom: int, grid: list[float], legend: int) -> tuple[str, np.ndarray]:
    r, g, b = (img[top:bottom, :, i].astype(int) for i in range(3))
    mag = (r > 200) & (g < 90) & (b > 200)
    yel = (r > 200) & (g > 200) & (b < 110)
    mag[: legend - top, LEGEND_COLS] = False
    yel[: legend - top, LEGEND_COLS] = False
    slope, icpt = np.polyfit(grid, [250.0, 200.0, 150.0, 100.0, 50.0], 1)
    cols = np.nonzero((mag | yel).sum(0) > 3)[0]
    groups = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
    seq, ots = [], []
    for grp in groups:
        if len(grp) < 4:
            continue
        mid = grp[len(grp) // 2 - 1: len(grp) // 2 + 2]
        m, y = mag[:, mid].sum(), yel[:, mid].sum()
        fill = (mag | yel)[:, mid].any(1)
        row = top + np.nonzero(fill)[0][0] - OUTLINE
        seq.append("L" if m > y else "H")
        ots.append(slope * row + icpt)
    return "".join(seq), np.array(ots)


def polish(seq: str, d: np.ndarray) -> np.ndarray:
    st = s.Stack.of(seq)
    sol = least_squares(lambda x: st.res_jac(x)[0], d, jac=lambda x: st.res_jac(x)[1], bounds=(0.0, np.inf),
                        method="trf", x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=2000)
    return sol.x


def main() -> None:
    page = pypdf.PdfReader(sys.argv[1]).pages[2]
    raw = page["/Resources"]["/XObject"]["/Im6"].get_object()["/Resources"]["/XObject"]["/Im1"].get_object()
    img = np.asarray(Image.open(io.BytesIO(raw.get_data())).convert("RGB"))
    rows = []
    for name, top, bottom, grid, legend in PANELS:
        seq, ot = bars(img, top, bottom, grid, legend)
        n = np.array([s.N_IDX[m] for m in seq])
        d0 = ot / n
        d = polish(seq, d0)
        mf_raw, mf = 100 * s.oracle_rmse(seq, d0), 100 * s.oracle_rmse(seq, d)
        rows.append({"design": name, "layers": len(seq), "tot_raw": float(ot.sum()), "mf_raw": mf_raw,
                     "mf_oracle": mf, "tot": s.total_ot(seq, d), "max_shift_nm": float(np.abs((d - d0) * n).max()),
                     "seq": seq, "ot_raw": " ".join(f"{v:.2f}" for v in ot), "d_nm": " ".join(f"{v:.6f}" for v in d)})
        print(f"{name}: N {len(seq)} first {seq[0]} TOT raw {ot.sum():.1f} MF raw {mf_raw:.4f} -> polished "
              f"{mf:.4f} TOT {s.total_ot(seq, d):.1f} max OT shift {rows[-1]['max_shift_nm']:.2f} nm", flush=True)
    with (s.HERE / "fig4_2020_designs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
