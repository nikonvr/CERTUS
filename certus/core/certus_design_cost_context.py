"""Prepare the optical inputs shared by DESIGN's cost and gradient callers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


def design_layer_indices(
    material_indices: dict[str, np.ndarray], materials: Sequence[str], dtype: type = np.complex128,
) -> np.ndarray:
    """Build the contiguous wavelength-by-layer array for a material sequence."""
    return np.ascontiguousarray(np.array([material_indices[name] for name in materials], dtype=dtype).T)


def optim_prepare_stack_nk_back(
    mats: dict[str, Any],
    stack: Sequence[Any],
    wls: np.ndarray,
    *,
    stack_back: Sequence[Any],
    ep_back: Any,
    has_back_stack: bool,
    complex_dtype: type,
    float_dtype: type,
    substrate_key: str = "Substrate",
    cast_materials: bool = False,
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample material indices and assemble the substrate, front and rear arrays."""
    mats_nk = {key: material.get_nk(wls) for key, material in mats.items()}
    if cast_materials:
        mats_nk = {key: np.asarray(index, dtype=complex_dtype) for key, index in mats_nk.items()}
    if substrate_key not in mats_nk:
        keys = {key.lower(): key for key in mats_nk}
        substrate_key = keys.get("substrate", substrate_key)
    substrate = np.ascontiguousarray(mats_nk[substrate_key])
    front = design_layer_indices(mats_nk, [layer.mat for layer in stack], complex_dtype)
    if has_back_stack:
        rear = design_layer_indices(mats_nk, [layer.mat for layer in stack_back], complex_dtype)
        rear_thickness = np.ascontiguousarray(ep_back, dtype=float_dtype)
    else:
        rear = np.zeros((len(wls), 0), dtype=complex_dtype)
        rear_thickness = np.zeros(0, dtype=float_dtype)
    return mats_nk, substrate, front, rear, rear_thickness


@dataclass(frozen=True)
class DesignCostContext:
    """Wavelength grid, material indices, targets and rear geometry of a single cost."""

    wls: np.ndarray
    mats_nk: dict[str, np.ndarray]
    n_sub: np.ndarray
    n_front: np.ndarray
    n_back: np.ndarray
    d_back: np.ndarray
    has_back_calc: bool
    target_values: np.ndarray | None
    target_weights: np.ndarray | None

    def normal_targets(self) -> tuple[np.ndarray, np.ndarray]:
        if self.target_values is None or self.target_weights is None:
            raise ValueError("This context has no normal-incidence targets")
        return self.target_values, self.target_weights


def prepare_design_cost_context(
    mats: dict[str, Any],
    stack: Sequence[Any],
    wls: np.ndarray,
    targets: list | None,
    *,
    has_back_calc: bool = False,
    has_back_stack: bool = False,
    stack_back: Sequence[Any] = (),
    ep_back: Any = (),
    substrate_key: str = "Substrate",
    cast_materials: bool = False,
) -> DesignCostContext:
    """Build one context for the requested grid. Oblique callers supply their own target groups."""
    from certus.domain.constants import get_complex_dtype, get_float_dtype
    from certus_physics import prepare_targets_vectorized

    float_dtype, complex_dtype = get_float_dtype(), get_complex_dtype()
    wls = np.ascontiguousarray(wls, dtype=float_dtype)
    mats_nk, substrate, front, rear, rear_thickness = optim_prepare_stack_nk_back(
        mats, stack, wls, stack_back=stack_back, ep_back=ep_back, has_back_stack=has_back_stack,
        float_dtype=float_dtype, complex_dtype=complex_dtype, substrate_key=substrate_key,
        cast_materials=cast_materials,
    )
    values, weights = (None, None) if targets is None else prepare_targets_vectorized(wls, targets)
    return DesignCostContext(wls, mats_nk, substrate, front, rear, rear_thickness, has_back_calc, values, weights)
