from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any
from unittest.mock import patch

import numpy as np

from spline_pipeline import worker_spline_auto_clean_knots


@dataclass
class _CfgStub:
    auto_clean_neighbor_pull_enabled: bool = True
    auto_clean_neighbor_pull_ratios: tuple[float, ...] = (0.20,)
    manual_node_insert_polish_maxfun: int | None = None

    def replace(self, **changes: Any) -> "_CfgStub":
        data = {
            "auto_clean_neighbor_pull_enabled": self.auto_clean_neighbor_pull_enabled,
            "auto_clean_neighbor_pull_ratios": self.auto_clean_neighbor_pull_ratios,
            "manual_node_insert_polish_maxfun": self.manual_node_insert_polish_maxfun,
        }
        data.update(changes)
        return _CfgStub(**data)


def _make_base_result(sigma_knots: np.ndarray, rmse: float = 1.0) -> dict[str, Any]:
    return {
        "sigma_knots": np.asarray(sigma_knots, dtype=np.float64).ravel().copy(),
        "rmse": float(rmse),
        "d_nm": 17050.0,
    }


def test_auto_clean_prefers_neighbor_pull_variant_when_better() -> None:
    sigma0 = np.asarray([0.10, 0.20, 0.30, 0.40, 0.50], dtype=np.float64)
    base = _make_base_result(sigma0, rmse=1.0)
    cfg = _CfgStub(auto_clean_neighbor_pull_enabled=True, auto_clean_neighbor_pull_ratios=(0.20,))
    stop = Event()

    pulled = np.asarray([0.10, 0.22, 0.38, 0.50], dtype=np.float64)
    calls: list[np.ndarray] = []

    rmse_map = {
        tuple(np.round(sigma0, 6)): 1.0,  # nominal
        tuple(np.round(np.asarray([0.10, 0.30, 0.40, 0.50]), 6)): 1.05,
        tuple(np.round(np.asarray([0.10, 0.20, 0.40, 0.50]), 6)): 0.96,
        tuple(np.round(np.asarray([0.10, 0.20, 0.30, 0.50]), 6)): 1.03,
        tuple(np.round(pulled, 6)): 0.90,
    }

    def _fake_insert(
        _cfg: Any,
        base_result: dict[str, Any],
        _stop_event: Event,
        _extra_sigma_knots: np.ndarray,
        *,
        target_sigma_knots: np.ndarray,
        force_reopt: bool,
        live_cb: Any,
    ) -> dict[str, Any]:
        _ = (force_reopt, live_cb)
        sk = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        calls.append(sk.copy())
        key = tuple(np.round(sk, 6))
        rmse = float(rmse_map.get(key, 9.0))
        out = dict(base_result)
        out["sigma_knots"] = sk
        out["rmse"] = rmse
        return out

    with patch("spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        out = worker_spline_auto_clean_knots(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            tolerance=0.20,
            progress_cb=None,
            live_cb=None,
        )

    assert out is not None
    out_sk = np.asarray(out["sigma_knots"], dtype=np.float64).ravel()
    assert np.allclose(out_sk, pulled)
    assert np.isclose(float(out["rmse"]), 0.90) or np.isclose(float(out["rmse"]), 0.91)

    # Guardrail: auto-clean never moves the two extreme knots.
    assert calls
    assert all(np.isclose(float(sk[0]), 0.10) and np.isclose(float(sk[-1]), 0.50) for sk in calls)



def test_auto_clean_without_neighbor_pull_only_tests_baseline_removals() -> None:
    sigma0 = np.asarray([0.10, 0.20, 0.30, 0.40, 0.50], dtype=np.float64)
    base = _make_base_result(sigma0, rmse=1.0)
    cfg = _CfgStub(auto_clean_neighbor_pull_enabled=False, auto_clean_neighbor_pull_ratios=(0.20,))
    stop = Event()

    calls: list[np.ndarray] = []

    rmse_map = {
        tuple(np.round(sigma0, 6)): 1.0,
        tuple(np.round(np.asarray([0.10, 0.30, 0.40, 0.50]), 6)): 1.05,
        tuple(np.round(np.asarray([0.10, 0.20, 0.40, 0.50]), 6)): 0.96,
        tuple(np.round(np.asarray([0.10, 0.20, 0.30, 0.50]), 6)): 1.03,
    }

    def _fake_insert(
        _cfg: Any,
        base_result: dict[str, Any],
        _stop_event: Event,
        _extra_sigma_knots: np.ndarray,
        *,
        target_sigma_knots: np.ndarray,
        force_reopt: bool,
        live_cb: Any,
    ) -> dict[str, Any]:
        _ = (force_reopt, live_cb)
        sk = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        calls.append(sk.copy())
        key = tuple(np.round(sk, 6))
        rmse = float(rmse_map.get(key, 9.0))
        out = dict(base_result)
        out["sigma_knots"] = sk
        out["rmse"] = rmse
        return out

    with patch("spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        out = worker_spline_auto_clean_knots(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            tolerance=0.20,
            progress_cb=None,
            live_cb=None,
        )

    assert out is not None
    out_sk = np.asarray(out["sigma_knots"], dtype=np.float64).ravel()
    assert np.allclose(out_sk, np.asarray([0.10, 0.20, 0.40, 0.50], dtype=np.float64))

    # No neighbor-pull value (0.22 / 0.38) should appear when disabled.
    flat = np.concatenate([np.asarray(sk, dtype=np.float64).ravel() for sk in calls])
    assert not np.any(np.isclose(flat, 0.22))
    assert not np.any(np.isclose(flat, 0.38))


