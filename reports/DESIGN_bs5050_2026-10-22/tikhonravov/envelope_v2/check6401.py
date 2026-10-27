"""Oracle check of the best 50/50 designs per N on a 6401-point grid (400-1200 nm), against the 1601-point value.

usage: python check6401.py CURVE.csv [CURVE.csv ...]   -> check6401.txt (best design per N over all curves)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import search as s

HERE = Path(__file__).resolve().parent


def main() -> None:
    best: dict[int, tuple[float, str, np.ndarray, str]] = {}
    for f in sys.argv[1:]:
        for r in csv.DictReader((HERE / f).open(encoding="utf-8")):
            n, v = int(r["layers"]), float(r["rmse_1601_oracle"])
            if v < best.get(n, (np.inf,))[0]:
                best[n] = (v, r["seq"], np.array([float(x) for x in r["d_nm"].split()]), f)
    wl = np.linspace(400.0, 1200.0, 6401)
    out = ["N  RMSE 1601 (oracle)  RMSE 6401 (oracle)  ratio  thinnest_nm  total_QWOT  source"]
    for n in sorted(best):
        if n < 20:
            continue
        v, seq, d, f = best[n]
        t = np.array([s.oracle.rt_stack(w, [complex(s.N_IDX[m]) for m in seq], d, complex(1.0), complex(s.N_SUB))[1]
                      for w in wl])
        v6 = float(np.sqrt(np.mean((t - 0.5) ** 2)))
        out.append(f"{n:2d}  {v:.4e}  {v6:.4e}  {v6 / v:.3f}  {d.min():8.2f}  "
                   f"{np.sum(d * np.array([4 * s.N_IDX[m] for m in seq])) / s.L0:7.2f}  {f}")
        print(out[-1], flush=True)
    (HERE / "check6401.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
