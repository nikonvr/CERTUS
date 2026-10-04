"""INDEX's single-layer kernels are the independent oracle's plate (audit v2, plan S3.2).

`certus/physics/certus_tmm_single_layer.py` is the hot path of INDEX and INDEX SPLINE: one film on a substrate, read through the back face of the plate (`calculate_transmission_single` and its
array wrappers), the same on an absorbing substrate (`_calculate_RT_absorbing_sub_single`), and the fused mean-square-error kernels PGlobal evaluates a whole generation with
(`batch_single_layer_T_mse`, `batch_single_layer_RT_mse`). The first face-reflectance kernel of the file is checked against the oracle elsewhere (`tests/oracle/test_tmm_oracle.py`); none of
these was: a swapped index in a batch kernel gives a smooth objective that the search minimises faithfully.

What is pinned here, against `tests/oracle/tmm_reference.py` (`rt_plate_incoherent` and `rt_stack_oblique`, written from Macleod, sharing no code with `certus.physics`):

    the film on a transparent plate: R with the back face and T, at 1e-11, over random films (absorbing or not, thickness zero included) and substrates
    the array wrappers of the plate, point by point; and the reflectance wrappers, which are the FRONT SURFACE alone, an infinite back face (the frosted glass, ETAT D75: they used to return
    the plate's R, back face included, while their docstrings said "front-surface")
    the sentinels INDEX relies on (an index below one, a zero film index) and the conservation of energy
    the film on an absorbing substrate, exactly, against the oracle's plate: the film read from air into the complex index of the substrate, the interfaces seen from inside
    with its real part (ETAT D75: the kernel read the front with the real part too, an error of first order in the extinction of the substrate, up to 0.25 k)
    the batch kernels: the weighted mean square error of every candidate, its weights, its normalisation, and that one candidate does not read another's row
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from certus.physics.certus_tmm_single_layer import (
    _calculate_RT_absorbing_sub_single,
    batch_single_layer_RT_mse,
    batch_single_layer_T_mse,
    calculate_reflection_array,
    calculate_reflection_single,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    calculate_transmission_array,
    calculate_transmission_single,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

import tmm_reference as oracle  # noqa: E402

pytestmark = pytest.mark.kernels

SUBSTRATE_THICKNESS = 1.0e6  # nm, the millimetre INDEX assumes unless told


def plate(wavelength, n, k, d, n_sub, k_sub=0.0, substrate_thickness=SUBSTRATE_THICKNESS):
    """(R, T) of film | plate | air by the oracle, normal incidence: the film (n - ik, d nm) on a plate whose back face is bare."""
    return oracle.rt_plate_incoherent(
        float(wavelength), [complex(n, -k)], [float(d)], [], [], complex(n_sub, -k_sub), 0.0, True, substrate_thickness
    )


def random_cases(count, seed):
    """Films and substrates drawn once: half the films without absorption, thicknesses from nothing to 1.5 um, wavelengths from the near UV to the near infrared."""
    rng = np.random.default_rng(seed)
    wavelength = rng.uniform(250.0, 2200.0, count)
    n = rng.uniform(1.2, 3.6, count)
    k = np.where(rng.random(count) < 0.5, 0.0, rng.uniform(0.0, 1.5, count))
    d = rng.uniform(0.0, 1500.0, count)
    d[:3] = 0.0
    n_sub = rng.uniform(1.0, 3.6, count)
    return wavelength, n, k, d, n_sub


CASES = random_cases(120, seed=20261001)


def cases():
    return list(zip(*CASES, strict=True))


# --- the film on a transparent plate -------------------------------------------------------------------------------------------------------


def test_the_total_reflectance_and_transmittance_of_a_film_are_the_oracles_plate():
    for wavelength, n, k, d, n_sub in cases():
        r, t = calculate_transmission_single(wavelength, n, k, d, complex(n_sub, 0.0))
        r_oracle, t_oracle = plate(wavelength, n, k, d, n_sub)
        assert r == pytest.approx(r_oracle, abs=1e-11), (wavelength, n, k, d, n_sub)
        assert t == pytest.approx(t_oracle, abs=1e-11), (wavelength, n, k, d, n_sub)


def test_a_film_that_does_not_absorb_on_a_transparent_plate_keeps_every_photon():
    for wavelength, n, k, d, n_sub in cases():
        if k == 0.0:
            r, t = calculate_transmission_single(wavelength, n, 0.0, d, complex(n_sub, 0.0))
            assert r + t == pytest.approx(1.0, abs=1e-11)


def test_an_absorbing_film_loses_flux_and_never_creates_it():
    lost = []
    for wavelength, n, k, d, n_sub in cases():
        if k > 0.0:
            r, t = calculate_transmission_single(wavelength, n, k, d, complex(n_sub, 0.0))
            assert r + t <= 1.0 + 1e-11
            lost.append(1.0 - r - t)
    assert max(lost) > 0.1  # and the sample does contain films that absorb, so the bound above is not vacuous


def test_a_film_of_no_thickness_is_the_bare_plate():
    for n_sub in (1.0, 1.45, 1.52, 2.4, 3.42):
        r1 = ((1.0 - n_sub) / (1.0 + n_sub)) ** 2
        r, t = calculate_transmission_single(550.0, 2.2, 0.3, 0.0, complex(n_sub, 0.0))
        assert r == pytest.approx(2.0 * r1 / (1.0 + r1), abs=1e-12)
        assert t == pytest.approx((1.0 - r1) / (1.0 + r1), abs=1e-12)


def test_a_substrate_index_below_one_is_refused_with_nan():
    # NaN and inf too: the guard lives in a kernel compiled without fastmath, which cannot fold `np.isfinite` (R122, D75)
    for n_sub in (0.99, 0.5, 0.0, -1.5, np.nan, np.inf, -np.inf):
        r, t = calculate_transmission_single(550.0, 1.5, 0.0, 100.0, complex(n_sub, 0.0))
        assert np.isnan(r)
        assert np.isnan(t)


def test_a_film_without_any_index_is_refused_with_nan():
    r, t = calculate_transmission_single(550.0, 0.0, 0.0, 100.0, complex(1.52, 0.0))
    assert np.isnan(r)
    assert np.isnan(t)


# --- the array wrappers ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("thickness", [0.0, 35.0, 120.0, 480.0, 1400.0])
def test_the_array_kernels_are_the_oracles_plate_at_every_point(thickness):
    wavelength, n, k, _d, n_sub = random_cases(40, seed=int(thickness) + 7)
    r, t = calculate_RT_single_layer_backside_array(wavelength, n, k, thickness, n_sub)
    t_only = calculate_transmission_array(wavelength, n, k, thickness, n_sub)
    expected = np.array([plate(w, n_i, k_i, thickness, ns_i) for w, n_i, k_i, ns_i in zip(wavelength, n, k, n_sub, strict=True)])
    np.testing.assert_allclose(r, expected[:, 0], rtol=0.0, atol=1e-11)
    np.testing.assert_allclose(t, expected[:, 1], rtol=0.0, atol=1e-11)
    np.testing.assert_allclose(t_only, expected[:, 1], rtol=0.0, atol=1e-11)


def front_surface(wavelength, n, k, d, n_sub):
    """R of the film on an infinite substrate by the oracle: the front surface alone."""
    return oracle.rt_stack(float(wavelength), [complex(n, -k)], [float(d)], 1.0 + 0.0j, complex(n_sub, 0.0))[0]


def test_the_scalar_reflectance_is_the_front_surface_alone():
    # a frosted glass is an infinite back face (ETAT D75, decided by the owner): nothing comes back from the rough back, the front surface alone reflects
    for wavelength, n, k, d, n_sub in cases():
        r = calculate_reflection_single(wavelength, n, k, d, n_sub)
        assert r == pytest.approx(front_surface(wavelength, n, k, d, n_sub), abs=1e-11), (wavelength, n, k, d, n_sub)


def test_the_front_surface_is_not_the_plate():
    # the two differ by the back face for a film that lets light through, so the test above tells them apart
    gaps = []
    for wavelength, n, k, d, n_sub in cases():
        if k == 0.0 and d > 50.0 and n_sub > 1.3:
            gaps.append(abs(calculate_reflection_single(wavelength, n, k, d, n_sub) - plate(wavelength, n, k, d, n_sub)[0]))
    assert min(gaps) > 1e-4


@pytest.mark.parametrize("thickness", [0.0, 35.0, 120.0, 480.0, 1400.0])
def test_the_reflectance_array_is_the_front_surface_at_every_point(thickness):
    wavelength, n, k, _d, n_sub = random_cases(40, seed=int(thickness) + 13)
    expected = np.array([front_surface(w, n_i, k_i, thickness, ns_i) for w, n_i, k_i, ns_i in zip(wavelength, n, k, n_sub, strict=True)])
    np.testing.assert_allclose(calculate_reflection_array(wavelength, n, k, thickness, n_sub), expected, rtol=0.0, atol=1e-11)


def test_a_film_of_no_thickness_reflects_the_bare_interface_alone():
    for n_sub in (1.0, 1.33, 1.52, 2.4, 3.42):
        assert calculate_reflection_single(550.0, 2.2, 0.3, 0.0, n_sub) == pytest.approx(((1.0 - n_sub) / (1.0 + n_sub)) ** 2, abs=1e-12)


def test_the_reflectance_wrappers_refuse_a_substrate_below_one_at_that_point_only():
    wavelength = np.array([450.0, 550.0, 650.0])
    result = calculate_reflection_array(wavelength, np.full(3, 1.5), np.zeros(3), 120.0, np.array([1.52, 0.95, 1.52]))
    assert np.isfinite(result[0])
    assert np.isnan(result[1])
    assert np.isfinite(result[2])
    assert np.isnan(calculate_reflection_single(550.0, 1.5, 0.0, 120.0, 0.5))


# --- the film on an absorbing substrate ----------------------------------------------------------------------------------------------------


SUBSTRATE_EXTINCTIONS = [0.0, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2]


@pytest.mark.parametrize("k_sub", SUBSTRATE_EXTINCTIONS)
@pytest.mark.parametrize("substrate_thickness", [5.0e5, SUBSTRATE_THICKNESS])
def test_the_absorbing_substrate_kernel_is_the_oracles_plate(k_sub, substrate_thickness):
    for wavelength, n, k, d, n_sub in cases()[:50]:
        r, t = _calculate_RT_absorbing_sub_single(wavelength, n, k, d, n_sub, k_sub, substrate_thickness)
        r_expected, t_expected = plate(wavelength, n, k, d, n_sub, k_sub, substrate_thickness)
        assert r == pytest.approx(r_expected, abs=1e-11), (wavelength, n, k, d, n_sub, k_sub)
        assert t == pytest.approx(t_expected, abs=1e-11), (wavelength, n, k, d, n_sub, k_sub)


def test_without_extinction_the_absorbing_substrate_kernel_is_the_transparent_plate():
    for wavelength, n, k, d, n_sub in cases():
        r, t = _calculate_RT_absorbing_sub_single(wavelength, n, k, d, n_sub, 0.0, SUBSTRATE_THICKNESS)
        r_transparent, t_transparent = calculate_transmission_single(wavelength, n, k, d, complex(n_sub, 0.0))
        assert r == pytest.approx(r_transparent, abs=1e-11)
        assert t == pytest.approx(t_transparent, abs=1e-11)


def test_the_flux_that_an_absorbing_substrate_takes_is_not_created_back():
    for wavelength, n, k, d, n_sub in cases()[:60]:
        r, t = _calculate_RT_absorbing_sub_single(wavelength, n, k, d, n_sub, 1e-4, SUBSTRATE_THICKNESS)
        assert 0.0 <= r <= 1.0
        assert 0.0 <= t <= 1.0
        assert r + t <= 1.0 + 1e-11


def test_an_opaque_substrate_transmits_nothing_and_a_thin_one_transmits_more():
    r_thick, t_thick = _calculate_RT_absorbing_sub_single(550.0, 2.0, 0.0, 100.0, 1.52, 0.1, SUBSTRATE_THICKNESS)
    _r_thin, t_thin = _calculate_RT_absorbing_sub_single(550.0, 2.0, 0.0, 100.0, 1.52, 1e-5, 1.0e4)
    _r_mid, t_mid = _calculate_RT_absorbing_sub_single(550.0, 2.0, 0.0, 100.0, 1.52, 1e-5, 1.0e6)
    assert t_thick < 1e-50
    assert t_thin > t_mid > t_thick
    assert r_thick == pytest.approx(oracle.rt_stack(550.0, [2.0 + 0.0j], [100.0], 1.0 + 0.0j, 1.52 - 0.1j)[0], abs=1e-11)  # only the front is seen, into n - ik


def test_the_absorbing_substrate_array_is_the_scalar_kernel_at_every_point():
    wavelength, n, k, _d, n_sub = random_cases(40, seed=11)
    k_sub = np.linspace(0.0, 2e-4, 40)
    r, t = calculate_RT_single_layer_absorbing_substrate_array(wavelength, n, k, 150.0, n_sub, k_sub, SUBSTRATE_THICKNESS)
    for i in range(40):
        r_i, t_i = _calculate_RT_absorbing_sub_single(wavelength[i], n[i], k[i], 150.0, n_sub[i], k_sub[i], SUBSTRATE_THICKNESS)
        assert r[i] == pytest.approx(r_i, abs=1e-14)
        assert t[i] == pytest.approx(t_i, abs=1e-14)


def test_the_absorbing_substrate_kernel_refuses_what_the_transparent_one_refuses():
    for n_sub in (0.99, 0.0, -1.5):
        r, t = _calculate_RT_absorbing_sub_single(550.0, 1.5, 0.0, 100.0, n_sub, 1e-5, SUBSTRATE_THICKNESS)
        assert np.isnan(r)
        assert np.isnan(t)
    r, t = _calculate_RT_absorbing_sub_single(550.0, 0.0, 0.0, 100.0, 1.52, 1e-5, SUBSTRATE_THICKNESS)
    assert np.isnan(r)
    assert np.isnan(t)


# --- the fused mean-square-error kernels of PGlobal -----------------------------------------------------------------------------------------


N_CANDIDATES = 5
N_PIXELS = 12


def batch_inputs():
    rng = np.random.default_rng(31)
    wavelength = np.linspace(380.0, 1100.0, N_PIXELS)
    n_sub = rng.uniform(1.4, 1.6, N_PIXELS)
    weights = rng.uniform(0.2, 2.0, N_PIXELS)
    t_exp = rng.uniform(0.4, 0.95, N_PIXELS)
    r_exp = rng.uniform(0.02, 0.3, N_PIXELS)
    n_batch = rng.uniform(1.3, 2.6, (N_CANDIDATES, N_PIXELS))
    k_batch = np.where(rng.random((N_CANDIDATES, N_PIXELS)) < 0.5, 0.0, rng.uniform(0.0, 0.2, (N_CANDIDATES, N_PIXELS)))
    d_batch = rng.uniform(40.0, 900.0, N_CANDIDATES)
    return wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch


def squared_errors_by_the_oracle(wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch):
    """The weighted sum of squared errors of every candidate, for T and for R, from the oracle's plate."""
    acc_t = np.zeros(len(d_batch))
    acc_r = np.zeros(len(d_batch))
    for i in range(len(d_batch)):
        for j in range(len(wavelength)):
            r, t = plate(wavelength[j], n_batch[i, j], k_batch[i, j], d_batch[i], n_sub[j])
            acc_t[i] += weights[j] * (t_exp[j] - t) ** 2
            acc_r[i] += weights[j] * (r_exp[j] - r) ** 2
    return acc_t, acc_r


