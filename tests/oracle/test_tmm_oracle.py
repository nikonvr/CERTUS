"""Confrontation of production TMM paths with an independent reference.

This is the safety net that was missing from the project. As long as these tests pass, a
refactoring physics modules cannot silently alter results
digital — which has happened at least twice in recent history
(bug de signe monocouche, perte de @njit lors de l'extraction des gradients).

Guiding principle: **a test that cannot fail when the bug is present is not
not a test.** Every test below has been verified as failing on the code before
correctif (voir les commentaires « GARDE-FOU »).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from tmm_reference import (  # noqa: E402
    n_hat,
    r_single_layer_front,
    rt_stack,
    rt_stack_oblique,
)

from certus.physics.certus_opt_tmm import compute_TMM_generic  # noqa: E402
from certus.physics.certus_tmm_single_layer import (  # noqa: E402
    calculate_RT_single_layer_single,
)

TWO_PI = 2.0 * math.pi

#Tolerance: we demand machine precision, not a vague resemblance.
#Production paths and oracle do the same operations in an order
#different ; 1e-12 leaves the arithmetic margin floating and nothing more.
ATOL = 1e-12

# ── Frozen corpus ─────────────────────────────── ───────────────────────────────
# Covers: transparent dielectric, low absorption, high absorption, metal
#(n < 1, high k), low index, very high index. The thicknesses sweep the
# sous-quart-d'onde, le quart-d'onde et le multi-onde.

MATERIALS = [
    pytest.param(2.30, 0.00, id="dielectrique-Nb2O5"),
    pytest.param(1.46, 0.00, id="dielectrique-SiO2"),
    pytest.param(2.30, 0.01, id="faible-absorption"),
    pytest.param(2.30, 0.05, id="absorption-moderee"),
    pytest.param(2.30, 0.50, id="forte-absorption"),
    pytest.param(2.30, 3.00, id="tres-forte-absorption"),
    pytest.param(0.15, 3.50, id="metal-argent"),
    pytest.param(1.20, 7.00, id="metal-aluminium"),
    pytest.param(4.00, 0.02, id="indice-tres-haut"),
]

THICKNESSES_NM = [5.0, 20.0, 59.8, 120.0, 400.0, 1000.0]
WAVELENGTHS_NM = [400.0, 550.0, 700.0, 1000.0]


@pytest.mark.parametrize("n_real, k_val", MATERIALS)
@pytest.mark.parametrize("thickness_nm", THICKNESSES_NM)
def test_single_layer_front_matches_oracle(n_real: float, k_val: float, thickness_nm: float) -> None:
    """``calculate_RT_single_layer_single`` must reproduce the oracle to machine precision.

    CAUTION: with the old sign (``phi_i = +k·n_imag·d`` to
    certus_tmm_single_layer.py:41) this test fails as soon as ``k > 0`` — until
    46 points difference at k=3, where the clamp saturated the reflectance at R=1.
    """
    produced = calculate_RT_single_layer_single(550.0, n_real, k_val, thickness_nm, 1.52)
    expected = r_single_layer_front(550.0, n_real, k_val, thickness_nm, 1.52)

    assert produced == pytest.approx(expected, abs=ATOL), (
        f"n={n_real} k={k_val} d={thickness_nm}nm : "
        f"production={produced:.10f} oracle={expected:.10f} "
        f"ecart={abs(produced - expected) * 100:.3f} points"
    )


@pytest.mark.parametrize("n_real, k_val", MATERIALS)
@pytest.mark.parametrize("thickness_nm", THICKNESSES_NM)
def test_infinite_substrate_matches_oracle(n_real: float, k_val: float, thickness_nm: float) -> None:
    """``calculate_reflection_infinite_substrate_single`` doit reproduire l'oracle.

    GUARD: this function developed the characteristic matrix by hand with
    ``-i·sin(δ)/n̂`` instead of ``+i`` from the project's Macleod convention. Exact to
    k = 0, it reached **82 points** of reflectance difference at k > 0. Living path:
    n,k adjustment of CERTUS_INDEX and its gradients by finite differences.
    It now delegates to ``compute_TMM_generic``.
    """
    from certus.physics.certus_opt_tmm import (
        calculate_reflection_infinite_substrate_single,
    )

    produced = calculate_reflection_infinite_substrate_single(
        550.0, n_real, k_val, thickness_nm, complex(1.52, 0.0)
    )
    expected = r_single_layer_front(550.0, n_real, k_val, thickness_nm, 1.52)

    assert produced == pytest.approx(expected, abs=ATOL), (
        f"n={n_real} k={k_val} d={thickness_nm}nm : "
        f"ecart={abs(produced - expected) * 100:.3f} points"
    )


@pytest.mark.parametrize("n_real, k_val", MATERIALS)
@pytest.mark.parametrize("wavelength_nm", WAVELENGTHS_NM)
def test_monolayer_generic_matches_oracle(n_real: float, k_val: float, wavelength_nm: float) -> None:
    """``compute_TMM_generic`` — production multi-layer path — on one layer."""
    layers = np.array([n_hat(n_real, k_val)], dtype=np.complex128)
    thicknesses = np.array([120.0], dtype=np.float64)

    r_prod, t_prod = compute_TMM_generic(
        TWO_PI / wavelength_nm, thicknesses, layers, 1.0 + 0.0j, 1.52 + 0.0j
    )
    r_ref, t_ref = rt_stack(
        wavelength_nm, [n_hat(n_real, k_val)], [120.0], 1.0 + 0.0j, 1.52 + 0.0j
    )

    assert r_prod == pytest.approx(r_ref, abs=ATOL), f"R : {r_prod} vs {r_ref}"
    assert t_prod == pytest.approx(t_ref, abs=ATOL), f"T : {t_prod} vs {t_ref}"


# Real stacks, from the simplest to the most representative of a design.
#Reminder of the order: index 0 = adjacent to the SUBSTRATE, index N-1 = adjacent to the AIR.
STACKS = [
    pytest.param([(1.46, 0.0)], [100.0], id="monocouche-SiO2"),
    pytest.param([(2.30, 0.0), (1.46, 0.0)], [59.8, 94.2], id="bicouche-HL"),
    pytest.param(
        [(2.30, 0.0), (1.46, 0.0), (2.30, 0.0), (1.46, 0.0)],
        [59.8, 94.2, 59.8, 94.2],
        id="quart-onde-HLHL",
    ),
    pytest.param(
        [(2.30, 0.02), (1.46, 0.0), (2.30, 0.02), (1.46, 0.0), (2.30, 0.02)],
        [59.8, 94.2, 59.8, 94.2, 30.0],
        id="HLHLH-absorbant",
    ),
    pytest.param(
        [(1.46, 0.0), (0.15, 3.5), (1.46, 0.0)],
        [80.0, 15.0, 80.0],
        id="metal-encapsule",
    ),
]


@pytest.mark.parametrize("layers_nk, thicknesses", STACKS)
@pytest.mark.parametrize("wavelength_nm", WAVELENGTHS_NM)
def test_multilayer_matches_oracle(
    layers_nk: list[tuple[float, float]], thicknesses: list[float], wavelength_nm: float
) -> None:
    """Empilements multicouches complets contre l'oracle."""
    complex_layers = [n_hat(n, k) for n, k in layers_nk]

    r_prod, t_prod = compute_TMM_generic(
        TWO_PI / wavelength_nm,
        np.array(thicknesses, dtype=np.float64),
        np.array(complex_layers, dtype=np.complex128),
        1.0 + 0.0j,
        1.52 + 0.0j,
    )
    r_ref, t_ref = rt_stack(wavelength_nm, complex_layers, thicknesses, 1.0 + 0.0j, 1.52 + 0.0j)

    assert r_prod == pytest.approx(r_ref, abs=ATOL), f"R : {r_prod} vs {r_ref}"
    assert t_prod == pytest.approx(t_ref, abs=ATOL), f"T : {t_prod} vs {t_ref}"


