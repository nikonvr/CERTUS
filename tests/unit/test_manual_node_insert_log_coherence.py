from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from typing import Any
from unittest.mock import patch

import numpy as np

from certus.spline.spline_pipeline import insert_manual_sigma_nodes


@dataclass
class _CfgStub:
    n_mono_band_nm: tuple[float, float] = (1.4, 2.6)
    polish_maxfun: int = 100
    node_model_spectral_polish_maxfun: int | None = None
    manual_node_insert_polish_maxfun: int | None = 50
    manual_node_insert_max_rmse_regression_abs: float = 0.0
    manual_node_insert_max_rmse_regression_rel: float = 0.0
    substrate_n_offset: float = 0.0
    n_sub: np.ndarray = field(default_factory=lambda: np.asarray([1.75], dtype=np.float64))
    substrate_n_base: np.ndarray | None = None


def _base_result() -> dict[str, Any]:
    return {
        "sigma_knots": np.asarray([0.10, 0.20, 0.30], dtype=np.float64),
        "rmse": 1.0,
        "substrate_n_offset": 0.0,
        "n_sub_effective": np.asarray([1.75], dtype=np.float64),
        "d_nm": 1700.0,
    }


def _fake_bounds(_cfg: Any, sk_new: np.ndarray):
    n = 1 + 2 * int(np.asarray(sk_new).size)
    bounds = np.zeros((n, 2), dtype=np.float64)
    bounds[:, 0] = -10.0
    bounds[:, 1] = 10.0
    x0 = np.zeros(n, dtype=np.float64)
    k = int(np.asarray(sk_new).size)
    lo = np.full(k, -1.0, dtype=np.float64)
    hi = np.full(k, 1.0, dtype=np.float64)
    return bounds, x0, lo, hi


def test_manual_insert_logs_attempt_then_accepted_with_same_op_id() -> None:
    cfg = _CfgStub()
    base = _base_result()
    stop = Event()
    events: list[tuple[str, dict[str, Any]]] = []

    def _capture(_log: Any, event: str, seq: str = "", **payload: Any) -> None:
        _ = seq
        events.append((event, payload))

    def _fake_polish(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "x_best": np.asarray([1700.0, 0.1, 0.2, 0.3, 0.11, 0.22, 0.33], dtype=np.float64),
            "n_lam": np.asarray([1.9, 1.8], dtype=np.float64),
            "k_lam": np.asarray([0.01, 0.02], dtype=np.float64),
            "d_nm": 1700.5,
            "spectral_mse": 0.81,
            "spectral_rmse": 0.9,
            "profile_interp": "smooth",
        }

    with (
        patch("certus.spline.spline_pipeline_utils._log_spline_pipeline_json", side_effect=_capture),
        patch("certus.spline.spline_pipeline_mesh_insert.build_segment_optimizer_x_vector", return_value=(np.asarray([1700.0, 0.1, 0.2, 0.3, 0.11, 0.22, 0.33], dtype=np.float64), None)),
        patch("certus.spline.spline_pipeline_mesh_insert.x_slice_n_to_physical_nodes", side_effect=lambda x, *_a, **_k: np.asarray(x, dtype=np.float64).copy()),
        patch("certus.spline.spline_pipeline_mesh_insert.physical_nodes_to_x_slice_n", side_effect=lambda x, *_a, **_k: np.asarray(x, dtype=np.float64).copy()),
        patch("certus.spline.spline_pipeline_mesh_insert._bounds_x0_for_sigma_knots", side_effect=_fake_bounds),
        patch("certus.spline.spline_pipeline_mesh_insert._spectral_polish_node_mesh_profile", side_effect=_fake_polish),
        patch("certus.spline.spline_pipeline_mesh_insert._sync_theoretical_tr_from_nk_dict", return_value=None),
        patch("certus.spline.spline_pipeline_mesh_insert.log_index_spline_d_trace", return_value=None),
    ):
        out = insert_manual_sigma_nodes(
            cfg,
            base,
            stop,
            np.asarray([0.1, 0.2, 0.25, 0.3], dtype=np.float64),
        )

    assert out is not base
    assert len(events) >= 2

    first_event, first_payload = events[0]
    second_event, second_payload = events[1]
    assert first_event == "manual_node_insert_attempt"
    assert second_event == "manual_node_insert_accepted"
    assert first_payload.get("op_id") is not None
    assert second_payload.get("op_id") == first_payload.get("op_id")
    assert first_payload.get("mesh_removed_count") == 0
    assert first_payload.get("mesh_added_count") == 1
    assert first_payload.get("mesh_before_lambda_summary") == "[3.3, 5.0, 10.0]"
    assert first_payload.get("mesh_after_lambda_summary") == "[3.3, 4.0, 5.0, 10.0]"
    assert second_payload.get("mesh_added_count") == 1


def test_manual_insert_logs_attempt_then_rejected_with_same_op_id() -> None:
    cfg = _CfgStub()
    base = _base_result()
    stop = Event()
    events: list[tuple[str, dict[str, Any]]] = []

    def _capture(_log: Any, event: str, seq: str = "", **payload: Any) -> None:
        _ = seq
        events.append((event, payload))

    def _fake_polish(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "x_best": np.asarray([1700.0, 0.1, 0.2, 0.3, 0.11, 0.22, 0.33], dtype=np.float64),
            "n_lam": np.asarray([1.9, 1.8], dtype=np.float64),
            "k_lam": np.asarray([0.01, 0.02], dtype=np.float64),
            "d_nm": 1700.5,
            "spectral_mse": 1.21,
            "spectral_rmse": 1.1,
            "profile_interp": "smooth",
        }

    with (
        patch("certus.spline.spline_pipeline_utils._log_spline_pipeline_json", side_effect=_capture),
        patch("certus.spline.spline_pipeline_mesh_insert.build_segment_optimizer_x_vector", return_value=(np.asarray([1700.0, 0.1, 0.2, 0.3, 0.11, 0.22, 0.33], dtype=np.float64), None)),
        patch("certus.spline.spline_pipeline_mesh_insert.x_slice_n_to_physical_nodes", side_effect=lambda x, *_a, **_k: np.asarray(x, dtype=np.float64).copy()),
        patch("certus.spline.spline_pipeline_mesh_insert.physical_nodes_to_x_slice_n", side_effect=lambda x, *_a, **_k: np.asarray(x, dtype=np.float64).copy()),
        patch("certus.spline.spline_pipeline_mesh_insert._bounds_x0_for_sigma_knots", side_effect=_fake_bounds),
        patch("certus.spline.spline_pipeline_mesh_insert._spectral_polish_node_mesh_profile", side_effect=_fake_polish),
    ):
        out = insert_manual_sigma_nodes(
            cfg,
            base,
            stop,
            np.asarray([0.1, 0.2, 0.25, 0.3], dtype=np.float64),
        )

    assert out is base
    assert len(events) >= 2

    first_event, first_payload = events[0]
    second_event, second_payload = events[1]
    assert first_event == "manual_node_insert_attempt"
    assert second_event == "manual_node_insert_rejected"
    assert first_payload.get("op_id") is not None
    assert second_payload.get("op_id") == first_payload.get("op_id")
    assert second_payload.get("mesh_removed_count") == 0
    assert second_payload.get("mesh_added_count") == 1
    assert second_payload.get("mesh_after_lambda_summary") == "[3.3, 4.0, 5.0, 10.0]"
