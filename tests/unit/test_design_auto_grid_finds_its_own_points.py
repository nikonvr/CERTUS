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
    LAYERS_PER_NYQUIST_MIN,
    auto_grid_tot_nm,
    base_grid,
    estimate_layers_and_tot,
    layers_tot_ceiling_nm,
    merge_bands,
    nyquist_count,
    points_in_bands,
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


# A layer ceiling N gives a TOT ceiling by the degrees of freedom (owner, 2026-11-21): N layers shape about
# 4 * TOT * sum(delta_sigma) * r values, r = N / (4 TOT sum(delta_sigma)) of the free envelope of the 50/50 beamsplitter
# being 0.69 to 1.37 (report questions_design_2026-11-13, section 2.2); its least value bounds the TOT from above. An
# empirical estimate: a TOT ceiling given by the user wins over it.


def test_a_layer_ceiling_gives_a_tot_ceiling_by_the_degrees_of_freedom():
    assert LAYERS_PER_NYQUIST_MIN == 0.69
    sigma = 1.0 / 400.0 - 1.0 / 1200.0
    assert layers_tot_ceiling_nm([(400.0, 1200.0)], 34) == pytest.approx(34 / (4.0 * 0.69 * sigma), rel=1e-12)
    width = (1.0 / 400.0 - 1.0 / 500.0) + (1.0 / 600.0 - 1.0 / 700.0)
    assert layers_tot_ceiling_nm([(400.0, 500.0), (600.0, 700.0)], 10) == pytest.approx(10 / (4.0 * 0.69 * width), rel=1e-12)
    overlapping = layers_tot_ceiling_nm([(400.0, 500.0), (450.0, 600.0)], 10)
    assert overlapping == pytest.approx(layers_tot_ceiling_nm([(400.0, 600.0)], 10), rel=1e-12), "a band counts once"
    for layers, bands in ((None, [(400.0, 1200.0)]), (0, [(400.0, 1200.0)]), (34, []), (34, [(500.0, 500.0)])):
        assert layers_tot_ceiling_nm(bands, layers) == 0.0


def test_the_13_layer_beamsplitter_of_the_envelope_is_below_its_tot_ceiling():
    # 19.02 QWOT at 500 nm for N = 13 (envelope of 2026-10-26); its own r is 0.82
    assert layers_tot_ceiling_nm([(400.0, 1200.0)], 13) / 125.0 > 19.02


def test_a_tot_ceiling_given_wins_over_the_estimate_from_the_layers_never_below_the_design():
    bands = [(400.0, 1200.0)]
    from_layers = layers_tot_ceiling_nm(bands, 34)
    assert auto_grid_tot_nm(1000.0, None, 500.0, max_layers=34, bands=bands) == from_layers
    assert auto_grid_tot_nm(1000.0, 30, 500.0, max_layers=34, bands=bands) == pytest.approx(3750.0)
    assert auto_grid_tot_nm(1000.0, 80, 500.0, max_layers=34, bands=bands) == pytest.approx(10000.0)
    assert auto_grid_tot_nm(9000.0, None, 500.0, max_layers=34, bands=bands) == 9000.0
    assert auto_grid_tot_nm(9000.0, 30, 500.0, max_layers=34, bands=bands) == 9000.0


def test_without_a_layer_ceiling_the_former_rule_holds_to_the_bit():
    for stack, qwot in ((1000.0, None), (1000.0, 30), (4000.0, 30), (1234.5678, 17.25)):
        before = auto_grid_tot_nm(stack, qwot, 500.0)
        assert auto_grid_tot_nm(stack, qwot, 500.0, max_layers=None, bands=[(400.0, 1200.0)]) == before
        assert auto_grid_tot_nm(stack, qwot, 500.0, max_layers=34) == before, "no band, no layer ceiling"


def test_points_in_bands_counts_the_grid_inside_each_band():
    grid = base_grid([(400.0, 500.0), (600.0, 700.0)], 2000.0)
    counts = points_in_bands([(400.0, 500.0), (600.0, 700.0), (450.0, 650.0)], grid)
    assert counts[0] + counts[1] == grid.size
    assert counts[2] == np.count_nonzero((grid >= 450.0) & (grid <= 650.0))


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


def test_final_selection_uses_the_refined_grid_merit(monkeypatch, qapp):
    from certus.core import certus_design_worker_utils
    from certus.physics import design_fast_kernels
    from certus.workers import certus_design_workers
    from certus_physics import Layer

    material = SimpleNamespace(n4=1.5, get_nk=lambda wl: np.full(len(wl), 1.5 + 0j))
    wavelengths = np.array([500.0, 550.0, 600.0])
    worker = certus_design_workers.OptimWorker({
        "mats": {"H": material, "Substrate": material}, "stack": [Layer(mat="H", qwot=1.0)],
        "ep0": np.array([100.0]), "wls": wavelengths, "tgts": [Target(500.0, 600.0, 0.5, 0.5)],
        "l0": 550.0, "memetic_children": 1, "auto_wavelength_grid": True,
    })
    monkeypatch.setattr(worker, "_prepare_pglobal_inputs", lambda **_: (1, None, None, 1))
    monkeypatch.setattr(worker, "_prepare_optimizer_entry", lambda **_: (np.array([100.0]), None, None, None, None))
    monkeypatch.setattr(worker, "_run_pglobal_setup", lambda *_: (None, 0.0))

    def global_result(**_kwargs):
        worker.best_rmse_seen = worker.best_rmse_final = 0.01
        worker.best_ep_final = np.array([100.0])
        return SimpleNamespace(x=np.array([100.0]), y=0.0001)

    def refine(**kwargs):
        grid = np.array([500.0, 525.0, 550.0, 600.0])
        return grid, material.get_nk(grid), material.get_nk(grid)[:, None], np.empty((4, 0)), np.full(4, 0.5), np.ones(4)

    monkeypatch.setattr(worker, "_run_memetic_global", global_result)
    monkeypatch.setattr(certus_design_worker_utils, "maybe_refine_grid_auto", refine)
    monkeypatch.setattr(design_fast_kernels, "prepare_normal_fast_context", lambda **_: {"has_weak_k": False})
    monkeypatch.setattr(worker, "_evaluate_thicknesses", lambda *_args, **_kwargs: 0.16)
    monkeypatch.setattr(certus_design_workers, "run_coord_descent_5cycles", lambda **_: (np.array([120.0]), 0.04, 0.2))
    results = []
    worker.signals.finished.connect(results.append)

    worker.run()

    assert len(results) == 1
    np.testing.assert_array_equal(results[0]["ep"], [120.0])
    assert results[0]["rmse"] == pytest.approx(0.2)
