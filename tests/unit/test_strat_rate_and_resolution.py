"""Rate mode and monochromator resolution -- the four things 👤 asked for on 2026-08-11.

  1. the user allows or refuses Rate from the final table;
  2. the sqrt(3) correction, the slit being RECTANGULAR;
  3. the resolution noise factor, /1.5 x1 x2 x5;
  4. the slit reported as part of the strategy.

🔴 Every one defaults to the historical behaviour, and that is constraint C1: a new
parameter must be inert unless asked for, to the bit.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_strat_robustness import (
    NOMINAL_RESOLUTION_NM,
    RATE_MAX_VARIANTS_PER_STRATEGY,
    RESOLUTION_NOISE_FACTOR,
    _expand_with_rate_variants,
    _rate_candidate_layers,
    _resolution_noise_factor,
    _resolve_robustness_noise_levels,
)
from certus.physics.certus_strat_growth import (
    D_SCAN_VAL,
    PHOTOMETRIC_CURVATURE_AMP,
    RATE_TURN_NM,
    SLIT_PROFILE_NODES,
    simulate_growth_kernel,
    slit_bias_at,
)

QWOT_500 = np.array([53.19, 85.62, 53.19, 85.62, 53.19, 85.62], dtype=np.float64)


# --------------------------------------------------------------------------- #
# 1. Rate: the user's switch, and where the variants are placed
# --------------------------------------------------------------------------- #

def _strat(bounds, sid=1):
    return {"strategy_id": sid, "blocks": [{"start": a, "end": b, "wavelength": 544.0}
                                           for a, b in bounds]}


def test_rate_is_ON_by_default_since_it_is_the_general_case():
    """👤 2026-08-12: *"add that rate is always allowed, it is the general case"*.

    🔴 This test was the opposite one until that date, and it deliberately BREAKS C1 --
    same reasoning as the slit bias and the index corridor: a default that hides a mode
    the machine offers describes an instrument that does not exist. What C1 protects is
    the ability to reproduce the historical path, and that is the next test.
    """
    strategies = [_strat([(0, 24), (24, 48)])]
    out = _expand_with_rate_variants(strategies, {}, 48, _Log())
    assert len(out) > len(strategies)
    assert out[0] is strategies[0], "l'originale reste candidate a l'identique"


def test_rate_can_still_be_refused_and_then_nothing_moves():
    """The historical path stays reachable, and it must come back byte for byte."""
    strategies = [_strat([(0, 24), (24, 48)])]
    assert _expand_with_rate_variants(strategies, {"allow_rate": False}, 48, _Log()) is strategies


def test_the_candidates_are_the_last_layer_of_each_block_deepest_first():
    """👤 the layer whose wavelength changes at i+1 -- the next one has no anchors anyway.

    Deepest first, because A24 measured that a Rate layer inherits an error falling as
    1/sqrt(n) with the number of reference layers of its material: it is at its most
    accurate late in the stack, which is also where 17-36 measured every crash happens.

    ⚠️ A margin-ordered key replaced this on 2026-08-12 and was reverted the same day --
    the measurement it rested on was a per-STRATEGY quantity used to order LAYERS. See
    the comment in `_rate_candidate_layers`; do not re-derive the rule from those numbers.
    """
    assert _rate_candidate_layers(_strat([(0, 24), (24, 40), (40, 48)]), 48) == [39, 23]


def test_a_degenerate_strategy_yields_no_candidate():
    """🔴 On one wavelength per layer, EVERY layer is a boundary and the placement says
    nothing. Measured 2026-08-11: 47 variants from a single 48-block strategy, 1928 over
    241 strategies -- a sixfold Monte-Carlo cost for candidates nobody asked about."""
    assert _rate_candidate_layers(_strat([(i, i + 1) for i in range(48)]), 48) == []


def test_the_number_of_variants_per_strategy_is_capped():
    """👤 asked for the trial on the ten best, not on everything. The cap must bite."""
    bounds = [(0, 8), (8, 16), (16, 24), (24, 32), (32, 40), (40, 48)]
    got = _rate_candidate_layers(_strat(bounds), 48)
    assert len(got) == RATE_MAX_VARIANTS_PER_STRATEGY
    assert got == [39, 31, 23], "les plus PROFONDES doivent etre gardees"


def test_the_final_layer_of_the_stack_is_excluded():
    """It has no successor, so no downstream cost -- but it is also the LAST chance to
    correct everything accumulated. The two pull opposite ways, so it gets its own
    experiment rather than a free ride in this one (A24)."""
    assert 47 not in _rate_candidate_layers(_strat([(0, 48)]), 48)


def test_enabling_rate_adds_one_variant_per_boundary():
    strategies = [_strat([(0, 24), (24, 40), (40, 48)], sid=7)]
    out = _expand_with_rate_variants(strategies, {"allow_rate": True}, 48, _Log())
    assert len(out) == 3                       # the original plus two variants
    assert [v["rate_layers"] for v in out[1:]] == [[39], [23]]
    assert all("RATE_L" in v["origin"] for v in out[1:])
    assert out[0] is strategies[0], "l'originale ne doit pas etre modifiee"


def test_a_variant_carries_exactly_one_rate_layer():
    """Two Rate layers interact -- the second inherits an estimate the first froze."""
    out = _expand_with_rate_variants([_strat([(0, 20), (20, 35), (35, 48)])],
                                     {"allow_rate": True}, 48, _Log())
    assert all(len(v["rate_layers"]) == 1 for v in out[1:])


# --------------------------------------------------------------------------- #
# 1b. The kernel: a Rate layer deposits a whole number of turns
# --------------------------------------------------------------------------- #

def _grow(i_layer, history, is_rate):
    return simulate_growth_kernel(
        QWOT_500, i_layer, history, 540.0,
        2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
        1.0, 0.0, 2.0, 0, 0, 0.0, 0, 0, 0.0,
        1.0, 0.0, 0.0, True, 1, -1.0, -1.0, is_rate,
    )


def test_a_rate_layer_deposits_a_whole_number_of_turns():
    """🟢 The U(0, 0.125 nm) quantisation of 9bis-7, appearing with no parameter posed."""
    hist = np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64)
    th, dyn, _, _, _ = _grow(4, hist, True)
    assert abs(th / RATE_TURN_NM - round(th / RATE_TURN_NM)) < 1e-9, (
        f"{th} nm n'est pas un multiple de {RATE_TURN_NM} nm"
    )
    assert dyn == -1.0, "une couche Rate n'est PAS surveillee : dyn doit le dire"


def test_rate_copies_the_error_it_does_not_add_one():
    """14: d_real_i / d_nom_i = harmonic mean of the previous ratios of that material.

    Deposit every previous H layer 5 % thick and the Rate layer must come out ~5 % thick
    too -- frozen, not amplified, and not corrected either.
    """
    hist = np.array([53.19 * 1.05, 85.62, 53.19 * 1.05, 85.62], dtype=np.float64)
    th, _, _, _, _ = _grow(4, hist, True)
    assert th / QWOT_500[4] == pytest.approx(1.05, abs=0.01)


def test_rate_is_refused_without_a_measured_reference():
    """👤 Q2: forbidden until a layer of that material has been deposited under POEM.

    On layer 0 there is no previous H layer, so the kernel must fall through to the
    normal photometric path instead of inventing a rate.
    """
    th_rate, dyn_rate, _, _, _ = _grow(0, np.zeros(0, dtype=np.float64), True)
    th_poem, dyn_poem, _, _, _ = _grow(0, np.zeros(0, dtype=np.float64), False)
    assert th_rate == th_poem and dyn_rate == dyn_poem


# --------------------------------------------------------------------------- #
# 2 and 3. Resolution
# --------------------------------------------------------------------------- #

def test_the_nominal_slit_is_inert():
    """C1: 2 nm is the slit the measured noise corresponds to, so its factor is 1."""
    assert _resolution_noise_factor({}) == 1.0
    assert _resolution_noise_factor({"monochromator_resolution_nm": NOMINAL_RESOLUTION_NM}) == 1.0


def test_the_table_is_the_one_the_physicist_gave():
    assert RESOLUTION_NOISE_FACTOR[5.0] == pytest.approx(1 / 1.5)
    assert RESOLUTION_NOISE_FACTOR[2.0] == 1.0
    assert RESOLUTION_NOISE_FACTOR[1.0] == 2.0
    assert RESOLUTION_NOISE_FACTOR[0.5] == 5.0


def test_a_slit_the_machine_does_not_have_is_refused_not_interpolated():
    """🔴 Four estimated points do not make a law, and a law would authorise settings
    that do not exist on the machine (12.7)."""
    with pytest.raises(ValueError, match="not one of"):
        _resolution_noise_factor({"monochromator_resolution_nm": 3.0})


def test_the_slit_scales_the_noise_levels():
    base = {"trigger_tolerance": 0.5}
    nominal = _resolve_robustness_noise_levels(dict(base))
    wide = _resolve_robustness_noise_levels({**base, "monochromator_resolution_nm": 5.0})
    narrow = _resolve_robustness_noise_levels({**base, "monochromator_resolution_nm": 0.5})
    assert wide[1] == pytest.approx(nominal[1] / 1.5)
    assert narrow[1] == pytest.approx(nominal[1] * 5.0)


def test_the_three_monte_carlo_levels_keep_their_ratios():
    """The slit scales the AMPLITUDE; it must not disturb the 0.5x / 1x / 2x structure."""
    lv = _resolve_robustness_noise_levels(
        {"trigger_tolerance": 0.5, "monochromator_resolution_nm": 1.0}
    )
    assert lv[1] / lv[0] == pytest.approx(2.0)
    assert lv[2] / lv[1] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# 4. The slit bias must VARY along the growth -- 👤 "model the slits more
#    faithfully, without exploding the time budget" (2026-08-11)
# --------------------------------------------------------------------------- #

def _grow_slit(profiles):
    return simulate_growth_kernel(
        QWOT_500, 4, np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64), 540.0,
        2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
        1.0, 0.0, 2.0, 0, 0, 0.0, 0, 0, 0.0,
        1.0, 0.0, 0.0, True, 1, -1.0, -1.0, False, profiles,
    )[0]


def test_no_profile_is_bit_identical_to_a_zero_profile():
    """C1. `None` and an all-zero profile are two spellings of "no slit effect"."""
    assert _grow_slit(None).hex() == _grow_slit(
        np.zeros((6, SLIT_PROFILE_NODES), dtype=np.float64)
    ).hex()


def test_a_constant_bias_is_absorbed_by_poem_however_large():
    """🔑 THE MEASUREMENT THAT JUSTIFIES THE WHOLE PROFILE.

    A constant added to every reading is exactly the `b` of `T -> a.T + b`, and 12.1
    proved POEM rigorously invariant under it. So a bias modelled as ONE NUMBER PER
    LAYER -- which is what the code did until 2026-08-11 -- is transparent to POEM no
    matter how big it is.

    📏 A constant of 1e-2, TWENTY TIMES the reading-noise amplitude, moves the stopping
    thickness by 1.8e-11 nm: nine decades below the 0.05 nm under which 16 forbids
    concluding anything at all.

    🔴 This test cannot fail on the old code -- it cannot even be WRITTEN against it,
    because a scalar bias has no other shape to be compared with. That is the point:
    the defect was not a wrong number, it was a missing degree of freedom.
    """
    ref = _grow_slit(None)
    for amp in (1e-4, 1e-3, 1e-2):
        got = _grow_slit(np.full((6, SLIT_PROFILE_NODES), amp, dtype=np.float64))
        assert abs(got - ref) < 1e-9, f"constante {amp:g} -> {got - ref:.2e} nm"


def test_a_varying_bias_moves_the_stop_in_proportion_to_itself():
    """Trap 1, the other way round: the quantity MUST vary with what drives it.

    Same amplitudes as above but shaped over the sweep instead of flat. The stopping
    point now moves, and linearly -- an amplitude 100 times larger displaces 100 times
    further. A profile that changed nothing would mean the array never reached the
    kernel; a displacement independent of the amplitude would mean it reached it and
    something else decided.
    """
    ref = _grow_slit(None)
    u = np.linspace(0.0, 3.0, SLIT_PROFILE_NODES)
    shifts = []
    for amp in (1e-5, 1e-4, 1e-3):
        prof = np.ascontiguousarray(
            np.tile((amp * np.sin(2.0 * np.pi * u / 3.0))[None, :], (6, 1))
        )
        shifts.append(abs(_grow_slit(prof) - ref))
    assert shifts[0] > 1e-4, "le profil n'atteint pas le calcul"
    assert shifts[1] / shifts[0] == pytest.approx(10.0, rel=0.05)
    assert shifts[2] / shifts[1] == pytest.approx(10.0, rel=0.05)


def test_the_profile_is_clamped_never_extrapolated():
    """Beyond the swept window the profile was never measured. Extrapolating a
    curvature term there would grow without bound in exactly the region the sweep
    stops short of."""
    prof = np.zeros((2, SLIT_PROFILE_NODES), dtype=np.float64)
    prof[0, 0], prof[0, -1] = -7.0, 11.0
    assert slit_bias_at(prof, 0, -5.0) == -7.0
    assert slit_bias_at(prof, 0, 1e6) == 11.0
    assert slit_bias_at(prof, 0, 0.0) == -7.0
    assert slit_bias_at(prof, 0, D_SCAN_VAL) == 11.0


def test_the_profile_axis_matches_the_sweep_the_kernel_actually_runs():
    """🔴 The profile is sampled on u = d / d_nominal over [0, D_SCAN_VAL] and read back
    on the same axis. If the two ever diverged, every bias would land at the wrong
    thickness with no error raised anywhere -- the invisible failure of trap 1."""
    prof = np.zeros((1, SLIT_PROFILE_NODES), dtype=np.float64)
    prof[0, (SLIT_PROFILE_NODES - 1) // 2] = 1.0        # spike at mid-sweep
    assert slit_bias_at(prof, 0, D_SCAN_VAL / 2.0) == pytest.approx(1.0)


class _Log:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


# --------------------------------------------------------------------------- #
# 5. Photometric CURVATURE -- 👤 2026-08-12, and it replaces the affine model
# --------------------------------------------------------------------------- #

def _grow_photo(aff_s=1.0, aff_o=0.0, curv=0.0, block_start=0):
    return simulate_growth_kernel(
        QWOT_500, 4, np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64), 540.0,
        2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
        1.0, 0.0, 2.0, 0, block_start, 0.0, 0, 0, 0.0,
        aff_s, aff_o, curv, True, 1, -1.0, -1.0, False, None,
    )[0]


def test_the_curvature_vanishes_at_both_ends_of_the_scale():
    """🔑 THE SHAPE IS FORCED BY HOW THE MACHINE MEASURES, not chosen for convenience.

    T = (S - D)/(V - D), re-referenced every rotation at 4 Hz. T = 0 means S = D and
    T = 1 means S = V, so those two values are the measurement's OWN anchors: any
    multiplicative drift of the chain leaves them exact. The residual error is therefore
    pinned at both ends and free in between -- 👤 *"maximal near T = 0.5, certainly not
    at 1 or 0"*.
    """
    def delta(t):
        return 4.0 * PHOTOMETRIC_CURVATURE_AMP * t * (1.0 - t)
    assert delta(0.0) == 0.0
    assert delta(1.0) == 0.0
    assert delta(0.5) == pytest.approx(PHOTOMETRIC_CURVATURE_AMP)
    assert delta(0.3) < delta(0.5) and delta(0.7) < delta(0.5)


def test_the_amplitude_is_the_one_the_physicist_specified():
    """👤 at T = 0.5 the true value lies between 0.4975 and 0.5025, bounds at 2 sigma.

    The project's draw is bounded on [-1, 1] with sigma = 1/3, so an amplitude A gives
    sigma = A/3 and 2 sigma = 2A/3. Requiring 2 sigma = 2.5e-3 fixes A = 3.75e-3.
    """
    assert 2.0 * PHOTOMETRIC_CURVATURE_AMP / 3.0 == pytest.approx(0.0025)


def test_poem_absorbs_the_affine_but_NOT_the_curvature():
    """🔴 THE WHOLE REASON THE MODEL CHANGED, and it is measurable in one call each.

    12.1 proves POEM rigorously invariant under `T -> a.T + b`. So the affine distortion
    the code carried until 2026-08-12 was the one shape POEM cancels for free -- and the
    ×41.2 "protection" was measured against a perturbation that is both absorbed by the
    mechanism AND largely removed by the machine's own dark/void referencing.

    📏 Measured here: a 5 % gain moves the stop by 9e-12 nm, an offset of 0.02 by 4e-11 nm,
    while the curvature at the specified amplitude moves it by 1.28 nm -- twenty-five
    times the 0.05 nm below which 16 forbids concluding anything from a thickness gap.

    Same structural mistake as the slit bias, found the same day: the perturbation had
    been given the shape the mechanism is immune to.
    """
    ref = _grow_photo()
    assert abs(_grow_photo(aff_s=1.05) - ref) < 1e-9, "l'affine doit etre absorbe"
    assert abs(_grow_photo(aff_o=0.02) - ref) < 1e-9, "l'affine doit etre absorbe"
    moved = abs(_grow_photo(curv=PHOTOMETRIC_CURVATURE_AMP) - ref)
    assert moved > 0.05, f"la courbure ne mord pas ({moved:.2e} nm)"


def test_the_curvature_grows_with_its_amplitude():
    """Trap 1: the quantity must respond to what drives it."""
    ref = _grow_photo()
    small = abs(_grow_photo(curv=PHOTOMETRIC_CURVATURE_AMP) - ref)
    large = abs(_grow_photo(curv=6.667 * PHOTOMETRIC_CURVATURE_AMP) - ref)
    assert large > small > 0.0


def test_a_zero_curvature_is_bit_identical_to_the_historical_path():
    """C1, for the parameter that replaces the affine one."""
    assert _grow_photo(curv=0.0).hex() == _grow_photo().hex()
