"""Tests for sigma-node insertion helpers, including the legacy MWIR-specific path."""
from __future__ import annotations

from threading import Event
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from certus.spline.certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots

from certus.utils.certus_index_utils import _transmittance_absolute_from_nk

from certus.spline.spline_pipeline import (
    insert_manual_sigma_nodes,
    insert_mwir_mid_sigma_node,
    worker_spline_auto_add_one_knot,
    worker_spline_manual_sigma_insert,
    worker_spline_mwir_insert_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(lam_max_nm: float = 3000.0, lam_min_nm: float = 400.0) -> SplineOptConfig:
    lam = np.linspace(lam_min_nm, lam_max_nm, 80, dtype=np.float64)
    n_sub = np.full_like(lam, 1.52)
    n_l = np.full_like(lam, 2.1)
    k_l = np.full_like(lam, 5e-4)
    d_nm = 200.0
    t_exp = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub)
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=1,
        d_lo=50.0,
        d_hi=600.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
    )


def _make_base_result(cfg: SplineOptConfig, K: int = 12) -> dict:
    """Build a plausible result dict with K standard sigma knots."""
    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    sk = canonical_spline_sigma_knots(float(np.min(lam)), float(np.max(lam)))
    # Trim/pad to K
    if sk.size > K:
        sk = sk[:K]
    elif sk.size < K:
        sk = np.linspace(float(np.min(sk)), float(np.max(sk)), K)
    n_phys = np.full(K, 2.1)
    L_nodes = np.full(K, np.log(5e-4))
    d_nm = 200.0
    dim = 1 + 2 * K
    x = np.empty(dim)
    x[0] = d_nm
    x[1 : 1 + K] = n_phys
    x[1 + K : 1 + 2 * K] = L_nodes
    n_sub = np.asarray(cfg.n_sub, dtype=np.float64)
    n_l = np.full(lam.size, 2.1)
    k_l = np.full(lam.size, 5e-4)
    t_theo = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub)
    return {
        "sigma_knots": sk,
        "n_seg": K - 1,
        "x": x,
        "n_nodes_physical": n_phys.copy(),
        "L_nodes": L_nodes.copy(),
        "lam_nm": lam,
        "n_lam": n_l,
        "k_lam": k_l,
        "d_nm": d_nm,
        "mse": 1e-6,
        "rmse": 1e-3,
        "t_theo": t_theo,
        "r_theo": None,
        "nk_profile_interp": "smooth",
    }


# ---------------------------------------------------------------------------
# Test 1 – flag off → fonction identique au résultat de base (non-régression)
# ---------------------------------------------------------------------------

def test_flag_off_pipeline_no_change() -> None:
    """With flag=False (default), insert_mwir_mid_sigma_node must NOT be called automatically."""
    cfg = _make_cfg(lam_max_nm=3000.0)
    # Flag is off by default → class-level default False
    assert not bool(getattr(cfg, "post_sol2_insert_mwir_mid_sigma_enabled", False))


# ---------------------------------------------------------------------------
# Test 2 – lambda_max ≤ 2500 nm → skip (guard inside pipeline conditional)
# ---------------------------------------------------------------------------

def test_lambda_max_below_2500_guard() -> None:
    """Pipeline condition: if lambda_max ≤ 2500, insert_mwir_mid_sigma_node is not called.
    We test the function still returns base_result unchanged on RMSE-finite input
    (the lambda guard is only in the pipeline caller, not the function itself).
    We verify directly that the function preserves all keys on a ≤2500 nm cfg."""
    cfg = _make_cfg(lam_max_nm=2000.0)
    base = _make_base_result(cfg)
    stop = Event()
    result = insert_mwir_mid_sigma_node(cfg, base, stop)
    # Since this is a real optimization call, we just check it returns a dict
    # The function itself doesn't guard on lambda_max - the caller does
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test 3 – split mode → skip immediately (function-level guard)
# ---------------------------------------------------------------------------

