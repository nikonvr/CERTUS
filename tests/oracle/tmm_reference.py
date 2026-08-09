"""Independent TMM Reference — written to be demonstrably fair, not fast.

REASON FOR BEING
-------------
This module does NOT share ANY code with ``certus.physics``. It is written directly
from Macleod, *Thin-Film Optical Filters*, 4th ed., chap. 2, with 2x2 matrices
explicit numpy. It is slow, not compiled, not optimized, and that is intentional: it serves
of oracle against which the project's fast paths are validated.

Any discrepancy between this module and ``certus.physics`` is a fault of one of them.
In case of doubt, this is the one that can be reread line by line facing the book.

CONVENTIONS
-----------
* Convention Macleod ``n̂ = n − ik`` avec ``k >= 0``. Le temps est en ``exp(+iωt)``,
  which makes the imaginary part of the index NEGATIVE for an absorbent medium.
* Admittance at normal incidence: ``η = n̂`` (vacuum admittance units).
* Phase shift of a layer: ``δ = 2π n̂ d / λ``, with ``d`` and ``λ`` in nanometers.
* Layer order — SAME as ``certus.physics.certus_opt_tmm.compute_TMM_generic``
  pour permettre une comparaison directe :

      index 0 = layer adjacent to the SUBSTRATE (output)
      index N-1 = layer adjacent to the INCIDENT medium (air)

  The Macleod matrix product goes from the incident middle (leftmost factor)
  towards the substrate (rightmost factor), i.e. ``M = L[N-1] @ ... @ L[0]``.

AUTO-VALIDATION
---------------
The conservation of energy ``R + T <= 1`` on any passive stack is a
property of physics, not of implementation. It is verified by the tests:
if the convention sign were reversed here, ``R + T > 1`` would appear
immediately (this is exactly the symptom described in CLAUDE.md §3).
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
        n: real part of the refractive index.
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
    """Characteristic matrix of a single layer, at normal incidence.

    Macleod eq. 2.88:

        M = [[    cos δ     , (i sin δ) / η ],
             [ i η sin δ    ,     cos δ     ]]

    with ``δ = 2π n̂ d / λ`` and ``η = n̂`` at normal incidence.

    Args:
        n_layer: complex layer index, ``n − ik`` convention.
        thickness_nm: physical thickness in nm.
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
    """Produces matrices characteristic of the stacking.

    Order: ``index 0`` = substrate side, ``index N-1`` = incident side.
    The product is therefore ``M = L[N-1] @ L[N-2] @ ... @ L[0]``.

    Args:
        n_layers: indices complexes, du substrat vers l'incident.
        thicknesses_nm: thicknesses in nm, same order.
        wavelength_nm: longueur d'onde dans le vide en nm.

    Returns:
        Matrice 2x2 complexe de l'assemblage.
    """
    n_arr = np.asarray(n_layers, dtype=np.complex128)
    d_arr = np.asarray(thicknesses_nm, dtype=np.float64)

    if n_arr.shape != d_arr.shape:
        raise ValueError(f"n_layers {n_arr.shape} et thicknesses {d_arr.shape} incompatibles")

    total = np.eye(2, dtype=np.complex128)
    # From the incident side (N-1) to the substrate side (0): right multiplication.
    for i in range(len(n_arr) - 1, -1, -1):
        total = total @ characteristic_matrix(n_arr[i], d_arr[i], wavelength_nm)

    return total


def rt_from_assembly(matrix: np.ndarray, n_inc: complex, n_sub: complex) -> tuple[float, float]:
    """Extract (R, T) from the assembly matrix. Macleod eq. 2.93 to 2.96.

        [B; C] = M @ [1; η_sub]

        r = (η_inc·B − C) / (η_inc·B + C)      R = |r|²

        T = 4 · η_inc · Re(η_sub) / |η_inc·B + C|² (real η_inc)

    Args:
        matrix: matrice 2x2 de l'assemblage.
        n_inc: index of the incident environment (real in practice: air).
        n_sub: indice complexe du substrat.

    Returns:
        Torque ``(R, T)``, reflectance and power transmittance.
    """
    bc = matrix @ np.array([1.0 + 0.0j, n_sub], dtype=np.complex128)
    b_val, c_val = bc[0], bc[1]

    y_sys = n_inc * b_val + c_val
    if abs(y_sys) < 1e-14:
        return 0.0, 0.0

    r_amp = (n_inc * b_val - c_val) / y_sys
    reflectance = float(abs(r_amp) ** 2)

    # T = 4·Re(η_inc)·Re(η_sub) / |η_inc·B + C|² — valid for a real incident.
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

    Signature aligned with ``compute_TMM_generic`` (same order conventions) in order to
    que la comparaison soit directe.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_layers: complex indices, index 0 = substrate side.
        thicknesses_nm: thicknesses in nm, same order.
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
    """Front face reflectance of a single layer on substrate.

    Contrepartie de ``certus.physics.certus_tmm_single_layer.calculate_RT_single_layer_single``.
    No rear face term: semi-infinite substrate, front reflection only.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_film_real: real part of the layer index.
        n_film_k: extinction coefficient k >= 0 of the layer.
        thickness_nm: physical thickness in nm.
        n_sub: real index of the substrate.
        n_inc: indice du milieu incident.

    Returns:
        Reflectance R in [0, 1].
    """
    matrix = characteristic_matrix(n_hat(n_film_real, n_film_k), thickness_nm, wavelength_nm)
    reflectance, _ = rt_from_assembly(matrix, complex(n_inc, 0.0), complex(n_sub, 0.0))
    return reflectance


# ── Incidence oblique ────────────────────────────────────────────────────────
#Macleod chap. 2.10. The Snell invariant ``n₀ sin θ₀`` is conserved in everything
#stacking; the angle in an absorbent diaper is COMPLEX, and that's normal.
#The inclined admittance replaces n̂ in the characteristic matrix:
#     s (TE) : η = n̂ cos θ
#     p (TM) : η = n̂ / cos θ
# and the phase shift becomes δ = 2π n̂ d cos θ / λ.


def _cos_theta_in_medium(n_medium: complex, snell_invariant: float) -> complex:
    """cos θ dans un milieu d'indice ``n_medium``, par l'invariant de Snell.

    Args:
        n_medium: indice complexe du milieu.
        snell_invariant: ``n₀ sin θ₀``, preserved throughout the stack.

    Returns:
        ``cos θ``, complex in general (complex angle in an absorbing medium).
    """
    sin_theta = snell_invariant / n_medium
    return np.sqrt(1.0 - sin_theta * sin_theta + 0j)


def tilted_admittance(n_medium: complex, snell_invariant: float, s_polarisation: bool) -> complex:
    """Inclined admittance of a medium. Macleod eq. 2.36 and 2.37.

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
    """(R, T) of a stack in oblique incidence, for a given polarization.

    Order of layers identical to the rest of the module and to ``certus.physics``:
    index 0 = substrate side, index N-1 = incident side.

    Args:
        wavelength_nm: longueur d'onde dans le vide en nm.
        n_layers: indices complexes, convention ``n − ik``.
        thicknesses_nm: thicknesses in nm.
        angle_deg: angle of incidence in the incident medium, in degrees.
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