@pytest.mark.parametrize("layers_nk, thicknesses", STACKS)
@pytest.mark.parametrize("wavelength_nm", WAVELENGTHS_NM)
def test_energy_conservation(
    layers_nk: list[tuple[float, float]], thicknesses: list[float], wavelength_nm: float
) -> None:
    """R + T <= 1 sur tout empilement passif.

    This is a property of PHYSICS, not of implementation. Its violation is
    direct symptom of a reversed index convention (n+ik instead of n−ik):
    stacking then produces a non-physical gain. See CLAUDE.md §3.
    """
    complex_layers = [n_hat(n, k) for n, k in layers_nk]

    reflectance, transmittance = compute_TMM_generic(
        TWO_PI / wavelength_nm,
        np.array(thicknesses, dtype=np.float64),
        np.array(complex_layers, dtype=np.complex128),
        1.0 + 0.0j,
        1.52 + 0.0j,
    )

    assert reflectance >= -ATOL, f"R negatif : {reflectance}"
    assert transmittance >= -ATOL, f"T negatif : {transmittance}"
    assert reflectance + transmittance <= 1.0 + 1e-9, (
        f"GAIN NON PHYSIQUE : R+T = {reflectance + transmittance:.12f} > 1 "
        f"(lambda={wavelength_nm}nm). Convention d'indice probablement inversee."
    )


