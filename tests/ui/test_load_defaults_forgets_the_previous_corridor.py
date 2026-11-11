"""`_load_defaults` leaves nothing of the previous sample in the corridor state of the INDEX SPLINE window.

`Reset to defaults` forgets the file, the last result and the RMSE(d) curve. It kept eight attributes of the corridor
state, which the drawing of the two corridor tabs and the grid recalculation had written for the previous sample: the
interval the profiling code gave (`_corridor_rmse_smart_interval`, the first choice of `Generate corridor (auto smart)`),
the two dictionaries the clipboard export writes, the grid that was asked, and the four arrays the crosshair of the k
corridor reads (audit of the corridors, Q11). Measured on a window on 2026-11-11: after `_load_defaults`, the interval
was still (98.0, 102.0), the one of the sample drawn before.

The table of the corridor state says which attributes belong to a sample; the last test holds `_load_defaults` to it.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.ui.certus_index_spline_corridor_state import CORRIDOR_STATE

#: What the corridor code wrote for a sample and `_load_defaults` did not put back.
LEFT_BEHIND = (
    "_corridor_rmse_smart_interval",
    "_corridor_rmse_parab_export",
    "_corridor_rmse_robust_export",
    "_corridor_rmse_requested_grid",
    "_corridor_k_crosshair_lam",
    "_corridor_k_crosshair_nom",
    "_corridor_k_crosshair_lo",
    "_corridor_k_crosshair_hi",
)

#: Not of a sample: the settings of the robust preset and of the live drawing, two clocks, and the label object of the
#: plot, which goes with the items of the plot.
NOT_OF_A_SAMPLE = {
    "_corridor_rmse_grid_live_t0",
    "_corridor_rmse_live_last_plot_ts",
    "_corridor_rmse_live_plot_min_interval_s",
    "_corridor_rmse_curvature_label",
    "_corridor_rmse_manual_slider_scale",
    "_corridor_parabola_half_window_pts",
    "_corridor_symmetric_center_mode",
    "_corridor_adaptive_rmse_ref_half_width_nm",
    "_corridor_adaptive_rmse_probe_steps_each_side",
    "_corridor_adaptive_rmse_noise_factor",
    "_corridor_adaptive_rmse_min",
}


def alike(a: object, b: object) -> bool:
    """The same value, an empty list and an empty array being both `no point yet`, and nan being nan."""
    if isinstance(a, (list, np.ndarray)) or isinstance(b, (list, np.ndarray)):
        return isinstance(a, (list, np.ndarray)) and isinstance(b, (list, np.ndarray)) and len(a) == len(b) == 0
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return type(a) is type(b) and a == b


def profiled(d_best: float) -> dict:
    """A result with an RMSE(d) profile around `d_best` and the interval the profiling code gives with it."""
    d = np.linspace(d_best - 5.0, d_best + 5.0, 11)
    return {
        "profile_d_values_nm": d,
        "profile_d_rmse_values": 1e-3 + 1e-5 * (d - d_best) ** 2,
        "profile_d_interval_nm": (d_best - 2.0, d_best + 2.0),
        "d_nm": d_best,
        "rmse": 1e-3,
    }


@pytest.fixture
def window_after_a_sample(qapp):
    """The window once the two corridor tabs were drawn for a sample at 100 nm and a grid was asked around it."""
    from CERTUS_INDEX_SPLINE import CertusIndexSplineApp

    window = CertusIndexSplineApp()
    sample = profiled(100.0)
    window._last_result = dict(sample)
    window._plot_corridor_rmse_tab(sample)
    # what _start_corridor_rmse_grid_recalc and _plot_corridor_tab leave, without a worker nor a spectrum
    window._corridor_rmse_requested_grid = np.linspace(95.0, 105.0, 11)
    lam = np.linspace(400.0, 800.0, 5)
    window._corridor_k_crosshair_lam = lam.copy()
    window._corridor_k_crosshair_nom = np.full(lam.size, 1e-3)
    window._corridor_k_crosshair_lo = np.full(lam.size, 5e-4)
    window._corridor_k_crosshair_hi = np.full(lam.size, 2e-3)
    return window


def test_the_drawing_of_a_sample_writes_what_the_reset_has_to_forget(window_after_a_sample):
    window = window_after_a_sample
    assert window._corridor_rmse_smart_interval == (98.0, 102.0)
    assert [name for name in LEFT_BEHIND if alike(getattr(window, name), CORRIDOR_STATE[name].default())] == []


def test_load_defaults_puts_back_what_was_written_for_the_sample(window_after_a_sample):
    window = window_after_a_sample
    window._load_defaults()
    assert window._corridor_rmse_smart_interval is None
    assert [name for name in LEFT_BEHIND if not alike(getattr(window, name), CORRIDOR_STATE[name].default())] == []


def test_the_table_marks_as_reset_every_attribute_that_belongs_to_a_sample():
    assert {name for name, entry in CORRIDOR_STATE.items() if not entry.reset} == NOT_OF_A_SAMPLE
    assert set(LEFT_BEHIND) <= {name for name, entry in CORRIDOR_STATE.items() if entry.reset}
