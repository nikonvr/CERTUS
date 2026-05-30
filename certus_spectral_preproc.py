# -*- coding: utf-8 -*-
"""Root-level facade: re-exports certus.utils.certus_spectral_preproc publicly.

Tests that do ``import certus_spectral_preproc`` (or use pytest.importorskip) will
find this module when the project root is on sys.path.
"""
from certus.utils.certus_spectral_preproc import (  # noqa: F401
    auto_tune_savgol_params,
    auto_tune_savgol_params_from_dataframe,
    dynamic_savgol_blend,
    smooth_spectrum_auto,
    smooth_dataframe_auto,
    summarize_smoothing_quality,
)

__all__ = [
    "auto_tune_savgol_params",
    "auto_tune_savgol_params_from_dataframe",
    "dynamic_savgol_blend",
    "smooth_spectrum_auto",
    "smooth_dataframe_auto",
    "summarize_smoothing_quality",
]
