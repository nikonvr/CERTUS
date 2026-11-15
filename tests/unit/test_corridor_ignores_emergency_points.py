"""An emergency point of the RMSE(d) grid never decides the corridor (audit 2026-11-15, M-L3c).

When a thickness of the grid has no fit, ``_build_emergency_fit_record`` writes a last-resort record for it
(``point_status_code == 3``): the seed, not re-optimised, or an invented RMSE of 5 times the worst. These records stay
in the output, marked, but they took part in the minimum of the curve, in the promotion of the best refit to the final
result and in the n, k envelope of the corridor.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import numpy as np

from certus.spline import spline_pipeline_corridors_runner as runner
from certus.spline.certus_corridor_orchestrator_utils import _package_profile_grid_result
from certus.ui.certus_index_spline_corridor_gen import _CorridorGenMixin

K = 3
D = [90.0, 100.0, 110.0]
RMSE = [0.020, 0.030, 0.001]  # the lowest RMSE is the emergency point at 110 nm
STATUS = [0, 0, 3]
N_CURVES = [np.full(5, 2.0), np.full(5, 2.1), np.full(5, 5.0)]
K_CURVES = [np.full(5, 1e-3), np.full(5, 2e-3), np.full(5, 0.5)]


def _packaged() -> dict:
    return _package_profile_grid_result(
        d_list=list(D),
        r_list=list(RMSE),
        n_list=list(N_CURVES),
        k_list=list(K_CURVES),
        nit_list=[1.0, 1.0, 0.0],
        nfev_list=[5.0, 5.0, 0.0],
        point_kind_list=[0, 0, 0],
        point_status_code_list=list(STATUS),
        x_nodes_best_list=[np.full(2 * K, 1.0 + i) for i in range(3)],
        t0=0.0,
        d_arr=np.array(D),
        d0=100.0,
        i_center=1,
        nom_pack_present=False,
        n_branch_trigger=0,
        n_branch_extra_points=0,
        n_global_opt_runs=0,
        n_global_opt_improved=0,
        branch_events=[],
        global_opt_events=[],
        best_global_rmse=float("nan"),
        best_global_result=None,
        rmse_nominal_baseline_for_grid=0.030,
        rmse_abs_ref=0.030,
        sk=np.linspace(1.0, 3.0, K),
        cfg=SimpleNamespace(n_mono_band_nm=None),
        base_eff={},
        k=K,
        coverage_complete=True,
    )


def test_the_emergency_point_stays_in_the_output_marked() -> None:
    out = _packaged()
    np.testing.assert_array_equal(out["profile_d_values_nm"], D)
    np.testing.assert_array_equal(out["profile_d_manual_grid_point_status_code"], STATUS)
    assert out["profile_d_manual_grid_fallback_emergency_points"] == 1


def test_the_curve_minimum_is_a_fitted_point() -> None:
    minimum = _packaged()["profile_d_manual_grid_curve_minimum_result"]
    assert minimum is not None
    assert minimum["d_nm"] == 90.0
    assert minimum["rmse"] == 0.020


def test_the_promotion_to_the_final_result_skips_the_emergency_point(monkeypatch) -> None:
    # The seed resynchronisation that follows a promotion needs a full spline configuration: not the subject here.
    monkeypatch.setattr(runner, "_sync_promoted_corridor_seed_state", lambda *_a, **_k: None)
    out = {"d_nm": 100.0, "rmse": 0.030}
    extra = {
        "profile_d_status": "manual_grid",
        "profile_d_values_nm": np.array(D),
        "profile_d_rmse_values": np.array(RMSE),
        "profile_d_n_curves": np.vstack(N_CURVES),
        "profile_d_k_curves": np.vstack(K_CURVES),
        "profile_d_manual_grid_point_status_code": np.array(STATUS, dtype=np.int32),
    }
    runner._maybe_promote_best_corridor_refit(SimpleNamespace(), out, extra, logging.getLogger("test"))
    assert out["d_nm"] == 90.0
    assert out["rmse"] == 0.020
    np.testing.assert_array_equal(out["n_lam"], N_CURVES[0])


def test_the_corridor_envelope_leaves_the_emergency_curves_out() -> None:
    source = {
        "profile_d_values_nm": np.array(D),
        "profile_d_n_curves": np.vstack(N_CURVES),
        "profile_d_k_curves": np.vstack(K_CURVES),
        "profile_d_manual_grid_point_status_code": np.array(STATUS, dtype=np.int32),
    }
    host = SimpleNamespace(logger=None)
    payload = _CorridorGenMixin._build_manual_corridor_payload(host, source, {}, 85.0, 115.0)
    assert payload is not None
    assert payload["manual_corridor_selected_count"] == 2
    assert float(np.max(payload["corridor_n_hi"])) == 2.1
    assert float(np.max(payload["corridor_k_hi"])) < 0.1
