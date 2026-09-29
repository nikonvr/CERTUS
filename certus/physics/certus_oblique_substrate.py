"""The substrate at oblique incidence: how an absorbing exit medium is read.

A substrate that absorbs (`n̂ = n - ik`, `k > 0`) has a COMPLEX angle of propagation at oblique incidence,
and a complex admittance. The oblique kernels read it that way, through `oblique_exit_admittance`, for
what enters it from a stack (the spectrum of a front stack, the analytic gradient of DESIGN's objective,
and the forward direction of the R/T + derivatives kernel that DESIGN's plate is built from, at normal
incidence too). Before, they kept the real part of the index and dropped the absorption: for an index of
1.7 - 1.11i at 30 degrees under a layer of 2.3 x 100 nm, R was off by 0.22 (s) and 0.19 (p), measured
against `tests/oracle/tmm_reference.py`.

For the way through an incoherent plate with a back side, the substrate is a plate of thickness D that
loses flux on each pass: `certus_substrate_absorption`. The interfaces seen from inside keep the real
part of its index; the loss is carried by the plate.
"""

from __future__ import annotations

import numpy as np
from numba import njit

SMALL_EPSILON = 1e-12


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def oblique_exit_admittance(n_exit: complex, sin_theta_air: float, is_s_pol: bool) -> tuple[complex, bool]:
    """Tilted admittance of an exit medium that may absorb, and whether it is usable.

    Macleod eq. 2.36 (s: ``n cos θ``) and 2.37 (p: ``n / cos θ``), with the cosine of the angle in the
    medium taken from the Snell invariant ``sin θ₀`` (the incident medium is air). The angle is complex
    in an absorbing medium. This is the formula the stack layers already use in these kernels, and the
    one of ``tests/oracle/tmm_reference.py``.

    Returns ``(η, True)``, or ``(0, False)`` when the p admittance is not finite (``cos θ = 0``).
    """
    sin_t = sin_theta_air / n_exit
    cos_t = np.sqrt(1.0 - sin_t * sin_t)
    if is_s_pol:
        return n_exit * cos_t, True
    if abs(cos_t) < SMALL_EPSILON:
        return complex(0.0, 0.0), False
    return n_exit / cos_t, True
