"""Unit tests for _detect_corridor_spike — validates B4 FIX (unbiased parabola).

The spike detector should flag genuine discontinuities (sudden jumps) but NOT
flag naturally rising RMSE trends. The B4 fix feeds *all* evaluated points
(including rejected ones) so the parabola reflects the true RMSE(d) trend.
"""
from __future__ import annotations

import numpy as np
import pytest

from certus.spline.spline_profile_corridors import _detect_corridor_spike


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _parabolic_rmse(d_vals: list[float], d0: float, a: float, b: float) -> list[float]:
    """RMSE = a*(d - d0)^2 + b  (smooth parabola)."""
    return [a * (d - d0) ** 2 + b for d in d_vals]


# ────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────

class TestDetectCorridorSpike:
    """Core unit tests for the spike detection function."""

    def test_smooth_parabola_no_spike(self) -> None:
        """A smoothly rising RMSE should NEVER be flagged as a spike."""
        d0 = 100.0
        d_vals = [100.0 + i * 0.5 for i in range(10)]
        rmse_vals = _parabolic_rmse(d_vals, d0, 1e-4, 0.001)

        # Next point follows the parabola exactly
        d_try = 105.0
        rm = 1e-4 * (105.0 - d0) ** 2 + 0.001

        is_spike, rm_pred, tol, sigma = _detect_corridor_spike(
            d_vals, rmse_vals, d_try, rm, d0, 2e-5,
        )
        assert not is_spike, "Smooth parabolic point should not be flagged as spike"

    def test_genuine_spike_detected(self) -> None:
        """A sudden 10× jump should be detected as a spike."""
        d0 = 100.0
        d_vals = [100.0 + i * 0.5 for i in range(10)]
        rmse_vals = _parabolic_rmse(d_vals, d0, 1e-4, 0.001)

        # Genuine spike: 10× the expected value
        d_try = 105.0
        rm_expected = 1e-4 * (105.0 - d0) ** 2 + 0.001
        rm_spike = rm_expected * 10.0

        is_spike, rm_pred, tol, sigma = _detect_corridor_spike(
            d_vals, rmse_vals, d_try, rm_spike, d0, 2e-5,
        )
        assert is_spike, "Genuine 10× spike should be detected"

    def test_too_few_points_no_detection(self) -> None:
        """With < 5 history points, no spike detection should occur."""
        d_vals = [100.0, 100.5, 101.0, 101.5]
        rmse_vals = [0.001, 0.0011, 0.0013, 0.0016]

        is_spike, rm_pred, tol, sigma = _detect_corridor_spike(
            d_vals, rmse_vals, 102.0, 0.01, 100.0, 2e-5,
        )
        assert not is_spike, "Should not flag spike with < 5 points"
        assert not np.isfinite(rm_pred), "Prediction should be NaN with < 5 points"

    def test_natural_concave_rise_not_spike(self) -> None:
        """B4 regression guard: a concave RMSE rise (steeper than parabola)
        should NOT be flagged when the full history is fed.

        This is the exact scenario the B4 fix addresses: when the parabola is
        fitted on ALL points (including rising ones), it adapts to the trend
        and does not incorrectly reject valid boundary points.
        """
        d0 = 100.0
        # RMSE rises cubically (steeper than quadratic) — natural for dispersive films
        d_vals = [100.0 + i * 0.5 for i in range(12)]
        rmse_vals = [0.001 + 2e-5 * (d - d0) ** 3 for d in d_vals]

        # Next point follows the cubic trend
        d_try = 106.0
        rm = 0.001 + 2e-5 * (d_try - d0) ** 3

        is_spike, rm_pred, tol, sigma = _detect_corridor_spike(
            d_vals, rmse_vals, d_try, rm, d0, 2e-5,
        )
        # With all points in the history, the parabola adapts to the rising trend.
        # The point should NOT be flagged as a spike because the jump ratio
        # relative to recent steps is smooth.
        # Note: the detector uses a double check (parabola + jump_ratio >= 3.0),
        # so a smooth continuation should pass even if the parabola overshoots.
        assert not is_spike, (
            "Natural concave rise should not be flagged — B4 regression"
        )

    def test_returns_prediction_and_tolerance(self) -> None:
        """Verify that rm_pred and tol are finite when enough points are given."""
        d0 = 100.0
        d_vals = [100.0 + i * 0.5 for i in range(8)]
        rmse_vals = _parabolic_rmse(d_vals, d0, 1e-4, 0.001)

        d_try = 104.0
        rm = 1e-4 * (104.0 - d0) ** 2 + 0.001

        is_spike, rm_pred, tol, sigma = _detect_corridor_spike(
            d_vals, rmse_vals, d_try, rm, d0, 2e-5,
        )
        assert np.isfinite(rm_pred), "Prediction should be finite"
        assert np.isfinite(tol), "Tolerance should be finite"
        assert tol >= 2e-5, "Tolerance should be at least parab_tol_abs"