def test_auto_clean_rejects_candidate_when_returned_mesh_is_inconsistent() -> None:
    sigma0 = np.asarray([0.10, 0.20, 0.30, 0.40, 0.50], dtype=np.float64)
    base = _make_base_result(sigma0, rmse=1.0)
    cfg = _CfgStub(auto_clean_neighbor_pull_enabled=False, auto_clean_neighbor_pull_ratios=(0.20,))
    stop = Event()

    bad_target = np.asarray([0.10, 0.20, 0.40, 0.50], dtype=np.float64)

    def _fake_insert(
        _cfg: Any,
        base_result: dict[str, Any],
        _stop_event: Event,
        _extra_sigma_knots: np.ndarray,
        *,
        target_sigma_knots: np.ndarray,
        force_reopt: bool,
        live_cb: Any,
    ) -> dict[str, Any]:
        _ = (force_reopt, live_cb)
        sk_target = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        out = dict(base_result)
        # Simulate 05b fallback/rollback behavior: returns seed mesh unchanged
        # even when the requested target mesh differs.
        out["sigma_knots"] = np.asarray(base_result["sigma_knots"], dtype=np.float64).ravel().copy()
        if sk_target.size == bad_target.size and np.allclose(sk_target, bad_target):
            out["rmse"] = 0.90
        else:
            out["rmse"] = 1.0
        return out

    with patch("spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        out = worker_spline_auto_clean_knots(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            tolerance=0.20,
            progress_cb=None,
            live_cb=None,
        )

    assert out is not None
    out_sk = np.asarray(out["sigma_knots"], dtype=np.float64).ravel()
    assert np.allclose(out_sk, sigma0)
    assert np.isclose(float(out["rmse"]), 1.0)


def test_auto_clean_cancel_emits_canceled_progress_not_100_percent() -> None:
    sigma0 = np.asarray([0.10, 0.20, 0.30, 0.40, 0.50], dtype=np.float64)
    base = _make_base_result(sigma0, rmse=1.0)
    cfg = _CfgStub(auto_clean_neighbor_pull_enabled=False, auto_clean_neighbor_pull_ratios=(0.20,))
    stop = Event()
    progress_events: list[tuple[float, str]] = []
    call_count = {"n": 0}

    def _progress_cb(p: float, m: str) -> None:
        progress_events.append((float(p), str(m)))

    def _fake_insert(
        _cfg: Any,
        base_result: dict[str, Any],
        _stop_event: Event,
        _extra_sigma_knots: np.ndarray,
        *,
        target_sigma_knots: np.ndarray,
        force_reopt: bool,
        live_cb: Any,
    ) -> dict[str, Any]:
        _ = (force_reopt, live_cb)
        call_count["n"] += 1
        sk = np.asarray(target_sigma_knots, dtype=np.float64).ravel().copy()
        out = dict(base_result)
        out["sigma_knots"] = sk
        out["rmse"] = 1.0
        if call_count["n"] >= 2:
            stop.set()
        return out

    with patch("spline_pipeline.insert_manual_sigma_nodes", side_effect=_fake_insert):
        _ = worker_spline_auto_clean_knots(
            base,
            cfg,
            stop,
            target_sigma_knots=sigma0,
            tolerance=0.20,
            progress_cb=_progress_cb,
            live_cb=None,
        )

    assert progress_events
    last_p, last_msg = progress_events[-1]
    assert last_p == -1.0
    assert "canceled" in last_msg.lower()
