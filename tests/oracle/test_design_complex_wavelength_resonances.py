"""Physical checks for the optional complex-wavelength DESIGN treatment."""
from __future__ import annotations

import numpy as np
import pytest
from tmm_reference import stack_matrix

from certus.physics.design_resonances import (
    Resonance,
    ResonanceSettings,
    TransmissionBand,
    TransmissionProblem,
    analyze_resonances,
    refine_resonances,
    transmission_denominator,
)


def cavity() -> tuple[TransmissionProblem, np.ndarray]:
    indices = np.array([2.35, 1.45] * 7 + [2.35, 1.45, 2.35] + [1.45, 2.35] * 7)
    thicknesses = 500.37 / (4 * indices)
    thicknesses[15] *= 2
    return TransmissionProblem(indices, 1.52, (TransmissionBand(496., 505., 0., 1.),)), thicknesses


def test_complex_denominator_reuses_the_canonical_matrix_and_matches_the_oracle():
    problem, d = cavity()
    wavelengths = np.array([499 + 1j, 500.37 + 1j, 500.4 - 0.2j, 501 + 0j])
    actual = transmission_denominator(problem, d, wavelengths)
    expected = []
    for wavelength in wavelengths:
        b, c = stack_matrix(problem.indices.astype(complex), d, wavelength) @ np.array([1., 1.52])
        expected.append(b + c)
    np.testing.assert_allclose(actual, expected, rtol=5e-11, atol=5e-11)


def test_a_cavity_peak_hidden_between_nominal_points_is_located_and_counted():
    problem, d = cavity()
    analysis = analyze_resonances(problem, d)
    assert len(analysis.charged_peaks) == 1
    peak = analysis.charged_peaks[0]
    assert peak.wavelength_nm == pytest.approx(500.37, abs=0.1)
    assert peak.height > 0.5
    assert 0 < peak.width_nm < 0.5
    assert analysis.counts[0].located == analysis.counts[0].counted == 1
    assert analysis.charged_mf > 10 * analysis.nominal_mf


def test_refinement_preserves_fixed_layers_input_data_and_declared_bounds():
    problem, d = cavity()
    original = d.copy()
    variable = np.array([14, 15, 16], dtype=np.int64)
    settings = ResonanceSettings(rounds=2, burst=8)
    result = refine_resonances(problem, d, settings=settings, variable_indices=variable,
                               lower_bounds=d * 0.99, upper_bounds=d * 1.01)
    np.testing.assert_array_equal(d, original)
    fixed = np.setdiff1d(np.arange(len(d)), variable)
    np.testing.assert_array_equal(result.thicknesses[fixed], original[fixed])
    assert np.all(result.thicknesses >= d * 0.99)
    assert np.all(result.thicknesses <= d * 1.01)
    assert result.final.charged_mf <= result.initial.charged_mf


def test_an_explicit_zero_round_run_is_an_audit_without_refinement():
    problem, d = cavity()
    result = refine_resonances(problem, d, settings=ResonanceSettings(rounds=0))
    np.testing.assert_array_equal(result.thicknesses.view(np.uint64), d.view(np.uint64))
    assert result.selected_round == 0
    assert result.final.counts[0].counted == 1


def test_a_gain_medium_is_rejected_before_any_complex_continuation():
    problem, _ = cavity()
    indices = problem.indices.astype(complex)
    indices[0] += 0.01j  # n + ik with k > 0 is a gain medium in the n - ik convention
    with pytest.raises(ValueError, match="gain"):
        TransmissionProblem(indices, 1.52, problem.bands)


def _lossy_stack():
    rng = np.random.default_rng(7)
    indices = np.array([2.45, 0.12 - 3.45j, 1.45, 1.8 - 3.33j, 2.15, 1.38, 2.35 - 0.002j, 1.65] * 2)
    return indices, rng.uniform(5., 160., len(indices))


@pytest.mark.parametrize("quantity", ["T", "R"])
def test_the_absorbing_kernel_matches_the_independent_reference(quantity):
    from tmm_reference import rt_stack

    from certus.physics.design_resonances import _res_jac

    indices, d = _lossy_stack()
    problem = TransmissionProblem(indices, 1.52, (TransmissionBand(400., 700., 0.5, 1.),), quantity=quantity)
    wl = np.linspace(400., 700., 31)
    res, _ = _res_jac(problem, d, wl, np.zeros(len(wl)), np.empty(0, dtype=np.int64))
    expected = [rt_stack(w, indices, d, n_sub=1.52)[0 if quantity == "R" else 1] for w in wl]
    np.testing.assert_allclose(res, expected, rtol=1e-11, atol=1e-12)


@pytest.mark.parametrize("quantity", ["T", "R"])
def test_the_absorbing_kernel_jacobian_matches_finite_differences(quantity):
    from certus.physics.design_resonances import _res_jac

    indices, d = _lossy_stack()
    problem = TransmissionProblem(indices, 1.52, (TransmissionBand(400., 700., 0.5, 1.),), quantity=quantity)
    wl = np.linspace(400., 700., 13)
    variable = np.arange(len(d), dtype=np.int64)
    _, jac = _res_jac(problem, d, wl, np.zeros(len(wl)), variable)
    step = 1e-5
    for i in variable:
        up, down = d.copy(), d.copy()
        up[i] += step
        down[i] -= step
        fd = (_res_jac(problem, up, wl, np.zeros(len(wl)), variable[:0])[0]
              - _res_jac(problem, down, wl, np.zeros(len(wl)), variable[:0])[0]) / (2 * step)
        np.testing.assert_allclose(jac[:, i], fd, rtol=1e-5, atol=1e-9)


