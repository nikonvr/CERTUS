"""Oracle contract tests for Numba CPUDispatcher functions (Lot D4)."""

import pytest
from numba.core.registry import CPUDispatcher

import certus_physics
from certus.physics.certus_opt_tmm import compute_RT_from_matrix
from certus.physics.certus_strat_growth import simulate_growth_kernel
from certus.physics.gradient_oblique import _compute_oblique_gradient_contrib_kernel
from certus.physics.gradient_metal import _compute_metal_tmm_gradient_kernel
from certus.physics.certus_strat_math import _solve_quadratic_target


def test_numba_cpu_dispatcher_contracts():
    """Action D4 — Verify all critical Numba JIT physics kernels are valid CPUDispatcher objects."""
    numba_kernels = [
        compute_RT_from_matrix,
        simulate_growth_kernel,
        _compute_oblique_gradient_contrib_kernel,
        _compute_metal_tmm_gradient_kernel,
        _solve_quadratic_target,
    ]

    for fn in numba_kernels:
        assert isinstance(
            fn, CPUDispatcher
        ), f"Physics kernel {fn.__name__} is not a valid Numba CPUDispatcher!"
