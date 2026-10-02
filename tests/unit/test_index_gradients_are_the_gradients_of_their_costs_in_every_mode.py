"""INDEX's objectives hand the optimiser the gradient of their own cost, in every mode (audit v2, plan S3.2; ETAT D75).

Four objectives drive the fits of INDEX: `TLUObjective` (a Tauc-Lorentz-Urbach law, 7 parameters, thickness included), `IRGlobalObjective` (a Sellmeier law for n and an 8-parameter law for k,
13 parameters, the infrared stage) and the two objectives that refine k of that stage as a spline in log k: `Phase23SplineObjective` (fixed knots) and `Phase23Pass2SplineObjective` (knots that
move). Each has a cost (`__call__`) and an analytic gradient (`gradient`), and a mode for the data (transmission, reflection, both), for the normalisation by the substrate, for an absorbing
substrate and for the frosted glass. A gradient that is not the slope of the cost makes L-BFGS-B stop early or walk away, and nothing fails: the search "converges". `TLUObjective` and the two
spline objectives were only ever tested through mocks; `IRGlobalObjective` in one of its modes (`test_phase2_gradient.py`).

Every mode is compared here with central finite differences of its own cost, at one point, over the whole parameter vector:

    IRGlobalObjective, 3 data types x normalised or not x transparent or absorbing substrate: 1e-6 of the largest component (measured 1e-8)
    the two spline objectives, the same twelve each: 1e-6 (measured 1e-8)
    TLUObjective, the same twelve: 5e-3 (measured 1.4e-4) with a step ten times larger (the cost itself is noisy near 1e-10: its k is a difference of two nearly equal numbers wherever it is small, ETAT D71,
    and a step of 1e-5 turns that noise into a 1e-3 error of the numerical slope; a wrong sign or scale of the gradient is off by 0.1 or more)
    the frosted glass (reflection only, no normalisation): an infinite back face (ETAT D75, decided by the owner on 2026-10-02: only the front surface reflects, nothing comes back from the
    rough back), for the cost and the gradient alike, with the three objectives of the stage and `TLUObjective` alone and with an absorbing substrate, which a frosted glass does not read.
    Before the decision the cost was the plate's (back face included, 0.03 to 0.04 of reflectance more) and the gradient the infinite substrate's: a relative gap of 2.9 for the stage and
    0.046 for `TLUObjective` with an absorbing substrate; the seven tests of this mode were `xfail(strict)` until the cost was changed
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_index_objectives import (
    IRGlobalObjective,
    Phase23Pass2SplineObjective,
    Phase23SplineObjective,
    TLUObjective,
)
from certus.physics.certus_tmm_substrate import calculate_bare_substrate_RT, calculate_bare_substrate_T_absorbing
from certus.utils.certus_index_utils import DataType, sellmeier_2poles_eval_nj

# [A, B1, L1, B2, L2] of the Sellmeier law, then the 8 parameters of the law of k (the point of `test_phase2_gradient.py`)
P_IR = np.array([1.5, 0.5, 0.2, 0.1, 0.1, -1.0, -10.0, -2.0, -15.0, 0.05, 1.0, 0.2, 2.0])
# [thickness, Eg, A, E0, C, Eu, eps_inf]
P_TLU = np.array([150.0, 3.2, 120.0, 4.5, 1.5, 0.15, 3.0])

# the spline objectives: six knots between 0.4 and 2 um carrying log k, and (pass 2) the four internal knots' positions
KNOTS_UM = np.linspace(0.4, 2.0, 6)
LOG_K_AT_THE_KNOTS = np.log([2e-3, 3e-3, 5e-3, 4e-3, 6e-3, 8e-3])
INTERNAL_KNOTS_UM = np.array([0.7, 1.0, 1.3, 1.6])
K_MAX = 0.2

SUBSTRATE_INDEX = 1.52
SUBSTRATE_EXTINCTION = 3e-5
SUBSTRATE_THICKNESS_NM = 1.0e6

DATA_TYPES = [DataType.TRANSMISSION, DataType.REFLECTION, DataType.BOTH]


class IRConfig:
    """The fields of INDEX's configuration that `IRGlobalObjective` reads."""

    def __init__(self, frosted, data_type, normalised, absorbing, k_substrate):
        self.is_frosted_glass = frosted
        self.data_type = data_type
        self.use_normalized = normalised
        self.weight_T = 0.5
        self.weight_R = 0.5
        self.lambda_min = 400
        self.lambda_max = 2000
        self.exclude_min = None
        self.exclude_max = None
        self.has_absorbing_substrate = absorbing
        self.k_sub_data = k_substrate if absorbing else None
        self.substrate_thickness_nm = SUBSTRATE_THICKNESS_NM if absorbing else None


