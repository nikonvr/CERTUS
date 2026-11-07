r"""Appendix A table of the OE paper (2026-11-03): the re-created 101-layer design in GROUPS column groups.

Reads the design of Code 1 (OE_resonances/code/three_line_101_recreated.csv), checks that every thickness printed in the
current appendix_design.tex is unchanged (3 decimals), and rewrites appendix_design.tex with GROUPS groups of
`#, material, d (nm)` (the previous file had 4).
usage: python appendix_table.py OE_DIR [GROUPS]
"""

import csv
import math
import re
import sys
from pathlib import Path

oe = Path(sys.argv[1])
groups = int(sys.argv[2]) if len(sys.argv) > 2 else 5
rows = [(int(r["layer"]), r["material"], float(r["thickness_nm"]))
        for r in csv.DictReader(open(oe / "code" / "three_line_101_recreated.csv", encoding="utf-8"))]
old = (oe / "appendix_design.tex").read_text(encoding="utf-8")
printed = {int(i): (m, t) for i, m, t in re.findall(r"(\d+) & ([HL]) & ([\d.]+)", old)}
bad = [i for i, m, t in rows if printed.get(i) != (m, f"{t:.3f}")]
if len(printed) != len(rows) or bad:
    sys.exit(f"appendix and Code 1 disagree: {len(printed)} printed rows, mismatches at layers {bad[:10]}")
n = math.ceil(len(rows) / groups)
spec = ("@{\\qquad}" if groups < 6 else "@{\\quad}").join(["rcr"] * groups)  # six groups fit the text width with \quad
head = " & ".join([r"\# & & $d$ (nm)"] * groups)
lines = [old.splitlines()[0], rf"\begin{{tabular}}{{{spec}}}\toprule", head + r"\\ \midrule"]
for k in range(n):
    cells = []
    for g in range(groups):
        j = g * n + k
        cells.append(f"{rows[j][0]} & {rows[j][1]} & {rows[j][2]:.3f}" if j < len(rows) else " & & ")
    lines.append(" & ".join(cells) + r"\\")
lines += [r"\bottomrule", r"\end{tabular}"]
(oe / "appendix_design.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(rows)} layers in {groups} groups of {n} rows; every printed thickness unchanged")
