"""Lot 2a: where did the floor eps1 >= 1 act on the 11 certified Tauc-Lorentz fits of the deposit database?

For each reference of example/database_depots/references_index.json: unfloored eps1 (code after the removal) on its
fit band, or on the measured range of its deposits (catalogue.json) when the band is not given, and the count of points
where eps1 < 1 (where the old floor changed the value). Run from the root: python reports/nuit_2026-11-19/p2a_floor_reach.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from certus.physics.certus_optical_models import epsilon1_TL_analytic

HC_EV_NM = 1239.84193
ROOT = Path(__file__).resolve().parents[2]
refs = json.loads((ROOT / "example/database_depots/references_index.json").read_text(encoding="utf-8"))["references"]
catalogue = json.loads((ROOT / "example/database_depots/catalogue.json").read_text(encoding="utf-8"))["depots"]
measured = {entry["id"]: entry["lambda_nm"] for entry in catalogue}
print(f"{'reference':<22} {'band nm':>13} {'min eps1':>9} {'pts<1':>6} / {'pts':>4}  {'lambda of first eps1<1':>22}")
for ref in refs:
    p = ref["parametres"]
    lo, hi = ref.get("bande_nm") or [None, None]
    ranges = [measured[dep] for dep in ref["depots"] if dep in measured]
    lo = float(lo) if lo else max(r[0] for r in ranges)
    hi = float(hi) if hi else min(r[1] for r in ranges)
    wl = np.linspace(lo, hi, 2000)
    eps1 = epsilon1_TL_analytic(HC_EV_NM / wl, p["Eg"], p["A"], p["E0"], p["C"], p["eps_inf"])
    below = eps1 < 1.0
    first = f"{wl[below].max():.0f}" if below.any() else "-"
    print(f"{ref['nom']:<22} {lo:>6.0f}-{hi:<6.0f} {eps1.min():>9.3f} {int(below.sum()):>6} / {wl.size:>4}  {first:>22}")
