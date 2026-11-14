"""The wavelength grid of DESIGN that finds its own points (`certus.core.certus_design_auto_grid`).

A target gives only lambda_min and lambda_max. The base grid takes `oversampling * 4 * TOT * delta_sigma` intervals per
band (the Nyquist count of 1/T); `refine_grid` adds points where Simpson and the trapezoid disagree on the merit, and
stops when their summed gap is below the tolerance. These tests use functions whose integral is known, so that the
error is measured, not estimated; the physics of a real stack is in the report of 2026-11-13.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.core.certus_design_auto_grid import (
    auto_grid_tot_nm,
    base_grid,
    estimate_layers_and_tot,
    merge_bands,
    nyquist_count,
    refine_grid,
    target_values_and_weights,
)
from certus_physics import Target, prepare_targets_vectorized


def lorentzian(center_nm: float, width: float):
    """A peak of half-width `width` in ln(lambda), and its exact mean over a band in ln(lambda)."""

    def f(lam: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + ((np.log(lam) - np.log(center_nm)) / width) ** 2)

    def mean(lo: float, hi: float) -> float:
        u0, u1, uc = np.log(lo), np.log(hi), np.log(center_nm)
        return width * (np.arctan((u1 - uc) / width) - np.arctan((u0 - uc) / width)) / (u1 - u0)

    return f, mean


def test_the_base_grid_has_the_nyquist_count_of_its_tot():
    tot = 3000.0
    grid = base_grid([(400.0, 1200.0)], tot, oversampling=3.0)
    assert grid.size == int(np.ceil(3.0 * nyquist_count(400.0, 1200.0, tot))) + 1
    assert grid[0] == pytest.approx(400.0)
    assert grid[-1] == pytest.approx(1200.0)
    np.testing.assert_allclose(np.diff(1.0 / grid), np.diff(1.0 / grid)[0], rtol=1e-9)


def test_a_thin_stack_still_gets_the_least_number_of_points():
    assert base_grid([(500.0, 510.0)], 10.0).size == 9


def test_separate_bands_keep_their_gap_and_touching_ones_merge():
    assert merge_bands([(600.0, 700.0), (400.0, 500.0), (500.0, 550.0)]) == [(400.0, 550.0), (600.0, 700.0)]
    grid = base_grid([(400.0, 500.0), (600.0, 700.0)], 2000.0)
    assert not np.any((grid > 500.0) & (grid < 600.0))


def test_a_resolved_merit_adds_no_point():
    grid = base_grid([(400.0, 800.0)], 500.0)
    result = refine_grid([(400.0, 800.0)], grid, lambda lam: 0.25 + 0.0 * lam)
    assert result.converged
    assert result.rounds == 0
    np.testing.assert_array_equal(result.wavelengths, grid)
    assert result.merit == pytest.approx(0.25)


def test_a_narrow_peak_gets_points_until_its_merit_is_within_the_tolerance():
    f, mean = lorentzian(553.0, 2e-4)
    grid = base_grid([(500.0, 600.0)], 2000.0)
    exact = mean(500.0, 600.0)
    result = refine_grid([(500.0, 600.0)], grid, f, rel_tol=0.01)
    assert result.converged
    assert result.merit == pytest.approx(exact, rel=0.02)
    assert set(grid) <= set(result.wavelengths), "points are only added"
    assert result.wavelengths.size < 400, "and only where they are needed"


def test_points_are_never_put_in_a_gap_between_bands():
    f, _mean = lorentzian(500.0, 5e-4)
    result = refine_grid([(400.0, 500.0), (600.0, 700.0)], base_grid([(400.0, 500.0), (600.0, 700.0)], 1000.0), f)
    assert not np.any((result.wavelengths > 500.0) & (result.wavelengths < 600.0))


def test_a_line_between_two_nodes_is_missed_unless_it_is_anchored():
    center, width = 550.123, 1e-5  # a Gaussian in ln(lambda), without tails to see it from the nodes
    exact = width * np.sqrt(np.pi) / np.log(1.2)

    def f(lam: np.ndarray) -> np.ndarray:
        return np.exp(-(((np.log(lam) - np.log(center)) / width) ** 2))

    grid = base_grid([(500.0, 600.0)], 500.0)
    blind = refine_grid([(500.0, 600.0)], grid, f, abs_tol=1e-12)
    anchored = refine_grid([(500.0, 600.0)], grid, f, anchors=[center], abs_tol=1e-12)
    assert blind.merit < 0.01 * exact, "the documented limit: a line narrower than the spacing is not seen"
    assert anchored.merit == pytest.approx(exact, rel=0.05)


def test_the_point_budget_is_kept_and_said():
    f, _mean = lorentzian(553.0, 1e-5)
    result = refine_grid([(500.0, 600.0)], base_grid([(500.0, 600.0)], 100.0), f, max_points=60)
    assert result.wavelengths.size <= 60
    assert not result.converged


def test_the_target_values_are_those_of_the_cost():
    targets = [Target(400.0, 700.0, 0.2, 0.8, 2.0), Target(650.0, 900.0, 0.5, 0.5, 1.0), Target(950.0, 990.0, 0.1, 0.1, 1.0, False)]
    wls = np.linspace(380.0, 1000.0, 157)
    vals, weights = target_values_and_weights(targets, wls)
    cost_vals, cost_weights = prepare_targets_vectorized(wls, targets)
    np.testing.assert_allclose(vals, cost_vals, rtol=0, atol=1e-15)
    np.testing.assert_array_equal(weights > 0, cost_weights > 0)
    assert set(np.unique(weights)) == {0.0, 1.0, 2.0}


def test_the_contrast_estimate_of_the_50_50_beamsplitter():
    estimate = estimate_layers_and_tot([Target(400.0, 1200.0, 0.5, 0.5)], 2.35, 1.45)
    assert estimate.layers == pytest.approx(13.05, abs=0.01)
    assert estimate.tot_nm / 125.0 == pytest.approx(19.0, abs=0.01), "QWOT at 500 nm"
    assert estimate.nyquist == pytest.approx(nyquist_count(400.0, 1200.0, estimate.tot_nm))


def test_an_antireflection_has_no_contrast_estimate():
    assert estimate_layers_and_tot([Target(400.0, 700.0, 1.0, 1.0)], 2.35, 1.45).layers == 0.0


def test_the_grid_resolves_the_larger_of_the_design_and_the_ceiling():
    assert auto_grid_tot_nm(1000.0, None, 500.0) == 1000.0
    assert auto_grid_tot_nm(1000.0, 30, 500.0) == pytest.approx(3750.0)


@pytest.mark.parametrize("has_back_calc", [False, True])
def test_refinement_samples_the_transmission_of_the_selected_geometry(monkeypatch, has_back_calc):
    from certus.core import certus_design_auto_grid
    from certus.core.certus_design_worker_utils import maybe_refine_grid_auto
    from certus.physics import certus_tmm_matrix, certus_tmm_oblique

    wl = np.array([500.0, 550.0, 600.0])
    refined_wl = np.array([500.0, 525.0, 550.0, 600.0])
    material = SimpleNamespace(get_nk=lambda points: np.full(len(points), 1.5 + 0j))
    substrate = material.get_nk(wl)
    front = substrate[:, None]
    back = np.empty((len(wl), 0), dtype=np.complex128)
    tgts = [Target(500.0, 600.0, 0.5, 0.5, 1.0)]
    vals, weights = prepare_targets_vectorized(wl, tgts)

    monkeypatch.setattr(certus_tmm_matrix, "calculate_RT_no_backside", lambda *_: (None, np.full(len(wl), 0.5)))
    monkeypatch.setattr(certus_tmm_oblique, "calc_spectrum_full_oblique_exact", lambda *_: (None, np.full(len(wl), 0.75)))

    def refine(_bands, _wl, squared_residual, **_kwargs):
        np.testing.assert_array_equal(squared_residual(wl), np.full(len(wl), 0.0625 if has_back_calc else 0.0))
        return certus_design_auto_grid.GridRefinement(refined_wl, 0.0, 0.0, 1, 3, True)

    monkeypatch.setattr(certus_design_auto_grid, "refine_grid", refine)
    result = maybe_refine_grid_auto(
        ep_current=np.array([100.0]), mats={"Substrate": material, "H": material},
        stack=[SimpleNamespace(mat="H")], tgts=tgts, wls=wl, float_dtype=np.float64, complex_dtype=np.complex128,
        has_back_calc=has_back_calc, has_back_stack=False, stack_back=[], d_back=np.empty(0),
        n_sub=substrate, n_layers_T=front, n_back_T=back, tgt_vals=vals, tgt_weights=weights, rel_tol=0.01,
    )
    np.testing.assert_array_equal(result[0], refined_wl)
    assert all(len(array) == len(refined_wl) for array in result)
