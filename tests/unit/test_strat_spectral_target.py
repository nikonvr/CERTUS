"""Axe 3 — STRAT doit classer contre la CIBLE, pas contre le spectre nominal.

👤 Le physicien : *« le plus important est la cible spectrale respectee. »* Or STRAT
classified on the deviation from the NOMINAL spectrum, unweighted, and 📏 had never received the
target — zero occurrences of `targets` throughout the module. He therefore responded to “what
strategy best reproduces the spectrum of thicknesses designed? » and not “which
best respects the target? ".

🔴 WHY WEIGHTING IS NOT A REFINEMENT. On the justice of the peace — a dichroic
passe-court — la bande BLOQUEE pese 146 points sur 301 avec une exigence de 0,1 % de
transmission, et un RMSE uniforme la fait compter EXACTEMENT AUTANT que la bande
passing, where a deviation of a whole point is of no consequence. The requirement is there 500 times
plus dure et elle pese pareil.

⚠️ DISTINCTION TO PRESERVE, and it is physical: the point AIMED during the deposit remains
le nominal fige — c'est le mecanisme meme de l'auto-compensation. Seule la figure de
merit WHO CLASSIFIES moves to the weighted target. These tests therefore do not touch anything from the core of
croissance.

🔴 PERIMETER — ONLY 48-LAYER DICHROIC IS A VALID EXAMPLE.
👤 The Physicist, 2026-08-06. The data in this file is SYNTHETIC: they are used
to verify a calculation mechanism, not to measure a physical quantity. None
conclusion sur le monitoring ne peut en etre tiree. Le juge de paix est
`example/example_strat/JSON-strat-example.json`.
"""

import numpy as np
import pytest

import certus_physics  # noqa: F401  (facade : evite l'import circulaire)
from certus_physics import compute_batch_rmse, prepare_targets_vectorized
from certus_physics.structures import Target

WL = np.linspace(400.0, 700.0, 301)
N_SUB = np.full(WL.size, complex(1.52, 0.0), dtype=np.complex128)
N_LAYERS = np.full((WL.size, 4), complex(2.3, 0.0), dtype=np.complex128)
THICK = np.array([[60.0, 100.0, 60.0, 100.0], [61.0, 100.0, 60.0, 100.0]])
_EMPTY = np.empty(0, dtype=np.complex128)

#: The zones of the justice of the peace, as the physicist states them: passing at ~96% of
#: transmission jusqu'a 540 nm, bloquee sous 0,1 % au-dela de 560 nm. La transition
#: is NOT specified — and this is voluntary, no one controls the shape of a front.
DICHROIC_ZONES = [
    Target(400.0, 540.0, 0.96, 0.96, 1.0, True),
    Target(560.0, 700.0, 0.0, 0.0, 10.0, True),
]


def _rmse(target, weights=None):
    return compute_batch_rmse(THICK, WL, _EMPTY, _EMPTY, N_SUB, target, N_LAYERS, weights)


@pytest.mark.unit
def test_omitting_weights_is_bit_identical_to_passing_none():
    """Le chemin par defaut doit etre le meme, argument omis ou explicitement None.

    Without this, an A/B against the baseline would measure numba specialization as much as
    le changement de modele.
    """
    flat = np.full(WL.size, 0.5)
    assert np.array_equal(_rmse(flat), _rmse(flat, None))


@pytest.mark.unit
def test_uniform_weights_reproduce_the_unweighted_functional():
    """🔴 Des poids UNIFORMES doivent redonner exactement le RMSE non pondere.

    This is the condition which makes the weighting interpretable: if constant weights
    changeaient le resultat, le chiffre pondere ne serait pas comparable au chiffre
    historique, et l'axe 3 melangerait deux effets.
    """
    flat = np.full(WL.size, 0.5)
    ref = _rmse(flat)
    got = _rmse(flat, np.ones(WL.size))
    assert float(np.max(np.abs(ref - got))) == 0.0


