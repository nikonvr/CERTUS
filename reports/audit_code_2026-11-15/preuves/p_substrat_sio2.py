"""Audit C1 (lot 4): which index does STRAT give its 'SiO2' substrate? Compared with fused silica (Malitson 1965).

    python reports/audit_code_2026-11-15/preuves/p_substrat_sio2.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402

from certus.utils.certus_db_helpers import find_matching_sheets  # noqa: E402


def malitson(wl_nm: float) -> float:
    x = (wl_nm / 1000.0) ** 2
    return float(np.sqrt(1 + 0.6961663 * x / (x - 0.0684043**2) + 0.4079426 * x / (x - 0.1162414**2)
                         + 0.8974794 * x / (x - 9.896161**2)))


params = seq.load_params(ROOT / "example" / "example_strat" / "JSON-strat-example.json")
db = params.get("materials_db_instance") or params.get("materials_db")
print("nSub_id =", repr(params["nSub_id"]), "| db type:", type(db).__name__)
names = db.get_material_list()
print("SiO2 sheets in the database:", [m for m in names if "sio2" in m.lower()], "| exact 'SiO2':", "SiO2" in names)
print("sheets matched for 'SiO2':", find_matching_sheets("SiO2", names))
inner = db._db
print("'SiO2' in", type(inner.materials).__name__, ":", "SiO2" in inner.materials,
      "| Sellmeier SiO2 at 550 nm:", round(inner._sellmeier_n(0.55, *inner.SELLMEIER_COEFFS["SiO2"]), 5))
for wl in (400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0):
    n = seq.material_index(params, params["nSub_id"], wl)
    print(f"{wl:5.0f} nm  STRAT n_sub = {n.real:.5f}{n.imag:+.2e}j   Malitson = {malitson(wl):.5f}   diff = {n.real - malitson(wl):+.5f}")
