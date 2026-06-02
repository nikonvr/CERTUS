from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from CERTUS_INDEX_SPLINE import CertusIndexSplineApp


def test_prepare_data_th_tab_series_builds_expected_columns_on_piecewise_grid() -> None:
    # Use a lambda span crossing the 400 nm and 1200 nm grid transitions.
    lam_nm = np.array([350.0, 500.0, 900.0, 1300.0], dtype=np.float64)
    n_lam = np.array([1.55, 1.60, 1.68, 1.72], dtype=np.float64)
    k_lam = np.array([1.0e-4, 2.0e-4, 8.0e-4, 1.5e-3], dtype=np.float64)
    t_theo = np.array([0.75, 0.72, 0.66, 0.61], dtype=np.float64)
    r_theo = np.array([0.10, 0.11, 0.14, 0.16], dtype=np.float64)

    result = {
        "lam_nm": lam_nm,
        "n_lam": n_lam,
        "k_lam": k_lam,
        "t_theo": t_theo,
        "r_theo": r_theo,
        "d_nm": 212.5,
        "substrate_name": "Sapphire (Al2O3)",
    }

    stub = SimpleNamespace(
        df=None,
        logger=None,
        _lam_piecewise_report_grid_nm=CertusIndexSplineApp._lam_piecewise_report_grid_nm,
    )

    out = CertusIndexSplineApp._prepare_data_th_tab_series(stub, result)

    assert out is not None
    lam_g, n_g, k_g, d_g, ns_g, t_g, r_g = out

    expected_grid = CertusIndexSplineApp._lam_piecewise_report_grid_nm(350.0, 1300.0)
    assert np.allclose(lam_g, expected_grid)

    assert lam_g.shape == n_g.shape == k_g.shape == d_g.shape == ns_g.shape == t_g.shape == r_g.shape
    assert np.all(np.isfinite(n_g))
    assert np.all(np.isfinite(k_g))
    assert np.all(np.isfinite(t_g))
    assert np.all(np.isfinite(r_g))
    assert np.allclose(d_g, 212.5)

    # ns should be computed for all points when substrate lookup succeeds.
    assert np.all(np.isfinite(ns_g))

    # Spot-check interpolation at anchors.
    idx_500 = int(np.where(np.isclose(lam_g, 500.0))[0][0])
    idx_900 = int(np.where(np.isclose(lam_g, 900.0))[0][0])
    assert np.isclose(n_g[idx_500], 1.60)
    assert np.isclose(n_g[idx_900], 1.68)
    assert np.isclose(t_g[idx_500], 0.72)
    assert np.isclose(r_g[idx_900], 0.14)


def test_prepare_data_th_tab_series_prefers_effective_substrate_index_from_result() -> None:
    lam_nm = np.array([350.0, 500.0, 900.0, 1300.0], dtype=np.float64)
    n_sub_effective = np.array([1.91, 1.92, 1.94, 1.97], dtype=np.float64)
    result = {
        "lam_nm": lam_nm,
        "n_lam": np.array([1.55, 1.60, 1.68, 1.72], dtype=np.float64),
        "k_lam": np.array([1.0e-4, 2.0e-4, 8.0e-4, 1.5e-3], dtype=np.float64),
        "t_theo": np.array([0.75, 0.72, 0.66, 0.61], dtype=np.float64),
        "r_theo": np.array([0.10, 0.11, 0.14, 0.16], dtype=np.float64),
        "d_nm": 212.5,
        "substrate_name": "Sapphire (Al2O3)",
        "n_sub_effective": n_sub_effective,
    }

    stub = SimpleNamespace(
        df=None,
        logger=None,
        _lam_piecewise_report_grid_nm=CertusIndexSplineApp._lam_piecewise_report_grid_nm,
    )

    out = CertusIndexSplineApp._prepare_data_th_tab_series(stub, result)

    assert out is not None
    lam_g, _, _, _, ns_g, _, _ = out
    idx_500 = int(np.where(np.isclose(lam_g, 500.0))[0][0])
    idx_900 = int(np.where(np.isclose(lam_g, 900.0))[0][0])

    assert np.isclose(ns_g[idx_500], 1.92)
    assert np.isclose(ns_g[idx_900], 1.94)
