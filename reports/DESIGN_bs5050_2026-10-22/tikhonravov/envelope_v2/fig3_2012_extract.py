"""Layer optical thicknesses of the ten 51-layer three-line designs of Tikhonravov & Trubetskov, AO 51, 7319 (2012),
Fig. 3, read from the vector bars of the PDF (page 5), 2026-10-29.

Purpose: judge their designs with our merit function, to tell a definition difference from a search difference
(our 2012 procedure reaches 0.875 against their 0.464-0.599, while the hot mirror reproduces their 0.865 exactly).

usage: python fig3_2012_extract.py PDF   -> fig3_2012_bars.csv (raw rectangles), then the panels are calibrated
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pypdf

HERE = Path(__file__).resolve().parent
TOKEN = re.compile(r"\[[^\]]*\]|\([^)]*\)|/[^\s/\[\]()<>]+|[-+]?\d*\.?\d+|[A-Za-z*'\"]+")


def rects(page) -> list[tuple[float, float, float, float, tuple]]:
    """(x0, y0, x1, y1, fill colour) of every `re` in device space, CTM tracked through q/Q/cm."""
    data = page.get_contents().get_data().decode("latin1")
    stack, ctm, fill, nums, out = [], (1, 0, 0, 1, 0, 0), (), [], []
    for tok in TOKEN.findall(data):
        if re.fullmatch(r"[-+]?\d*\.?\d+", tok):
            nums.append(float(tok))
            continue
        if tok == "q":
            stack.append((ctm, fill))
        elif tok == "Q" and stack:
            ctm, fill = stack.pop()
        elif tok == "cm" and len(nums) >= 6:
            a, b, c, d, e, f = nums[-6:]
            A, B, C, D, E, F = ctm
            ctm = (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)
        elif tok in ("rg", "sc", "scn", "g", "k") and nums:
            fill = tuple(nums[-{"g": 1, "k": 4}.get(tok, 3):])
        elif tok == "re" and len(nums) >= 4:
            x, y, w, h = nums[-4:]
            A, B, C, D, E, F = ctm
            xs = [A * px + C * py + E for px, py in ((x, y), (x + w, y + h))]
            ys = [B * px + D * py + F for px, py in ((x, y), (x + w, y + h))]
            out.append((min(xs), min(ys), max(xs), max(ys), fill))
        nums = []
    return out


def main() -> None:
    page = pypdf.PdfReader(sys.argv[1]).pages[4]
    rs = rects(page)
    with (HERE / "fig3_2012_bars.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["x0", "y0", "x1", "y1", "fill"])
        for r in rs:
            w.writerow([f"{v:.4f}" for v in r[:4]] + [" ".join(f"{c:g}" for c in r[4])])
    print(len(rs), "rectangles")


if __name__ == "__main__":
    main()