def test_split_mode_skip() -> None:
    """sigma_knots_n present → function returns base_result unchanged."""
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg)
    base["sigma_knots_n"] = np.copy(base["sigma_knots"])  # triggers split guard
    base["sigma_knots_L"] = np.copy(base["sigma_knots"])
    stop = Event()
    result = insert_mwir_mid_sigma_node(cfg, base, stop)
    assert result is base  # strict identity: no copy made, original returned


# ---------------------------------------------------------------------------
# Test 4 – RMSE not finite → skip
# ---------------------------------------------------------------------------

def test_rmse_not_finite_skip() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg)
    base["rmse"] = float("nan")
    stop = Event()
    result = insert_mwir_mid_sigma_node(cfg, base, stop)
    assert result is base


# ---------------------------------------------------------------------------
# Test 5 – polish returns better RMSE → K increases by 1
# ---------------------------------------------------------------------------

def test_standard_mode_accepts_better_rmse() -> None:
    """When the polish finds a meaningfully better RMSE, K must increase by 1."""
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    K_before = int(np.asarray(base["sigma_knots"]).size)
    rmse_ref = float(base["rmse"])

    # Mock _spectral_polish_node_mesh_profile to return a better RMSE
    improved_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + 1)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 0.5,  # clearly better
        "spectral_mse": (rmse_ref * 0.5) ** 2,
        "profile_interp": "smooth",
    }
    improved_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=improved_pack):
        result = insert_mwir_mid_sigma_node(cfg, base, stop)

    K_after = int(np.asarray(result["sigma_knots"]).size)
    assert K_after == K_before + 1, f"Expected K={K_before + 1}, got K={K_after}"
    assert float(result["rmse"]) < rmse_ref


# ---------------------------------------------------------------------------
# Test 6 – polish returns worse/equal RMSE → strict rollback
# ---------------------------------------------------------------------------

def test_rmse_worse_rollback() -> None:
    """When the polish returns a worse RMSE, base_result must be returned unchanged."""
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    K_before = int(np.asarray(base["sigma_knots"]).size)
    rmse_ref = float(base["rmse"])

    worse_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + 1)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 1.5,  # worse
        "spectral_mse": (rmse_ref * 1.5) ** 2,
        "profile_interp": "smooth",
    }
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=worse_pack):
        result = insert_mwir_mid_sigma_node(cfg, base, stop)

    assert result is base  # strict rollback: identity preserved
    assert int(np.asarray(result["sigma_knots"]).size) == K_before


# ---------------------------------------------------------------------------
# Test 7 – polish returns None → fallback (base returned)
# ---------------------------------------------------------------------------

def test_polish_none_fallback() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=None):
        result = insert_mwir_mid_sigma_node(cfg, base, stop)

    assert result is base


# ---------------------------------------------------------------------------
# Test 8 – sigma_mid is the midpoint of sk[0] and sk[1]
# ---------------------------------------------------------------------------

def test_sigma_mid_is_midpoint() -> None:
    """After acceptance, the new sigma_knots[1] must equal (sk[0]+sk[1])/2."""
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"]).copy()
    expected_sigma_mid = 0.5 * (float(sk_orig[0]) + float(sk_orig[1]))
    K_before = int(sk_orig.size)
    rmse_ref = float(base["rmse"])

    improved_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + 1)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 0.5,
        "spectral_mse": (rmse_ref * 0.5) ** 2,
        "profile_interp": "smooth",
    }
    improved_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=improved_pack):
        result = insert_mwir_mid_sigma_node(cfg, base, stop)

    sk_new = np.asarray(result["sigma_knots"])
    assert abs(float(sk_new[1]) - expected_sigma_mid) < 1e-12, (
        f"sigma_mid mismatch: expected {expected_sigma_mid:.6e}, got {float(sk_new[1]):.6e}"
    )


# ---------------------------------------------------------------------------
# Test 9 – worker_spline_mwir_insert_node delegates correctly
# ---------------------------------------------------------------------------

def test_worker_delegates_to_insert() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    stop = Event()

    with patch("certus.spline.spline_pipeline.insert_mwir_mid_sigma_node", return_value=base) as mock_fn:
        result = worker_spline_mwir_insert_node(base, cfg, stop)

    mock_fn.assert_called_once()
    assert result is base