def test_absentee_half_wave_layer() -> None:
    """A half-wave layer is optically absent: R must equal that of the bare substrate.

    Exact analytical identity, independent of any implementation. Classic trap
    errors of factor 2 in the phase shift (δ = 2π n d / λ and not π n d / λ).
    """
    wavelength_nm = 550.0
    n_layer = 2.30
    half_wave_nm = wavelength_nm / (2.0 * n_layer)

    r_with_layer, _ = compute_TMM_generic(
        TWO_PI / wavelength_nm,
        np.array([half_wave_nm], dtype=np.float64),
        np.array([n_hat(n_layer, 0.0)], dtype=np.complex128),
        1.0 + 0.0j,
        1.52 + 0.0j,
    )
    r_bare = ((1.0 - 1.52) / (1.0 + 1.52)) ** 2

    assert r_with_layer == pytest.approx(r_bare, abs=1e-10)


def test_perfect_quarter_wave_antireflection() -> None:
    """A quarter-wave of index sqrt(n_sub) exactly cancels the reflection.

    Second analytical identity: jointly locks the phase shift AND the
    formule d'extraction R/T.
    """
    wavelength_nm = 550.0
    n_sub = 1.52
    n_ar = math.sqrt(n_sub)
    quarter_wave_nm = wavelength_nm / (4.0 * n_ar)

    reflectance, _ = compute_TMM_generic(
        TWO_PI / wavelength_nm,
        np.array([quarter_wave_nm], dtype=np.float64),
        np.array([n_hat(n_ar, 0.0)], dtype=np.complex128),
        1.0 + 0.0j,
        complex(n_sub, 0.0),
    )

    assert reflectance == pytest.approx(0.0, abs=1e-12)


def test_bare_interface_matches_fresnel() -> None:
    """Without layer, we must find Fresnel: R = ((1-ns)/(1+ns))²."""
    for n_sub in (1.46, 1.52, 2.0, 3.5):
        reflectance, _ = compute_TMM_generic(
            TWO_PI / 550.0,
            np.array([], dtype=np.float64),
            np.array([], dtype=np.complex128),
            1.0 + 0.0j,
            complex(n_sub, 0.0),
        )
        expected = ((1.0 - n_sub) / (1.0 + n_sub)) ** 2
        assert reflectance == pytest.approx(expected, abs=1e-12), f"n_sub={n_sub}"


# ── Implementation contracts ──────────────────────── ────────────────────────


# ── Incidence oblique ────────────────────────────────────────────────────────

ANGLES_DEG = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0]
OBLIQUE_STACK = [(2.30, 0.05), (1.46, 0.0), (2.30, 0.05)]
OBLIQUE_THICKNESSES = [59.8, 94.2, 59.8]


@pytest.mark.parametrize("angle_deg", ANGLES_DEG)
@pytest.mark.parametrize("s_pol", [True, False], ids=["pol-s", "pol-p"])
def test_oblique_matches_oracle(angle_deg: float, s_pol: bool) -> None:
    """Le chemin oblique de production doit reproduire l'oracle, s et p confondues.

    CLAUDE.md §5.1 notes that ``certus_tmm_oblique.py`` is correct because its callers
    pass ``phi.imag`` already signed, which offsets the conjugate returned by
    ``compute_complex_phase_components``. C'est une compensation, pas une preuve : ce test
    replaces it with an independent verification (inclined Macleod admittances,
    eq. 2.36-2.37, complex angle in the absorbent layers).
    """
    from certus.physics.certus_tmm_oblique import _oblique_stack_rt_single

    layers = [n_hat(n, k) for n, k in OBLIQUE_STACK]
    sin_air = math.sin(math.radians(angle_deg))
    cos_air = math.cos(math.radians(angle_deg))

    r_prod, t_prod = _oblique_stack_rt_single(
        550.0,
        np.array(layers, dtype=np.complex128),
        np.array(OBLIQUE_THICKNESSES, dtype=np.float64),
        sin_air,
        cos_air,
        1.0,
        1.52,
        s_pol,
    )
    r_ref, t_ref = rt_stack_oblique(
        550.0, layers, OBLIQUE_THICKNESSES, angle_deg, s_pol, 1.0 + 0.0j, 1.52 + 0.0j
    )

    assert r_prod == pytest.approx(r_ref, abs=ATOL), f"R : {r_prod} vs {r_ref}"
    assert t_prod == pytest.approx(t_ref, abs=ATOL), f"T : {t_prod} vs {t_ref}"


