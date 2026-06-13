# -*- coding: utf-8 -*-

"""Contract tests for live corridor RMSE payloads."""

from __future__ import annotations

import numpy as np

from certus.spline.certus_index_spline_corridor_contract import (
    CORRIDOR_LIVE_STATUS,
    normalize_corridor_live_payload,
)


def test_normalize_corridor_live_payload_prefers_live_keys() -> None:
    payload = {
        "profile_d_values_nm": np.array([3.0, 1.0, 2.0]),
        "profile_d_rmse_values": np.array([0.3, 0.1, 0.2]),
        "profile_d_status": CORRIDOR_LIVE_STATUS,
    }

    out = normalize_corridor_live_payload(payload)

    np.testing.assert_allclose(out["profile_d_values_nm"], np.array([3.0, 1.0, 2.0]))
    np.testing.assert_allclose(out["profile_d_rmse_values"], np.array([0.3, 0.1, 0.2]))
    assert out["profile_d_status"] == CORRIDOR_LIVE_STATUS
    np.testing.assert_allclose(out["corridor_d_plot"], np.array([3.0, 1.0, 2.0]))
    np.testing.assert_allclose(out["corridor_rmse_plot"], np.array([0.3, 0.1, 0.2]))


def test_normalize_corridor_live_payload_supports_legacy_keys() -> None:
    payload = {
        "d_plot": np.array([10.0, 20.0, 15.0]),
        "r_plot": np.array([1.0, 2.0, 1.5]),
    }

    out = normalize_corridor_live_payload(payload)

    np.testing.assert_allclose(out["profile_d_values_nm"], np.array([10.0, 20.0, 15.0]))
    np.testing.assert_allclose(out["profile_d_rmse_values"], np.array([1.0, 2.0, 1.5]))
    assert out["profile_d_status"] == CORRIDOR_LIVE_STATUS
    np.testing.assert_allclose(out["corridor_d_vis"], np.array([10.0, 20.0, 15.0]))
    np.testing.assert_allclose(out["corridor_rmse_vis"], np.array([1.0, 2.0, 1.5]))


def test_normalize_corridor_live_payload_trims_mismatched_lengths() -> None:
    payload = {
        "profile_d_values_nm": np.array([1.0, 2.0, 3.0, 4.0]),
        "profile_d_rmse_values": np.array([0.1, 0.2]),
        "profile_d_status": CORRIDOR_LIVE_STATUS,
    }

    out = normalize_corridor_live_payload(payload)

    np.testing.assert_allclose(out["profile_d_values_nm"], np.array([1.0, 2.0]))
    np.testing.assert_allclose(out["profile_d_rmse_values"], np.array([0.1, 0.2]))
    assert out["profile_d_values_nm"].size == out["profile_d_rmse_values"].size