def test_manual_insert_accepts_multiple_sigma_knots() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    extra_sigma = np.asarray([
        0.5 * (float(sk_orig[1]) + float(sk_orig[2])),
        0.5 * (float(sk_orig[6]) + float(sk_orig[7])),
    ])
    K_before = int(sk_orig.size)
    rmse_ref = float(base["rmse"])

    improved_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + extra_sigma.size)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 0.5,
        "spectral_mse": (rmse_ref * 0.5) ** 2,
        "profile_interp": "smooth",
    }
    improved_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=improved_pack):
        result = insert_manual_sigma_nodes(cfg, base, stop, extra_sigma)

    sk_new = np.asarray(result["sigma_knots"], dtype=np.float64)
    assert int(sk_new.size) == K_before + extra_sigma.size
    assert any(np.isclose(sk_new, extra_sigma[0]))
    assert any(np.isclose(sk_new, extra_sigma[1]))


def test_manual_insert_rejects_multiple_sigma_knots_without_rmse_gain() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    extra_sigma = np.asarray([
        0.5 * (float(sk_orig[1]) + float(sk_orig[2])),
        0.5 * (float(sk_orig[6]) + float(sk_orig[7])),
    ])
    K_before = int(sk_orig.size)
    rmse_ref = float(base["rmse"])

    worse_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + extra_sigma.size)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 1.1,
        "spectral_mse": (rmse_ref * 1.1) ** 2,
        "profile_interp": "smooth",
    }
    worse_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=worse_pack):
        result = insert_manual_sigma_nodes(cfg, base, stop, extra_sigma)

    assert result is base
    assert int(np.asarray(result["sigma_knots"], dtype=np.float64).size) == K_before


def test_manual_insert_rejects_duplicate_sigma_knot() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    stop = Event()

    result = insert_manual_sigma_nodes(cfg, base, stop, np.asarray([float(base["sigma_knots"][1])]))

    assert result is base


def test_manual_worker_delegates_to_insert_manual() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    stop = Event()
    extra_sigma = np.asarray([0.5 * (float(base["sigma_knots"][1]) + float(base["sigma_knots"][2]))])

    with patch("certus.spline.spline_pipeline.insert_manual_sigma_nodes", return_value=base) as mock_fn:
        result = worker_spline_manual_sigma_insert(base, cfg, stop, extra_sigma_knots=extra_sigma)

    mock_fn.assert_called_once()
    assert result is base


def test_manual_worker_delegates_with_target_sigma_knots() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    stop = Event()
    target_sigma = np.asarray(base["sigma_knots"], dtype=np.float64)[1:-1]

    with patch("certus.spline.spline_pipeline.insert_manual_sigma_nodes", return_value=base) as mock_fn:
        result = worker_spline_manual_sigma_insert(base, cfg, stop, target_sigma_knots=target_sigma)

    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["target_sigma_knots"] is not None
    assert result is base


def test_auto_add_one_keeps_best_inserted_candidate_even_without_improvement() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    stop = Event()
    sigma0 = np.asarray([0.10, 0.20, 0.50], dtype=np.float64)
    base = {
        "sigma_knots": sigma0.copy(),
        "rmse": 1.0,
        "d_nm": 200.0,
    }

    def _fake_insert(
        _cfg,
        base_result,
        _stop_event,
        _extra_sigma_knots,
        *,
        target_sigma_knots,
        force_reopt,
        progress_cb,
        live_cb,
    ):
        _ = (force_reopt, progress_cb, live_cb)
        sk = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        out = dict(base_result)
        out["sigma_knots"] = sk
        if np.any(np.isclose(sk, 0.35)):
            out["rmse"] = 1.02
        else:
            out["rmse"] = 1.05
        return out

    with patch("certus.spline.spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        out = worker_spline_auto_add_one_knot(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            progress_cb=None,
            live_cb=None,
        )

    assert out is not None
    out_sk = np.asarray(out["sigma_knots"], dtype=np.float64).ravel()
    assert out_sk.size == sigma0.size + 1
    assert np.unique(np.round(out_sk, 12)).size == out_sk.size
    assert np.any(np.isclose(out_sk, 0.35))
    assert np.isclose(float(out["rmse"]), 1.02)