@pytest.mark.unit
def test_zero_total_weight_returns_infinity_not_zero():
    """No area covering the grid, the score must BE INFINITE.

    Returning 0 would make any strategy look perfect — a score of zero
    est le meilleur possible. C'est le mode de defaillance silencieux typique : une
    incorrectly entered configuration would transform the ranking into a draw without a
    seule ligne de journal ne le signale.
    """
    flat = np.full(WL.size, 0.5)
    out = _rmse(flat, np.zeros(WL.size))
    assert np.all(np.isinf(out))


@pytest.mark.unit
def test_zones_weight_the_specified_bands_and_only_them():
    """Zones should weight what is specified, and leave the rest at zero.

    📏 Sur les zones du dichroique, 282 points sur 301 sont ponderes. Les 19 restants
    are exactly the 540-560 nm TRANSITION, which no one specified.

    📌 Consequence de premier ordre, et elle n'est pas anodine : aujourd'hui le score de
    STRAT est essentiellement une mesure de DECALAGE DU FRONT (le front p95 vaut 9,2
    points when the bandwidth is 1.7). With correct zones, the front ceases
    to count — we no longer judge a strategy on a quantity that the user does not have
    never asked.
    """
    vals, weights = prepare_targets_vectorized(WL, DICHROIC_ZONES)

    assert int(np.count_nonzero(weights)) == 282
    edge = (WL > 540.0) & (WL < 560.0)
    assert np.all(weights[edge] == 0.0), "la transition non specifiee est ponderee"
    assert np.all(weights[~edge] > 0.0), "une bande specifiee n'est pas ponderee"

    #The target linearly interpolates from tmin to tmax on each zone; here both
    #terminals are equal, so the value is constant per band.
    assert vals[np.argmin(np.abs(WL - 450.0))] == pytest.approx(0.96)
    assert vals[np.argmin(np.abs(WL - 650.0))] == pytest.approx(0.0)


@pytest.mark.unit
def test_uniform_weighting_cannot_tell_the_two_bands_apart_at_all():
    """🔴 At equal weight, an error in BLOCKED band and the same in PASSENGER band have
    RIGOUREUSEMENT le meme cout — et c'est le coeur du probleme.

    📏 Sur le juge de paix, les deux bandes font exactement la meme largeur : 141 points
    each on the 301 of the grid. A uniform RMSE is therefore literally INCAPABLE
    de distinguer une strategie qui rate la bande bloquee d'une strategie qui rate la
    bande passante — les deux scores sont egaux a la precision machine.

    Or l'exigence n'est pas la meme d'un facteur ~500 : 0,1 % de transmission en bande
    blocked against an integer tolerable bandwidth point. **This is not a defect
    de sensibilite du critere, c'est une indifference exacte.** Et c'est exactement ce
    que la ponderation par zone repare.

    Ce test verrouille les DEUX faits : l'indifference a poids egaux, et le fait que le
    poids de zone la leve.
    """
    passband = WL <= 540.0
    stopband = WL >= 560.0
    assert int(passband.sum()) == int(stopband.sum()) == 141

    # A rate la bande bloquee, B rate la bande passante — de la meme quantite.
    err_a = np.where(stopband, 0.02, 0.001)
    err_b = np.where(stopband, 0.001, 0.02)

    def score(err, w_stop):
        w = np.zeros(WL.size)
        w[passband] = 1.0
        w[stopband] = w_stop
        return float(np.sqrt(np.sum(w * err**2) / np.sum(w)))

    # (1) A poids egaux : indifference EXACTE, aux derniers bits pres.
    assert score(err_a, 1.0) == pytest.approx(score(err_b, 1.0), rel=1e-12)

    # (2) A poids 10 sur la bande bloquee : A devient nettement plus mauvaise que B.
    assert score(err_a, 10.0) > 1.5 * score(err_b, 10.0), (
        "le poids de zone ne parvient pas a rendre la bande bloquee prioritaire : "
        f"A={score(err_a, 10.0):.5f} contre B={score(err_b, 10.0):.5f}"
    )
