"""D108, D109, D114: an unphysical input is a ValueError at the door of the fastmath kernels, never a plausible number.

Measured before (AUDIT_ARGON_code_2026-10-19 section 2.4):
- `get_nk_from_spline(..., use_cache=True)` turned a NaN knot into `n = k = 0` (`np.nan_to_num`), a layer that the
  TMM treats as absent: the bare-substrate spectrum, with no message;
- a negative thickness, a negative extinction (`k < 0` is gain under `n - ik`) or a substrate with `n <= 0` reached
  the kernels and gave a spectrum;
- `xyz_from_spectrum` interpolated with `np.interp`, which answers garbage for a decreasing grid and propagates NaN.

Decision of the owner (2026-11-19): strict `ValueError` (docs/ETAT.md section 3).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytestmark = pytest.mark.kernels

WLS = np.array([500.0, 600.0, 700.0])
LAYERS = np.full((3, 2), complex(1.9, 0.0))
THICKNESS = np.array([100.0, 120.0])
SUBSTRATE = np.full(3, complex(1.52, 0.0))


# =============================================================================
# get_nk_from_spline (D108)
# =============================================================================


@pytest.mark.parametrize("use_cache", [True, False])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_spline_knot_that_is_not_finite_is_refused_on_both_paths(use_cache, bad) -> None:
    from certus.physics.certus_optical_models import get_nk_from_spline

    knots = np.array([400.0, 550.0, 700.0, 850.0])
    values = np.array([2.0, 1.95, 1.9, 1.88, 0.01, 0.005, 0.0, 0.0])
    values[1] = bad

    with pytest.raises(ValueError, match="finite"):
        get_nk_from_spline(values, knots, WLS, use_cache=use_cache)


def test_a_finite_spline_still_answers_as_before() -> None:
    from certus.physics.certus_optical_models import get_nk_from_spline

    knots = np.array([400.0, 550.0, 700.0, 850.0])
    values = np.array([2.0, 1.95, 1.9, 1.88, 0.01, 0.005, 0.0, 0.0])
    n, k = get_nk_from_spline(values, knots, WLS)

    assert np.all(np.isfinite(n))
    assert np.all(n > 1.8)
    assert np.all(k >= 0.0)


# =============================================================================
# The normal-incidence TMM wrapper (D109, D114)
# =============================================================================


def test_the_tmm_refuses_a_negative_thickness() -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    with pytest.raises(ValueError, match="thickness"):
        calculate_RT_vectorized_real(np.array([100.0, -1.0]), LAYERS, SUBSTRATE, WLS)


def test_the_tmm_refuses_a_negative_extinction() -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    gain = LAYERS.copy()
    gain[1, 0] = complex(1.9, +0.01)  # n - ik with k = -0.01

    with pytest.raises(ValueError, match="k >= 0"):
        calculate_RT_vectorized_real(THICKNESS, gain, SUBSTRATE, WLS)


@pytest.mark.parametrize("n_sub", [0.0, -1.52])
def test_the_tmm_refuses_a_substrate_without_a_positive_index(n_sub) -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    substrate = SUBSTRATE.copy()
    substrate[2] = complex(n_sub, 0.0)

    with pytest.raises(ValueError, match="substrate"):
        calculate_RT_vectorized_real(THICKNESS, LAYERS, substrate, WLS)


def test_a_zero_thickness_and_a_lossless_layer_are_still_valid() -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real

    r, t = calculate_RT_vectorized_real(np.array([0.0, -0.0]), LAYERS, SUBSTRATE, WLS)

    assert np.all(np.isfinite(r))
    assert np.all(np.isfinite(t))


# =============================================================================
# The oblique wrappers move the thicknesses (D114)
# =============================================================================


def test_the_oblique_wrappers_refuse_a_negative_thickness() -> None:
    from certus.physics.certus_tmm_oblique import (
        calc_spectrum_oblique_backside_vectorized,
        calc_spectrum_oblique_vectorized,
    )

    thickness = np.array([100.0, -5.0])
    with pytest.raises(ValueError, match="thickness"):
        calc_spectrum_oblique_vectorized(WLS, LAYERS, thickness, SUBSTRATE, 30.0, "s")
    with pytest.raises(ValueError, match="thickness"):
        calc_spectrum_oblique_backside_vectorized(WLS, LAYERS, thickness, SUBSTRATE, 30.0, "p")


@pytest.mark.parametrize("n_sub", [0.0, -1.52])
def test_the_oblique_wrappers_refuse_a_substrate_without_a_positive_index(n_sub) -> None:
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    substrate = SUBSTRATE.copy()
    substrate[0] = complex(n_sub, 0.0)
    with pytest.raises(ValueError, match="substrate"):
        calc_spectrum_oblique_vectorized(WLS, LAYERS, THICKNESS, substrate, 30.0, "s")


# =============================================================================
# The preparation of DESIGN's arrays: indices checked once (D108, D114)
# =============================================================================


def _material(nk: np.ndarray) -> SimpleNamespace:
    return SimpleNamespace(get_nk=lambda wls: np.asarray(nk, dtype=np.complex128))


def _prepare(mats: dict, *, ep_back=(), has_back_stack=False, stack_back=()):
    from certus.core.certus_design_cost_context import optim_prepare_stack_nk_back

    stack = [SimpleNamespace(mat="H"), SimpleNamespace(mat="L")]
    return optim_prepare_stack_nk_back(
        mats, stack, WLS, stack_back=stack_back, ep_back=ep_back, has_back_stack=has_back_stack,
        complex_dtype=np.complex128, float_dtype=np.float64,
    )


def _valid_mats() -> dict:
    return {
        "H": _material(np.full(3, complex(2.1, -0.001))),
        "L": _material(np.full(3, complex(1.46, 0.0))),
        "Substrate": _material(SUBSTRATE),
    }


def test_valid_materials_are_prepared_as_before() -> None:
    _mats_nk, substrate, front, rear, rear_thickness = _prepare(_valid_mats())

    assert front.shape == (3, 2)
    assert substrate.shape == (3,)
    assert rear.shape == (3, 0)
    assert rear_thickness.shape == (0,)


@pytest.mark.parametrize("bad", [complex(float("nan"), 0.0), complex(2.0, float("inf"))])
def test_a_material_index_that_is_not_finite_is_refused(bad) -> None:
    mats = _valid_mats()
    nk = np.full(3, complex(2.1, 0.0))
    nk[1] = bad
    mats["H"] = _material(nk)

    with pytest.raises(ValueError, match="finite"):
        _prepare(mats)


def test_a_material_with_negative_extinction_is_refused() -> None:
    mats = _valid_mats()
    mats["L"] = _material(np.full(3, complex(1.46, +0.002)))

    with pytest.raises(ValueError, match="k >= 0"):
        _prepare(mats)


def test_a_substrate_without_a_positive_index_is_refused() -> None:
    mats = _valid_mats()
    mats["Substrate"] = _material(np.full(3, complex(0.0, 0.0)))

    with pytest.raises(ValueError, match="substrate"):
        _prepare(mats)


@pytest.mark.parametrize("bad", [-1.0, float("nan")])
def test_a_rear_thickness_that_is_negative_or_not_finite_is_refused(bad) -> None:
    with pytest.raises(ValueError, match=r"thickness|finite"):
        _prepare(_valid_mats(), ep_back=[100.0, bad], has_back_stack=True,
                 stack_back=[SimpleNamespace(mat="H"), SimpleNamespace(mat="L")])


# =============================================================================
# xyz_from_spectrum (D108)
# =============================================================================


def test_xyz_refuses_a_spectrum_that_is_not_finite() -> None:
    from certus.physics.certus_colorimetry import xyz_from_spectrum

    wls = np.linspace(380.0, 780.0, 81)
    r = np.full(81, 0.5)
    r[10] = np.nan

    with pytest.raises(ValueError, match="finite"):
        xyz_from_spectrum(wls, r)


def test_xyz_refuses_wavelengths_that_do_not_increase() -> None:
    from certus.physics.certus_colorimetry import xyz_from_spectrum

    wls = np.linspace(780.0, 380.0, 81)

    with pytest.raises(ValueError, match="increas"):
        xyz_from_spectrum(wls, np.full(81, 0.5))


def test_xyz_of_a_valid_spectrum_is_unchanged() -> None:
    from certus.physics.certus_colorimetry import xyz_from_spectrum

    wls = np.linspace(380.0, 780.0, 81)
    xyz = xyz_from_spectrum(wls, np.full(81, 1.0))

    assert xyz.shape == (3,)
    assert np.all(np.isfinite(xyz))
    assert xyz[1] == pytest.approx(100.0, rel=1e-2)


# =============================================================================
# The guards of certus_inputs themselves, at their exact boundaries (mutation pilot, 2026-11-19)
# =============================================================================


def test_a_zero_or_positive_thickness_passes_the_guard() -> None:
    from certus.physics.certus_inputs import require_non_negative_thickness

    assert require_non_negative_thickness(d=np.array([0.0, -0.0, 0.5, 120.0])) is None


def test_one_negative_thickness_among_valid_ones_is_refused_by_name() -> None:
    from certus.physics.certus_inputs import require_non_negative_thickness

    with pytest.raises(ValueError, match=r"^d: a thickness must be >= 0 nm$"):
        require_non_negative_thickness(d=np.array([10.0, -1e-12, 20.0]))


def test_a_lossless_or_absorbing_index_passes_the_extinction_guard() -> None:
    from certus.physics.certus_inputs import require_non_negative_extinction

    assert require_non_negative_extinction(n=np.array([complex(2.0, 0.0), complex(2.0, -0.0), complex(1.5, -3.0)])) is None


@pytest.mark.parametrize("gain", [1e-12, 0.5])
def test_one_index_with_negative_extinction_is_refused_by_name(gain) -> None:
    from certus.physics.certus_inputs import require_non_negative_extinction

    message = r"^n: k >= 0 is required \(index n - ik\); a negative extinction is gain$"
    with pytest.raises(ValueError, match=message):
        require_non_negative_extinction(n=np.array([complex(2.0, 0.0), complex(2.0, gain), complex(2.0, 0.0)]))


def test_a_positive_substrate_passes_the_guard() -> None:
    from certus.physics.certus_inputs import require_positive_substrate

    assert require_positive_substrate(s=np.array([complex(1e-9, 0.0), complex(1.52, -0.1)])) is None


@pytest.mark.parametrize("n_sub", [0.0, -0.0, -1.0])
def test_one_substrate_value_without_positive_index_is_refused_by_name(n_sub) -> None:
    from certus.physics.certus_inputs import require_positive_substrate

    with pytest.raises(ValueError, match=r"^s: the substrate index must have n > 0$"):
        require_positive_substrate(s=np.array([complex(1.52, 0.0), complex(n_sub, 0.0), complex(1.52, 0.0)]))


def test_the_physical_substrate_guard_checks_finite_positive_and_extinction() -> None:
    from certus.physics.certus_inputs import require_physical_substrate

    assert require_physical_substrate(s=np.array([complex(1.52, -0.001)])) is None
    with pytest.raises(ValueError, match="finite"):
        require_physical_substrate(s=np.array([complex(np.nan, 0.0)]))
    with pytest.raises(ValueError, match="n > 0"):
        require_physical_substrate(s=np.array([complex(-1.0, 0.0)]))
    with pytest.raises(ValueError, match="k >= 0"):
        require_physical_substrate(s=np.array([complex(1.52, 0.01)]))