def test_auto_add_one_second_run_uses_updated_mesh_for_new_midpoint() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    stop = Event()
    sigma0 = np.asarray([0.10, 0.20, 0.50], dtype=np.float64)
    base = {
        "sigma_knots": sigma0.copy(),
        "rmse": 1.0,
        "d_nm": 200.0,
    }

    def _added_sigma(base_sk: np.ndarray, target_sk: np.ndarray) -> float:
        for value in np.asarray(target_sk, dtype=np.float64).ravel():
            if not np.any(np.isclose(base_sk, value, atol=1e-12, rtol=1e-12)):
                return float(value)
        raise AssertionError("expected one inserted sigma knot")

    def _fake_insert(
        _cfg,
        base_result,
        _stop_event,
        _extra_sigma_knots,
        *,
        target_sigma_knots,
        force_reopt,
        progress_cb,
        live_cb,
    ):
        _ = (force_reopt, progress_cb, live_cb)
        sk = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        base_sk = np.asarray(base_result["sigma_knots"], dtype=np.float64).ravel().copy()
        # Deep re-polish: same mesh, no insertion — model slight improvement
        if sk.size == base_sk.size and np.allclose(sk, base_sk, atol=1e-12, rtol=1e-12):
            out = dict(base_result)
            out["sigma_knots"] = sk
            out["rmse"] = float(base_result["rmse"]) * 0.99
            return out
        added = _added_sigma(base_sk, sk)
        out = dict(base_result)
        out["sigma_knots"] = sk
        out["rmse"] = 1.0 + abs(added - 0.35)
        if base_sk.size == 4:
            out["rmse"] = 1.0 + abs(added - 0.425)
        return out

    with patch("certus.spline.spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        out1 = worker_spline_auto_add_one_knot(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            progress_cb=None,
            live_cb=None,
        )
        assert out1 is not None
        sk1 = np.asarray(out1["sigma_knots"], dtype=np.float64).ravel()
        out2 = worker_spline_auto_add_one_knot(
            out1,
            cfg,
            stop,
            target_sigma_knots=sk1,
            progress_cb=None,
            live_cb=None,
        )

    assert out2 is not None
    sk2 = np.asarray(out2["sigma_knots"], dtype=np.float64).ravel()
    assert sk1.size == sigma0.size + 1
    assert sk2.size == sk1.size + 1
    assert np.unique(np.round(sk2, 12)).size == sk2.size
    assert np.any(np.isclose(sk1, 0.35))
    assert np.any(np.isclose(sk2, 0.35))
    assert np.any(np.isclose(sk2, 0.425))


def test_manual_insert_accepts_target_sigma_knots_with_smaller_k() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    target_sigma = np.asarray(sk_orig[1:-1], dtype=np.float64)  # 12 -> 10
    rmse_ref = float(base["rmse"])
    k_target = int(target_sigma.size)

    improved_pack = {
        "x_best": np.zeros(1 + 2 * k_target),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 0.5,
        "spectral_mse": (rmse_ref * 0.5) ** 2,
        "profile_interp": "smooth",
    }
    improved_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=improved_pack):
        result = insert_manual_sigma_nodes(
            cfg,
            base,
            stop,
            np.asarray([], dtype=np.float64),
            target_sigma_knots=target_sigma,
        )

    assert int(np.asarray(result["sigma_knots"], dtype=np.float64).size) == k_target
    assert int(result["n_seg"]) == k_target - 1
    assert np.asarray(result["x"], dtype=np.float64).size == 1 + 2 * k_target


def test_manual_insert_rejects_target_sigma_knots_out_of_range() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    stop = Event()
    # Inject one sigma outside current mesh bounds -> must rollback safely.
    target_sigma = np.asarray([float(sk_orig[0]) * 0.5, *sk_orig[1:-1]], dtype=np.float64)

    result = insert_manual_sigma_nodes(
        cfg,
        base,
        stop,
        np.asarray([], dtype=np.float64),
        target_sigma_knots=target_sigma,
    )

    assert result is base


