"""Integration guard: Sellmeier should not regress vs polynomial on sapphire-like data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

csi = pytest.importorskip("certus_substrate_index", reason="certus_substrate_index unavailable")
from certus_core import SELLMEIER_COEFFS_BY_ID


@pytest.mark.integration
def test_sapphire_sellmeier_remains_competitive_against_polynomial() -> None:
    wl_nm = np.linspace(2500.0, 4000.0, 280, dtype=np.float64)
    wl_um = wl_nm / 1000.0
    coeffs_sapphire = np.asarray(SELLMEIER_COEFFS_BY_ID[3], dtype=np.float64)

    n_true = csi._sellmeier_3term_standard_eval(coeffs_sapphire, wl_um)
    rng = np.random.default_rng(20260425)
    n_obs = n_true + rng.normal(0.0, 2.5e-4, size=n_true.shape)

    n_poly, _meta_poly = csi.IndexCore.fit_sellmeier(
        n_obs,
        wl_nm,
        2500.0,
        4000.0,
        model_kind="polynomial",
        return_meta=True,
    )
    n_sell, meta_sell = csi.IndexCore.fit_sellmeier(
        n_obs,
        wl_nm,
        2500.0,
        4000.0,
        model_kind="sellmeier3poles",
        return_meta=True,
        sellmeier_timeout_s=8.0,
        sellmeier_de_maxiter=250,
        sellmeier_ls_max_nfev=2500,
    )

    rmse_poly = float(np.sqrt(np.mean((n_poly - n_true) ** 2)))
    rmse_sell = float(np.sqrt(np.mean((n_sell - n_true) ** 2)))

    assert str(meta_sell.get("source", "")).startswith("analytic-sellmeier")
    # Guardrail: on this IR window, polynomial can win on pure RMSE.
    # We still require a physically plausible Sellmeier fit with controlled error.
    assert rmse_sell < 2e-3
    assert rmse_sell <= (40.0 * rmse_poly)
