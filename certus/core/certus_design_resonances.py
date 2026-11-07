"""Headless input boundary for the optional DESIGN resonance tool."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from certus.physics.certus_opt_tmm import Material
from certus.physics.design_resonances import TransmissionBand, TransmissionProblem

if TYPE_CHECKING:
    from certus_physics.structures import Layer, Target


@dataclass(frozen=True)
class DesignResonanceInput:
    """Snapshot with physical thicknesses, locked-layer positions and its explicit reference grid."""

    problem: TransmissionProblem
    thicknesses: np.ndarray
    variable_indices: np.ndarray
    materials: tuple[str, ...]


@dataclass(frozen=True)
class LinearTarget:
    """DESIGN's target ramp: tmin at lmin to tmax at lmax (as in certus_design_worker_utils), between the points too."""

    lmin: float
    lmax: float
    tmin: float
    tmax: float

    def __call__(self, wavelengths: np.ndarray) -> np.ndarray:
        wl = np.asarray(wavelengths, dtype=np.float64)
        return self.tmin + (self.tmax - self.tmin) * (wl - self.lmin) / (self.lmax - self.lmin)


def resonance_lower_bounds(problem: TransmissionProblem, physical_nm: float,
                            optical_nm: float | None = None) -> np.ndarray:
    """Combine the explicit physical floor with any active file optical-thickness floor."""
    if not np.isfinite(physical_nm) or physical_nm <= 0:
        raise ValueError("The minimum physical thickness must be positive and finite.")
    bounds = np.full(len(problem.indices), physical_nm)
    if optical_nm is not None:
        if not np.isfinite(optical_nm) or optical_nm <= 0:
            raise ValueError("The minimum optical thickness must be positive and finite.")
        bounds = np.maximum(bounds, optical_nm / problem.indices.real)
    return bounds


def prepare_design_resonances(materials: dict[str, Material], layers: list[Layer], targets: list[Target],
                              thicknesses: np.ndarray, *, step_nm: float = 1.,
                              oblique: bool = False, backside: bool = False) -> DesignResonanceInput:
    """Require a genuinely constant Cauchy model, not an analytic continuation of sampled dispersion.

    This explicit tool uses the submitted paper's equal-weight uniform reference
    grid. It does not change DESIGN's ordinary spectral-quadrature objective.
    """
    if oblique or backside:
        raise ValueError("Resonance analysis currently requires normal incidence and no back surface.")
    if not layers:
        raise ValueError("The front design has no layers.")
    active = [t for t in targets if t.valid()]
    if not active:
        raise ValueError("At least one active transmission target is required.")
    if any(t.w != active[0].w for t in active):
        raise ValueError("The reference resonance tool requires equal target weights.")
    names = tuple(layer.mat for layer in layers)
    substrate_key = next((name for name in materials if name.lower() == "substrate"), None)
    if substrate_key is None:
        raise ValueError("The design substrate is missing.")
    for name in (*names, substrate_key):
        material = materials.get(name)
        if not isinstance(material, Material) or material.n4 != material.n7:
            raise ValueError(f"{name}: constant indices are required; set its 400-nm and 700-nm indices equal.")
    bands = tuple(TransmissionBand(float(t.lmin), float(t.lmax),
                                   float(t.tmin) if t.tmin == t.tmax else LinearTarget(t.lmin, t.lmax, t.tmin, t.tmax),
                                   step_nm) for t in active)
    problem = TransmissionProblem(np.array([materials[name].n4 for name in names]),
                                  float(materials[substrate_key].n4), bands)
    d = np.array(thicknesses, dtype=float, copy=True)
    if d.shape != (len(layers),) or not np.isfinite(d).all() or np.any(d <= 0):
        raise ValueError("The current physical thicknesses do not match the front layer list.")
    variable = np.array([i for i, layer in enumerate(layers) if layer.var], dtype=np.int64)
    return DesignResonanceInput(problem, d, variable, names)
