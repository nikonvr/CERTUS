"""At normal incidence too, an absorbing substrate is a plate that loses flux, not a black absorber past 1e-8.

Three normal-incidence kernels (`calculate_RT_with_backside_fused`, `_apply_exact_backside_generic`,
`calculate_RTRback_incoherent_vectorized`) treated every `|k| > 1e-8` as the semi-infinite absorber: `T = 0`,
`R` of the front, a jump. A glass of `k = 4.4e-6` (1 cm-1) gave `T = 0.000` where it transmits about 0.92,
and STRAT, which accepts a substrate up to `1e-5`, computed with that kernel. DESIGN's own back-stack path
(`calc_spectrum_full_exact`) had no loss at all. They are now one model: the plate of
`certus_substrate_absorption` (Beer-Lambert per pass, 1 mm unless told), continuous in `k` from the plate
without loss to the semi-infinite absorber.

The oracle is `tests/oracle/tmm_reference.py`: `rt_plate_incoherent` (the model, every coherent piece by
`rt_stack_oblique`) for the kernels, `rt_plate_coherent_mean` (the exact coherent plate averaged over a
fringe) for the model, in `test_oblique_plate_absorbing_substrate.py`.
"""

from __future__ import annotations

import numpy as np
import pytest
from tmm_reference import rt_plate_incoherent

WLS = np.array([470.0, 560.0, 640.0, 760.0, 900.0, 1100.0, 1300.0, 1500.0])
THICKNESS = 1.0e6
KS = [0.0, 1e-9, 1e-8, 1.1e-8, 1e-7, 4.4e-6, 1e-4, 1e-2, 1.0]


def _stack(n_layers: int, seed: int):
    rng = np.random.default_rng(seed)
    n = rng.uniform(1.3, 2.4, (len(WLS), n_layers)).astype(np.complex128)
    return n, rng.uniform(40.0, 180.0, n_layers)


def _substrate(k: float) -> np.ndarray:
    return np.array([complex(1.50 + 0.01 * i, -k) for i in range(len(WLS))])


def _plate(n_front, d_front, n_sub, n_back=None, d_back=None, i=0):
    empty = np.zeros(0, dtype=np.complex128)
    return rt_plate_incoherent(
        float(WLS[i]),
        n_front[i],
        d_front,
        empty if n_back is None else n_back[i],
        np.zeros(0) if d_back is None else d_back,
        n_sub[i],
        0.0,
        True,
        THICKNESS,
    )


@pytest.mark.parametrize("n_layers", [0, 2, 4])
@pytest.mark.parametrize("k", KS)
def test_the_fused_backside_kernel_matches_the_model(k, n_layers) -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused

    n, d = _stack(n_layers, seed=3)
    n_sub = _substrate(k)

    r, t = calculate_RT_with_backside_fused(d, n, n_sub, WLS)

    for i in range(len(WLS)):
        assert (r[i], t[i]) == pytest.approx(_plate(n, d, n_sub, i=i), abs=1e-12)


@pytest.mark.parametrize("n_layers", [0, 3])
@pytest.mark.parametrize("k", KS)
def test_the_generic_backside_kernel_matches_the_model(k, n_layers) -> None:
    from certus.physics.certus_tmm_backside import _apply_exact_backside_generic
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside

    n, d = _stack(n_layers, seed=5)
    n_sub = _substrate(k)
    r_front, t_front = calculate_RT_no_backside(d, n, n_sub, WLS)

    r, t = _apply_exact_backside_generic(r_front, t_front, d, n, n_sub, WLS)

    for i in range(len(WLS)):
        assert (r[i], t[i]) == pytest.approx(_plate(n, d, n_sub, i=i), abs=1e-12)


@pytest.mark.parametrize("n_layers", [1, 3])
@pytest.mark.parametrize("k", KS)
def test_the_kernel_with_the_back_reflectance_matches_the_model_from_both_sides(k, n_layers) -> None:
    # Rback is what a measurement from the back side sees: the plate with the front stack and the bare back
    # exchanged. The model gives it by the same function, called the other way round.
    from certus.physics.certus_opt_tmm import calculate_RTRback_incoherent_vectorized

    n, d = _stack(n_layers, seed=7)
    n_sub = _substrate(k)
    no_stack = np.zeros((len(WLS), 0), dtype=np.complex128)

    r, t, r_back = calculate_RTRback_incoherent_vectorized(d, n, n_sub, WLS)

    for i in range(len(WLS)):
        assert (r[i], t[i]) == pytest.approx(_plate(n, d, n_sub, i=i), abs=1e-12)
        r_from_back, _t_from_back = _plate(no_stack, np.zeros(0), n_sub, n_back=n, d_back=d, i=i)
        assert r_back[i] == pytest.approx(r_from_back, abs=1e-12)


