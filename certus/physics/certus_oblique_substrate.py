"""The oblique-incidence kernels read the substrate as transparent: what that costs, and saying it.

Every oblique kernel of this package (the spectrum, its backside variants and the analytic
gradients that DESIGN's objective is built from) keeps the real part of the substrate index and
drops its absorption. For a dielectric the loss is negligible; for a substrate that absorbs it is
not, and the screen shows nothing of it. This module says so, once per process, when it matters.
Reading the complex substrate in the kernels is a decision of the owner (docs/ETAT.md, section 5).
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

#: The largest absorption ``|k|`` of the substrate for which reading it as transparent costs less
#: than 1e-3 on R, at any angle, in both polarizations and for an index from 1.5 to 4.5. Measured
#: against ``tests/oracle/tmm_reference.py`` in ``tests/oracle/test_oblique_transparent_substrate_bound.py``;
#: for an index of 1.7 - 1.11i the loss reaches 0.23.
OBLIQUE_TRANSPARENT_SUBSTRATE_K_MAX = 0.03

_reported = False


def warn_if_oblique_substrate_absorbs(n_sub) -> bool:
    """Say, once per process, that the oblique kernels ignore the absorption of the substrate.

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
            "Oblique incidence: the substrate is read as transparent (real part of its index only). "
            f"Its absorption (k up to {k_max:.3g}) is ignored, so R and T can be off by more than 1e-3, "
            "and by up to about 0.25 for a metal. Normal incidence reads the complex index and is not affected."
        )
        logging.getLogger("CERTUS").warning(message)
        warnings.warn(message, UserWarning, stacklevel=3)
    return True
