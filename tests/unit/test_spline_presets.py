"""Presets matériaux INDEX SPLINE (headless)."""
from __future__ import annotations

import numpy as np
import pytest

from certus_core import K_MAX_LIMIT, N_MAX_LIMIT, N_MIN_LIMIT
from certus_index_spline_core import canonical_spline_sigma_knots

from spline_presets import (
    NB2O5_PRESET_KNOTS,
    SIO2_PRESET_KNOTS,
    project_manual_material_preset,
    _project_nb2o5_preset_to_sigma_knots,
    _project_sio2_preset_to_sigma_knots,
    _interp_n_L_linear_on_sigma,
    _project_tabulated_nk_lam_preset_to_sigma_knots,
)


def test_nb2o5_preset_knot_count() -> None:
    assert len(NB2O5_PRESET_KNOTS["sk"]) == len(NB2O5_PRESET_KNOTS["n"]) == len(NB2O5_PRESET_KNOTS["L"])


def test_project_nb2o5_matches_reference_d() -> None:
    sk = np.asarray(NB2O5_PRESET_KNOTS["sk"], dtype=np.float64)
    _, _, _, d = _project_nb2o5_preset_to_sigma_knots(sk)
    assert abs(d - float(NB2O5_PRESET_KNOTS["d_nm"])) < 1e-6


def test_sio2_preset_knot_count() -> None:
    assert len(SIO2_PRESET_KNOTS["sk"]) == len(SIO2_PRESET_KNOTS["n"]) == len(SIO2_PRESET_KNOTS["L"]) == 14


def test_sio2_preset_visible_n_order_of_magnitude() -> None:
    """Ordre de grandeur SiO₂ (visible) : n ~ 1,45-1,47 - pas ~2 comme Nb₂O₅."""
    n = SIO2_PRESET_KNOTS["n"]
    assert float(np.min(n)) > 1.35 and float(np.max(n)) < 1.55


def test_project_sio2_matches_reference_d_without_hint() -> None:
    sk = np.asarray(SIO2_PRESET_KNOTS["sk"], dtype=np.float64)
    _, _, _, d = _project_sio2_preset_to_sigma_knots(sk, d_nm_hint=None)
    assert abs(d - float(SIO2_PRESET_KNOTS["d_nm"])) < 1e-6


def test_project_manual_all_ids() -> None:
    sk = np.linspace(2e-4, 2.8e-3, 8)
    for pid in ("nb2o5", "sio2", "ta2o5", "Nb₂O₅"):
        s, n, L, d = project_manual_material_preset(pid, sk, d_nm_hint=100.0)
        assert s.shape == n.shape == L.shape == sk.shape
        assert np.all(np.isfinite(n)) and np.all(np.isfinite(L))
        assert np.isfinite(d)


@pytest.mark.parametrize(
    "lam_lo,lam_hi",
    [
        (150.0, 320.0),
        (200.0, 450.0),
        (700.0, 1100.0),
        (2200.0, 2800.0),
        (3800.0, 9800.0),
        (180.0, 7200.0),
        (250.0, 5000.0),
    ],
)
def test_manual_presets_robust_across_spectral_window(lam_lo: float, lam_hi: float) -> None:
    """Maillage canonique selon λ_min/λ_max du fichier : n, L finis et dans les bornes CERTUS."""
    sk = canonical_spline_sigma_knots(
        lam_lo,
        lam_hi,
        min_delta_lambda_over_lambda_mean=None,
    )
    assert sk.size >= 2
    for pid in ("nb2o5", "sio2", "ta2o5"):
        _s, n, L, d = project_manual_material_preset(pid, sk, d_nm_hint=1500.0)
        assert _s.shape == n.shape == L.shape == sk.shape
        assert np.all(np.isfinite(n)) and np.all(np.isfinite(L))
        assert np.isfinite(d) and float(d) > 0.0
        assert np.all(n >= N_MIN_LIMIT - 1e-9) and np.all(n <= N_MAX_LIMIT + 1e-9)
        k = np.exp(L)
        assert np.all(k >= 1e-30) and np.all(k <= K_MAX_LIMIT + 1e-9)


# ─────────────────────────────────────────────────────────────────────
# Additional Coverage Boost for spline_presets.py
# ─────────────────────────────────────────────────────────────────────


class TestSplinePresetsCoverageBoost:
    def test_interp_n_L_linear_on_sigma_empty(self):
        n, L = _interp_n_L_linear_on_sigma(
            np.array([1.0, 2.0]), np.array([1.5, 1.6]), np.array([-10.0, -10.0]), np.array([])
        )
        assert n.size == 0
        assert L.size == 0

    def test_interp_n_L_linear_on_sigma_errors(self):
        with pytest.raises(ValueError, match="inconsistent sk_ref"):
            _interp_n_L_linear_on_sigma(
                np.array([1.0]), np.array([1.5]), np.array([-10.0]), np.array([1.5])
            )

    def test_project_nb2o5_empty_target(self, monkeypatch):
        # Temporarily mock sk_ref.size to < 2 to hit that branch
        orig_sk = NB2O5_PRESET_KNOTS["sk"]
        try:
            NB2O5_PRESET_KNOTS["sk"] = [1.0]
            sk_target = np.array([1.5])
            res_sk, n, L, d = _project_nb2o5_preset_to_sigma_knots(sk_target)
            assert np.all(n == 0.0)
        finally:
            NB2O5_PRESET_KNOTS["sk"] = orig_sk

    def test_project_sio2_empty_target(self, monkeypatch):
        orig_sk = SIO2_PRESET_KNOTS["sk"]
        try:
            SIO2_PRESET_KNOTS["sk"] = [1.0]
            sk_target = np.array([1.5])
            res_sk, n, L, d = _project_sio2_preset_to_sigma_knots(sk_target)
            assert np.all(n == 0.0)
        finally:
            SIO2_PRESET_KNOTS["sk"] = orig_sk

    def test_project_tabulated_preset_empty_target(self):
        res_sk, n, L, d = _project_tabulated_nk_lam_preset_to_sigma_knots(
            np.array([400.0, 500.0]), np.array([1.5, 1.6]), np.array([1e-5, 1e-5]), np.array([])
        )
        assert res_sk.size == 0
        assert n.size == 0
        assert L.size == 0
        assert d == 3000.0

    def test_project_tabulated_preset_errors(self):
        with pytest.raises(ValueError, match="inconsistent lengths"):
            _project_tabulated_nk_lam_preset_to_sigma_knots(
                np.array([400.0]), np.array([1.5]), np.array([1e-5]), np.array([1.5])
            )

    def test_project_manual_material_preset_unknown(self):
        with pytest.raises(ValueError, match="unknown material preset"):
            project_manual_material_preset("unknown_preset_id", np.array([1.5]))

