"""One model of an absorbing substrate, and the limits of the backside approximations, in one place.

A substrate that absorbs (`n̂ = n - ik`, `k > 0`) is a plate of thickness D: what enters through the front
stack crosses it, is partly lost on the way (Beer-Lambert), meets the back stack, and comes back. The
kernels that build that plate (`Rf`, `Tf` of the front stack, `Rf'` seen from the substrate, `Rb'` and
`Tb` of the back) combine them incoherently:

    T_total = Tf · Tb · τ / (1 - Rf' · Rb' · τ²)
    R_total = Rf + Tf · T_front_rev · Rb' · τ² / (1 - Rf' · Rb' · τ²)

`τ` is the flux left after ONE pass through the plate, `substrate_internal_transmittance`. `τ = 1` is the
plate without loss the kernels always assumed; `τ = 0` is the semi-infinite absorber (nothing comes back
from the back side, `T_total = 0`, `R_total = Rf`). The two are the ends of the same formula, so the
answer is continuous in `k`. Writing `Rb_eff = Rb' · τ²` and `Tb_eff = Tb · τ`, the combination is the
one without loss with `Rb_eff` and `Tb_eff` in place of `Rb'` and `Tb`: the callers that combine them
apply `τ` to the two back-side quantities and keep their formulas and their derivatives.

Before, three normal-incidence kernels treated every `|k| > 1e-8` as the semi-infinite absorber (`T = 0`,
a jump), STRAT validated the backside approximation up to `1e-5`, INDEX had its own Beer-Lambert plate with
a thickness, and the oblique plate kernels dropped the absorption altogether. A glass with `k = 4.4e-6`
(α = 1 cm⁻¹) gave `T = 0.000` where it transmits about 0.92.

The thickness of a substrate is not asked by DESIGN or STRAT: `DEFAULT_SUBSTRATE_THICKNESS_NM` stands in
for it (1 mm), and every kernel takes it as an optional trailing argument.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from numba import njit

SMALL_EPSILON = 1e-12

#: The thickness of the substrate when the caller does not give one: 1 mm, in nm.
DEFAULT_SUBSTRATE_THICKNESS_NM: Final[float] = 1.0e6

#: STRAT's own approximation of the backside is valid only for layers and a substrate that are real
#: enough (`validate_backside_real_clues`). These are its limits, defined here once; five modules of
#: `certus/physics` each had a copy.
K_MAX_LAYER_BACKSIDE: Final[float] = 0.001
K_MAX_SUBSTRATE_BACKSIDE: Final[float] = 0.00001


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def substrate_internal_transmittance(k: float, wavelength_nm: float, thickness_nm: float, cos_theta: float) -> float:
    """Fraction of the flux left after ONE pass through the plate: ``exp(-4π |k| D / (λ cos θ))``.

    `k` is the absorption index of the substrate (its sign does not matter: `n̂ = n - ik`), `D` its
    thickness, `θ` the angle of propagation in it (`cos θ = 1` at normal incidence). Exactly 1.0 for
    `k == 0`. A `cos θ` that vanishes (grazing) means the flux does not cross: 0.0.
    """
    if k == 0.0:
        return 1.0
    if cos_theta < SMALL_EPSILON or wavelength_nm <= 0.0:
        return 0.0
    return float(np.exp(-4.0 * np.pi * abs(k) * thickness_nm / (wavelength_nm * cos_theta)))


@njit(cache=True, fastmath=False, nogil=True, error_model="numpy")
def plate_internal_transmittance(n_sub: np.ndarray, wls: np.ndarray, angle_deg: float, thickness_nm: float) -> np.ndarray:
    """`substrate_internal_transmittance` per wavelength, at the angle of incidence `angle_deg` in air.

    The angle in the substrate comes from the REAL part of its index (Snell): a plate loses more when the
    ray crosses it obliquely. A real part that cannot carry the ray (`sin θ > 1`) lets nothing through.
    """
    tau = np.empty(len(wls), dtype=np.float64)
    sin_air = np.sin(np.deg2rad(angle_deg))
    for i in range(len(wls)):
        n_real = n_sub[i].real
        cos_sub = 0.0
        if n_real > SMALL_EPSILON:
            sin_sub = sin_air / n_real
            cos_sub = np.sqrt(max(0.0, 1.0 - sin_sub * sin_sub))
        tau[i] = substrate_internal_transmittance(n_sub[i].imag, wls[i], thickness_nm, cos_sub)
    return tau


def apply_plate_loss(
    rb_prime: np.ndarray,
    tb: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    angle_deg: float,
    thickness_nm: float = DEFAULT_SUBSTRATE_THICKNESS_NM,
) -> tuple[np.ndarray, np.ndarray]:
    """The back-side quantities of an incoherent plate, seen through the loss of the substrate.

    Returns `(Rb' · τ², Tb · τ)`: the callers keep their combination and its derivatives, written for a
    plate without loss, and put these in place of `Rb'` and `Tb`. Without absorption `τ` is exactly 1 and
    the two arrays come back unchanged, bit for bit.
    """
    tau = plate_internal_transmittance(
        np.ascontiguousarray(n_sub, dtype=np.complex128),
        np.ascontiguousarray(wls, dtype=np.float64),
        float(angle_deg),
        float(thickness_nm),
    )
    return rb_prime * tau * tau, tb * tau
