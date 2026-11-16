"""Audit L3-m3: does the RMSE(d) corridor start from the n, k the window displays?

Runs the SPLINE pipeline on the example of `bench_examples.py index_spline`, then rebuilds n(lambda), k(lambda) from
what `_extract_knots_and_nodes_from_result` hands the corridor, and compares them with `n_lam`, `k_lam` of the result.
    python reports/audit_code_2026-11-15/preuves/p_corridor_depart.py
"""

import os
import sys
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import bench_examples as B  # noqa: E402
import numpy as np  # noqa: E402

B.qapp()
import certus_physics  # noqa: E402
from certus.spline.certus_corridor_utils import _extract_knots_and_nodes_from_result  # noqa: E402
from certus.spline.spline_objective import nk_from_x_pwlnk, physical_nodes_to_x_slice_n  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

certus_physics.warmup_physics()
app = CertusIndexSplineApp()
app._on_load(path=str(ROOT / "example" / "example_index_spline" / "TSIO2-1700-1.xlsx"))
cfg = app._build_opt_config(notify=False)
res = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a: None)
sk_n = np.asarray(res.get("sigma_knots_n", []), dtype=float)
sk_L = np.asarray(res.get("sigma_knots_L", res.get("sigma_knots", [])), dtype=float)
print("x_encoding:", res.get("x_encoding"), "| K_n:", sk_n.size, "| K_L:", sk_L.size,
      "| max |sigma_n - sigma_L|:", float(np.max(np.abs(sk_n - sk_L))) if sk_n.size == sk_L.size and sk_n.size else "sizes differ")
sk, n_nodes, L_nodes, d_nm, _meta = _extract_knots_and_nodes_from_result(res)
lam = np.asarray(res.get("lam_nm", res.get("lam_full", cfg.lam_exp)), dtype=float)
n_disp = np.asarray(res["n_lam"], dtype=float)
k_disp = np.asarray(res["k_lam"], dtype=float)
if lam.size != n_disp.size:
    lam = np.asarray(cfg.lam_exp, dtype=float)
xi = physical_nodes_to_x_slice_n(n_nodes, sk, cfg.n_mono_band_nm)
n_c, k_c = nk_from_x_pwlnk(np.concatenate(([d_nm], xi, L_nodes)), lam, sk, cfg.k_clip_lo, cfg.k_clip_hi,
                          sig_pre=None, n_mono_band_nm=cfg.n_mono_band_nm, profile_interp=str(cfg.nk_profile_interp))
print("RMSE of the result:", res.get("rmse"), "| d:", d_nm)
print("corridor start vs displayed: max |dn| =", float(np.max(np.abs(n_c - n_disp))),
      "| max |dk| =", float(np.max(np.abs(k_c - k_disp))), "| max |dk|/k =",
      float(np.max(np.abs(k_c - k_disp) / np.maximum(np.abs(k_disp), 1e-12))))
