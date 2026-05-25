"""Unit tests for certus_index_utils.py — Phase 3 coverage improvement."""
from __future__ import annotations

import numpy as np
import pytest

from certus_index_utils import (
    _lam_uniform_grid,
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _sorted_finite_sigma_knots,
    _transmittance_absolute_from_nk,
    log_structured_json_event,
    spectral_rmse_weights,
)


# ── log_structured_json_event ──


class TestLogStructuredJsonEvent:
    def test_none_logger_is_noop(self):
        """No exception when logger is None."""
        log_structured_json_event(None, "CH", "evt")

    def test_emits_json_line(self, caplog):
        import logging

        log = logging.getLogger("certus_test_json")
        log.setLevel(logging.DEBUG)
        with caplog.at_level(logging.INFO, logger="certus_test_json"):
            log_structured_json_event(log, "TEST_CH", "my_event", seq="s1", foo=42)
        assert any("TEST_CH" in r.message and '"event":"my_event"' in r.message for r in caplog.records)

    def test_non_serializable_field_does_not_raise(self, caplog):
        import logging

        log = logging.getLogger("certus_test_json2")
        log.setLevel(logging.DEBUG)
        # np.array is not JSON-serializable — should silently swallow
        log_structured_json_event(log, "CH", "evt", bad=np.array([1, 2]))


# ── spectral_rmse_weights ──


class TestSpectralRmseWeights:
    def test_single_point_returns_ones(self):
        w = spectral_rmse_weights(np.array([500.0]))
        np.testing.assert_array_equal(w, [1.0])

    def test_uniform_grid_sums_to_n(self):
        lam = np.linspace(300, 900, 200)
        w = spectral_rmse_weights(lam)
        assert w.shape == lam.shape
        np.testing.assert_allclose(np.sum(w), lam.size, rtol=1e-10)

    def test_non_uniform_grid_sums_to_n(self):
        lam = np.sort(np.concatenate([np.linspace(300, 400, 100), np.linspace(800, 900, 10)]))
        w = spectral_rmse_weights(lam)
        np.testing.assert_allclose(np.sum(w), lam.size, rtol=1e-10)

    def test_all_weights_positive(self):
        w = spectral_rmse_weights(np.linspace(200, 1000, 50))
        assert np.all(w > 0)


# ── _lam_uniform_grid ──


class TestLamUniformGrid:
    def test_basic_grid(self):
        g = _lam_uniform_grid(300.0, 900.0, 10.0)
        assert g[0] == 300.0
        assert g[-1] == 900.0
        np.testing.assert_allclose(np.diff(g), 10.0, atol=1e-9)

    def test_reversed_bounds_empty(self):
        g = _lam_uniform_grid(900.0, 300.0, 10.0)
        assert g.size == 0

    def test_nan_bounds_empty(self):
        g = _lam_uniform_grid(float("nan"), 900.0, 10.0)
        assert g.size == 0

    def test_tight_range_single_point(self):
        g = _lam_uniform_grid(499.0, 501.0, 5.0)
        assert g.size == 1
        assert g[0] == 500.0

    def test_dtype_is_float64(self):
        g = _lam_uniform_grid(300.0, 900.0, 50.0)
        assert g.dtype == np.float64


# ── _sorted_finite_sigma_knots ──


class TestSortedFiniteSigmaKnots:
    def test_none_returns_empty(self):
        assert _sorted_finite_sigma_knots(None).size == 0

    def test_empty_returns_empty(self):
        assert _sorted_finite_sigma_knots([]).size == 0

    def test_filters_negative_and_zero(self):
        r = _sorted_finite_sigma_knots([-1.0, 0.0, 1.0, 2.0])
        np.testing.assert_array_equal(r, [1.0, 2.0])

    def test_filters_nan_and_inf(self):
        r = _sorted_finite_sigma_knots([float("nan"), float("inf"), 3.0, 1.0])
        np.testing.assert_array_equal(r, [1.0, 3.0])

    def test_removes_duplicates(self):
        r = _sorted_finite_sigma_knots([5.0, 3.0, 5.0, 1.0])
        np.testing.assert_array_equal(r, [1.0, 3.0, 5.0])

    def test_result_is_sorted(self):
        r = _sorted_finite_sigma_knots([10.0, 2.0, 7.0, 4.0])
        assert np.all(np.diff(r) > 0)


# ── _ratio_theoretical_from_nk ──


class TestRatioTheoreticalFromNk:
    @pytest.fixture
    def glass_setup(self):
        lam = np.linspace(400, 800, 50)
        n_sub = np.full_like(lam, 1.52)
        return lam, n_sub

    def test_zero_thickness_ratio_near_one(self, glass_setup):
        lam, n_sub = glass_setup
        n_l = np.full_like(lam, 1.52)  # same as substrate
        k_l = np.zeros_like(lam)
        ratio = _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm=0.001, n_sub=n_sub)
        np.testing.assert_allclose(ratio, 1.0, atol=0.01)

    def test_output_shape_matches_input(self, glass_setup):
        lam, n_sub = glass_setup
        n_l = np.full_like(lam, 2.0)
        k_l = np.zeros_like(lam)
        ratio = _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm=100.0, n_sub=n_sub)
        assert ratio.shape == lam.shape


# ── _transmittance_absolute_from_nk ──


class TestTransmittanceAbsoluteFromNk:
    def test_zero_k_high_transmittance(self):
        lam = np.linspace(400, 800, 30)
        n_sub = np.full_like(lam, 1.52)
        n_l = np.full_like(lam, 1.52)
        k_l = np.zeros_like(lam)
        t = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm=1.0, n_sub=n_sub)
        assert np.all(t > 0.8), "Near-zero k should give high transmittance"

    def test_absorbing_film_reduces_transmittance(self):
        lam = np.linspace(400, 800, 30)
        n_sub = np.full_like(lam, 1.52)
        n_l = np.full_like(lam, 2.0)
        k_l_lo = np.full_like(lam, 0.001)
        k_l_hi = np.full_like(lam, 0.5)
        t_lo = _transmittance_absolute_from_nk(lam, n_l, k_l_lo, 200.0, n_sub)
        t_hi = _transmittance_absolute_from_nk(lam, n_l, k_l_hi, 200.0, n_sub)
        assert np.mean(t_hi) < np.mean(t_lo), "Higher k should reduce transmittance"


# ── _reflectance_ratio_theoretical_from_nk ──


class TestReflectanceRatioTheoreticalFromNk:
    def test_output_shape(self):
        lam = np.linspace(400, 800, 20)
        n_sub = np.full_like(lam, 1.52)
        n_l = np.full_like(lam, 2.0)
        k_l = np.full_like(lam, 0.01)
        r = _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, 150.0, n_sub)
        assert r.shape == lam.shape

    def test_positive_values(self):
        lam = np.linspace(400, 800, 20)
        n_sub = np.full_like(lam, 1.52)
        n_l = np.full_like(lam, 2.0)
        k_l = np.full_like(lam, 0.01)
        r = _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, 150.0, n_sub)
        assert np.all(r >= 0)
