"""FIELD's peak and reflection tangents differentiate its production field traces."""

import numpy as np
import pytest

from certus.core.certus_field_core import calculate_opt_metrics
from certus.core.certus_field_gradient import field_metric_gradients


@pytest.mark.parametrize("polarization", [0, 1, 2])
@pytest.mark.parametrize("angle", [0.0, 0.67])
@pytest.mark.parametrize("wavelength", [520.0, 843.0])
@pytest.mark.parametrize("points", [5, 50])
def test_peaks_and_reflectance_match_finite_differences(polarization, angle, wavelength, points):
    factors = np.array([0.83, 1.23, 0.51, 0.72, 1.41])
    types = [0, 1, 1, 0, 1]
    args = (2.3, 1.45, 1.52, 650.0)
    rest = (types, 1.1, points, angle, polarization, wavelength)
    analytic = np.asarray(field_metric_gradients(*args, factors, *rest))
    numeric = np.empty_like(analytic)
    for layer in range(len(factors)):
        up, down = factors.copy(), factors.copy()
        up[layer] += 1e-6
        down[layer] -= 1e-6
        upper = calculate_opt_metrics(*args, up, *rest)
        lower = calculate_opt_metrics(*args, down, *rest)
        numeric[:, layer] = [(upper[key] - lower[key]) / 2e-6 for key in ("R", "max_peak_1", "max_peak_2")]
    np.testing.assert_allclose(analytic, numeric, rtol=3e-5, atol=2e-7)


@pytest.mark.parametrize("min_field", [False, True])
@pytest.mark.parametrize("range_r", [(1.0, 1.0), (0.9, 0.95), (0.01, 0.02)])
@pytest.mark.parametrize("polarization", [0, 1, 2])
def test_complete_merit_gradient_follows_the_active_wavelength(min_field, range_r, polarization, monkeypatch):
    import scipy.optimize

    from certus.workers.certus_field_workers import _field_gradient_options, top_level_objective_function
    from certus.workers.certus_field_workers_dto import FieldParamsDTO

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("The analytic path fell back to finite differences")

    monkeypatch.setattr(scipy.optimize, "approx_fprime", unexpected_fallback)

    factors = np.array([0.83, 1.23, 0.51, 0.72, 1.41])
    params = FieldParamsDTO(n1_rs=[2.3, 2.3], n2_rs=[1.45, 1.45], nSub_rs=[1.52, 1.52],
                           n_supers=[1.0, 1.0], l0=650.0, lambda_calcs=[520.0, 843.0],
                           emp_factors=factors, layer_types=[0, 1, 1, 0, 1], theta_inc=0.67,
                           seuil_int_1=0.2, seuil_int_2=0.3, alpha=3.0, integral_points=50,
                           rmin=range_r[0], rmax=range_r[1], min_field_active=min_field,
                           pol_flag=polarization, analytic_gradient=True)

    def cost(x):
        return top_level_objective_function(
            x, params.n1_rs, params.n2_rs, params.nSub_rs, params.l0, params.seuil_int_1,
            params.seuil_int_2, params.alpha, params.integral_points, params.n_supers,
            params.theta_inc, params.pol_flag, params.lambda_calcs, params.layer_types,
            params.rmin, params.rmax, params.min_field_active,
        )

    analytic = _field_gradient_options(cost, params)["jac"](factors)
    numeric = np.empty_like(factors)
    for layer in range(len(factors)):
        up, down = factors.copy(), factors.copy()
        up[layer] += 1e-6
        down[layer] -= 1e-6
        numeric[layer] = (cost(up) - cost(down)) / 2e-6
    np.testing.assert_allclose(analytic, numeric, rtol=3e-5, atol=2e-6)


def test_cleanup_gradient_uses_the_merged_stack(monkeypatch):
    from types import SimpleNamespace

    from certus.workers import certus_field_workers as workers
    from certus.workers.certus_field_workers_dto import FieldParamsDTO

    params = FieldParamsDTO(n1_rs=[2.3], n2_rs=[1.45], nSub_rs=[1.52], n_supers=[1.0],
                           l0=650.0, lambda_calcs=[520.0], layer_types=[0, 1, 0],
                           emp_factors=[0.8, 0.001, 1.1], analytic_gradient=True,
                           alpha=0.2, maxiter=20)
    minimize = workers.minimize
    dimensions = []

    def inspect(fun, x, **kwargs):
        dimensions.append(len(x))
        grad = kwargs["jac"](x)
        step = 1e-6
        numeric = (fun(x + step) - fun(x - step)) / (2 * step)
        assert grad[0] == pytest.approx(numeric, rel=3e-5, abs=2e-6)
        return minimize(fun, x, **kwargs)

    monkeypatch.setattr(workers, "minimize", inspect)
    _, types, cleaned, cost = workers.FieldWorkerThread._clean_and_reoptimize(
        SimpleNamespace(_is_running=True), params.emp_factors, params.layer_types, 0.2, params
    )
    assert cleaned
    assert types == [0]
    assert dimensions == [1]
    assert np.isfinite(cost)
