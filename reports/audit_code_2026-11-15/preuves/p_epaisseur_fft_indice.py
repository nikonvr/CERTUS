"""Audit M-L5g: which index divides the optical path in INDEX's FFT thickness pre-estimate.

Calls the real `CertusIndexEventsMixin._auto_detect_from_file` on a stub window whose `target_data` is a synthetic
spectrum from the independent reference TMM (`tests/oracle/tmm_reference.py`, non-dispersive indices), then reads the
thickness bounds it writes into `sb_dmin` / `sb_dmax` (they become the fit's `thickness_min/max`).
    python reports/audit_code_2026-11-15/preuves/p_epaisseur_fft_indice.py
"""

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tmm_reference import rt_stack  # noqa: E402

from certus.ui.certus_index_ui_events import CertusIndexEventsMixin  # noqa: E402


class Combo:
    def __init__(self, items):
        self.items, self.i = list(items), 0

    def findText(self, t):
        return self.items.index(t) if t in self.items else -1

    def setCurrentIndex(self, i):
        self.i = i

    def currentText(self):
        return self.items[self.i]


class Spin:
    def __init__(self):
        self.v = None

    def setValue(self, v):
        self.v = v

    def value(self):
        return self.v


class Window:
    pass


lam = np.linspace(400.0, 1000.0, 601)
cases = (  # (film, n_film, d_nm, substrate, n_sub, file name that selects the substrate, column)
    ("SiO2", 1.46, 500.0, "Si", 3.88, "sio2_on_wafer.csv", "R"),
    ("SiO2", 1.46, 1000.0, "Si", 3.88, "sio2_on_wafer.csv", "R"),
    ("Ta2O5", 2.10, 500.0, "Si", 3.88, "ta2o5_on_wafer.csv", "R"),
    ("TiO2", 2.30, 500.0, "SiO2", 1.46, "tio2_on_fusedsilica.csv", "T"),
)
for film, nf, d, sub, ns, fname, col in cases:
    rt = np.array([rt_stack(w, [complex(nf)], [d], 1.0 + 0j, complex(ns)) for w in lam])
    w = Window()
    w.cb_sub = Combo(["N-BK7", "SiO2", "Si", "Al2O3"])
    w.sb_dmin, w.sb_dmax = Spin(), Spin()
    w.logger = logging.getLogger("audit")
    w.target_data = pd.DataFrame({"lambda": lam, col: rt[:, 0] if col == "R" else rt[:, 1]})
    CertusIndexEventsMixin._auto_detect_from_file(w, fname)
    lo, hi = w.sb_dmin.v, w.sb_dmax.v
    inside = lo is not None and lo <= d <= hi
    print(f"{film:5s} n={nf:.2f} d={d:6.0f} nm on {sub:4s} (picked: {w.cb_sub.currentText():4s}) | "
          f"d_hat={w._estimated_thickness_nm:7.1f} nm = {w._estimated_thickness_nm / d:.3f} d | "
          f"bounds [{lo:.0f}, {hi:.0f}] nm | true d inside: {inside}")
