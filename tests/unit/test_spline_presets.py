"""Tests for spline_presets material projection helpers."""
from __future__ import annotations

import numpy as np
import pytest

from spline_presets import (
    _interp_n_L_linear_on_sigma,
    _project_nb2o5_preset_to_sigma_knots,
    _project_sio2_preset_to_sigma_knots,
    _project_tabulated_nk_lam_preset_to_sigma_knots,
    project_manual_material_preset,
)


def test_interp_n_L_linear_on_sigma_basic() -> None:
    sk_ref = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    n_ref = np.array([1.4, 1.5, 1.6], dtype=np.float64)
    L_ref = np.array([-10.0, -9.0, -8.0], dtype=np.float64)
    sk_tgt = np.array([0.0015, 0.0025], dtype=np.float64)
    n_out, L_out = _interp_n_L_linear_on_sigma(sk_ref, n_ref, L_ref, sk_tgt)
    assert n_out.shape == sk_tgt.shape
    assert L_out.shape == sk_tgt.shape
    assert np.all(np.isfinite(n_out))
    assert np.all(np.isfinite(L_out))


def test_project_nb2o5_preset() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    sk_out, n_out, L_out, d_out = _project_nb2o5_preset_to_sigma_knots(sk)
    assert sk_out.shape == sk.shape
    assert n_out.shape == sk.shape
    assert L_out.shape == sk.shape
    assert d_out > 0


def test_project_sio2_preset_uses_hint() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    _, _, _, d_out = _project_sio2_preset_to_sigma_knots(sk, d_nm_hint=1234.5)
    assert d_out == pytest.approx(1234.5)


def test_project_tabulated_preset_to_sigma_knots() -> None:
    lam = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    n = np.array([2.0, 2.1, 2.2], dtype=np.float64)
    k = np.array([0.01, 0.02, 0.03], dtype=np.float64)
    sk = np.array([0.0015, 0.0025], dtype=np.float64)
    sk_out, n_out, L_out, d_out = _project_tabulated_nk_lam_preset_to_sigma_knots(lam, n, k, sk, d_nm_hint=777.0)
    assert sk_out.shape == sk.shape
    assert n_out.shape == sk.shape
    assert L_out.shape == sk.shape
    assert d_out == pytest.approx(777.0)


def test_project_manual_material_preset_dispatches() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    for preset in ("nb2o5", "sio2", "ta2o5"):
        out = project_manual_material_preset(preset, sk, d_nm_hint=999.0)
        assert len(out) == 4
        assert out[0].shape == sk.shape


def test_project_manual_material_preset_unknown_raises() -> None:
    with pytest.raises(ValueError):
        project_manual_material_preset("unknown", np.array([0.001], dtype=np.float64))
