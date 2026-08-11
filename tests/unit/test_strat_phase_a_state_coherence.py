"""Phase A must remember the world it judged in -- defect 17-23.

`update_run_states_kernel` propagates the simulated thicknesses that become the
history against which the NEXT layer's candidates are judged. It used to hand the
growth kernel 16 arguments out of 22, so `affine_scale`, `affine_offset`,
`poem_enabled`, `smoothing_window` and the two corridor indices silently took their
neutral defaults.

The consequence is not subtle: Phase A judged candidates under photometric drift, an
index corridor and reading smoothing, then propagated a history simulated with none of
them. The remembered stack was systematically cleaner than the world it was a history
of -- at every layer, cumulatively.

The kernel's own docstring already stated the principle, for `block_start_layer`:
"evaluating them without the block history while the candidates were evaluated with it
would produce a Phase A inconsistent with itself". Only the list of parameters it
applied to was incomplete.

🔴 Every test here must FAIL on the pre-fix code -- there, the extra arguments did not
exist, so the propagated state could not depend on them by construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus_physics import update_run_states_kernel

#: Same fixture discipline as test_strat_corridor_envelope: the upstream layers must
#: really have been deposited, otherwise every call returns the crash sentinel and the
#: assertions compare sentinels instead of physics.
QWOT_500 = np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64)
I_LAYER = 2
N_RUNS = 6
BEST_WL = 540.0


def _propagate(**kw) -> np.ndarray:
    history = np.tile(QWOT_500[:I_LAYER], (N_RUNS, 1))
    return update_run_states_kernel(
        QWOT_500,
        I_LAYER,
        history,
        BEST_WL,
        2.35 + 0j,
        1.46 + 0j,
        1.52 + 0j,
        1.0,
        np.zeros(N_RUNS, dtype=np.float64),
        2.0,
        0,
        kw.get("block_start_layer", -1),
        kw.get("signal_noise_scale", 0.0),
        kw.get("signal_noise_seed", 0),
        kw.get("tp_hysteresis", 0.0),
        kw.get("affine_scale_amp", 0.0),
        kw.get("affine_offset_amp", 0.0),
        kw.get("affine_seed", 0),
        kw.get("poem_enabled", True),
        kw.get("smoothing_window", 1),
        kw.get("index_corridor", 0.0),
        kw.get("index_seed", 0),
        kw.get("corridor_lo", 0.0),
        kw.get("corridor_hi", 0.0),
    )


def test_the_fixture_actually_simulates_something():
    """If this returns the sentinel, every assertion below is vacuous."""
    out = _propagate()
    assert np.all(out < 1e5), f"le montage plante ({out}) : les tests suivants ne testent rien"


def test_neutral_parameters_are_bit_identical_to_the_legacy_call():
    """C1: the six new parameters at their neutral values must not move a bit.

    Compared against the call that omits them entirely -- the exact signature every
    caller used before the fix.
    """
    history = np.tile(QWOT_500[:I_LAYER], (N_RUNS, 1))
    legacy = update_run_states_kernel(
        QWOT_500, I_LAYER, history, BEST_WL,
        2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
        1.0, np.zeros(N_RUNS, dtype=np.float64), 2.0, 0, -1, 0.0, 0, 0.0,
    )
    now = _propagate()
    assert np.array_equal(legacy, now, equal_nan=True)
    assert [v.hex() for v in legacy] == [v.hex() for v in now]


def test_affine_distortion_reaches_the_propagated_state():
    """Trap 1: a parameter that changes nothing does not reach the computation."""
    base = _propagate()
    drifted = _propagate(affine_scale_amp=0.05, affine_offset_amp=0.02, affine_seed=4242)
    assert not np.array_equal(base, drifted), (
        "la derive photometrique n'atteint pas la propagation d'etat de la Phase A"
    )


def test_index_corridor_reaches_the_propagated_state():
    base = _propagate()
    perturbed = _propagate(index_corridor=0.005, index_seed=777, corridor_lo=400.0, corridor_hi=700.0)
    assert not np.array_equal(base, perturbed), (
        "le corridor d'indice n'atteint pas la propagation d'etat de la Phase A"
    )


def test_poem_can_be_switched_off_in_the_propagated_state():
    """The POEM-off arms propagated their history WITH POEM. That is not the same run.

    ⚠️ TWO INGREDIENTS ARE REQUIRED, and both are physics rather than plumbing. Two
    earlier versions of this test failed, and both failures were the correct answer:

    1. **An upstream error.** With a perfect history and no noise there is nothing to
       compensate, so POEM and the absolute level agree to the last bit -- both
       returned exactly 53.19 nm.
    2. **A block history** (`block_start_layer = 0`). POEM anchors on the two last
       turning points OBSERVED; on an isolated layer there are not two of them, so
       `poem_ok` is False whatever `poem_enabled` says. Without the block, the
       compensation seen (51.85 nm) came from the ABSOLUTE fallback, not from POEM.

    Neither is a workaround to make a test pass: together they are the only regime in
    which the two branches are allowed to differ at all. Measured here, 2 nm too thick
    on layer 0: POEM lands at 52.744579 nm, the absolute fallback at 51.849247 nm.
    """
    history = np.tile(QWOT_500[:I_LAYER], (N_RUNS, 1))
    history[:, 0] += 2.0                       # layer 0 came out 2 nm too thick

    def run(poem: bool) -> np.ndarray:
        return update_run_states_kernel(
            QWOT_500, I_LAYER, history, BEST_WL,
            2.35 + 0j, 1.46 + 0j, 1.52 + 0j,
            1.0, np.zeros(N_RUNS, dtype=np.float64), 2.0, 0,
            0,                                  # block_start_layer = 0 -> POEM has anchors
            0.0, 0, 0.0,
            0.0, 0.0, 0, poem, 1, 0.0, 0, 0.0, 0.0,
        )

    on, off = run(True), run(False)
    assert np.all(on < 1e5) and np.all(off < 1e5), "montage plantant, le test ne prouve rien"
    assert not np.array_equal(on, off), (
        "poem_enabled n'atteint pas la propagation d'etat : les bras POEM-off "
        "propageaient un historique obtenu AVEC POEM"
    )
    assert on[0] == pytest.approx(52.744579, abs=1e-5)
    assert off[0] == pytest.approx(51.849247, abs=1e-5)


def test_the_draw_is_per_run_not_shared():
    """C2: the distortion is drawn once per RUN, never once for all of them.

    Passing a ready-made `affine_scale` scalar would have applied a single draw to
    every run -- a fresh C2 violation committed while repairing 17-23. The runs must
    therefore not all move by the same amount.
    """
    base = _propagate()
    drifted = _propagate(affine_scale_amp=0.05, affine_offset_amp=0.02, affine_seed=4242)
    deltas = drifted - base
    assert np.ptp(deltas) > 1e-12, (
        f"tous les tirages bougent de la meme quantite ({deltas}) : le tirage est "
        "partage au lieu d'etre fait par tirage"
    )


def test_an_active_corridor_without_an_envelope_raises():
    """17-25 again: silence was the bug, on this path too."""
    with pytest.raises(ValueError, match="corridor_lo/corridor_hi"):
        _propagate(index_corridor=0.005, index_seed=777)
