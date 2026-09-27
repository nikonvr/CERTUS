"""The corridor result publishes the keys that the interface and the report read (D34).

`_package_corridor_results` was rewritten when the corridor code was split, and the rewrite
dropped outputs that the old version -- left behind, 433 lines, never called -- still produced.
Two of them have readers in the product: the corridors tooltip reads
`profile_d_seed_gate_kept_rate` (its "Seed gate: N % ..." sentence never appeared), and the
spline report reads `profile_d_rmse_opt` (always blank). Both are computed here exactly as the
old version did; no existing value changes.
"""

from __future__ import annotations

import numpy as np


def _ctx(**over):
    from certus.spline.spline_profile_corridors import CorridorProfileContext

    fields = dict(
        _use_hetero=False, _user_mask=None, adaptive_abs_meta={}, auto_relaxed_alpha=False,
        base_result={"n_lam": np.array([1.0, 1.1]), "k_lam": np.array([0.1, 0.1])},
        boundary_refine_calls=0, center_seed_kept=True,
        cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
        chi2_vals=[1.0, 2.0], d0=5.0, d_vals=[4.9, 5.1], delta_chi2=1.0,
        fit_fail_values=[], fit_nfev_values=[], fit_nit_values=[], fit_try_values=[],
        k_curves=[np.array([0.12, 0.08]), np.array([0.11, 0.09])], log_coaching=False,
        maxfun_prof=10, min_side=1,
        n_curves=[np.array([1.09, 1.07]), np.array([1.10, 1.08])], nom_pack=None,
        pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola",
                                 "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0,
                                 "mode": "alpha"})(),
        rmse_opt=0.1, rmse_ref_tag="best_polished", rmse_thr_sub="alpha", rmse_thresh=0.2,
        rmse_thresh_active=0.2, rmse_vals=[0.2, 0.21], scientific_nominal=False,
        seed_gate_auto_escalated_global=False, seed_gate_deltas=np.array([], dtype=np.float64),
        seed_gate_eval_count=4, seed_gate_kept_count=3, seed_gate_saturated_global=False,
        sig_r=0.0, sig_t=0.0, sigma_r_f_hetero=None, sigma_t_f_hetero=None, t0=0.0,
        threshold_basis_eff="alpha", threshold_fallback_reason="", tol_abs=0.0, tol_abs_effective=0.0,
        use_abs_delta=False, use_adaptive_abs_delta=False, use_lr=False,
        sk=np.array([1.0]), x_nodes_center=np.array([1.0]), x0_default=np.array([1.0]),
        bounds_nodes=np.array([[0.0, 2.0]]), chi2_min=float("nan"), x_curves=None,
        corridor_ref_n_lam=np.array([1.0, 1.0]), corridor_ref_k_lam=np.array([0.1, 0.1]),
        _push_live_point_from_payload=None, live_streamer=None,
        center_seed_gate_eval_count=0, center_seed_gate_kept_count=0,
        center_seed_gate_delta_refit_minus_seed=float("nan"),
    )
    fields.update(over)
    return CorridorProfileContext(**fields)


def test_the_seed_gate_rate_that_the_tooltip_reads_is_published() -> None:
    from certus.spline.spline_profile_corridors import _package_corridor_results

    out = _package_corridor_results(_ctx())
    assert out["profile_d_seed_gate_kept_rate"] == 0.75


def test_no_evaluation_gives_a_nan_rate_not_a_division_error() -> None:
    from certus.spline.spline_profile_corridors import _package_corridor_results

    out = _package_corridor_results(_ctx(seed_gate_eval_count=0, seed_gate_kept_count=0))
    assert np.isnan(out["profile_d_seed_gate_kept_rate"])


def test_the_best_rmse_that_the_report_reads_is_published() -> None:
    from certus.spline.spline_profile_corridors import _package_corridor_results

    out = _package_corridor_results(_ctx())
    assert out["profile_d_rmse_opt"] == 0.1


def test_the_old_copy_is_gone() -> None:
    """One packaging function, so that the two cannot drift apart again."""
    import certus.spline.certus_corridor_orchestrator_utils as utils

    assert not hasattr(utils, "_package_corridor_results")
