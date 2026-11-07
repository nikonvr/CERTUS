"""Dataset 1 of the method paper (OE_resonances/dataset, 2026-11-02, owner): the classical three-line design without its
substrate-side L layer, as re-polished (fig4_2020_classical_nolsub.csv) and after the charge of its poles (last round of
threeline_track_height_classical103.csv), written in the format of Code 1 (layer, material, thickness_nm; layer 1 on the
substrate) with the thicknesses exactly as measured, then judged again from the written files by Code 1.
usage: python oe_dataset_classical.py OE_CODE_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import classical_trub104 as ct  # puts OE_CODE_DIR (argv[1]) on the path and imports Code 1
import numpy as np

#: source, file of Dataset 1, MF of Table 1 on the 277 points and resolved (%)
SOURCES = (("fig4_2020_classical_nolsub.csv", "three_line_classical_103_recreated.csv", 0.0133, 0.0354),
           ("threeline_track_height_classical103.csv", "three_line_classical_103_charged.csv", 0.0350, 0.0350))


def main() -> None:
    out = Path(sys.argv[1]).parent / "dataset"
    out.mkdir(exist_ok=True)
    for src, dst, mf_nom, mf_res in SOURCES:
        rows = list(csv.DictReader(open(src, encoding="utf-8")))
        r = rows[-1] if "round" in rows[0] else rows[0]
        seq, tokens = r["seq"], r["d_nm"].split()
        with open(out / dst, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["layer", "material", "thickness_nm"])
            w.writerows((k + 1, m, t) for k, (m, t) in enumerate(zip(seq, tokens, strict=True)))
        back = list(csv.DictReader(open(out / dst, encoding="utf-8")))
        nl = [ct.N_IDX[b["material"]] for b in back]
        d = np.array([float(b["thickness_nm"]) for b in back])
        a, b = ct.judged(nl, d, 1.0)[0], ct.judged(nl, d, 0.0002)[0]
        print(f"{dst}: {len(back)} layers, first {back[0]['material']} {back[0]['thickness_nm']} nm; MF on the 277 "
              f"points {a:.4f} % (Table 1: {mf_nom}), resolved {b:.4f} % (Table 1: {mf_res})", flush=True)


if __name__ == "__main__":
    main()
