"""In INDEX's frosted-glass mode the gradient of the IR-global stage is not the gradient of its cost (audit v2, plan S3.2; ETAT D75).

`IRGlobalObjective` is what the IR stage of INDEX minimises (13 parameters: a Sellmeier law for n, an 8-parameter law for k). Its cost, `__call__`, takes the reflectance of the film from
`calculate_transmission_single`: the film on a plate whose back face reflects (the "plate" of the oracle). Its gradient, `gradient`, takes it from
`calculate_reflection_infinite_substrate_single`, a film on a substrate that goes on for ever, when `is_frosted_glass` is on (the radio button is described for "opaque / frosted glass
substrates where only reflectance (R) is measured", and the first tooltip written in the code, overwritten by that one, read "Infinite-substrate model, reflectance only"). Two models, one
search: L-BFGS-B follows a slope that is not the slope of the surface it is on. Outside the frosted mode the two agree to 7e-8.

The first test is the control: the same objective, the same data, the same parameters, standard mode, and the gradient is the finite-difference gradient of the cost. The second is what the
frosted mode should satisfy and does not (relative error about 2.5, measured 2026-10-01): it is `xfail(strict)`, so that the day the cost or the gradient is changed - which one is right is the
owner's decision, ETAT D75 - the test turns red and the marker has to go.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_index_objectives import IRGlobalObjective
from certus.utils.certus_index_utils import DataType, sellmeier_2poles_eval_nj

# [A, B1, L1, B2, L2] of the Sellmeier law, then the 8 parameters of the law of k (the same point as `test_phase2_gradient.py`)
P0 = np.array([1.5, 0.5, 0.2, 0.1, 0.1, -1.0, -10.0, -2.0, -15.0, 0.05, 1.0, 0.2, 2.0])


class Config:
    """The fields of INDEX's configuration that `IRGlobalObjective` reads."""

    def __init__(self, frosted):
        self.is_frosted_glass = frosted
        self.data_type = DataType.REFLECTION
        self.use_normalized = False
        self.weight_T = 0.5
        self.weight_R = 0.5
        self.lambda_min = 400
        self.lambda_max = 2000
        self.exclude_min = None
        self.exclude_max = None
        self.has_absorbing_substrate = False
        self.k_sub_data = None
        self.substrate_thickness_nm = None


def objective(frosted):
    wavelengths = np.linspace(400.0, 2000.0, 50)
    n_reference = sellmeier_2poles_eval_nj(P0[:5], wavelengths / 1000.0)
    obj = IRGlobalObjective(
        wavelengths,
        np.linspace(0.8, 0.9, 50),
        np.linspace(0.1, 0.05, 50),
        np.full(50, 1.5),
        np.full(50, 0.92),
        np.full(50, 0.08),
        100.0,
        n_reference,
        Config(frosted),
    )
    obj.n_tol = 100.0  # the continuity guard with the first stage is not what is tested
    return obj


def relative_gap_to_finite_differences(frosted):
    obj = objective(frosted)
    analytic = np.array(obj.gradient(P0), copy=True)
    numeric = np.zeros_like(P0)
    for i in range(len(P0)):
        step = 1e-5 * max(1.0, abs(P0[i]))
        up, down = P0.copy(), P0.copy()
        up[i] += step
        down[i] -= step
        numeric[i] = (obj(up) - obj(down)) / (2.0 * step)
    return float(np.max(np.abs(analytic - numeric)) / np.max(np.abs(numeric)))


def test_in_the_standard_mode_the_gradient_is_the_gradient_of_the_cost():
    assert relative_gap_to_finite_differences(frosted=False) < 1e-5


@pytest.mark.xfail(
    strict=True,
    reason="D75: the cost of the frosted mode is the plate (back face included), its gradient the infinite substrate (measured relative gap 2.5)",
)
def test_in_the_frosted_glass_mode_the_gradient_is_the_gradient_of_the_cost():
    assert relative_gap_to_finite_differences(frosted=True) < 1e-5
