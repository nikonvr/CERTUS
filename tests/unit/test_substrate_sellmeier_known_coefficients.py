"""Synthetic Sellmeier regression (known coefficients)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

csi = pytest.importorskip("certus_substrate_index", reason="certus_substrate_index unavailable")
from certus_core import SELLMEIER_COEFFS_BY_ID


@pytest.mark.unit
@pytest.mark.parametrize("substrate_id", [0, 1, 3])  # SiO2, BK7, Sapphire
def test_fit_sellmeier_recovers_known_synthetic_curve(substrate_id: int) -> None:
    coeffs = np.asarray(SELLMEIER_COEFFS_BY_ID[int(substrate_id)], dtype=np.float64)
    wl_nm = np.linspace(400.0, 1600.0, 260, dtype=np.float64)
    wl_um = wl_nm / 1000.0

    n_ref = csi._sellmeier_3term_standard_eval(coeffs, wl_um)
    n_fit, meta = csi.IndexCore.fit_sellmeier(
        n_ref,
        wl_nm,
        float(wl_nm.min()),
        float(wl_nm.max()),
        model_kind="sellmeier3poles",
        return_meta=True,
        sellmeier_timeout_s=6.0,
        sellmeier_de_maxiter=120,
        sellmeier_ls_max_nfev=1200,
    )

    m = np.isfinite(n_fit) & np.isfinite(n_ref)
    rmse = float(np.sqrt(np.mean((n_fit[m] - n_ref[m]) ** 2)))

    assert str(meta.get("source", "")).startswith("analytic-sellmeier")
    # Numerical target kept realistic for CI stability across platforms.
    assert rmse < 2e-3
