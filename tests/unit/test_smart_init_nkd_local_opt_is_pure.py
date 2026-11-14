"""Chantier 21 (a): the Smart Init 3-knot n/k/d polish left the UI thread code unchanged in bits.

``_legacy_nkd_local_opt`` is a verbatim copy of the body that lived in
``certus/ui/certus_index_spline_smart_init.py::SmartInitPreviewManager.run_nkd_local_opt``
(x0, bounds, parameter order, loss, L-BFGS-B options). The pure function in ``certus.spline`` must
return the same ``res.x``, ``res.fun`` and ``res.nfev`` to the bit.
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.optimize as opt

from certus.spline.certus_index_spline_core import (
    SPLINE_PWL_N_SEG,
    DataType,
    SplineOptConfig,
    rmse_at_spline_stage_x0_init,
)
from certus.spline.spline_smart_init import optimize_smart_init_nkd_packet

L_LO, L_HI = -12.0, 0.5


def _cfg() -> SplineOptConfig:
    lam = np.linspace(400.0, 800.0, 40)
    t_exp = 0.80 + 0.06 * np.cos(2.0 * np.pi * 1.0e4 / lam)
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=np.full_like(lam, 1.52),
        data_type=DataType.TRANSMISSION,
        n_seg=SPLINE_PWL_N_SEG,
        d_lo=500.0,
        d_hi=4000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
    )


def _legacy_nkd_local_opt(cfg, sk, n_phys, L_nodes, d_nm, idx, k_n, L_lo_g, L_hi_g, relax):
    if idx == 0:
        idx_list = [0, 1, 2]
    elif idx == k_n - 1:
        idx_list = [k_n - 3, k_n - 2, k_n - 1]
    else:
        idx_list = [idx - 1, idx, idx + 1]
    idx_list = [i for i in idx_list if 0 <= i < k_n]

    init_ne = np.asarray(n_phys, dtype=np.float64).ravel().copy()
    init_Le = np.asarray(L_nodes, dtype=np.float64).ravel().copy()
    cur_sk = np.asarray(sk, dtype=np.float64).ravel()

    n_len = len(idx_list)
    x0 = np.zeros(1 + 2 * n_len)
    x0[0] = d_nm
    for pos, i_node in enumerate(idx_list):
        x0[1 + pos] = init_ne[i_node]
        x0[1 + n_len + pos] = init_Le[i_node]

    bounds = [(float(cfg.d_lo), float(cfg.d_hi))]
    bounds.extend((1.0, 3.3) for _ in idx_list)
    bounds.extend((L_lo_g, L_hi_g) for _ in idx_list)

    def loss(x):
        cur_d = x[0]
        cur_ne = init_ne.copy()
        cur_Le = init_Le.copy()
        for pos, i_node in enumerate(idx_list):
            cur_ne[i_node] = x[1 + pos]
            cur_Le[i_node] = x[1 + n_len + pos]
        _, rmse = rmse_at_spline_stage_x0_init(cfg, cur_sk, cur_ne, cur_Le, cur_d, relax_n_mono=relax)
        return float(rmse)

    res = opt.minimize(loss, x0, method="L-BFGS-B", bounds=bounds, options={"maxfun": 150})
    return res, idx_list


@pytest.mark.parametrize("idx", [0, 2, 4])
def test_pure_nkd_packet_matches_legacy_ui_body_to_the_bit(idx: int) -> None:
    cfg = _cfg()
    k = 5
    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)
    ne = np.array([1.62, 1.64, 1.66, 1.69, 1.73], dtype=np.float64)
    Le = np.array([-7.0, -6.5, -6.0, -5.5, -5.0], dtype=np.float64)
    d_nm = 1234.5

    old, old_idx = _legacy_nkd_local_opt(cfg, sk, ne, Le, d_nm, idx, k, L_LO, L_HI, False)
    new = optimize_smart_init_nkd_packet(
        cfg, sk, ne, Le, d_nm, idx, k_n=k, L_lo=L_LO, L_hi=L_HI, relax_n_mono=False
    )

    assert new.idx_list == old_idx
    assert new.result.x.tobytes() == old.x.tobytes()
    assert float(new.result.fun) == float(old.fun)
    assert new.result.nfev == old.nfev
    assert old.nfev > 1 + 2 * len(old_idx)  # the optimizer moved, the comparison is not trivial