def test_the_general_kernel_reproduces_the_lossless_design_kernel():
    from certus.physics import design_resonances as native

    problem, d = cavity()
    wl = np.linspace(496., 505., 37)
    target = np.full(len(wl), 0.2)
    variable = np.arange(len(d), dtype=np.int64)
    fast = native._res_jac(problem, d, wl, target, variable)
    general_problem = TransmissionProblem(problem.indices, 1.52, problem.bands, quantity="R")
    r_minus = native._res_jac(general_problem, d, wl, 1. - target, variable)  # R - (1 - target) = (1 - T) - 1 + target
    general = (-r_minus[0], -r_minus[1])
    np.testing.assert_allclose(general[0], fast[0], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(general[1], fast[1], rtol=1e-8, atol=1e-10)


def test_a_wavelength_dependent_target_is_evaluated_between_the_grid_points():
    band = TransmissionBand(400., 500., lambda wl: 0.2 + 0.6 * (wl - 400.) / 100., 10.)
    np.testing.assert_allclose(band.target_at(np.array([400., 455.])), [0.2, 0.53])
    assert band.target_slope(450.) == pytest.approx(0.006)
    with pytest.raises(ValueError, match="fractions"):
        TransmissionBand(400., 500., lambda wl: wl / 100., 10.)


def test_a_hidden_cavity_peak_is_still_located_with_a_weakly_absorbing_layer():
    problem, d = cavity()
    indices = problem.indices.astype(complex)
    indices[15] -= 1e-5j  # weak absorption in the spacer: the pole moves off the axis, the peak remains
    lossy = TransmissionProblem(indices, 1.52, problem.bands)
    analysis = analyze_resonances(lossy, d)
    assert analysis.counts[0].located == analysis.counts[0].counted == 1
    assert len(analysis.charged_peaks) == 1
    lossless_pole = analyze_resonances(problem, d).resonances[0].sigma
    assert analysis.resonances[0].sigma.imag > lossless_pole.imag


def test_an_initial_state_outside_the_ot_budget_is_rejected():
    problem, d = cavity()
    with pytest.raises(ValueError, match="optical-thickness"):
        refine_resonances(problem, d, settings=ResonanceSettings(max_ot_nm=1.))


def test_a_desired_transmission_resonance_is_counted_without_charging_an_error_minimum():
    problem, d = cavity()
    passing = TransmissionProblem(problem.indices, 1.52, (TransmissionBand(496., 505., 1., 1.),))
    analysis = analyze_resonances(passing, d)
    assert analysis.counts[0].located == analysis.counts[0].counted == 1
    assert not analysis.charged_peaks


def test_cancellation_does_not_apply_a_partly_refined_design():
    problem, d = cavity()
    result = refine_resonances(problem, d, cancelled=lambda: True)
    assert result.cancelled
    np.testing.assert_array_equal(result.thicknesses.view(np.uint64), d.view(np.uint64))


def test_the_inner_refinement_follows_a_peak_beyond_the_old_detection_window():
    from certus.physics.design_resonances import _peak_top

    problem, d = cavity()
    peak = analyze_resonances(problem, d).charged_peaks[0]
    factor = 1.02
    moved = Resonance(peak.sigma / factor, peak.wavelength_nm * factor, peak.width_nm * factor, 0)
    wavelength, height = _peak_top(problem, d * factor, moved, restrict_band=False)
    assert wavelength > problem.bands[0].upper_nm
    assert wavelength == pytest.approx(500.37 * factor, abs=0.1)
    assert height > 0.5


def test_a_missing_localization_is_not_certified_by_a_zero_peak_list(monkeypatch):
    from certus.physics import design_resonances as native

    problem, d = cavity()
    monkeypatch.setattr(native, "_locate", lambda *_args: ())
    with pytest.raises(RuntimeError, match="0 located, 1/1 counted"):
        analyze_resonances(problem, d)


def test_the_optimizer_receives_the_total_derivative_at_the_moving_real_maximum(monkeypatch):
    from certus.physics import design_resonances as native

    problem, d = cavity()
    original_solver = native.least_squares
    checked = []

    def solver(fun, x0, *, jac, **kwargs):
        step = 1e-4
        columns = []
        for i in range(len(x0)):
            delta = np.zeros_like(x0)
            delta[i] = step
            columns.append((fun(x0 + delta) - fun(x0 - delta)) / (2 * step))
        expected = np.column_stack(columns)
        np.testing.assert_allclose(jac(x0), expected, rtol=3e-3, atol=1e-7)
        checked.append(True)
        return original_solver(fun, x0, jac=jac, **kwargs)

    monkeypatch.setattr(native, "least_squares", solver)
    refine_resonances(problem, d, settings=ResonanceSettings(rounds=1, burst=1),
                      variable_indices=np.array([0, 1, 15], dtype=np.int64))
    assert checked == [True]
