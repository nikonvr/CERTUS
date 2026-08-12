"""The margin must survive the plumbing -- A23 stage 2, end to end.

`turning_point_margins` is tested in isolation elsewhere, and it was wrong four times
before it was right. This file tests something different and just as easy to get wrong:
that the margin computed in the kernel actually REACHES the caller, and still responds
to the physics once it has.

🔴 A quantity that does not vary with what it measures is an artefact -- Trap 1, and the
project has paid for it three times. Applied to an instrument the rule is the same: if
the margin does not move when the noise moves, it is not measuring the noise, and every
critical-layer verdict built on it would be decoration.

The sweep is therefore the test. A single value proves nothing here.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from certus.physics.certus_strat_batch import simulate_stack_robustness_batch

N_LAYERS = 4
N_RUNS = 8
#: QWOT at 500 nm; monitored away from it, because a quarter-wave watched at its own
#: lambda_0 stops on the turning point where dT/dd = 0 and crashes 100 % -- correctly.
THICK = np.array([53.19, 85.62, 53.19, 85.62], dtype=np.float64)
WLS = np.array([540.0, 540.0, 540.0, 540.0], dtype=np.float64)
SENTINEL = 1e17


def _run(sigma: float, hysteresis: float = 1.66 * 5e-4):
    return simulate_stack_robustness_batch(
        THICK,
        WLS,
        np.full(N_LAYERS, 2.35 + 0j, dtype=np.complex128),
        np.full(N_LAYERS, 1.46 + 0j, dtype=np.complex128),
        np.full(N_LAYERS, 1.52 + 0j, dtype=np.complex128),
        np.zeros((N_RUNS, N_LAYERS), dtype=np.float64),
        1.0,
        2.0,
        0,
        np.full(N_LAYERS, sigma, dtype=np.float64),
        4242,
        hysteresis,
        0.0,
        0.0,
        0.0,
        0,
        True,
        1,
        0.0,
        0,
        0.0,
        0.0,
    )


def test_the_margins_come_out_of_the_batch_at_all():
    """Shape first: a margin that never leaves the kernel cannot be wrong, only absent."""
    thick, dyns, m_level, m_missed, m_fab = _run(5e-4)
    assert m_level.shape == (N_RUNS, N_LAYERS)
    assert m_missed.shape == (N_RUNS, N_LAYERS)
    assert m_fab.shape == (N_RUNS, N_LAYERS)
    assert np.isfinite(m_level).all(), "les marges ne doivent jamais etre NaN"


def test_at_least_one_margin_is_actually_constrained():
    """All-sentinel would mean 'nothing ever constrains anything' -- the inert filter."""
    _, _, m_level, m_missed, m_fab = _run(5e-4)
    constrained = sum(int((m < SENTINEL).sum()) for m in (m_level, m_missed, m_fab))
    assert constrained > 0, (
        "toutes les marges valent la sentinelle : rien n'est jamais contraint, "
        "ce qui est le motif du filtre inerte (controle 4 de 20)"
    )


def test_the_level_margin_follows_the_noise():
    """Trap 1, the decisive control. Divide sigma by 100 and the margin must grow.

    Less reading noise means the stopping level lands further inside the reachable
    band, so the layer is further from failing. A margin flat in sigma is not governed
    by the noise, and would designate a critical layer for reasons that are not physics.
    """
    got = []
    for sigma in (2e-3, 5e-4, 5e-5, 5e-6):
        _, _, m_level, _, _ = _run(sigma)
        finite = m_level[m_level < SENTINEL]
        assert finite.size, f"aucune marge de niveau contrainte a sigma = {sigma}"
        got.append(float(finite.min()))
    assert got[-1] > got[0], (
        f"la marge de niveau ne suit pas le bruit : {got} -- artefact, pas physique"
    )
    assert all(b >= a for a, b in pairwise(got)), (
        f"la marge de niveau n'est pas monotone en sigma : {got}"
    )


def test_the_counting_margin_follows_the_threshold():
    """The other knob: at a fixed signal, raising the hysteresis makes counting fragile.

    ⚠️ Reads the MISSED margin specifically, not a merged counting margin. A first
    version took min(missed, fabricated) and the number jumped from 0.15 A to 505 A
    between two noise levels -- a factor 3000, purely because the binding cause
    switched. Physically real, and unreadable. A23: one margin per layer AND per cause.

    A wider threshold needs a bigger ripple to see an extremum, so the missed-margin
    shrinks. That is the second half of the Trap 1 control -- the margin must respond
    to BOTH the noise and the rule, since it is the distance between them.
    """
    got = []
    for f in (0.5, 1.0, 1.66, 3.0):
        _, _, _, m_missed, _ = _run(5e-4, hysteresis=f * 5e-4)
        finite = m_missed[m_missed < SENTINEL]
        if finite.size:
            got.append((f, float(finite.min())))
    assert len(got) >= 2, f"pas assez de points contraints pour conclure : {got}"
    assert got[-1][1] < got[0][1], (
        f"la marge de comptage ne suit pas le seuil : {got}"
    )


def test_a_margin_is_reproducible_for_a_given_seed():
    """C2: same seed, same draws, same margins. Otherwise nothing is comparable."""
    a = _run(5e-4)[2]
    b = _run(5e-4)[2]
    assert np.array_equal(a, b, equal_nan=True)
