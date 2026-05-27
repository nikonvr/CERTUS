"""Tests unitaires : certus_spectral_preproc — filtrage Savitzky-Golay."""

from __future__ import annotations

import numpy as np
import pytest

from certus.utils.certus_spectral_preproc import (
    auto_tune_savgol_params,
    dynamic_savgol_blend,
)


class TestAutoTuneSavgolParams:
    def test_returns_window_and_order(self) -> None:
        lam = np.linspace(300, 800, 100)
        rng = np.random.default_rng(42)
        y = np.sin(lam / 100) + rng.normal(0, 0.01, 100)
        y_mat = y.reshape(1, -1)  # 1 spectrum as 2D matrix
        wl, order, heavy = auto_tune_savgol_params(lam, y_mat, mode="T")
        assert isinstance(wl, int)
        assert isinstance(order, int)
        assert wl >= 3  # minimum window
        assert wl % 2 == 1  # must be odd
        assert order >= 1


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
