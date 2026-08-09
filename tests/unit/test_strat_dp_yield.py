"""Axis 4.1 — YIELD enters the objective of the RFP, instead of being discarded.

Phase A measures the rate of non-terminating deposits **by layer and by length
d'onde**, le range dans chaque entree… et `certus_strat_workers_pipeline.py` ne
retenait que `x["cost"]` pour construire la carte donnee a la DP. Le plantage ne
servait qu'a un seuil binaire d'elimination : une lambda a 0,001 % et une a 0,106 %
were treated identically, even though they differed by a factor of one hundred on the sole
grandeur qui **se compose** sur la hauteur de l'empilement.

The yield of a stack is `prod(1 - p_i)`, whose logarithm is **additive** —
exactement ce qu'une DP de Bellman optimise exactement. Ce n'est pas un proxy :
`-log(1 - p)` est une composante **directe** de `P(conforme)`, la ou le cout en
nanometres affiche ρ = −0,04 avec le resultat.

⚠️ THIS DATA JUST BECAME INFORMATIONAL. As long as the detection was done on a
courbe TMM parfaite, le plantage valait zero presque partout et cette carte aurait ete
flat. Axis 4.1 was not feasible before axes 1.1 and 1.2.

🔴 PERIMETER — ONLY 48-LAYER DICHROIC IS A VALID EXAMPLE.
👤 The Physicist, 2026-08-06. The data in this file is SYNTHETIC: they are used
to verify a calculation mechanism, not to measure a physical quantity. None
conclusion sur le monitoring ne peut en etre tiree. Le juge de paix est
`example/example_strat/JSON-strat-example.json`.
"""

import math

import pytest

from certus.core.certus_strat_ranking import build_yield_cost_map, combine_cost_and_yield

#: Four lambdas of the same layer. The CHEAPEST in nanometers is also the one which does not
#: NEVER ends — this is the textbook case that the current lens cannot see.
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
    """The map must be exactly `-log(1 - p)`, not an approximation."""
    y = build_yield_cost_map(RAW)
    assert y[0][450.0] == 0.0
    assert y[0][452.0] == pytest.approx(-math.log1p(-0.001), rel=1e-12)
    assert y[0][454.0] == pytest.approx(-math.log1p(-0.05), rel=1e-12)


@pytest.mark.unit
def test_a_layer_that_never_completes_is_finite_but_enormous():
    """`p = 1` must be very expensive WITHOUT being worth infinity.

    `-log(0)` est infini, ce qui EXCLURAIT la candidate au lieu de la classer derniere —
    and if all the lambdas of a layer were worth 1, the DP would no longer have any path and
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
    expensive in nanometers**, which is here the one whose deposit NEVER ends. The cost
    en nm ignore totalement le plantage, qui n'intervient qu'ensuite comme couperet
    binary: the DP has therefore already spent its budget building paths that pass
    by an impossible layer.
    """
    assert _ranking(0.0)[0] == 456.0, "le cas d'ecole ne reproduit plus le defaut"


@pytest.mark.unit
def test_the_yield_term_demotes_it_immediately():
    """From weight 1, the lambda which never ends falls into LAST position."""
    assert _ranking(1.0)[-1] == 456.0


@pytest.mark.unit
def test_a_calibrated_weight_orders_by_yield_then_by_cost():
    """At sufficient weight, the order becomes that of yield, with cost dividing.

    This is the desired behavior: REORDERS performance where it is measurable, and
    laisse le cout en nanometres trancher ailleurs. 📏 Repere de calibration : a la
    tolerance of 0.107% per layer, `-log(1-p)` is 1.07e-3 nat; to weigh so much
    que 0,2 nm — l'ordre de grandeur du cout median mesure — il faut un poids d'environ
    200. **A balayer, pas a poser.**
    """
    assert _ranking(200.0) == [450.0, 452.0, 454.0, 456.0]


@pytest.mark.unit
def test_zero_weight_returns_the_very_same_object():
    """Zero weight = entry card AS IS, not a recalculated copy.

    Guarantees that no floating rounds are introduced on the default path: an A/B
    contre le baseline doit mesurer le changement de modele, et rien d'autre.
    """
    y = build_yield_cost_map(RAW)
    assert combine_cost_and_yield(COST_MAP, y, 0.0) is COST_MAP
    assert combine_cost_and_yield(COST_MAP, {}, 5.0) is COST_MAP


@pytest.mark.unit
def test_missing_crash_rate_costs_nothing_rather_than_crashing():
    """An entry without `crash_rate` should neither raise nor penalize.

    Entries come from several producers; a card that would explode on a
    cle absente rendrait l'axe 4.1 inutilisable des la premiere source heterogene.
    """
    y = build_yield_cost_map({0: [{"wl": 500.0, "cost": 0.3}]})
    assert y[0][500.0] == 0.0