def test_the_transmission_batch_is_the_weighted_mean_square_error_of_every_candidate():
    wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch = batch_inputs()
    acc_t, _acc_r = squared_errors_by_the_oracle(wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch)
    inv_npix = 1.0 / N_PIXELS
    result = batch_single_layer_T_mse(wavelength, n_sub, weights, inv_npix, t_exp, n_batch, k_batch, d_batch)
    assert result.shape == (N_CANDIDATES,)
    np.testing.assert_allclose(result, acc_t * inv_npix, rtol=1e-9, atol=0.0)


def test_the_normalisation_of_the_batch_is_the_factor_it_is_given():
    wavelength, n_sub, weights, t_exp, _r_exp, n_batch, k_batch, d_batch = batch_inputs()
    one = batch_single_layer_T_mse(wavelength, n_sub, weights, 1.0, t_exp, n_batch, k_batch, d_batch)
    third = batch_single_layer_T_mse(wavelength, n_sub, weights, 1.0 / 3.0, t_exp, n_batch, k_batch, d_batch)
    np.testing.assert_allclose(third, one / 3.0, rtol=1e-12, atol=0.0)


def test_a_point_of_no_weight_does_not_count():
    wavelength, n_sub, weights, t_exp, _r_exp, n_batch, k_batch, d_batch = batch_inputs()
    counted = batch_single_layer_T_mse(wavelength, n_sub, weights, 1.0 / N_PIXELS, t_exp, n_batch, k_batch, d_batch)
    no_weight = weights.copy()
    no_weight[4] = 0.0
    t_wild = t_exp.copy()
    t_wild[4] = 123.0
    with_a_wild_value = batch_single_layer_T_mse(wavelength, n_sub, no_weight, 1.0 / N_PIXELS, t_wild, n_batch, k_batch, d_batch)
    with_the_true_value = batch_single_layer_T_mse(wavelength, n_sub, no_weight, 1.0 / N_PIXELS, t_exp, n_batch, k_batch, d_batch)
    np.testing.assert_allclose(with_a_wild_value, with_the_true_value, rtol=1e-12, atol=0.0)
    assert not np.allclose(with_the_true_value, counted)  # and the point did count while it had a weight


