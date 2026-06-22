"""Unit tests: shared spectral preprocessing (certus_spectral_preproc)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from certus.utils.certus_spectral_preproc import (
    auto_tune_savgol_params,
    auto_tune_savgol_params_from_dataframe,
    dynamic_savgol_blend,
)


@pytest.mark.unit
class TestDynamicSavgolBlend:
    def test_shape_preserved_2d(self) -> None:
        x = np.linspace(400, 800, 64, dtype=np.float64)
        y = np.random.default_rng(0).random((3, 64))
        out = dynamic_savgol_blend(x, y, 15, 2, 25)
        assert out.shape == y.shape

    def test_shape_preserved_1d(self) -> None:
        x = np.linspace(400, 800, 64, dtype=np.float64)
        y = np.random.default_rng(1).random(64)
        out = dynamic_savgol_blend(x, y, 15, 2, 25)
        assert out.shape == y.shape


@pytest.mark.unit
class TestAutoTuneSavgol:
    def test_returns_odd_windows(self) -> None:
        x = np.linspace(400, 2400, 120, dtype=np.float64)
        rng = np.random.default_rng(2)
        y_mat = rng.random((2, 120))
        w, p, hw = auto_tune_savgol_params(x, y_mat, "Medium (Balanced)")
        assert w % 2 == 1 and hw % 2 == 1
        assert hw >= w
        assert p in (2, 3, 4)

    def test_from_dataframe_matches_matrix(self) -> None:
        x = np.linspace(400, 2400, 80, dtype=np.float64)
        rng = np.random.default_rng(3)
        df = pd.DataFrame({"wl": x, "a": rng.random(80), "b": rng.random(80)})
        w1, p1, h1 = auto_tune_savgol_params_from_dataframe(x, df, "Soft (High Fidelity)")
        w2, p2, h2 = auto_tune_savgol_params(x, df.iloc[:, 1:].values.T, "Soft (High Fidelity)")
        assert (w1, p1, h1) == (w2, p2, h2)

    def test_unknown_preset_uses_default_penalties_like_medium(self) -> None:
        x = np.linspace(400, 2400, 120, dtype=np.float64)
        rng = np.random.default_rng(4)
        y_mat = rng.random((2, 120))
        w_u, p_u, hw_u = auto_tune_savgol_params(x, y_mat, "Preset Inconnu XYZ")
        w_m, p_m, hw_m = auto_tune_savgol_params(x, y_mat, "Medium (Balanced)")
        assert (w_u, p_u, hw_u) == (w_m, p_m, hw_m)

    def test_extreme_mode_limits_poly_to_2(self) -> None:
        x = np.linspace(400, 2400, 120, dtype=np.float64)
        y_mat = np.random.default_rng(5).random((3, 120))
        w, p, hw = auto_tune_savgol_params(x, y_mat, "Extreme (Aggressive)")
        assert p == 2
        assert w % 2 == 1 and hw % 2 == 1 and hw >= w

    def test_auto_tune_single_curve_row(self) -> None:
        x = np.linspace(400, 800, 64, dtype=np.float64)
        y_mat = np.random.default_rng(6).random((1, 64))
        w, p, hw = auto_tune_savgol_params(x, y_mat, "Soft (High Fidelity)")
        assert w % 2 == 1 and hw % 2 == 1


@pytest.mark.unit
class TestDynamicSavgolBlendEdge:
    def test_small_length_preserves_shape(self) -> None:
        x = np.linspace(400, 800, 24, dtype=np.float64)
        y = np.random.default_rng(7).random((2, 24))
        out = dynamic_savgol_blend(x, y, 7, 2, 15)
        assert out.shape == y.shape
        assert np.all(np.isfinite(out))
