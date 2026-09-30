"""What the kernels are given, checked at the door: a wrong input is an error, never a wave or a zero.

Measured on 2026-09-30, before this module:
- any polarization string but `s` was computed as `p`: `'TE'` (which is s), `'S '`, `''`, `'Avg'` and
  `'unpolarized'` all gave the p answer. DESIGN's target table offered `Avg` ("unpolarized average") and
  computed p;
- an angle of 95 degrees was accepted (`R = 1`, no message), and a NaN angle ended in a `SystemError`;
- a non-finite thickness, index, wavelength or substrate gave `(R, T) = (0, 0)`: an optimizer that minimizes
  `R` rewards a NaN;
- a layer that absorbs enough (a metal of `k = 7` thicker than 10 µm, a `k = 3.5` one thicker than 20 µm) made
  the matrix elements overflow, and `(R, T)` came out as `(0, 0)` where the answer is that of the
  semi-infinite absorber.

The kernels are compiled with `fastmath`, which lets the compiler assume that no value is NaN or infinite: the
check cannot live inside them. It lives at the door (the Python wrappers, and the objective functions that
receive the optimizer's trial vectors). The overflow, on the other hand, is in the kernels, and a guard there
changes their bits by one unit in the last place (measured: 1e-15 relative on the real-substrate paths), which
the rule of the bit-identical inactive path does not allow without the owner's word: the wrapper that is called
from Python refuses such a layer (`require_layers_below_overflow`); the kernels called from compiled code
(DESIGN's cost) still answer `(0, 0)` for one. Its thickness is far beyond any design of this suite.
"""

from __future__ import annotations

import math

import numpy as np

#: Where `cos` and `sin` of a complex phase overflow: `|Im(phase)|` of about 709 (`exp`), i.e. `2 pi k d / lambda`.
PHASE_IMAG_OVERFLOW = 700.0

_S_NAMES = frozenset({"s", "te"})
_P_NAMES = frozenset({"p", "tm"})


def is_s_polarization(polarization: object) -> bool:
    """True for s (TE), False for p (TM); anything else is an error, not p.

    Case and surrounding spaces do not matter (`'S '` is s), and `TE` / `TM` are the same waves as `s` / `p`.
    `Avg` is not accepted: it needs both waves, and no kernel computes their average.
    """
    name = str(polarization).strip().lower()
    if name in _S_NAMES:
        return True
    if name in _P_NAMES:
        return False
    raise ValueError(f"polarization must be 's' or 'p' (TE / TM), got {polarization!r}")


def check_incidence_angle(angle_deg: object) -> float:
    """The angle of incidence in degrees, if it is finite and no more than 90 in absolute value.

    Beyond grazing (90) the wave does not reach the stack; a NaN is no angle. The sign does not matter to R
    and T (a negative angle is the mirror image), so it is accepted.
    """
    try:
        angle = float(angle_deg)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"angle of incidence must be a number of degrees, got {angle_deg!r}") from None
    if not math.isfinite(angle):
        raise ValueError(f"angle of incidence must be finite, got {angle_deg!r}")
    if abs(angle) > 90.0:
        raise ValueError(f"angle of incidence must lie between -90 and 90 degrees, got {angle_deg!r}")
    return angle


def require_finite(**arrays: object) -> None:
    """Raise a ValueError naming the first argument that holds a NaN or an infinity."""
    for name, values in arrays.items():
        if not np.all(np.isfinite(np.asarray(values))):
            raise ValueError(f"{name} must be finite (no NaN, no infinity)")


def require_layers_below_overflow(thicknesses: object, n_layers: object, wls: object) -> None:
    """Raise a ValueError if a layer absorbs so much that the matrix of the kernels overflows.

    `|Im(phase)| = 2 pi |Im n| d / lambda` beyond `PHASE_IMAG_OVERFLOW`: the layer is opaque (its transmitted
    amplitude is below e^-700), it is the semi-infinite absorber, and the kernel would answer `(0, 0)`.
    """
    n = np.asarray(n_layers)
    d = np.asarray(thicknesses, dtype=np.float64)
    if n.ndim != 2 or n.shape[1] != d.shape[0] or n.size == 0:
        return
    reach = 2.0 * math.pi * np.max(np.abs(n.imag), axis=0) * np.abs(d) / float(np.min(np.asarray(wls)))
    worst = int(np.argmax(reach))
    if reach[worst] > PHASE_IMAG_OVERFLOW:
        raise ValueError(
            f"layer {worst} absorbs too much for a stack calculation (|Im phase| = {reach[worst]:.0f}, beyond "
            f"{PHASE_IMAG_OVERFLOW:.0f}): it is opaque, and the kernel would answer (R, T) = (0, 0)"
        )