def test_a_candidate_does_not_read_the_row_of_another():
    wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch = batch_inputs()
    whole = batch_single_layer_T_mse(wavelength, n_sub, weights, 1.0 / N_PIXELS, t_exp, n_batch, k_batch, d_batch)
    for i in range(N_CANDIDATES):
        alone = batch_single_layer_T_mse(wavelength, n_sub, weights, 1.0 / N_PIXELS, t_exp, n_batch[i : i + 1].copy(), k_batch[i : i + 1].copy(), d_batch[i : i + 1].copy())
        assert alone[0] == pytest.approx(whole[i], rel=1e-12, abs=0.0)
    whole_rt = batch_single_layer_RT_mse(wavelength, n_sub, weights, 1.0 / N_PIXELS, t_exp, r_exp, n_batch, k_batch, d_batch, 1.0, 1.0)
    for i in range(N_CANDIDATES):
        alone = batch_single_layer_RT_mse(
            wavelength, n_sub, weights, 1.0 / N_PIXELS, t_exp, r_exp, n_batch[i : i + 1].copy(), k_batch[i : i + 1].copy(), d_batch[i : i + 1].copy(), 1.0, 1.0
        )
        assert alone[0] == pytest.approx(whole_rt[i], rel=1e-12, abs=0.0)


