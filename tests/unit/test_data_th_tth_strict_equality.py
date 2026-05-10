from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import numpy.testing as npt

from CERTUS_INDEX_SPLINE import CertusIndexSplineApp


def test_data_th_tth_strict_equality_on_grid_points() -> None:
    # Pick lambda values exactly on the reporting grid steps: 2 nm (<=400), 5 nm (400-1200), 10 nm (>1200).
    lam_nm = np.array([350.0, 352.0, 400.0, 405.0, 900.0, 1210.0], dtype=np.float64)

    t_theo = np.array([0.770000, 0.769000, 0.750000, 0.748000, 0.660000, 0.615000], dtype=np.float64)
    result = {
        "lam_nm": lam_nm,
        "n_lam": np.array([1.6000, 1.6100, 1.6200, 1.6300, 1.6800, 1.7100], dtype=np.float64),
        "k_lam": np.array([1.0e-4, 1.1e-4, 1.3e-4, 1.4e-4, 8.0e-4, 9.0e-4], dtype=np.float64),
        "t_theo": t_theo,
        "r_theo": np.array([0.0900, 0.0910, 0.1000, 0.1010, 0.1400, 0.1750], dtype=np.float64),
        "d_nm": 212.5,
        "substrate_name": "Sapphire (Al2O3)",
    }

    stub = SimpleNamespace(df=None, logger=None)
    stub._lam_piecewise_report_grid_nm = CertusIndexSplineApp._lam_piecewise_report_grid_nm

    out = CertusIndexSplineApp._prepare_data_th_tab_series(stub, result)
    assert out is not None

    lam_g, _n_g, _k_g, _d_g, _ns_g, t_g, _r_g = out

    # Exact index mapping on the same grid points.
    idx = [int(np.where(np.isclose(lam_g, x))[0][0]) for x in lam_nm]

    # Strict equality: Tth extracted from Data TH must be bitwise-equal to source t_theo on exact grid anchors.
    npt.assert_array_equal(t_g[idx], t_theo)

    # Same strict check for the quantity used in spectral ratio export: ratio_theo_pct = t_theo * 100.
    ratio_source = t_theo * 100.0
    npt.assert_array_equal(t_g[idx] * 100.0, ratio_source)
