"""Sec. 7.3: are the best resolved MFs of sec73_compare.py resolved? The best design of each arm (search on the grid,
the same cured, search with the poles charged) of both targets, judged by Code 1 on 0.001 and 0.0002 nm steps.
usage: python sec73_best_check.py OE_CODE_DIR
"""

from __future__ import annotations

import csv
import os

import classical_trub104 as ct  # puts OE_CODE_DIR (argv[1]) on the path and imports Code 1
import numpy as np

os.environ.setdefault("SEARCH_TARGET", "threeline")
import oe_dataset as od  # noqa: E402  (mf_target)


def best(path, key):
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if float(r.get("mf_nominal", 0.0) or 0.0) < 5.0]
    return min(rows, key=lambda r: float(r[key]))


def main() -> None:
    for t in ("mshape", "highpass"):
        for name, path, key in (("grid", f"nolsub_{t}_threshold_s9.csv", "mf_resolved"),
                                ("grid, cured", f"nolsub_{t}_cure_archive_s9.csv", "resolved_after"),
                                ("poles charged", f"poles3_nolsub_{t}_threshold_s9.csv", "mf_resolved")):
            r = best(path, key)
            if "seq" not in r:  # the threshold files carry no design: take it from the search files, same order
                tag = path.replace("_threshold_s9.csv", "")
                designs = list(csv.DictReader(open(f"curve_{tag}_free_s9.csv", encoding="utf-8")))
                designs += list(csv.DictReader(open(f"front_{tag}_free_s9.csv", encoding="utf-8")))
                judged = list(csv.DictReader(open(path, encoding="utf-8")))
                r = {**r, **designs[judged.index(r)]}
            nl = [ct.N_IDX[m] for m in r["seq"]]
            d = np.array([float(v) for v in r["d_nm"].split()])
            a, b = od.mf_target(t, nl, d, 0.001), od.mf_target(t, nl, d, 0.0002)
            print(f"{t}, {name}: {len(d)} layers, source {float(r[key]):.4f} %; Code 1 {a:.4f} % on 0.001 nm, {b:.4f} % "
                  f"on 0.0002 nm", flush=True)


if __name__ == "__main__":
    main()