@pytest.mark.parametrize(("w_t", "w_r"), [(1.0, 1.0), (2.0, 0.5), (0.3, 3.0)])
def test_the_reflection_and_transmission_batch_is_the_weighted_mean_of_both_errors(w_t, w_r):
    wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch = batch_inputs()
    acc_t, acc_r = squared_errors_by_the_oracle(wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch)
    inv_npix = 1.0 / N_PIXELS
    result = batch_single_layer_RT_mse(wavelength, n_sub, weights, inv_npix, t_exp, r_exp, n_batch, k_batch, d_batch, w_t, w_r)
    np.testing.assert_allclose(result, (w_t * acc_t + w_r * acc_r) * inv_npix / (w_t + w_r), rtol=1e-9, atol=0.0)


def test_a_batch_that_weighs_only_one_of_the_two_is_that_one_alone():
    wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch = batch_inputs()
    acc_t, acc_r = squared_errors_by_the_oracle(wavelength, n_sub, weights, t_exp, r_exp, n_batch, k_batch, d_batch)
    inv_npix = 1.0 / N_PIXELS
    only_t = batch_single_layer_RT_mse(wavelength, n_sub, weights, inv_npix, t_exp, r_exp, n_batch, k_batch, d_batch, 1.0, 0.0)
    only_r = batch_single_layer_RT_mse(wavelength, n_sub, weights, inv_npix, t_exp, r_exp, n_batch, k_batch, d_batch, 0.0, 1.0)
    np.testing.assert_allclose(only_t, acc_t * inv_npix, rtol=1e-9, atol=0.0)
    np.testing.assert_allclose(only_r, acc_r * inv_npix, rtol=1e-9, atol=0.0)
    np.testing.assert_allclose(only_t, batch_single_layer_T_mse(wavelength, n_sub, weights, inv_npix, t_exp, n_batch, k_batch, d_batch), rtol=1e-12, atol=0.0)
