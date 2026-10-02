"""A frosted glass is an infinite back face: INDEX's frosted mode reads the front surface alone (audit v2, plan S3.2; ETAT D75).

A glass whose back face is ground returns nothing from it: the substrate goes on for ever and only the front surface of the film reflects. The owner settled it on 2026-10-02 after the audit
had found the frosted mode of INDEX split in two: its cost took the reflectance of a PLATE (the film on a glass whose back face reflects, 0.03 to 0.04 more) through
`calculate_reflection_array`, documented as "front-surface" and routed through `calculate_transmission_single`, while its gradient took the infinite substrate. The cost is now the front surface
too, and the gradient test (`test_index_gradients_are_the_gradients_of_their_costs_in_every_mode.py`) keeps the two together.

What is pinned here, against `tests/oracle/tmm_reference.py` (`rt_stack` for the front surface alone, `rt_plate_incoherent` for the plate):

    `_compute_RT_from_config`, the one function the live plot, the export and the fit read the model through: the frosted glass is the front surface, T and the substrate reference are
    not defined, and an absorbing substrate is not read; the polished glass is still the plate
    the cost of the stage that follows the first fit (`IRGlobalObjective`) and of the Tauc-Lorentz fit (`TLUObjective`): zero when the data are the front surface of the model, not zero
    when they are the plate's; and the polished glass, with the plate's data, still zero
    the pointwise cost of the first search (`_point_cost_kernel`)
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from certus.core.certus_index_core import _point_cost_kernel
from certus.core.certus_index_objectives import IRGlobalObjective, TLUObjective
from certus.utils.certus_index_utils import DataType, k_law_8p_eval, sellmeier_2poles_eval_nj
from certus.workers.certus_index_workers import _compute_RT_from_config
from certus_physics import _compute_tlu_derivatives_kernel, calculate_bare_substrate_RT

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

SUBSTRATE_INDEX = 1.52
SUBSTRATE_THICKNESS = 1.0e6


def front_surface(wavelengths, n, k, thickness, n_sub=SUBSTRATE_INDEX):
    """R of a film on an infinite substrate, by the oracle: nothing comes back from the back face."""
    return np.array([oracle.rt_stack(float(w), [complex(n_i, -k_i)], [float(thickness)], 1.0 + 0.0j, complex(n_sub, 0.0))[0] for w, n_i, k_i in zip(wavelengths, n, k, strict=True)])


def plate(wavelengths, n, k, thickness, n_sub=SUBSTRATE_INDEX):
    """R of the same film on a plate whose back face reflects, by the oracle."""
    return np.array(
        [
            oracle.rt_plate_incoherent(float(w), [complex(n_i, -k_i)], [float(thickness)], [], [], complex(n_sub, 0.0), 0.0, True, SUBSTRATE_THICKNESS)[0]
            for w, n_i, k_i in zip(wavelengths, n, k, strict=True)
        ]
    )


def random_film(count=30, seed=5):
    rng = np.random.default_rng(seed)
    return rng.uniform(300.0, 1800.0, count), rng.uniform(1.4, 3.0, count), np.where(rng.random(count) < 0.4, 0.0, rng.uniform(0.0, 0.6, count))


def config(frosted, absorbing=False):
    return SimpleNamespace(
        is_frosted_glass=frosted,
        has_absorbing_substrate=absorbing,
        k_sub_data=np.full(30, 3e-5) if absorbing else None,
        substrate_thickness_nm=SUBSTRATE_THICKNESS if absorbing else None,
    )


# --- the model the plot, the export and the fit read ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("thickness", [0.0, 80.0, 250.0, 900.0])
def test_the_frosted_glass_is_the_front_surface_of_the_oracle(thickness):
    wavelengths, n, k = random_film()
    reflectance, transmittance, reference = _compute_RT_from_config(config(True), wavelengths, n, k, thickness, np.full(30, SUBSTRATE_INDEX))
    np.testing.assert_allclose(reflectance, front_surface(wavelengths, n, k, thickness), rtol=0.0, atol=1e-11)
    assert np.all(np.isnan(transmittance))
    assert np.all(np.isnan(reference))


def test_a_frosted_glass_does_not_read_an_absorbing_substrate():
    wavelengths, n, k = random_film()
    reflectance, _t, _ref = _compute_RT_from_config(config(True, absorbing=True), wavelengths, n, k, 120.0, np.full(30, SUBSTRATE_INDEX))
    np.testing.assert_allclose(reflectance, front_surface(wavelengths, n, k, 120.0), rtol=0.0, atol=1e-11)


def test_the_polished_glass_is_still_the_plate():
    wavelengths, n, k = random_film()
    reflectance, transmittance, reference = _compute_RT_from_config(config(False), wavelengths, n, k, 120.0, np.full(30, SUBSTRATE_INDEX))
    np.testing.assert_allclose(reflectance, plate(wavelengths, n, k, 120.0), rtol=0.0, atol=1e-11)
    assert np.all(np.isfinite(transmittance))
    assert np.all(np.isfinite(reference))


def test_the_frosted_glass_and_the_polished_glass_differ_by_the_back_face():
    wavelengths, n, k = random_film()
    frosted = _compute_RT_from_config(config(True), wavelengths, n, k, 120.0, np.full(30, SUBSTRATE_INDEX))[0]
    polished = _compute_RT_from_config(config(False), wavelengths, n, k, 120.0, np.full(30, SUBSTRATE_INDEX))[0]
    transparent = k == 0.0
    assert transparent.any()
    assert np.all(polished[transparent] - frosted[transparent] > 1e-3)  # the back face adds light to the reflectance of a film that lets it through
    assert np.all(polished >= frosted - 1e-12)  # and never takes any


# --- the stage that follows the first fit -------------------------------------------------------------------------------------------------

P_IR = np.array([1.5, 0.5, 0.2, 0.1, 0.1, -1.0, -10.0, -2.0, -15.0, 0.05, 1.0, 0.2, 2.0])
THICKNESS = 100.0


class IRConfig:
    def __init__(self, frosted, absorbing=False):
        self.is_frosted_glass = frosted
        self.data_type = DataType.REFLECTION
        self.use_normalized = False
        self.weight_T = 0.5
        self.weight_R = 0.5
        self.lambda_min = 400
        self.lambda_max = 2000
        self.exclude_min = None
        self.exclude_max = None
        self.has_absorbing_substrate = absorbing
        self.k_sub_data = np.full(50, 3e-5) if absorbing else None
        self.substrate_thickness_nm = SUBSTRATE_THICKNESS if absorbing else None


def ir_stage_cost(frosted, data_as, absorbing=False):
    """The cost of the stage at the parameters P_IR when the measured reflectance is `data_as(wavelengths, n, k)`."""
    wavelengths = np.linspace(400.0, 2000.0, 50)
    wavelengths_um = wavelengths / 1000.0
    n = sellmeier_2poles_eval_nj(P_IR[:5], wavelengths_um)
    k = np.array([k_law_8p_eval(float(x), P_IR[5:]) for x in wavelengths_um])
    n_sub = np.full(50, SUBSTRATE_INDEX)
    obj = IRGlobalObjective(
        wavelengths,
        np.zeros(50),
        data_as(wavelengths, n, k),
        n_sub,
        calculate_bare_substrate_RT(wavelengths, n_sub),
        np.full(50, 0.08),
        THICKNESS,
        n,
        IRConfig(frosted, absorbing),
    )
    obj.n_tol = 100.0
    return float(obj(P_IR))


def front_data(wavelengths, n, k):
    return front_surface(wavelengths, n, k, THICKNESS)


def plate_data(wavelengths, n, k):
    return plate(wavelengths, n, k, THICKNESS)


def test_the_stage_after_the_first_fit_has_no_error_when_the_data_are_the_front_surface_of_its_model():
    assert ir_stage_cost(True, front_data) < 1e-16


def test_the_stage_after_the_first_fit_has_an_error_when_the_data_are_the_plate():
    # the plate adds 0.03 to 0.04 of reflectance: the frosted stage does not model it
    assert ir_stage_cost(True, plate_data) > 1e-4


def test_the_stage_does_not_read_an_absorbing_substrate_for_a_frosted_glass():
    assert ir_stage_cost(True, front_data, absorbing=True) < 1e-16


def test_the_stage_still_models_the_plate_for_a_polished_glass():
    assert ir_stage_cost(False, plate_data) < 1e-16
    assert ir_stage_cost(False, front_data) > 1e-4


# --- the Tauc-Lorentz fit ---------------------------------------------------------------------------------------------------------------------

P_TLU = np.array([150.0, 3.2, 120.0, 4.5, 1.5, 0.15, 3.0])


def tlu_fit_cost(frosted, data_as):
    wavelengths = np.linspace(400.0, 1000.0, 61)
    n_sub = np.full(61, SUBSTRATE_INDEX)
    shape = TLUObjective(wavelengths, None, np.zeros(61), n_sub, DataType.REFLECTION, (50.0, 500.0), use_normalized=False, weight_T=1.0, weight_R=1.0, is_frosted_glass=frosted)
    n, k, _dn, _dk = _compute_tlu_derivatives_kernel(shape.E_array, *P_TLU[1:7])
    obj = TLUObjective(
        wavelengths, None, data_as(wavelengths, n, k, P_TLU[0]), n_sub, DataType.REFLECTION, (50.0, 500.0), use_normalized=False, weight_T=1.0, weight_R=1.0, is_frosted_glass=frosted
    )
    return float(obj(P_TLU))


def test_the_tauc_lorentz_fit_has_no_error_when_the_data_are_the_front_surface_of_its_model():
    assert tlu_fit_cost(True, lambda wl, n, k, d: front_surface(wl, n, k, d)) < 1e-16


def test_the_tauc_lorentz_fit_has_an_error_when_the_data_are_the_plate():
    assert tlu_fit_cost(True, lambda wl, n, k, d: plate(wl, n, k, d)) > 1e-4


def test_the_tauc_lorentz_fit_still_models_the_plate_for_a_polished_glass():
    assert tlu_fit_cost(False, lambda wl, n, k, d: plate(wl, n, k, d)) < 1e-16


# --- the pointwise cost of the first search -------------------------------------------------------------------------------------------------


def point_cost(frosted, target_r, n=2.1, k=0.05, wavelength=550.0, d=120.0):
    return _point_cost_kernel(n, k, wavelength, 0.0, target_r, 0.0, 1.0, SUBSTRATE_INDEX, 0.92, d, False, True, False, frosted)


@pytest.mark.parametrize(("n", "k", "wavelength", "d"), [(2.1, 0.05, 550.0, 120.0), (1.6, 0.0, 700.0, 300.0), (3.2, 0.4, 450.0, 60.0)])
def test_the_pointwise_cost_of_a_frosted_glass_is_the_squared_gap_to_the_front_surface(n, k, wavelength, d):
    front = front_surface([wavelength], [n], [k], d)[0]
    assert point_cost(True, front, n, k, wavelength, d) == pytest.approx(0.0, abs=1e-20)
    assert point_cost(True, front + 0.01, n, k, wavelength, d) == pytest.approx(1e-4, rel=1e-6)


def test_the_pointwise_cost_of_a_polished_glass_is_the_squared_gap_to_the_plate():
    wavelength, n, k, d = 550.0, 2.1, 0.0, 120.0
    plate_r = plate([wavelength], [n], [k], d)[0]
    assert point_cost(False, plate_r, n, k, wavelength, d) == pytest.approx(0.0, abs=1e-18)
    assert point_cost(True, plate_r, n, k, wavelength, d) > 1e-4
