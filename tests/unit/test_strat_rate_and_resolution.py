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
    RESOLUTION_NOISE_FACTOR,
    _expand_with_rate_variants,
    _rate_candidate_layers,
    _resolution_noise_factor,
    _resolve_robustness_noise_levels,
)
from certus.physics.certus_strat_growth import RATE_TURN_NM, simulate_growth_kernel

QWOT_500 = np.array([53.19, 85.62, 53.19, 85.62, 53.19, 85.62], dtype=np.float64)


# --------------------------------------------------------------------------- #
# 1. Rate: the user's switch, and where the variants are placed
# --------------------------------------------------------------------------- #

def _strat(bounds, sid=1):
    return {"strategy_id": sid, "blocks": [{"start": a, "end": b, "wavelength": 544.0}
                                           for a, b in bounds]}


def test_rate_is_off_unless_asked_for():
    """C1: absent key -> the candidate list comes back untouched, same objects."""
    strategies = [_strat([(0, 24), (24, 48)])]
    out = _expand_with_rate_variants(strategies, {}, 48, _Log())
    assert out is strategies


def test_the_candidates_are_the_last_layer_of_each_block():
    """👤 the layer whose wavelength changes at i+1 -- the next one has no anchors anyway."""
    assert _rate_candidate_layers(_strat([(0, 24), (24, 40), (40, 48)]), 48) == [23, 39]


def test_the_final_layer_of_the_stack_is_excluded():
    """It has no successor, so no downstream cost -- but it is also the LAST chance to
    correct everything accumulated. The two pull opposite ways, so it gets its own
    experiment rather than a free ride in this one (A24)."""
    assert 47 not in _rate_candidate_layers(_strat([(0, 48)]), 48)


def test_enabling_rate_adds_one_variant_per_boundary():
    strategies = [_strat([(0, 24), (24, 40), (40, 48)], sid=7)]
    out = _expand_with_rate_variants(strategies, {"allow_rate": True}, 48, _Log())
    assert len(out) == 3                       # the original plus two variants
    assert [v["rate_layers"] for v in out[1:]] == [[23], [39]]
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
        1.0, 0.0, True, 1, -1.0, -1.0, is_rate,
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


class _Log:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass
