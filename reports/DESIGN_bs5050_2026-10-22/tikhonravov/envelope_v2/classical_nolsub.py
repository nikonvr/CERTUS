"""Trubetskov's classical 104-layer three-line design (2020, Fig. 4, as re-created in fig4_2020_designs.csv) without its
low-index layer on the substrate (owner, 2026-11-02: "enleve cette couche"; L 94 nm on glass does nothing optically),
re-polished on the 277 points exactly as the re-creation was (fig4_2020_extract.polish), written to
fig4_2020_classical_nolsub.csv and then judged by classical_trub104.py. The shift is in optical thickness, as in
fig4_2020_designs.csv, here from the 104-layer design.
usage: python classical_nolsub.py
"""

from __future__ import annotations

import csv
import os

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from fig4_2020_extract import polish  # noqa: E402


def main() -> None:
    r = next(r for r in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if r["design"] == "classical")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    assert seq[:2] == "LH", seq[:2]
    seq1, d1 = seq[1:], d[1:]
    n1 = np.array([s.N_IDX[m] for m in seq1])
    print(f"dropped layer 1: L {d[0]:.2f} nm; {len(seq1)} layers, first {seq1[0]} {d1[0]:.2f} nm; "
          f"MF before the polish {100 * s.oracle_rmse(seq1, d1):.4f} %", flush=True)
    d2 = polish(seq1, d1)
    shift = float(np.abs((d2 - d1) * n1).max())
    mf, ot = 100 * s.oracle_rmse(seq1, d2), s.total_ot(seq1, d2)
    print(f"re-polished: MF {mf:.4f} % (oracle), OT {ot:.1f} nm, max OT shift {shift:.2f} nm, thinnest "
          f"{d2.min():.2f} nm, first {seq1[0]} {d2[0]:.2f} nm", flush=True)
    with open("fig4_2020_classical_nolsub.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["design", "layers", "mf_oracle", "tot", "max_shift_nm", "seq", "d_nm"])
        w.writeheader()
        w.writerow({"design": "classical", "layers": len(seq1), "mf_oracle": mf, "tot": ot, "max_shift_nm": shift,
                    "seq": seq1, "d_nm": " ".join(f"{v:.6f}" for v in d2)})


if __name__ == "__main__":
    main()
