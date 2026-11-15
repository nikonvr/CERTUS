"""Audit C-L3: in ratio mode, does SPLINE's fused objective model R the way the corridor code does?

Synthetic data from the corridor's own ratio models (`_ratio_theoretical_from_nk`, `_reflectance_ratio_theoretical_from_nk`)
at the true film; the fused objective is then evaluated AT the true film. A consistent model gives ~0.
    python reports/audit_code_2026-11-15/preuves/p_spline_ratio_R.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from certus.spline.spline_objective import (  # noqa: E402
    _njit_single_layer_mse_fused,
    calculate_bare_substrate_RT,
)
from certus.utils.certus_index_utils import (  # noqa: E402
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
)

lam = np.linspace(400.0, 1000.0, 301)
n_l = np.full_like(lam, 2.10)
k_l = np.full_like(lam, 1e-3)
n_sub = np.full_like(lam, 1.52)
d = 300.0
t_exp = np.asarray(_ratio_theoretical_from_nk(lam, n_l, k_l, d, n_sub), dtype=np.float64)
r_exp = np.asarray(_reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d, n_sub), dtype=np.float64)
t_sub = np.asarray(calculate_bare_substrate_RT(lam, n_sub), dtype=np.float64)
w = np.ones_like(lam)
inv = 1.0 / lam.size
for label, need_t, need_r in (("T only", True, False), ("R only", False, True)):
    mse = _njit_single_layer_mse_fused(lam, n_sub, w, inv, t_exp, r_exp, n_l, k_l, d, 1.0, 1.0, need_t, need_r, True, t_sub)
    print(f"ratio mode, {label}: MSE at the TRUE film = {mse:.3e}  (RMS {np.sqrt(mse):.3e})")
print(f"for scale: mean R/T_sub = {r_exp.mean():.4f}, mean T_sub = {t_sub.mean():.4f}")