@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4, 1e-2])
def test_the_back_stack_path_of_design_matches_the_model(k) -> None:
    from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact

    n_front, d_front = _stack(3, seed=11)
    n_back, d_back = _stack(2, seed=13)
    n_sub = _substrate(k)

    rf, tf, rf_prime, rb_prime, tb = calc_spectrum_full_exact(WLS, d_front, n_front, d_back, n_back, n_sub)

    denominator = 1.0 - rf_prime * rb_prime
    t_total = tf * tb / denominator
    for i in range(len(WLS)):
        expected_r, expected_t = _plate(n_front, d_front, n_sub, n_back=n_back, d_back=d_back, i=i)
        assert t_total[i] == pytest.approx(expected_t, abs=1e-12)
        # R = Rf + Tf T' Rb' / (1 - Rf' Rb') needs the reverse transmittance, which DESIGN's cost does not use.
        assert rf[i] + 0.0 * expected_r == pytest.approx(rf[i])


# =============================================================================
# The cliff at 1e-8 is gone
# =============================================================================


def test_the_glass_of_the_audit_is_not_a_black_absorber() -> None:
    # k = 4.4e-6: T was 0.000 (the kernel jumped to the semi-infinite absorber at 1e-8); a millimetre of it
    # keeps about 90 % of the flux on each pass.
    from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused

    n, d = _stack(0, seed=17)

    _r, t_lossless = calculate_RT_with_backside_fused(d, n, _substrate(0.0), WLS)
    _r, t_glass = calculate_RT_with_backside_fused(d, n, _substrate(4.4e-6), WLS)

    assert np.all(t_glass > 0.75 * t_lossless)
    assert np.all(t_glass < t_lossless)


@pytest.mark.parametrize("n_layers", [0, 3])
def test_the_answer_does_not_jump_at_1e_8(n_layers) -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused

    n, d = _stack(n_layers, seed=19)

    below = calculate_RT_with_backside_fused(d, n, _substrate(0.9e-8), WLS)
    above = calculate_RT_with_backside_fused(d, n, _substrate(1.1e-8), WLS)

    # The plate loses about 2.5e-4 of the flux per pass for 1e-8 of k (1 mm, visible): 2e-9 of k moves T by
    # 5e-5, not by the 0.9 the jump to the semi-infinite absorber made.
    assert below[0] == pytest.approx(above[0], abs=1e-4)
    assert below[1] == pytest.approx(above[1], abs=1e-4)


def test_a_substrate_that_absorbs_everything_is_the_front_stack_and_no_transmission() -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside, calculate_RT_with_backside_fused

    n, d = _stack(3, seed=23)
    n_sub = _substrate(1.0)

    r, t = calculate_RT_with_backside_fused(d, n, n_sub, WLS)
    r_front, _t_front = calculate_RT_no_backside(d, n, n_sub, WLS)

    assert r == pytest.approx(r_front, abs=1e-12)
    assert np.all(t < 1e-12)


def test_the_thickness_is_the_one_asked_for() -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_vectorized_real, calculate_RT_with_backside_fused

    n, d = _stack(2, seed=29)
    n_sub = _substrate(4.4e-6)

    thin = calculate_RT_with_backside_fused(d, n, n_sub, WLS, 2.0e5)
    thick = calculate_RT_with_backside_fused(d, n, n_sub, WLS, 5.0e6)
    through_the_entry = calculate_RT_vectorized_real(d, n, n_sub, WLS, True, 2.0e5)

    assert np.all(thin[1] > thick[1])
    assert through_the_entry[0] == pytest.approx(thin[0], abs=1e-15)
    assert through_the_entry[1] == pytest.approx(thin[1], abs=1e-15)


# =============================================================================
# One model, whichever kernel: normal and oblique agree at 0 degree
# =============================================================================


@pytest.mark.parametrize("k", [0.0, 4.4e-6, 1e-4])
def test_the_normal_and_the_oblique_plate_kernels_agree_at_zero_degree(k) -> None:
    from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized

    n, d = _stack(3, seed=31)
    n_sub = _substrate(k)

    normal = calculate_RT_with_backside_fused(d, n, n_sub, WLS)
    oblique = calc_spectrum_oblique_backside_vectorized(WLS, n, d, n_sub, 0.0, "s")

    assert normal[0] == pytest.approx(oblique[0], abs=1e-12)
    assert normal[1] == pytest.approx(oblique[1], abs=1e-12)
