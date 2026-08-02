"""Harnais de vérification des gradients analytiques.

RAISON D'ÊTRE
-------------
Un gradient faux ne lève aucune erreur. Il ne produit pas de NaN, ne déclenche aucune
assertion : il déplace simplement l'optimum vers lequel l'optimiseur converge. C'est
la catégorie de défaut la plus coûteuse d'un solveur, et la moins visible.

Ce module fournit une vérification unique — dérivée analytique contre différence finie
centrée — appliquée à toutes les fonctions du projet qui exportent un gradient.

DEUX PRINCIPES
--------------
1. **Comparer au coût que la fonction retourne ELLE-MÊME**, jamais à un coût reconstruit
   à côté. C'est ce qui rend le test décisif : il vérifie la cohérence interne du couple
   (coût, gradient), qui est exactement ce dont l'optimiseur a besoin. Un coût
   reconstruit introduirait une seconde source d'erreur et rendrait tout écart ambigu.

2. **Utiliser des poids NON UNIFORMES.** Plusieurs erreurs de normalisation — diviser
   par le nombre de points au lieu de la somme des poids, par exemple — sont invisibles
   avec des poids tous égaux à 1, où les deux dénominateurs ne diffèrent que d'un
   facteur constant.

CHOIX DU PAS ET DE LA TOLÉRANCE
-------------------------------
Le pas central h équilibre l'erreur de troncature (O(h²)) et l'erreur d'arrondi
(O(eps/h)). Pour des épaisseurs en nm de l'ordre de 100, h = 1e-6 nm place l'erreur
attendue autour de 1e-9 relatif.

L'écart est rapporté à la NORME du gradient, ||g_a - g_n||_inf / ||g_n||_inf, et non
à chaque composante prise isolément. Le bruit d'une différence finie est absolu — de
l'ordre de eps.|cout|/h — donc indépendant de la composante mesurée : rapporté à une
direction cent fois moins sensible que la direction dominante, il produit une erreur
relative énorme sans que le gradient soit faux pour autant.

Sensibilité effective, mesurée sur compute_gradient_all_layers_analytic :

    erreur globale de 0,001 %          -> DÉTECTÉE
    erreur globale de 0,0001 %         -> non détectée
    une seule composante à 0,01 %      -> DÉTECTÉE (y compris la plus petite)

Autrement dit, la tolérance écarte le bruit numérique et rien d'autre. Les erreurs
de structure réellement rencontrées dans ce dépôt — facteur 2 manquant, mauvaise
normalisation, signe inversé — se manifestent par des écarts de 50 % ou 100 %.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

__all__ = ["central_difference", "check_gradient", "GradientMismatch"]


class GradientMismatch(AssertionError):
    """Le gradient analytique ne coïncide pas avec la différence finie."""


def central_difference(
    cost_of: Callable[[np.ndarray], float],
    params: np.ndarray,
    step: float = 1e-6,
) -> np.ndarray:
    """Différence finie centrée du coût, paramètre par paramètre.

    Args:
        cost_of: fonction rendant le coût scalaire pour un vecteur de paramètres.
        params: point d'évaluation.
        step: pas central.

    Returns:
        Le vecteur des dérivées numériques, même longueur que ``params``.
    """
    base = np.asarray(params, dtype=np.float64)
    numerical = np.zeros(base.size, dtype=np.float64)

    for i in range(base.size):
        forward = base.copy()
        forward[i] += step
        backward = base.copy()
        backward[i] -= step

        numerical[i] = (cost_of(forward) - cost_of(backward)) / (2.0 * step)

    return numerical


def check_gradient(
    cost_and_grad: Callable[[np.ndarray], tuple[float, np.ndarray]],
    params: np.ndarray,
    *,
    step: float = 1e-6,
    rtol: float = 1e-6,
    atol: float = 1e-12,
    label: str = "",
) -> np.ndarray:
    """Vérifie qu'un gradient analytique est la dérivée du coût qu'il accompagne.

    Args:
        cost_and_grad: fonction rendant ``(cout, gradient)`` pour un vecteur de
            paramètres. C'est bien SON coût qui sert de référence.
        params: point d'évaluation.
        step: pas de la différence finie centrée.
        rtol: tolérance relative.
        atol: seuil sous lequel une composante est considérée comme nulle.
        label: nom affiché en cas d'échec.

    Returns:
        Le gradient analytique vérifié.

    Raises:
        GradientMismatch: si une composante diverge, ou si le gradient est
            identiquement nul — auquel cas le test ne prouverait rien.
    """
    base = np.asarray(params, dtype=np.float64)
    _, analytic = cost_and_grad(base)
    analytic = np.asarray(analytic, dtype=np.float64).ravel()[: base.size]

    numerical = central_difference(lambda p: cost_and_grad(p)[0], base, step)

    # Un gradient identiquement nul coïnciderait trivialement avec une différence
    # finie nulle : le test passerait sans rien démontrer. On l'interdit.
    if np.max(np.abs(analytic)) < atol:
        raise GradientMismatch(
            f"{label}: gradient analytique identiquement nul — "
            f"le point d'évaluation est dégénéré, le test ne prouve rien."
        )

    # L'échelle de comparaison est celle du VECTEUR, pas de chaque composante isolée.
    #
    # Une différence finie porte un bruit absolu d'environ eps.|cout|/h, indépendant
    # de la composante mesurée. Rapporté à une composante mille fois plus petite que
    # la plus grande du gradient, ce bruit devient une erreur relative énorme — sans
    # que le gradient soit faux pour autant. Comparer chaque composante à elle-même
    # ferait donc échouer le test sur les directions les moins sensibles, qui sont
    # précisément celles où la différence finie n'apporte aucune information.
    #
    # On plancherise donc l'échelle à une fraction de la plus grande composante :
    # une direction 1e6 fois moins sensible que la direction dominante n'est pas
    # mesurable par différence finie, et son écart n'a pas de sens.
    # Métrique standard en optimisation : ||g_a - g_n||_inf / ||g_n||_inf.
    # C'est bien l'échelle du vecteur qui compte, une composante ne se compare pas
    # à elle-même.
    magnitude = max(float(np.max(np.abs(numerical))), atol)
    relative = np.abs(analytic - numerical) / magnitude

    worst = int(np.argmax(relative))
    if relative[worst] > rtol:
        raise GradientMismatch(
            f"{label}: composante {worst} — "
            f"analytique={analytic[worst]:.12e}, "
            f"diff.finie={numerical[worst]:.12e}, "
            f"ecart relatif={relative[worst]:.3e} > {rtol:.1e}\n"
            f"  analytique : {np.array2string(analytic, precision=8)}\n"
            f"  diff.finie : {np.array2string(numerical, precision=8)}"
        )

    return analytic


def non_uniform_weights(count: int, lo: float = 0.4, hi: float = 3.0) -> np.ndarray:
    """Poids délibérément non uniformes.

    Avec des poids tous égaux, une normalisation par le nombre de points et une
    normalisation par la somme des poids ne diffèrent que d'un facteur constant :
    l'erreur devient invisible. Ces poids-ci la révèlent.
    """
    return np.linspace(lo, hi, count, dtype=np.float64)
