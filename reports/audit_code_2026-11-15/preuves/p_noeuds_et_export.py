"""Audit M-L3a (sigma knots decoded in order?) and M-L5c (`if ep:` on a NumPy array), by direct calls.

    python reports/audit_code_2026-11-15/preuves/p_noeuds_et_export.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from certus.spline.spline_objective import sigma_knots_decode  # noqa: E402

print("M-L3a: sigma_knots_decode on raw log-proportions whose last two intervals are tiny")
s_lo, s_hi = 1.0, 3.0
for tail in (-2.0, -8.0, -20.0):
    raw = np.array([0.0, 0.0, 0.0, 0.0, tail, tail])
    for eps in (None, 1e-3, 1e-2):
        sk = np.array(sigma_knots_decode(raw, s_lo, s_hi, eps))
        print(f"  tail {tail:6.1f} eps_s {eps!s:6}: knots {np.round(sk, 6)} strictly increasing: {bool(np.all(np.diff(sk) > 0))}")
print("M-L5c: the guard of ExportManager.export_excel, `if ep:`, on what a stopped run leaves in ep_current")
for ep in ([], [12.5, 80.1], np.array([12.5, 80.1])):
    try:
        print(f"  ep = {ep!r:28} -> bool(ep) = {bool(ep)}")
    except ValueError as exc:
        print(f"  ep = {ep!r:28} -> ValueError: {exc}")
