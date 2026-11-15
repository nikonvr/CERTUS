"""Audit M-L5a: is the substrate k aligned with the fitted wavelengths when lambda_min is raised?

`certus_index_ui_worker` builds `k_sub` on the FULL file grid; `certus_index_workers_opt_strat` masks `wls` to
[lambda_min, lambda_max] but passes `c.k_sub_data` whole to `TLUObjective`, whose forward model
(`calculate_RT_single_layer_absorbing_substrate_array`, objective l. 1843) and gradient kernel read `k_sub[i]` with the
MASKED index i. This calls that real forward function both ways on the same film.
    python reports/audit_code_2026-11-15/preuves/p_ksub_desaligne.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from certus.physics.certus_tmm_single_layer import calculate_RT_single_layer_absorbing_substrate_array  # noqa: E402

l_full = np.arange(250.0, 1001.0, 1.0)                  # file grid, 1 nm step
k_sub_full = 1e-3 * np.exp(-(l_full - 250.0) / 80.0)    # absorbing substrate, k falls with lambda
n_sub_full = np.full_like(l_full, 1.76)
D_sub = 0.5e6                                           # 0.5 mm
lambda_min = 400.0
mask = l_full >= lambda_min
wls = l_full[mask]
n = np.full_like(wls, 2.0)
k = np.zeros_like(wls)
d = 300.0

R_ok, T_ok = calculate_RT_single_layer_absorbing_substrate_array(wls, n, k, d, n_sub_full[mask], k_sub_full[mask], D_sub)
R_w, T_w = calculate_RT_single_layer_absorbing_substrate_array(wls, n, k, d, n_sub_full[mask], k_sub_full, D_sub)

print(f"file grid {l_full[0]:.0f}-{l_full[-1]:.0f} nm ({l_full.size} pts), lambda_min raised to {lambda_min:.0f} nm "
      f"-> {wls.size} fitted pts; k_sub passed: {k_sub_full.size} pts (worker) vs {wls.size} (aligned)")
for lam in (400.0, 500.0, 600.0, 800.0):
    i = int(np.argmin(np.abs(wls - lam)))
    print(f"  lambda={lam:4.0f} nm : k_sub read {k_sub_full[i]:.2e} (that of {l_full[i]:.0f} nm) instead of "
          f"{k_sub_full[mask][i]:.2e} | T {T_w[i]:.4f} instead of {T_ok[i]:.4f}")
print(f"max |dT| = {np.max(np.abs(T_w - T_ok)):.4f}, max |dR| = {np.max(np.abs(R_w - R_ok)):.4f}")
