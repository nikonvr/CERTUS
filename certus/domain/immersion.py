"""Immersed incidence: a stack lit from a medium of index n_inc instead of air.

The transfer-matrix kernels of CERTUS take the incident medium to be air. An immersed system, such as a coating
on the hypotenuse of a glass cube, is computed by them exactly once every index (layers, exit medium) is divided
by n_inc and every thickness multiplied by it, at the same angle of incidence. All the tilted admittances are then
divided by n_inc, so the ratios that set R and T are unchanged, and the phases 2 pi n d cos(theta) / lambda are
kept: the Snell invariant of the scaled system, 1 x sin(theta), is the true one divided by n_inc, as every index
is. No transfer-matrix formula is written here (CLAUDE.md, rule 7); `tests/oracle/test_immersed_incidence.py`
checks the result against the independent oracle computed directly in immersion.

Valid when the exit medium is semi-infinite. Behind a substrate plate, CERTUS puts air, which this scaling would
turn into a medium of index 1 / n_inc: a back side must be switched off in immersion.
"""

from __future__ import annotations

import math

import numpy as np

#: The incident medium of every kernel of CERTUS.
AIR_INDEX = 1.0


def check_incident_index(n_inc: float) -> float:
    """Return `n_inc` as a float, or raise ValueError if it is not a finite index of at least 1."""
    value = float(n_inc)
    if not math.isfinite(value) or value < AIR_INDEX:
        raise ValueError(f"incident medium index must be finite and >= 1, got {n_inc!r}")
    return value


def to_air_equivalent(
    n_layers: np.ndarray,
    d_layers: np.ndarray,
    n_sub: np.ndarray,
    n_inc: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The system lit from air that has the R and T, at the same angle, of `(n_layers, d_layers, n_sub)` lit from
    a medium of index `n_inc`.

    Args:
        n_layers: complex layer indices, any shape (convention n - ik).
        d_layers: physical thicknesses in nm.
        n_sub: complex index of the exit medium, any shape.
        n_inc: real index of the incident medium, >= 1.

    Returns:
        `(n_layers / n_inc, d_layers * n_inc, n_sub / n_inc)`. For `n_inc == 1` the three input objects themselves,
        so that the default path is unchanged to the bit.
    """
    value = check_incident_index(n_inc)
    if value == AIR_INDEX:
        return n_layers, d_layers, n_sub
    return (
        np.asarray(n_layers, dtype=np.complex128) / value,
        np.asarray(d_layers, dtype=np.float64) * value,
        np.asarray(n_sub, dtype=np.complex128) / value,
    )

