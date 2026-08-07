"""Axe 4.1 — le RENDEMENT entre dans l'objectif de la DP, au lieu d'etre jete.

La Phase A mesure le taux de depots non terminables **par couche et par longueur
d'onde**, le range dans chaque entree… et `certus_strat_workers_pipeline.py` ne
retenait que `x["cost"]` pour construire la carte donnee a la DP. Le plantage ne
servait qu'a un seuil binaire d'elimination : une lambda a 0,001 % et une a 0,106 %
etaient traitees a l'identique, alors qu'elles different d'un facteur cent sur la seule
grandeur qui **se compose** sur la hauteur de l'empilement.

Le rendement d'un empilement vaut `prod(1 - p_i)`, dont le logarithme est **additif** —
exactement ce qu'une DP de Bellman optimise exactement. Ce n'est pas un proxy :
`-log(1 - p)` est une composante **directe** de `P(conforme)`, la ou le cout en
nanometres affiche ρ = −0,04 avec le resultat.

⚠️ CETTE DONNEE VIENT DE DEVENIR INFORMATIVE. Tant que la detection se faisait sur une
courbe TMM parfaite, le plantage valait zero presque partout et cette carte aurait ete
plate. L'axe 4.1 n'etait pas realisable avant les axes 1.1 et 1.2.

🔴 PERIMETRE — SEUL LE DICHROIQUE 48 COUCHES EST UN EXEMPLE VALABLE.
👤 Le physicien, 2026-08-06. Les donnees de ce fichier sont SYNTHETIQUES : elles servent
a verifier une mecanique de calcul, pas a mesurer une grandeur physique. Aucune
conclusion sur le monitoring ne peut en etre tiree. Le juge de paix est
`example/example_strat/JSON-strat-example.json`.
"""

import math

import pytest

from certus.core.certus_strat_ranking import build_yield_cost_map, combine_cost_and_yield

#: Quatre lambda d'une meme couche. La MOINS CHERE en nanometres est aussi celle qui ne
#: se termine JAMAIS — c'est le cas d'ecole que l'objectif actuel ne sait pas voir.
RAW = {
    0: [
        {"wl": 450.0, "cost": 0.20, "crash_rate": 0.000},
        {"wl": 452.0, "cost": 0.18, "crash_rate": 0.001},
        {"wl": 454.0, "cost": 0.15, "crash_rate": 0.050},
        {"wl": 456.0, "cost": 0.10, "crash_rate": 1.000},
    ]
}
COST_MAP = {0: {e["wl"]: e["cost"] for e in RAW[0]}}


def _ranking(weight: float) -> list[float]:
    m = combine_cost_and_yield(COST_MAP, build_yield_cost_map(RAW), weight)
    return [wl for wl, _ in sorted(m[0].items(), key=lambda kv: kv[1])]


@pytest.mark.unit
def test_yield_map_is_the_log_of_the_yield():
    """La carte doit valoir exactement `-log(1 - p)`, pas une approximation."""
    y = build_yield_cost_map(RAW)
    assert y[0][450.0] == 0.0
    assert y[0][452.0] == pytest.approx(-math.log1p(-0.001), rel=1e-12)
    assert y[0][454.0] == pytest.approx(-math.log1p(-0.05), rel=1e-12)


@pytest.mark.unit
def test_a_layer_that_never_completes_is_finite_but_enormous():
    """`p = 1` doit couter tres cher SANS valoir l'infini.

    `-log(0)` est infini, ce qui EXCLURAIT la candidate au lieu de la classer derniere —
    et si toutes les lambda d'une couche valaient 1, la DP n'aurait plus aucun chemin et
    ne rendrait rien. Le plafonnement a `1 - 1e-9` preserve l'ordre entre mauvaises
    options tout en les rendant irrecevables en pratique.
    """
    v = build_yield_cost_map(RAW)[0][456.0]
    assert math.isfinite(v)
    assert v > 20.0


@pytest.mark.unit
def test_todays_objective_prefers_the_wavelength_that_never_completes():
    """🔴 LE DEFAUT, MONTRE EN UNE LIGNE.

    A poids nul — l'objectif d'aujourd'hui — la DP classe premiere la lambda **la moins
    chere en nanometres**, qui est ici celle dont le depot ne se termine JAMAIS. Le cout
    en nm ignore totalement le plantage, qui n'intervient qu'ensuite comme couperet
    binaire : la DP a donc deja depense son budget a construire des chemins qui passent
    par une couche impossible.
    """
    assert _ranking(0.0)[0] == 456.0, "le cas d'ecole ne reproduit plus le defaut"


@pytest.mark.unit
def test_the_yield_term_demotes_it_immediately():
    """Des le poids 1, la lambda qui ne se termine jamais tombe en DERNIERE position."""
    assert _ranking(1.0)[-1] == 456.0


@pytest.mark.unit
def test_a_calibrated_weight_orders_by_yield_then_by_cost():
    """A poids suffisant, l'ordre devient celui du rendement, le cout departageant.

    C'est le comportement recherche : le rendement REORDONNE la ou il est mesurable, et
    laisse le cout en nanometres trancher ailleurs. 📏 Repere de calibration : a la
    tolerance de 0,107 % par couche, `-log(1-p)` vaut 1,07e-3 nat ; pour peser autant
    que 0,2 nm — l'ordre de grandeur du cout median mesure — il faut un poids d'environ
    200. **A balayer, pas a poser.**
    """
    assert _ranking(200.0) == [450.0, 452.0, 454.0, 456.0]


@pytest.mark.unit
def test_zero_weight_returns_the_very_same_object():
    """Poids nul = carte d'entree TELLE QUELLE, pas une copie recalculee.

    Garantit qu'aucun arrondi flottant ne s'introduit sur le chemin par defaut : un A/B
    contre le baseline doit mesurer le changement de modele, et rien d'autre.
    """
    y = build_yield_cost_map(RAW)
    assert combine_cost_and_yield(COST_MAP, y, 0.0) is COST_MAP
    assert combine_cost_and_yield(COST_MAP, {}, 5.0) is COST_MAP


@pytest.mark.unit
def test_missing_crash_rate_costs_nothing_rather_than_crashing():
    """Une entree sans `crash_rate` ne doit ni lever ni penaliser.

    Les entrees viennent de plusieurs producteurs ; une carte qui exploserait sur une
    cle absente rendrait l'axe 4.1 inutilisable des la premiere source heterogene.
    """
    y = build_yield_cost_map({0: [{"wl": 500.0, "cost": 0.3}]})
    assert y[0][500.0] == 0.0