def ir_objective(frosted, data_type, normalised, absorbing):
    n_points = 50
    wavelengths = np.linspace(400.0, 2000.0, n_points)
    n_substrate = np.full(n_points, SUBSTRATE_INDEX)
    k_substrate = np.full(n_points, SUBSTRATE_EXTINCTION)
    if absorbing:
        t_substrate = calculate_bare_substrate_T_absorbing(wavelengths, n_substrate, k_substrate, SUBSTRATE_THICKNESS_NM)
    else:
        t_substrate = calculate_bare_substrate_RT(wavelengths, n_substrate)
    obj = IRGlobalObjective(
        wavelengths,
        np.linspace(0.8, 0.9, n_points),
        np.linspace(0.1, 0.05, n_points),
        n_substrate,
        t_substrate,
        np.full(n_points, 0.08),
        100.0,
        sellmeier_2poles_eval_nj(P_IR[:5], wavelengths / 1000.0),
        IRConfig(frosted, data_type, normalised, absorbing, k_substrate),
    )
    obj.n_tol = 100.0  # the continuity guard with the first stage is not what is tested
    return obj, P_IR


def spline_objective(frosted, data_type, normalised, absorbing):
    base, _ = ir_objective(frosted, data_type, normalised, absorbing)
    return Phase23SplineObjective(base, KNOTS_UM, K_MAX), np.concatenate([P_IR[:5], LOG_K_AT_THE_KNOTS])


def moving_knots_objective(frosted, data_type, normalised, absorbing):
    base, _ = ir_objective(frosted, data_type, normalised, absorbing)
    objective = Phase23Pass2SplineObjective(base, len(KNOTS_UM), KNOTS_UM[0], KNOTS_UM[-1], K_MAX, 0.05)
    return objective, np.concatenate([P_IR[:5], LOG_K_AT_THE_KNOTS, INTERNAL_KNOTS_UM])


def tlu_objective(frosted, data_type, normalised, absorbing):
    n_points = 61
    wavelengths = np.linspace(400.0, 1000.0, n_points)
    target_t = None if (frosted or data_type == DataType.REFLECTION) else 0.8 + 0.02 * np.cos(wavelengths / 70.0)
    target_r = None if (data_type == DataType.TRANSMISSION and not frosted) else 0.12 + 0.02 * np.sin(wavelengths / 90.0)
    obj = TLUObjective(
        wavelengths,
        target_t,
        target_r,
        np.full(n_points, SUBSTRATE_INDEX),
        data_type,
        (50.0, 500.0),
        use_normalized=normalised,
        weight_T=1.0,
        weight_R=1.0,
        is_frosted_glass=frosted,
        has_absorbing_substrate=absorbing,
        k_sub_data=np.full(n_points, SUBSTRATE_EXTINCTION) if absorbing else None,
        substrate_thickness_nm=SUBSTRATE_THICKNESS_NM if absorbing else None,
    )
    return obj, P_TLU