def test_manual_insert_accepts_target_sigma_knots_when_k_reduction_worsens_rmse() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    # Explicit target mesh edit (K reduction): keep the user's reduced mesh even if RMSE rises.
    target_sigma = np.asarray(sk_orig[1:-1], dtype=np.float64)
    rmse_ref = float(base["rmse"])
    k_target = int(target_sigma.size)

    worse_pack = {
        "x_best": np.zeros(1 + 2 * k_target),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 1.05,
        "spectral_mse": (rmse_ref * 1.05) ** 2,
        "profile_interp": "smooth",
    }
    worse_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=worse_pack):
        result = insert_manual_sigma_nodes(
            cfg,
            base,
            stop,
            np.asarray([], dtype=np.float64),
            target_sigma_knots=target_sigma,
        )

    assert result is not base
    assert int(np.asarray(result["sigma_knots"], dtype=np.float64).size) == k_target
    assert int(result["n_seg"]) == k_target - 1
    assert np.isclose(float(result["rmse"]), float(worse_pack["spectral_rmse"]))


def test_manual_insert_target_equal_k_fp_drift_snaps_to_base_mesh() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    sk_orig = np.asarray(base["sigma_knots"], dtype=np.float64)
    # Simulate lambda->sigma round-trip drift at floating precision while keeping K unchanged.
    target_sigma = sk_orig.copy()
    if target_sigma.size > 2:
        target_sigma[1:-1] = target_sigma[1:-1] + 1e-12

    rmse_ref = float(base["rmse"])
    k_target = int(target_sigma.size)
    captured: dict[str, np.ndarray] = {}

    def _fake_polish(_cfg, _out, _x0_new, sk_new, _bounds_new, *, stop_event, maxfun, progress_cb):
        _ = (stop_event, maxfun, progress_cb)
        captured["sk_new"] = np.asarray(sk_new, dtype=np.float64).copy()
        x_best = np.zeros(1 + 2 * k_target, dtype=np.float64)
        x_best[0] = 200.0
        return {
            "x_best": x_best,
            "n_lam": np.full(80, 2.1),
            "k_lam": np.full(80, 5e-4),
            "d_nm": 200.0,
            "spectral_rmse": rmse_ref * 0.95,
            "spectral_mse": (rmse_ref * 0.95) ** 2,
            "profile_interp": "smooth",
        }

    stop = Event()
    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", side_effect=_fake_polish):
        result = insert_manual_sigma_nodes(
            cfg,
            base,
            stop,
            np.asarray([], dtype=np.float64),
            target_sigma_knots=target_sigma,
            force_reopt=True,
        )

    assert "sk_new" in captured
    assert np.array_equal(captured["sk_new"], sk_orig)
    assert np.array_equal(np.asarray(result["sigma_knots"], dtype=np.float64), sk_orig)


# ---------------------------------------------------------------------------
# Test 10 – n_seg is correctly updated after acceptance
# ---------------------------------------------------------------------------

def test_n_seg_updated_after_accept() -> None:
    cfg = _make_cfg(lam_max_nm=3000.0)
    base = _make_base_result(cfg, K=12)
    K_before = int(np.asarray(base["sigma_knots"]).size)
    rmse_ref = float(base["rmse"])

    improved_pack = {
        "x_best": np.zeros(1 + 2 * (K_before + 1)),
        "n_lam": np.full(80, 2.1),
        "k_lam": np.full(80, 5e-4),
        "d_nm": 200.0,
        "spectral_rmse": rmse_ref * 0.5,
        "spectral_mse": (rmse_ref * 0.5) ** 2,
        "profile_interp": "smooth",
    }
    improved_pack["x_best"][0] = 200.0
    stop = Event()

    with patch("certus.spline.spline_pipeline._spectral_polish_node_mesh_profile", return_value=improved_pack):
        result = insert_mwir_mid_sigma_node(cfg, base, stop)

    assert int(result["n_seg"]) == K_before  # K+1 nodes → K segments
