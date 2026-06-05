"""Unit tests: certus_spectral_preproc — Savitzky-Golay filtering."""

from __future__ import annotations

import numpy as np
import pytest

from certus.utils.certus_spectral_preproc import (
    dynamic_savgol_blend,
    smooth_spectrum_auto,
)


# ---------------------------------------------------------------------------
# Formerly: auto_tune_savgol_params (function deleted/merged into
# smooth_spectrum_auto which returns parameters in its diagnostics).
# Assertions now apply to smooth_spectrum_auto + diagnostics.
# ---------------------------------------------------------------------------


class TestSmoothSpectrumAutoParams:
    """Verifies that smooth_spectrum_auto returns consistent parameters."""

    def test_returns_valid_window_and_order(self) -> None:
        lam = np.linspace(300, 800, 100)
        rng = np.random.default_rng(42)
        y = np.sin(lam / 100) + rng.normal(0, 0.01, 100)
        _y_sm, diag = smooth_spectrum_auto(lam, y, level="moyen")
        wl = diag["window_base"]
        order = diag["polyorder"]
        assert isinstance(wl, int)
        assert isinstance(order, int)
        assert wl >= 3, "window must be >= 3"
        assert wl % 2 == 1, "window must be odd"
        assert order >= 1

    def test_heavy_window_gte_base_window(self) -> None:
        lam = np.linspace(400, 1000, 150)
        y = np.cos(lam / 80)
        _y_sm, diag = smooth_spectrum_auto(lam, y, level="fort")
        assert diag["window_heavy"] >= diag["window_base"]

    def test_quality_score_in_range(self) -> None:
        lam = np.linspace(300, 800, 200)
        y = 0.5 + 0.1 * np.sin(lam / 50)
        _y_sm, diag = smooth_spectrum_auto(lam, y)
        assert 0.0 <= diag["quality_score"] <= 1.0


class TestDynamicSavgolBlend:
    def test_output_shape_matches_input(self) -> None:
        lam = np.linspace(300, 800, 100)
        y = np.sin(lam / 100)
        result = dynamic_savgol_blend(lam, y, base_window=7, poly=3)
        assert result.shape == y.shape

    def test_smooth_signal_approximately_unchanged(self) -> None:
        lam = np.linspace(300, 800, 100)
        y = np.ones_like(lam) * 0.5
        result = dynamic_savgol_blend(lam, y, base_window=7, poly=3)
        np.testing.assert_allclose(result, y, atol=1e-6)