@pytest.mark.parametrize("s_pol", [True, False], ids=["pol-s", "pol-p"])
def test_oblique_at_zero_degrees_equals_normal_incidence(s_pol: bool) -> None:
    """At 0°, the two polarizations must restore exactly the normal incidence.

    Analytical identity: at zero angle, ``cos θ = 1`` and inclined admittances
    both degenerate towards ``n̂``. Jointly locks the Snell invariant,
    the two admittance formulas and the inclined phase shift.
    """
    layers = [n_hat(n, k) for n, k in OBLIQUE_STACK]

    r_obl, t_obl = rt_stack_oblique(
        550.0, layers, OBLIQUE_THICKNESSES, 0.0, s_pol, 1.0 + 0.0j, 1.52 + 0.0j
    )
    r_normal, t_normal = rt_stack(550.0, layers, OBLIQUE_THICKNESSES, 1.0 + 0.0j, 1.52 + 0.0j)

    assert r_obl == pytest.approx(r_normal, abs=1e-14)
    assert t_obl == pytest.approx(t_normal, abs=1e-14)


@pytest.mark.parametrize("angle_deg", ANGLES_DEG)
@pytest.mark.parametrize("s_pol", [True, False], ids=["pol-s", "pol-p"])
def test_oblique_energy_conservation(angle_deg: float, s_pol: bool) -> None:
    """R + T <= 1 en incidence oblique aussi, pour les deux polarisations."""
    from certus.physics.certus_tmm_oblique import _oblique_stack_rt_single

    layers = [n_hat(n, k) for n, k in OBLIQUE_STACK]

    reflectance, transmittance = _oblique_stack_rt_single(
        550.0,
        np.array(layers, dtype=np.complex128),
        np.array(OBLIQUE_THICKNESSES, dtype=np.float64),
        math.sin(math.radians(angle_deg)),
        math.cos(math.radians(angle_deg)),
        1.0,
        1.52,
        s_pol,
    )

    assert reflectance + transmittance <= 1.0 + 1e-9, (
        f"GAIN NON PHYSIQUE a {angle_deg} deg : R+T = {reflectance + transmittance:.12f}"
    )


def test_hot_kernels_are_jit_compiled() -> None:
    """Hot kernels MUST remain compiled by Numba.

    WARNING: two of these kernels lost their decorator ``@njit`` during
    l'extraction de ``certus_opt_gradients.py`` vers les modules ``gradient_*``.
    The results remained OK, so no tests saw it — but the loops
    ``prange`` became sequential again (factor ~100 on the hot loop
    optimization in oblique incidence). This test makes regression impossible.
    """
    from numba.core.registry import CPUDispatcher

    import certus.physics.gradient_analytic as grad_analytic
    import certus.physics.gradient_metal as grad_metal
    import certus.physics.gradient_oblique as grad_oblique
    import certus.physics.certus_opt_tmm as opt_tmm

    required = [
        (opt_tmm, "compute_TMM_generic"),
        (opt_tmm, "compute_RT_from_matrix"),
        (grad_analytic, "_compute_gradient_analytic_kernel"),
        (grad_oblique, "_compute_oblique_rt_and_grads_kernel"),
        (grad_oblique, "_compute_oblique_gradient_contrib_kernel"),
        (grad_metal, "_compute_metal_tmm_gradient_kernel"),
    ]

    not_compiled = [
        f"{module.__name__}.{name}"
        for module, name in required
        if not isinstance(getattr(module, name), CPUDispatcher)
    ]

    assert not not_compiled, (
        "Noyaux chauds non compiles (decorateur @njit perdu ?) : " + ", ".join(not_compiled)
    )
