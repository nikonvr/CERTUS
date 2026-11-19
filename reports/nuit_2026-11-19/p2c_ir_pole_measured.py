"""Lot 2c: `sellmeier_ir_pole` (on by default since 2026-11-19) against the old default, on MEASURED substrate indices.

Data: example/exemple_substrate_index/exemple_substrate_index.xlsx (Al2O3, T and R, 400-...) and
example/database_index/indices RT substrats.xlsx (HPFS 7980, B270, 7315, sapphire 7157, silicon; T and R 250-5200 nm).
n comes from the two-face transmission of a non-absorbing plate (`IndexCore.n_from_tnu2f`), as SUBSTRATE does, on a
range where each plate is transparent (choice written per case). For each case: rms of (fit - data) on the fit range,
retained source, duration (warm), and the largest |on - off| over the fit range and over the full measured range
(extrapolation). No true curve here: the rms against data includes the measurement noise.

set PYTHONPATH=. && python reports/nuit_2026-11-19/p2c_ir_pole_measured.py
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import openpyxl

from certus.core.certus_substrate_index import IndexCore

ROOT = Path(__file__).resolve().parents[2]


def _workbook_rows(path: Path, sheet: str | None) -> tuple[tuple, list[tuple]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    return rows[0], rows[1:]


def _column(rows: list[tuple], j: int) -> np.ndarray:
    return np.array([float(r[j]) if isinstance(r[j], (int, float)) else np.nan for r in rows], dtype=np.float64)


cases: list[tuple[str, np.ndarray, np.ndarray, float, float]] = []

hdr, rows = _workbook_rows(ROOT / "example/exemple_substrate_index/exemple_substrate_index.xlsx", None)
wl1 = _column(rows, 0)
cases.append(("Al2O3 exemple_substrate_index", wl1, _column(rows, 1), float(np.nanmin(wl1)), float(np.nanmax(wl1))))

hdr, rows = _workbook_rows(ROOT / "example/database_index/indices RT substrats.xlsx", "16-02-2026 12.34.15")
wl2 = _column(rows, 1)
# (label, T column header, transparent fit range in nm): glasses before their UV edge and the 2.7 um OH band,
# sapphire up to 5 um, silicon above its band gap.
for label, header, lo, hi in (
    ("HPFS 7980", "T HPFS 7980 25x2", 300.0, 2500.0),
    ("B270", "T B270 41.5x1.0", 350.0, 2500.0),
    ("7315", "T 7315-25x2mm vmtim", 350.0, 2500.0),
    ("sapphire 7157", "T 7157 sapphire 25x1mm vmtim", 300.0, 5000.0),
    ("silicon", " Tsilicum double face 4 pouces ", 1300.0, 5200.0),
):
    cases.append((label, wl2, _column(rows, hdr.index(header)), lo, hi))
# The workbook's own NAVG columns: n averaged from T and R by its author, used as n directly (marked "n:").
navg: list[tuple[str, np.ndarray, np.ndarray, float, float]] = []
for label, header, lo, hi in (
    ("HPFS 7980 NAVG", "NAVG HPFS 7980 25x2", 300.0, 2500.0),
    ("B270 NAVG", "NAVG B270 1mm", 350.0, 2500.0),
    ("sapphire NAVG", "NAVG sapphire 2mm", 300.0, 5000.0),
    ("silicon NAVG", "NAVGsilicium", 1300.0, 5200.0),
):
    navg.append((label, wl2, _column(rows, hdr.index(header)), lo, hi))

print("case | range nm | n pts | old default: rms to data, source, s | ir pole: rms, source, s | max|on-off| fit / full")
for label, wl, values, lo, hi in [*cases, *navg]:
    order = np.argsort(wl)
    wl, values = wl[order], values[order]
    if label.endswith("NAVG"):
        ok = np.isfinite(wl) & np.isfinite(values) & (values > 1.0) & (values < 6.0)
        wl, n = wl[ok], values[ok]
    else:
        ok = np.isfinite(wl) & np.isfinite(values) & (values > 0.0) & (values < 100.0)
        wl, n = wl[ok], IndexCore.n_from_tnu2f(values[ok] / 100.0)
    fit = (wl >= lo) & (wl <= hi) & np.isfinite(n)
    IndexCore.fit_sellmeier(n, wl, lo, hi, valid_mask=fit, model_kind="sellmeier3poles", sellmeier_ir_pole=True)  # warm
    out, curves = [], []
    for ir in (False, True):
        t0 = time.perf_counter()
        curve, meta = IndexCore.fit_sellmeier(n, wl, lo, hi, valid_mask=fit, model_kind="sellmeier3poles",
                                              return_meta=True, sellmeier_ir_pole=ir)
        dt = time.perf_counter() - t0
        rms = float(np.sqrt(np.mean((curve[fit] - n[fit]) ** 2)))
        out.append(f"{rms:.3e} {str(meta['source']).replace('analytic-sellmeier-', '')} {dt:.2f}")
        curves.append(np.asarray(curve, dtype=np.float64))
    diff = np.abs(curves[1] - curves[0])
    full = np.isfinite(diff)
    print(f"{label} | {lo:.0f}-{hi:.0f} | {int(fit.sum())} | {out[0]} | {out[1]} | "
          f"{float(np.max(diff[fit])):.2e} / {float(np.max(diff[full])):.2e}")
