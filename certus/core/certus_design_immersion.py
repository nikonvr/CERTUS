"""DESIGN in immersion: a coating lit from a medium of index n_inc (a glass cube, a prism) instead of air.

The kernels of CERTUS take the incident medium to be air. A problem lit from a medium of index n_inc has the R and
T, at every angle, of the problem in which every index is divided by n_inc and every wavelength too, with the same
thicknesses and the same angle: the tilted admittances are all divided by n_inc, and the phases
2 pi n d cos(theta) / lambda are unchanged. DESIGN therefore solves the air-equivalent problem, unchanged, and only
its inputs and the wavelengths it shows are translated here. Thicknesses, and their gradients, stay physical.

The materials of DESIGN follow the Cauchy law n = A + B / lambda^2, set by n at 400 and 700 nm; n(c lambda) / c is
again a Cauchy law (A / c, B / c^3), so an immersed material is an ordinary `Material`.

`certus.domain.immersion` holds the same equivalence with scaled thicknesses, checked against the independent
oracle (`tests/oracle/test_immersed_incidence.py`); `tests/oracle/test_design_immersion.py` checks this one.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from certus.domain.immersion import AIR_INDEX, check_incident_index
from certus.physics.certus_opt_tmm import Material

#: Wavelengths (nm) at which a DESIGN material is set.
_CAUCHY_ANCHORS_NM = (400.0, 700.0)
#: Keys of a worker configuration that hold wavelengths (nm): arrays, then single values (l0: quarter-wave reference).
_WAVELENGTH_ARRAY_KEYS = ("wls", "wls_vis", "wls_optim")
_WAVELENGTH_SCALAR_KEYS = ("l0", "wls_min", "wls_max")
#: Keys that switch on a back side, which the equivalence does not cover.
_BACK_SIDE_KEYS = ("has_back", "back", "use_back_coat")


def immersed_material(material: Material, n_inc: float) -> Material:
    """The material of the air-equivalent problem: index n(n_inc lambda) / n_inc."""
    c = check_incident_index(n_inc)
    n = np.real(material.get_nk(np.array(_CAUCHY_ANCHORS_NM, dtype=np.float64) * c)) / c
    return Material(float(n[0]), float(n[1]))


def _scaled_target(target: Any, c: float) -> Any:
    return dataclasses.replace(target, lmin=float(target.lmin) / c, lmax=float(target.lmax) / c)


def immerse_design_cfg(cfg: dict[str, Any], n_inc: float) -> dict[str, Any]:
    """The configuration of the air-equivalent problem, for any DESIGN worker.

    Args:
        cfg: a worker configuration (materials under "mats", wavelengths under "wls", targets under "tgts" and
            "oblique_tgts").
        n_inc: index of the incident medium, >= 1.

    Returns:
        `cfg` itself for n_inc = 1 (the default path is unchanged to the bit); otherwise a copy with the materials,
        the wavelengths and the target bands translated, and "incident_index" set.

    Raises:
        ValueError: n_inc is not an index >= 1, the design is not in oblique mode, or a back side is computed (the
            equivalence needs a semi-infinite exit medium).
    """
    c = check_incident_index(n_inc)
    if c == AIR_INDEX:
        return cfg
    if not cfg.get("oblique_mode", False):
        raise ValueError("an immersed incident medium needs the oblique mode")
    if any(cfg.get(key, False) for key in _BACK_SIDE_KEYS):
        raise ValueError("an immersed incident medium needs the back side switched off")
    out = dict(cfg)
    out["mats"] = {key: immersed_material(mat, c) for key, mat in cfg.get("mats", {}).items()}
    for key in _WAVELENGTH_ARRAY_KEYS:
        if cfg.get(key) is not None:
            out[key] = np.asarray(cfg[key], dtype=np.float64) / c
    for key in _WAVELENGTH_SCALAR_KEYS:
        if cfg.get(key) is not None:
            out[key] = float(cfg[key]) / c
    for key in ("tgts", "oblique_tgts"):
        if cfg.get(key):
            out[key] = [_scaled_target(t, c) for t in cfg[key]]
    out["incident_index"] = c
    return out


def true_wavelengths(wls: np.ndarray, n_inc: float) -> np.ndarray:
    """The wavelengths of the immersed problem from those of the air-equivalent one."""
    c = check_incident_index(n_inc)
    if c == AIR_INDEX:
        return wls
    return np.asarray(wls, dtype=np.float64) * c


def true_targets(targets: Any, n_inc: float) -> Any:
    """The targets of the immersed problem from those of the air-equivalent one (bands multiplied by n_inc)."""
    c = check_incident_index(n_inc)
    if c == AIR_INDEX or not targets:
        return targets
    return [dataclasses.replace(t, lmin=float(t.lmin) * c, lmax=float(t.lmax) * c) for t in targets]


def immersed_cfg_for(window: Any, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """`immerse_design_cfg` with the incident index of a DESIGN window; None, with the reason in the window's log, when
    the configuration cannot be immersed (no oblique mode, back side on)."""
    try:
        return immerse_design_cfg(cfg, incident_index_of(window))
    except ValueError as exc:
        window.log(f"Incident medium: {exc}.", "ERROR")
        return None


def incident_index_of(source: Any) -> float:
    """The incident index of a worker configuration (dict) or of a DESIGN window (its spin box); 1 if none."""
    if isinstance(source, dict):
        return float(source.get("incident_index", AIR_INDEX))
    spin = getattr(source, "incident_index_spin", None)
    return float(spin.value()) if spin is not None else AIR_INDEX
