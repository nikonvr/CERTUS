"""Axe 3 — STRAT doit classer contre la CIBLE, pas contre le spectre nominal.

👤 Le physicien : *« le plus important est la cible spectrale respectee. »* Or STRAT
classait sur l'ecart au spectre du NOMINAL, non pondere, et 📏 n'avait jamais recu la
cible — zero occurrence de `targets` dans tout le module. Il repondait donc a « quelle
strategie reproduit le mieux le spectre des epaisseurs concues ? » et non a « laquelle
respecte le mieux la cible ? ».

🔴 POURQUOI LA PONDERATION N'EST PAS UN RAFFINEMENT. Sur le juge de paix — un dichroique
passe-court — la bande BLOQUEE pese 146 points sur 301 avec une exigence de 0,1 % de
transmission, et un RMSE uniforme la fait compter EXACTEMENT AUTANT que la bande
passante, ou un ecart d'un point entier est sans consequence. L'exigence y est 500 fois
plus dure et elle pese pareil.

⚠️ DISTINCTION A PRESERVER, et elle est physique : le point VISE pendant le depot reste
le nominal fige — c'est le mecanisme meme de l'auto-compensation. Seule la figure de
merite QUI CLASSE passe a la cible ponderee. Ces tests ne touchent donc rien du noyau de
croissance.

🔴 PERIMETRE — SEUL LE DICHROIQUE 48 COUCHES EST UN EXEMPLE VALABLE.
👤 Le physicien, 2026-08-06. Les donnees de ce fichier sont SYNTHETIQUES : elles servent
a verifier une mecanique de calcul, pas a mesurer une grandeur physique. Aucune
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

#: Les zones du juge de paix, telles que le physicien les enonce : passante a ~96 % de
#: transmission jusqu'a 540 nm, bloquee sous 0,1 % au-dela de 560 nm. La transition
#: n'est PAS specifiee — et c'est volontaire, personne ne pilote la forme d'un front.
DICHROIC_ZONES = [
    Target(400.0, 540.0, 0.96, 0.96, 1.0, True),
    Target(560.0, 700.0, 0.0, 0.0, 10.0, True),
]


def _rmse(target, weights=None):
    return compute_batch_rmse(THICK, WL, _EMPTY, _EMPTY, N_SUB, target, N_LAYERS, weights)


@pytest.mark.unit
def test_omitting_weights_is_bit_identical_to_passing_none():
    """Le chemin par defaut doit etre le meme, argument omis ou explicitement None.

    Sans cela, un A/B contre le baseline mesurerait la specialisation numba autant que
    le changement de modele.
    """
    flat = np.full(WL.size, 0.5)
    assert np.array_equal(_rmse(flat), _rmse(flat, None))


@pytest.mark.unit
def test_uniform_weights_reproduce_the_unweighted_functional():
    """🔴 Des poids UNIFORMES doivent redonner exactement le RMSE non pondere.

    C'est la condition qui rend la ponderation interpretable : si des poids constants
    changeaient le resultat, le chiffre pondere ne serait pas comparable au chiffre
    historique, et l'axe 3 melangerait deux effets.
    """
    flat = np.full(WL.size, 0.5)
    ref = _rmse(flat)
    got = _rmse(flat, np.ones(WL.size))
    assert float(np.max(np.abs(ref - got))) == 0.0


@pytest.mark.unit
def test_zero_total_weight_returns_infinity_not_zero():
    """Aucune zone ne recouvrant la grille, le score doit ETRE INFINI.

    Rendre 0 ferait passer n'importe quelle strategie pour parfaite — un score de zero
    est le meilleur possible. C'est le mode de defaillance silencieux typique : une
    configuration mal saisie transformerait le classement en tirage au sort sans qu'une
    seule ligne de journal ne le signale.
    """
    flat = np.full(WL.size, 0.5)
    out = _rmse(flat, np.zeros(WL.size))
    assert np.all(np.isinf(out))


@pytest.mark.unit
def test_zones_weight_the_specified_bands_and_only_them():
    """Les zones doivent ponderer ce qui est specifie, et laisser le reste a zero.

    📏 Sur les zones du dichroique, 282 points sur 301 sont ponderes. Les 19 restants
    sont exactement la TRANSITION 540-560 nm, que personne n'a specifiee.

    📌 Consequence de premier ordre, et elle n'est pas anodine : aujourd'hui le score de
    STRAT est essentiellement une mesure de DECALAGE DU FRONT (le front p95 vaut 9,2
    points quand la bande passante vaut 1,7). Avec des zones correctes, le front cesse
    de compter — on ne juge plus une strategie sur une grandeur que l'utilisateur n'a
    jamais demandee.
    """
    vals, weights = prepare_targets_vectorized(WL, DICHROIC_ZONES)

    assert int(np.count_nonzero(weights)) == 282
    edge = (WL > 540.0) & (WL < 560.0)
    assert np.all(weights[edge] == 0.0), "la transition non specifiee est ponderee"
    assert np.all(weights[~edge] > 0.0), "une bande specifiee n'est pas ponderee"

    # La cible interpole lineairement de tmin a tmax sur chaque zone ; ici les deux
    # bornes sont egales, donc la valeur est constante par bande.
    assert vals[np.argmin(np.abs(WL - 450.0))] == pytest.approx(0.96)
    assert vals[np.argmin(np.abs(WL - 650.0))] == pytest.approx(0.0)


@pytest.mark.unit
def test_uniform_weighting_cannot_tell_the_two_bands_apart_at_all():
    """🔴 A poids egaux, une erreur en bande BLOQUEE et la meme en bande PASSANTE ont
    RIGOUREUSEMENT le meme cout — et c'est le coeur du probleme.

    📏 Sur le juge de paix, les deux bandes font exactement la meme largeur : 141 points
    chacune sur les 301 de la grille. Un RMSE uniforme est donc litteralement INCAPABLE
    de distinguer une strategie qui rate la bande bloquee d'une strategie qui rate la
    bande passante — les deux scores sont egaux a la precision machine.

    Or l'exigence n'est pas la meme d'un facteur ~500 : 0,1 % de transmission en bande
    bloquee contre un point entier tolerable en bande passante. **Ce n'est pas un defaut
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
