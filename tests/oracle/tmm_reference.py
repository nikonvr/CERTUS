"""Référence TMM indépendante — écrite pour être manifestement juste, pas rapide.

RAISON D'ÊTRE
-------------
Ce module ne partage AUCUN code avec ``certus.physics``. Il est écrit directement
depuis Macleod, *Thin-Film Optical Filters*, 4e éd., chap. 2, avec des matrices 2x2
numpy explicites. Il est lent, non compilé, non optimisé, et c'est voulu : il sert
d'oracle contre lequel les chemins rapides du projet sont validés.

Toute divergence entre ce module et ``certus.physics`` est un défaut de l'un des deux.
En cas de doute, c'est celui-ci qui est relisible ligne à ligne face au livre.

CONVENTIONS
-----------
* Convention Macleod ``n̂ = n − ik`` avec ``k >= 0``. Le temps est en ``exp(+iωt)``,
  ce qui rend la partie imaginaire de l'indice NÉGATIVE pour un milieu absorbant.
* Admittance à incidence normale : ``η = n̂`` (unités d'admittance du vide).
* Déphasage d'une couche : ``δ = 2π n̂ d / λ``, avec ``d`` et ``λ`` en nanomètres.
* Ordre des couches — IDENTIQUE à ``certus.physics.certus_opt_tmm.compute_TMM_generic``
  pour permettre une comparaison directe :

      indice 0     = couche adjacente au SUBSTRAT (sortie)
      indice N-1   = couche adjacente au milieu INCIDENT (air)

  Le produit matriciel de Macleod va du milieu incident (facteur le plus à gauche)
  vers le substrat (facteur le plus à droite), soit ``M = L[N-1] @ ... @ L[0]``.

AUTO-VALIDATION
---------------
La conservation de l'énergie ``R + T <= 1`` sur tout empilement passif est une
propriété de la physique, pas de l'implémentation. Elle est vérifiée par les tests :
si le signe de la convention était inversé ici, ``R + T > 1`` apparaîtrait
immédiatement (c'est exactement le symptôme décrit dans CLAUDE.md §3).
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "characteristic_matrix",
    "stack_matrix",
    "rt_from_assembly",
    "rt_stack",
    "r_single_layer_front",
    "n_hat",
    "tilted_admittance",
    "rt_stack_oblique",
]


def n_hat(n: float, k: float = 0.0) -> complex:
    """Construit un indice complexe dans la convention du projet : ``n̂ = n − ik``.

    Args:
        n: partie réelle de l'indice de réfraction.
        k: coefficient d'extinction, positif ou nul.

    Returns:
        L'indice complexe ``n - 1j*k``.

    Raises:
        ValueError: si ``k < 0`` (non physique dans cette convention).
    """
    if k < 0.0:
        raise ValueError(f"k doit être >= 0 dans la convention n̂ = n − ik (reçu k={k})")
    return complex(n, -k)


def characteristic_matrix(n_layer: complex, thickness_nm: float, wavelength_nm: float) -> np.ndarray:
    """Matrice caractéristique d'une couche unique, à incidence normale.

    Macleod éq. 2.88 :

        M = [[    cos δ     , (i sin δ) / η ],
             [ i η sin δ    ,     cos δ     ]]

    avec ``δ = 2π n̂ d / λ`` et ``η = n̂`` à incidence normale.

    Args:
        n_layer: indice complexe de la couche, convention ``n − ik``.
        thickness_nm: épaisseur physique en nm.
        wavelength_nm: longueur d'onde dans le vide en nm.

    Returns:
        Matrice 2x2 complexe.
    """
    delta = 2.0 * np.pi * n_layer * thickness_nm / wavelength_nm

    cos_d = np.cos(delta)
    sin_d = np.sin(delta)
    eta = n_layer

    return np.array(
        [
            [cos_d, 1j * sin_d / eta],
            [1j * eta * sin_d, cos_d],
        ],
        dtype=np.complex128,
    )


def stack_matrix(
    n_layers: np.ndarray | list[complex],
    thicknesses_nm: np.ndarray | list[float],
    wavelength_nm: float,
) -> np.ndarray:
    """Produit des matrices caractéristiques de l'empilement.

    Ordre : ``indice 0`` = côté substrat, ``indice N-1`` = côté incident.
    Le produit est donc ``M = L[N-1] @ L[N-2] @ ... @ L[0]``.

    Args:
        n_layers: indices complexes, du substrat vers l'incident.
        thicknesses_nm: épaisseurs en nm, même ordre.
        wavelength_nm: longueur d'onde dans le vide en nm.

    Returns:
        Matrice 2x2 complexe de l'assemblage.
    """
    n_arr = np.asarray(n_layers, dtype=np.complex128)
    d_arr = np.asarray(thicknesses_nm, dtype=np.float64)

    if n_arr.shape != d_arr.shape:
        raise ValueError(f"n_layers {n_arr.shape} et thicknesses {d_arr.shape} incompatibles")

    total = np.eye(2, dtype=np.complex128)
    # Du côté incident (N-1) vers le côté substrat (0) : multiplication à droite.
    for i in range(len(n_arr) - 1, -1, -1):
        total = total @ characteristic_matrix(n_arr[i], d_arr[i], wavelength_nm)

    return total


def rt_from_assembly(matrix: np.ndarray, n_inc: complex, n_sub: complex) -> tuple[float, float]:
    """Extrait (R, T) de la matrice d'assemblage. Macleod éq. 2.93 à 2.96.

        [B; C] = M @ [1; η_sub]

        r = (η_inc·B − C) / (η_inc·B + C)      R = |r|²

        T = 4 · η_inc · Re(η_sub) / |η_inc·B + C|²      (η_inc réel)

    Args:
        matrix: matrice 2x2 de l'assemblage.
        n_inc: indice du milieu incident (réel en pratique : air).
        n_sub: indice complexe du substrat.

    Returns:
        Couple ``(R, T)``, réflectance et transmittance en puissance.
    """
    bc = matrix @ np.array([1.0 + 0.0j, n_sub], dtype=np.complex128)
    b_val, c_val = bc[0], bc[1]

    y_sys = n_inc * b_val + c_val
    if abs(y_sys) < 1e-14:
        return 0.0, 0.0

    r_amp = (n_inc * b_val - c_val) / y_sys
    reflectance = float(abs(r_amp) ** 2)

    # T = 4·Re(η_inc)·Re(η_sub) / |η_inc·B + C|²  — valable pour un incident réel.
    transmittance = float(4.0 * n_inc.real * n_sub.real / (abs(y_sys) ** 2))

    return reflectance, transmittance


def rt_stack(
    wavelength_nm: float,
    n_layers: np.ndarray | list[complex],
    thicknesses_nm: np.ndarray | list[float],
    n_inc: complex = 1.0 + 0.0j,
    n_sub: complex = 1.52 + 0.0j,
) -> tuple[float, float]:
    """(R, T) d'un empilement complet sur substrat semi-infini.

    Signature alignée sur ``compute_TMM_generic`` (mêmes conventions d'ordre) afin
    que la comparaison soit directe.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_layers: indices complexes, indice 0 = côté substrat.
        thicknesses_nm: épaisseurs en nm, même ordre.
        n_inc: indice du milieu incident.
        n_sub: indice complexe du substrat.

    Returns:
        Couple ``(R, T)``.
    """
    matrix = stack_matrix(n_layers, thicknesses_nm, wavelength_nm)
    return rt_from_assembly(matrix, n_inc, n_sub)


def r_single_layer_front(
    wavelength_nm: float,
    n_film_real: float,
    n_film_k: float,
    thickness_nm: float,
    n_sub: float,
    n_inc: float = 1.0,
) -> float:
    """Réflectance de face avant d'une couche unique sur substrat.

    Contrepartie de ``certus.physics.certus_tmm_single_layer.calculate_RT_single_layer_single``.
    Pas de terme de face arrière : substrat semi-infini, réflexion avant seule.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_film_real: partie réelle de l'indice de la couche.
        n_film_k: coefficient d'extinction k >= 0 de la couche.
        thickness_nm: épaisseur physique en nm.
        n_sub: indice réel du substrat.
        n_inc: indice du milieu incident.

    Returns:
        Réflectance R dans [0, 1].
    """
    matrix = characteristic_matrix(n_hat(n_film_real, n_film_k), thickness_nm, wavelength_nm)
    reflectance, _ = rt_from_assembly(matrix, complex(n_inc, 0.0), complex(n_sub, 0.0))
    return reflectance


# ── Incidence oblique ────────────────────────────────────────────────────────
# Macleod chap. 2.10. L'invariant de Snell ``n₀ sin θ₀`` se conserve dans tout
# l'empilement ; l'angle dans une couche absorbante est COMPLEXE, et c'est normal.
# L'admittance inclinée remplace n̂ dans la matrice caractéristique :
#     s (TE) : η = n̂ cos θ
#     p (TM) : η = n̂ / cos θ
# et le déphasage devient δ = 2π n̂ d cos θ / λ.


def _cos_theta_in_medium(n_medium: complex, snell_invariant: float) -> complex:
    """cos θ dans un milieu d'indice ``n_medium``, par l'invariant de Snell.

    Args:
        n_medium: indice complexe du milieu.
        snell_invariant: ``n₀ sin θ₀``, conservé dans tout l'empilement.

    Returns:
        ``cos θ``, complexe en général (angle complexe dans un milieu absorbant).
    """
    sin_theta = snell_invariant / n_medium
    return np.sqrt(1.0 - sin_theta * sin_theta + 0j)


def tilted_admittance(n_medium: complex, snell_invariant: float, s_polarisation: bool) -> complex:
    """Admittance inclinée d'un milieu. Macleod éq. 2.36 et 2.37.

    Args:
        n_medium: indice complexe du milieu.
        snell_invariant: ``n₀ sin θ₀``.
        s_polarisation: True pour s (TE), False pour p (TM).

    Returns:
        ``η = n̂ cos θ`` en s, ``η = n̂ / cos θ`` en p.
    """
    cos_theta = _cos_theta_in_medium(n_medium, snell_invariant)
    return n_medium * cos_theta if s_polarisation else n_medium / cos_theta


def rt_stack_oblique(
    wavelength_nm: float,
    n_layers: np.ndarray | list[complex],
    thicknesses_nm: np.ndarray | list[float],
    angle_deg: float,
    s_polarisation: bool,
    n_inc: complex = 1.0 + 0.0j,
    n_sub: complex = 1.52 + 0.0j,
) -> tuple[float, float]:
    """(R, T) d'un empilement en incidence oblique, pour une polarisation donnée.

    Ordre des couches identique au reste du module et à ``certus.physics`` :
    indice 0 = côté substrat, indice N-1 = côté incident.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_layers: indices complexes, convention ``n − ik``.
        thicknesses_nm: épaisseurs en nm.
        angle_deg: angle d'incidence dans le milieu incident, en degrés.
        s_polarisation: True pour s (TE), False pour p (TM).
        n_inc: indice du milieu incident.
        n_sub: indice du substrat.

    Returns:
        Couple ``(R, T)``.
    """
    n_arr = np.asarray(n_layers, dtype=np.complex128)
    d_arr = np.asarray(thicknesses_nm, dtype=np.float64)

    snell = float((n_inc * np.sin(np.deg2rad(angle_deg))).real)

    total = np.eye(2, dtype=np.complex128)
    for i in range(len(n_arr) - 1, -1, -1):
        n_layer = n_arr[i]
        cos_theta = _cos_theta_in_medium(n_layer, snell)
        eta = tilted_admittance(n_layer, snell, s_polarisation)

        delta = 2.0 * np.pi * n_layer * d_arr[i] * cos_theta / wavelength_nm
        cos_d, sin_d = np.cos(delta), np.sin(delta)

        layer_matrix = np.array(
            [[cos_d, 1j * sin_d / eta], [1j * eta * sin_d, cos_d]],
            dtype=np.complex128,
        )
        total = total @ layer_matrix

    eta_inc = tilted_admittance(n_inc, snell, s_polarisation)
    eta_exit = tilted_admittance(n_sub, snell, s_polarisation)

    bc = total @ np.array([1.0 + 0.0j, eta_exit], dtype=np.complex128)
    b_val, c_val = bc[0], bc[1]

    y_sys = eta_inc * b_val + c_val
    if abs(y_sys) < 1e-14:
        return 0.0, 0.0

    reflectance = float(abs((eta_inc * b_val - c_val) / y_sys) ** 2)
    transmittance = float(4.0 * eta_inc.real * eta_exit.real / (abs(y_sys) ** 2))

    return reflectance, transmittance