def relative_gap_to_finite_differences(obj, p, relative_step):
    cost = obj(p)
    assert np.isfinite(cost)
    analytic = np.array(obj.gradient(p), copy=True)
    numeric = np.zeros_like(p)
    for i in range(len(p)):
        step = relative_step * max(1.0, abs(p[i]))
        up, down = p.copy(), p.copy()
        up[i] += step
        down[i] -= step
        numeric[i] = (obj(up) - obj(down)) / (2.0 * step)
    assert np.max(np.abs(numeric)) > 1e-6  # a gradient that is zero everywhere would agree with anything
    return float(np.max(np.abs(analytic - numeric)) / np.max(np.abs(numeric)))


@pytest.mark.parametrize("absorbing", [False, True], ids=["transparent", "absorbing"])
@pytest.mark.parametrize("normalised", [False, True], ids=["absolute", "normalised"])
@pytest.mark.parametrize("data_type", DATA_TYPES, ids=lambda d: d.name.lower())
def test_the_infrared_stage_follows_the_slope_of_its_cost(data_type, normalised, absorbing):
    obj, p = ir_objective(False, data_type, normalised, absorbing)
    assert relative_gap_to_finite_differences(obj, p, relative_step=1e-5) < 1e-6


@pytest.mark.parametrize("absorbing", [False, True], ids=["transparent", "absorbing"])
@pytest.mark.parametrize("normalised", [False, True], ids=["absolute", "normalised"])
@pytest.mark.parametrize("data_type", DATA_TYPES, ids=lambda d: d.name.lower())
def test_the_tauc_lorentz_fit_follows_the_slope_of_its_cost(data_type, normalised, absorbing):
    obj, p = tlu_objective(False, data_type, normalised, absorbing)
    assert relative_gap_to_finite_differences(obj, p, relative_step=1e-4) < 5e-3


@pytest.mark.parametrize("absorbing", [False, True], ids=["transparent", "absorbing"])
def test_the_infrared_stage_follows_the_slope_of_its_cost_on_frosted_glass(absorbing):
    obj, p = ir_objective(True, DataType.REFLECTION, False, absorbing)
    assert relative_gap_to_finite_differences(obj, p, relative_step=1e-5) < 1e-6


def test_the_tauc_lorentz_fit_follows_the_slope_of_its_cost_on_frosted_glass():
    obj, p = tlu_objective(True, DataType.REFLECTION, False, False)
    assert relative_gap_to_finite_differences(obj, p, relative_step=1e-4) < 5e-3


def test_the_tauc_lorentz_fit_follows_the_slope_of_its_cost_on_frosted_glass_with_an_absorbing_substrate():
    obj, p = tlu_objective(True, DataType.REFLECTION, False, True)
    assert relative_gap_to_finite_differences(obj, p, relative_step=1e-4) < 5e-3


SPLINE_STAGES = pytest.mark.parametrize("build", [spline_objective, moving_knots_objective], ids=["fixed_knots", "moving_knots"])


@SPLINE_STAGES
@pytest.mark.parametrize("absorbing", [False, True], ids=["transparent", "absorbing"])
@pytest.mark.parametrize("normalised", [False, True], ids=["absolute", "normalised"])
@pytest.mark.parametrize("data_type", DATA_TYPES, ids=lambda d: d.name.lower())
def test_the_spline_stages_follow_the_slope_of_their_cost(data_type, normalised, absorbing, build):
    obj, x = build(False, data_type, normalised, absorbing)
    assert relative_gap_to_finite_differences(obj, x, relative_step=1e-5) < 1e-6


@SPLINE_STAGES
@pytest.mark.parametrize("absorbing", [False, True], ids=["transparent", "absorbing"])
def test_the_spline_stages_follow_the_slope_of_their_cost_on_frosted_glass(absorbing, build):
    obj, x = build(True, DataType.REFLECTION, False, absorbing)
    assert relative_gap_to_finite_differences(obj, x, relative_step=1e-5) < 1e-6
