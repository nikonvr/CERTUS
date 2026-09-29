"""The substrate at oblique incidence: how an absorbing exit medium is read, and what is still not.

A substrate that absorbs (`n̂ = n - ik`, `k > 0`) has a COMPLEX angle of propagation at oblique incidence,
and a complex admittance. The oblique kernels that end on a semi-infinite substrate (the spectrum of a
front stack, and the analytic gradient of DESIGN's objective built from it) read it that way, through
`oblique_exit_admittance`. Before, they kept the real part of the index and dropped the absorption: for
an index of 1.7 - 1.11i at 30 degrees under a layer of 2.3 x 100 nm, R was off by 0.22 (s) and 0.19
(p), measured against `tests/oracle/tmm_reference.py`.

The kernels that build an INCOHERENT plate with a back side (the substrate is then the middle medium
of the stack: internal reflections, and the loss along the plate) still read the real part only. This
module says so, once per process, when it matters (`warn_if_oblique_substrate_absorbs`).
"""

from __future__ import annotations

import logging
import warnings

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


#: The largest absorption ``|k|`` of the substrate for which reading it as transparent costs less
#: than 1e-3 on R, at any angle, in both polarizations and for an index from 1.5 to 4.5. Measured
#: against ``tests/oracle/tmm_reference.py`` in ``tests/oracle/test_oblique_transparent_substrate_bound.py``;
#: for an index of 1.7 - 1.11i under a layer of 2.3 x 100 nm at 30 degrees the loss reaches 0.22.
OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX = 0.03

_reported = False


def warn_if_oblique_substrate_absorbs(n_sub) -> bool:
    """Say, once per process, that the oblique PLATE kernels (with a back side) ignore the absorption.

    The message goes to the log and out as a ``UserWarning``. Returns True when the substrate
    absorbs beyond ``OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX``, whether or not it was said before.
    """
    global _reported
    n_sub = np.asarray(n_sub)
    k_max = float(np.max(np.abs(n_sub.imag))) if n_sub.size else 0.0
    if not k_max > OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX:
        return False
    if not _reported:
        _reported = True
        message = (
            "Oblique incidence with a back side: the substrate is read as transparent (real part of its index "
            f"only). Its absorption (k up to {k_max:.3g}) is ignored, so R and T can be off by more than 1e-3, "
            "and by up to about 0.25 for a metal. The calculation without a back side, and normal incidence, "
            "read the complex index and are not affected."
        )
        logging.getLogger("CERTUS").warning(message)
        warnings.warn(message, UserWarning, stacklevel=3)
    return True
