"""Three small decisions of `_build_opt_config` are methods of their own (audit v2, plan S5.2).

`_MeshOptimizationMixin._build_opt_config` reads some hundred widgets of the index-spline window into a `SplineOptConfig`: 301 lines, complexity 82. Three of the decisions it takes on
the way come out, each pinned here on a namespace (no window, no fit):

    _sigma_mesh_segments_of_the_spectrum   the minimum relative spacing of the mesh (0.02 when the window has no such field; none at all when it is not positive), and how many
                                           segments the sigma mesh of this spectrum gets - at least one
    _data_type_of_the_fit                  transmission and reflection together, reflection alone, or transmission alone
    _rmse_fit_band_nm                      the band the RMSE is restricted to, lowest bound first, or None
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui import certus_index_spline_mixins_ui as module
from certus.ui.certus_index_spline_mixins_ui import _MeshOptimizationMixin

DataType = module.DataType


# --- _sigma_mesh_segments_of_the_spectrum --------------------------------------------------------------------------------------------------


class Spin:
    def __init__(self, value) -> None:
        self._value = value

    def value(self):
        return self._value


@pytest.fixture
def knots(monkeypatch):
    """Replace the knot generator by a recorder that returns `size` knots."""
    seen = SimpleNamespace(calls=[], size=7)

    def fake(lam_min, lam_max, **kwargs):
        seen.calls.append((lam_min, lam_max, kwargs))
        return np.zeros(seen.size)

    monkeypatch.setattr(module, "canonical_spline_sigma_knots", fake)
    return seen


LAM = np.array([800.0, 1200.0, 2000.0, 1500.0])


def segments(window, lam=LAM):
    return _MeshOptimizationMixin._sigma_mesh_segments_of_the_spectrum(window, lam)


def test_the_mesh_spacing_of_the_window_is_handed_to_the_knot_generator_with_the_extent_of_the_spectrum(knots):
    spacing, _count = segments(SimpleNamespace(sp_mesh_min_dlam=Spin(0.05)))
    assert spacing == 0.05
    assert knots.calls == [(800.0, 2000.0, {"min_delta_lambda_over_lambda_mean": 0.05})]
    assert all(isinstance(bound, float) for bound in knots.calls[0][:2])


def test_a_window_without_a_spacing_field_means_0_02(knots):
    spacing, _count = segments(SimpleNamespace())
    assert spacing == 0.02
    assert knots.calls[0][2] == {"min_delta_lambda_over_lambda_mean": 0.02}


@pytest.mark.parametrize("value", [0.0, -0.1], ids=["zero", "negative"])
def test_a_spacing_that_is_not_positive_is_not_handed_over_but_is_still_reported(knots, value):
    spacing, _count = segments(SimpleNamespace(sp_mesh_min_dlam=Spin(value)))
    assert spacing == value
    assert knots.calls[0][2] == {}


def test_the_spacing_is_reported_as_a_float(knots):
    spacing, _count = segments(SimpleNamespace(sp_mesh_min_dlam=Spin(1)))
    assert isinstance(spacing, float)


@pytest.mark.parametrize(("size", "expected"), [(12, 11), (14, 13), (2, 1), (1, 1), (0, 1)], ids=["12 knots", "14 knots", "2 knots", "1 knot", "none"])
def test_the_segments_are_the_knots_minus_one_and_at_least_one(knots, size, expected):
    knots.size = size
    assert segments(SimpleNamespace(sp_mesh_min_dlam=Spin(0.02)))[1] == expected


# --- _data_type_of_the_fit ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("use_t", "use_r", "expected"),
    [(True, True, DataType.BOTH), (False, True, DataType.REFLECTION), (True, False, DataType.TRANSMISSION), (False, False, DataType.TRANSMISSION)],
    ids=["both", "reflection alone", "transmission alone", "neither falls to transmission"],
)
def test_the_data_type_follows_the_two_switches(use_t, use_r, expected):
    assert _MeshOptimizationMixin._data_type_of_the_fit(SimpleNamespace(), use_t, use_r) is expected


# --- _rmse_fit_band_nm -------------------------------------------------------------------------------------------------------------------


def band(**fields):
    return _MeshOptimizationMixin._rmse_fit_band_nm(SimpleNamespace(**fields))


def test_without_a_restriction_there_is_no_band():
    assert band() is None
    assert band(_rmse_fit_lambda_enabled=False, _rmse_fit_lambda_lo=900.0, _rmse_fit_lambda_hi=1100.0) is None


def test_a_restriction_gives_the_band_lowest_bound_first():
    assert band(_rmse_fit_lambda_enabled=True, _rmse_fit_lambda_lo=900.0, _rmse_fit_lambda_hi=1100.0) == (900.0, 1100.0)
    assert band(_rmse_fit_lambda_enabled=True, _rmse_fit_lambda_lo=1100.0, _rmse_fit_lambda_hi=900.0) == (900.0, 1100.0)


def test_the_bounds_are_read_as_floats():
    got = band(_rmse_fit_lambda_enabled=True, _rmse_fit_lambda_lo="900", _rmse_fit_lambda_hi=1100)
    assert got == (900.0, 1100.0)
    assert all(isinstance(bound, float) for bound in got)


# --- the configuration reads them ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        "_mesh_mdl, n_seg_mesh = self._sigma_mesh_segments_of_the_spectrum(lam)",
        "dt = self._data_type_of_the_fit(use_t, use_r)",
        "rmse_fit_lambda_nm = self._rmse_fit_band_nm()",
    ],
)
def test_the_configuration_asks_each_decision_to_its_method(call):
    assert call in inspect.getsource(_MeshOptimizationMixin._build_opt_config)
