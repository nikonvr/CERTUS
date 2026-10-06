"""DESIGN at normal incidence: the cost and its analytic gradient speak of the same substrate.

`cost_numba_fast` (what the optimizer minimizes, and what is reported) reads an absorbing substrate through
`calculate_RT_no_backside` or `calc_spectrum_full_exact`, which agree with `tests/oracle/tmm_reference.py`
to 1e-15. `compute_gradient_all_layers_analytic` did not, without a back stack: its analytic kernel computes
`T` from the substrate side (the substrate as the incident medium of the stack), which is the transmittance
only when the substrate does not absorb. Measured on 2026-09-30 against the oracle (mean of T^2 over eight
wavelengths): 1.8e-5 off at k = 1e-4, 1.8e-3 at k = 1e-2, 5.2e-2 at k = 0.3, 0.16 at k = 1.5. The optimizer
followed the gradient of another objective than the one it reported.

The weights of DESIGN average 1 (`spectral_rmse_weights`), and these tests used weights of mean 1 because the
gradient of the back-stack branch divided by the number of points where the cost divides by the sum of the
weights (PHY-12, D45 in docs/ETAT.md): the gradient was then too large by the mean weight. The last test pins the
fix with weights that are neither normalised nor all positive.
"""

from __future__ import annotations

import numpy as np
import pytest

WLS = np.array([470.0, 560.0, 640.0, 760.0, 900.0, 1100.0, 1300.0, 1500.0])


def _stack(n_layers: int, seed: int):
    rng = np.random.default_rng(seed)
    return rng.uniform(1.3, 2.4, (len(WLS), n_layers)).astype(np.complex128), rng.uniform(40.0, 180.0, n_layers)


def _substrate(k: float) -> np.ndarray:
    return np.array([complex(1.50 + 0.01 * i, -k) for i in range(len(WLS))])


@pytest.mark.parametrize("with_back_stack", [False, True])
@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4, 1e-2, 0.3])
def test_the_cost_and_the_analytic_gradient_agree_with_an_absorbing_substrate(k, with_back_stack) -> None:
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
    from certus.physics.gradient_utils import cost_numba_fast

    n_layers = 3
    n, d = _stack(n_layers, seed=37)
    n_back, d_back = _stack(2, seed=41) if with_back_stack else (np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0))
    n_sub = _substrate(k)
    rng = np.random.default_rng(43)
    targets = rng.uniform(0.2, 0.9, len(WLS))
    weights = rng.uniform(0.5, 1.0, len(WLS))
    weights /= weights.mean()
    var = np.arange(n_layers, dtype=np.int64)

    def cost(thicknesses):
        return cost_numba_fast(thicknesses, n, n_sub, WLS, targets, weights, 1.0, with_back_stack, n_back, d_back)

    value, gradient = compute_gradient_all_layers_analytic(
        d, n, n_sub, WLS, targets, weights, 1.0, with_back_stack, n_back, d_back, var
    )

    assert value == pytest.approx(cost(d), rel=1e-10)
    step = 1e-3
    for j in range(n_layers):
        up, down = d.copy(), d.copy()
        up[j] += step
        down[j] -= step
        assert gradient[j] == pytest.approx((cost(up) - cost(down)) / (2 * step), rel=1e-5, abs=1e-9)


@pytest.mark.parametrize("k", [1e-4, 1e-2, 0.3, 1.5])
def test_the_objective_of_the_gradient_is_the_transmittance_of_the_oracle(k) -> None:
    from tmm_reference import rt_stack

    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

    n, d = _stack(3, seed=47)
    n_sub = _substrate(k)
    no_target = np.zeros(len(WLS))
    ones = np.ones(len(WLS))

    value, _gradient = compute_gradient_all_layers_analytic(
        d, n, n_sub, WLS, no_target, ones, 1.0, False, np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0),
        np.arange(3, dtype=np.int64),
    )

    transmittance = np.array([rt_stack(float(WLS[i]), n[i], d, n_inc=1.0 + 0j, n_sub=n_sub[i])[1] for i in range(len(WLS))])
    assert value == pytest.approx(np.mean(transmittance**2), abs=1e-12)


def test_a_substrate_without_absorption_keeps_the_kernel_that_always_ran(monkeypatch) -> None:
    # C1: the analytic kernel of the front-only branch is untouched for a real substrate.
    import certus.physics.gradient_oblique as module

    used = []
    real_kernel = module._compute_gradient_analytic_kernel

    def spy(*args):
        used.append("plain")
        return real_kernel(*args)

    monkeypatch.setattr(module, "_compute_gradient_analytic_kernel", spy)
    n, d = _stack(2, seed=53)
    args = (d, n, None, WLS, np.full(len(WLS), 0.5), np.ones(len(WLS)), 1.0, False)
    empty = (np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0), np.arange(2, dtype=np.int64))

    module.compute_gradient_all_layers_analytic(*args[:2], _substrate(0.0), *args[3:], *empty)
    module.compute_gradient_all_layers_analytic(*args[:2], _substrate(1e-4), *args[3:], *empty)

    assert used == ["plain"]


@pytest.mark.parametrize("k", [0.0, 1e-6])
def test_with_a_back_stack_the_gradient_is_the_derivative_of_the_cost_whatever_the_weights(k) -> None:
    """Weights of 1 and 3 and points outside the targets (weight 0), as DESIGN builds them for two bands: the
    gradient divided by the number of valid points was 1.6 times too large here (sum of weights / count)."""
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
    from certus.physics.gradient_utils import cost_numba_fast

    n, d = _stack(3, seed=53)
    n_back, d_back = _stack(2, seed=59)
    n_sub = _substrate(k)
    targets = np.random.default_rng(61).uniform(0.2, 0.9, len(WLS))
    weights = np.array([1.0, 1.0, 3.0, 3.0, 0.0, 1.0, 3.0, 0.0])
    var = np.arange(3, dtype=np.int64)

    def cost(thicknesses):
        return cost_numba_fast(thicknesses, n, n_sub, WLS, targets, weights, 1.0, True, n_back, d_back)

    value, gradient = compute_gradient_all_layers_analytic(d, n, n_sub, WLS, targets, weights, 1.0, True, n_back, d_back, var)

    assert value == pytest.approx(cost(d), rel=1e-10)
    step = 1e-3
    for j in range(3):
        up, down = d.copy(), d.copy()
        up[j] += step
        down[j] -= step
        assert gradient[j] == pytest.approx((cost(up) - cost(down)) / (2 * step), rel=1e-5, abs=1e-9)
