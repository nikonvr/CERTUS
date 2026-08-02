"""Le gradient analytique de l'objectif spline doit être la dérivée de son coût.

Ce gradient n'avait aucune vérification indépendante, alors que sa règle de chaîne
portait un défaut : en mode ``smooth`` — le mode PAR DÉFAUT dès K >= 4 — le facteur
``exp(L_lam)`` était évalué avec l'interpolation LINÉAIRE PAR MORCEAUX, tandis que le
modèle direct interpole par matrice cubique. Corrigé, mais rien ne l'empêchait de
revenir.

Les deux modes sont testés : ``smooth`` est le chemin par défaut, ``pwl`` celui de
repli quand K < 4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from gradient_harness import check_gradient  # noqa: E402

from certus.core.certus_index_config import DataType  # noqa: E402
from certus.spline.certus_index_spline_config import SplineOptConfig  # noqa: E402
from certus.spline.spline_objective import SplinePWLObjective  # noqa: E402


def _make_config(n_points: int = 40) -> SplineOptConfig:
    """Configuration minimale mais réaliste : mesure en transmission sur substrat.

    Les données sont synthétiques et lisses ; peu importe qu'elles correspondent à un
    empilement réel, ce qui est testé est la cohérence interne du couple (coût,
    gradient), pas la justesse physique — celle-ci relève de l'oracle TMM.
    """
    lam = np.linspace(420.0, 900.0, n_points)

    # Transmission synthétique, douce et strictement dans (0, 1).
    t_exp = 0.80 + 0.06 * np.sin(lam / 90.0)

    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=np.full(n_points, 1.52),
        data_type=DataType.TRANSMISSION,
        n_seg=3,
        d_lo=50.0,
        d_hi=400.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="test",
    )


def _sigma_knots(config: SplineOptConfig, count: int) -> np.ndarray:
    """Nœuds équirépartis en sigma = 1/lambda, ordre croissant."""
    lam = np.asarray(config.lam_nm, dtype=np.float64)
    sig_lo = 1.0 / lam.max()
    sig_hi = 1.0 / lam.min()
    return np.linspace(sig_lo, sig_hi, count)


def _pack(thickness_nm: float, n_values: np.ndarray, k_values: np.ndarray) -> np.ndarray:
    """Vecteur d'optimisation : [d, n_noeuds..., ln(k)_noeuds...] (dim = 1 + 2K)."""
    return np.concatenate(([thickness_nm], n_values, np.log(k_values)))


# K >= 4 déclenche le mode "smooth" ; K = 3 force le repli "pwl".
@pytest.mark.parametrize(
    "knot_count, expected_mode",
    [(3, "pwl"), (4, "smooth"), (6, "smooth")],
    ids=["K3-pwl", "K4-smooth", "K6-smooth"],
)
def test_gradient_spline_coincide_avec_les_differences_finies(
    knot_count: int, expected_mode: str
) -> None:
    """GARDE-FOU : la règle de chaîne doit suivre l'interpolation du modèle.

    En mode ``smooth``, évaluer le facteur ``exp(L_lam)`` avec les poids linéaires
    au lieu de la matrice cubique produit un gradient faux — donc un optimiseur qui
    converge ailleurs, sans la moindre erreur visible.
    """
    config = _make_config()
    knots = _sigma_knots(config, knot_count)
    objective = SplinePWLObjective(config, knots)

    assert objective._interp_mode == expected_mode, (
        f"le mode d'interpolation attendu etait {expected_mode}, "
        f"obtenu {objective._interp_mode} — le test ne couvre pas ce qu'il croit"
    )

    # Valeurs de nœuds délibérément NON ALIGNÉES.
    #
    # Avec des valeurs en progression linéaire, une spline cubique passant par des
    # points alignés EST la droite : l'interpolation lissée et la linéaire par
    # morceaux coïncident exactement, et le test devient aveugle à toute confusion
    # entre les deux. Vérifié — avec np.linspace, réintroduire le défaut de règle de
    # chaîne du mode "smooth" ne faisait échouer aucun test.
    # Un profil courbe, plus proche d'une dispersion réelle, les sépare.
    positions = np.linspace(0.0, 1.0, knot_count)
    n_values = 2.10 + 0.25 * np.exp(-3.0 * positions)
    k_values = 0.004 + 0.016 * positions**2
    params = _pack(120.0, n_values, k_values)

    gradient = objective._compute_analytic_gradient(params)
    if gradient is None:
        pytest.skip("gradient analytique non supporte pour cette configuration")

    def cost_and_grad(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        analytic = objective._compute_analytic_gradient(candidate)
        return float(objective(candidate)), analytic

    # Pas plus large que pour les épaisseurs : les nœuds n et ln(k) sont d'ordre 1,
    # pas 100, et un pas de 1e-6 y serait dominé par l'arrondi.
    # Découpage en familles : [epaisseur] [noeuds n] [noeuds ln(k)].
    #
    # Sans ce découpage, le test est AVEUGLE au bloc k. Mesuré sur cette
    # configuration : le gradient vaut ~6,7e+02 sur les nœuds n et ~1e-04 sur les
    # nœuds ln(k), six ordres de grandeur d'écart. Rapportée à la norme globale, une
    # erreur de 2 % sur le bloc k pèse 3e-09 — indétectable. Or c'est précisément le
    # bloc k que la règle de chaîne du mode "smooth" affecte, via son facteur
    # exp(L_lam). Vérifié : sans découpage, réintroduire le défaut ne faisait échouer
    # aucun test.
    blocks = [
        (0, 1),
        (1, 1 + knot_count),
        (1 + knot_count, 1 + 2 * knot_count),
    ]

    check_gradient(
        cost_and_grad,
        params,
        step=1e-7,
        rtol=1e-4,
        blocks=blocks,
        label=f"gradient spline K={knot_count} mode={expected_mode}",
    )


def test_le_mode_smooth_est_bien_le_defaut() -> None:
    """Le mode par défaut doit rester "smooth" dès que K le permet.

    Si ce contrat changeait, les tests ci-dessus continueraient de passer tout en
    ne couvrant plus le chemin réellement emprunté en production.
    """
    config = _make_config()
    objective = SplinePWLObjective(config, _sigma_knots(config, 5))

    assert objective._interp_mode == "smooth"
    assert objective._interp_mat is not None


def test_mode_et_matrice_restent_coherents() -> None:
    """GARDE-FOU : _interp_mode et _interp_mat doivent s'accorder.

    Ils étaient résolus ensemble puis _interp_mode se faisait réaffecter plus bas
    avec la chaîne brute de la config. Pour K < 4, cela remettait "smooth" alors que
    _interp_mat valait None : le gradient prenait la branche smooth et opérait sur
    None.
    """
    config = _make_config()

    for knot_count in (2, 3, 4, 8):
        objective = SplinePWLObjective(config, _sigma_knots(config, knot_count))

        if objective._interp_mode == "smooth":
            assert objective._interp_mat is not None, (
                f"K={knot_count} : mode smooth mais matrice absente"
            )
        else:
            assert objective._interp_mode == "pwl"
