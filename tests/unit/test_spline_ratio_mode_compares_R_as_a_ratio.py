"""In ratio mode the SPLINE fused kernel must compare R as a ratio, like T (audit 2026-11-15, C-L3).

The file holds R_film / T_sub_bare (``prepare_exp_TR_for_fit``); the kernel used to divide T by T_sub but compare the
measured R ratio to the ABSOLUTE theoretical R, so the exact film kept an R cost of ~3e-4 (1.8 points RMS) and an R or
R+T fit converged elsewhere. At the exact film both costs must vanish.
"""

import numpy as np

from certus.spline.spline_objective import _njit_single_layer_mse_fused, calculate_bare_substrate_RT
from certus.utils.certus_index_utils import _ratio_theoretical_from_nk, _reflectance_ratio_theoretical_from_nk


def _exact_film_cost(need_t: bool, need_r: bool) -> float:
    lam = np.linspace(400.0, 1000.0, 301)
    n_l = np.full_like(lam, 2.10)
    k_l = np.full_like(lam, 1e-3)
    n_sub = np.full_like(lam, 1.52)
    d = 300.0
    t_exp = np.asarray(_ratio_theoretical_from_nk(lam, n_l, k_l, d, n_sub), dtype=np.float64)
    r_exp = np.asarray(_reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d, n_sub), dtype=np.float64)
    t_sub = np.asarray(calculate_bare_substrate_RT(lam, n_sub), dtype=np.float64)
    w = np.ones_like(lam)
    return _njit_single_layer_mse_fused(
        lam, n_sub, w, 1.0 / lam.size, t_exp, r_exp, n_l, k_l, d, 1.0, 1.0, need_t, need_r, True, t_sub
    )


def test_the_exact_film_has_no_R_cost_in_ratio_mode() -> None:
    assert _exact_film_cost(need_t=False, need_r=True) < 1e-20


def test_the_exact_film_has_no_T_cost_in_ratio_mode() -> None:
    assert _exact_film_cost(need_t=True, need_r=False) < 1e-20
