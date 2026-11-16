"""RE target windows and the METAL SINGLE export (audit 2026-11-15, L6-m5, L6-m6).

L6-m5: every RE target was given the half-width (wls[1] - wls[0]) / 2: on a non-uniform grid windows overlapped or left
       gaps, and on a decreasing grid the half-width was negative, so every target was rejected.
L6-m6: the METAL SINGLE export wrote R Target, n and k only: the fit could not be checked from the file.
"""

from __future__ import annotations

import inspect
from itertools import pairwise

import numpy as np

from certus.utils.certus_re_target_windows import re_target_windows


def test_l6_m5_a_decreasing_grid_gives_valid_windows() -> None:
    windows = re_target_windows(np.array([700.0, 600.0, 500.0]))
    assert windows == [(650.0, 750.0), (550.0, 650.0), (450.0, 550.0)]
    assert all(lo < hi for lo, hi in windows)


def test_l6_m5_a_non_uniform_grid_tiles_without_overlap_or_gap() -> None:
    wls = np.array([400.0, 402.0, 410.0, 430.0])
    windows = re_target_windows(wls)
    for (_, hi), (lo, _) in pairwise(windows):
        assert hi == lo
    assert windows[0] == (399.0, 401.0)
    assert windows[-1] == (420.0, 440.0)


def test_l6_m5_a_uniform_grid_keeps_the_former_windows() -> None:
    wls = np.arange(400.0, 420.0, 5.0)
    assert re_target_windows(wls) == [(w - 2.5, w + 2.5) for w in wls]


def test_l6_m6_the_metal_single_export_writes_the_computed_spectra() -> None:
    from certus.ui.certus_metal_single_gui import CertusMetalSingleApp

    source = inspect.getsource(CertusMetalSingleApp._build_export_spectra_dataframe)
    for column in ("R Calc", "T Target", "T Calc", "Rback Target", "Rback Calc"):
        assert f'"{column}"' in source
