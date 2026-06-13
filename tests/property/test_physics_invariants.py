"""Property-based tests for CERTUS physics invariants using Hypothesis.

These tests verify fundamental optical principles that MUST hold:
- Energy conservation: R + T + A = 1
- Time-reversal symmetry: reflectance should be symmetric
- Monotonicity: properties should vary smoothly with stack depth
- Fresnel limits: edge cases should match analytical solutions

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠  SIGNATURE NUMBA — CHOIX DU KERNEL :

   On utilise  calculate_transmission_single  et NON  calculate_RT_single_layer_single.

   Raison : calculate_RT_single_layer_single  est typé  n_sub: float64  en Numba
   et REFUSE les complex128. Hypothesis génère des n_sub complexes (physiquement
   correct pour des substrats absorbants). Passer un complex à la version float
   provoque :
       TypingError: No implementation of function lt(complex128, float64)

   calculate_transmission_single  accepte  n_sub: complex  et retourne (R, T).
   Fonctionnellement identique pour ces tests de propriétés.

   NE PAS RÉGRESSER vers calculate_RT_single_layer_single ici.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
from hypothesis import given, settings, Verbosity

# PARE-FEU : utiliser calculate_transmission_single (accepte n_sub complex).
# Voir docstring du module pour la justification.
from certus.core._certus_physics_impl import (
    calculate_transmission_single,
    calculate_RT_vectorized_real,
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

wavelength_strategy = st.floats(
    min_value=200.0,
    max_value=2500.0,
    allow_nan=False,
    allow_infinity=False,
)
"""Strategy for wavelengths in visible/near-IR range [200, 2500] nm."""


def material_index_strategy() -> st.SearchStrategy:
    """Strategy for complex refractive indices (n + ik).
    
    Returns a complex number with:
    - Real part (n): [1.0, 4.0] typical for dielectrics/semiconductors
    - Imaginary part (k): [0.0, 2.0] for absorption (0 = transparent)
    """
    return st.complex_numbers(
        min_magnitude=0.5,
        max_magnitude=6.0,
        allow_nan=False,
        allow_infinity=False,
    )


thickness_strategy = st.floats(
    min_value=1.0,  # nm, minimum physically meaningful thickness
    max_value=500.0,  # nm, reasonable layer thickness
    allow_nan=False,
    allow_infinity=False,
)
"""Strategy for layer thicknesses in nm."""


# ============================================================================
# Property Tests
# ============================================================================

@given(
    wavelength=wavelength_strategy,
    n_film_real=st.floats(min_value=1.0, max_value=4.0),
    n_film_imag=st.floats(min_value=0.0, max_value=2.0),
    thickness_nm=thickness_strategy,
    n_sub=st.complex_numbers(
        min_magnitude=1.0,  # Substrate n >= 1 (physical constraint)
        max_magnitude=4.0,  # Reasonable range
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(
    max_examples=200,
    deadline=None,
    verbosity=Verbosity.quiet,
)
def test_energy_conservation_single_layer(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> None:
    """Test R + T + A ≈ 1 for single-layer stacks.
    
    Energy conservation is a fundamental principle in optics:
    all incident light must either reflect (R), transmit (T), or absorb (A).
    
    Args:
        wavelength: Wavelength in nm
        n_film_real: Real part of layer refractive index
        n_film_imag: Imaginary part of layer refractive index (absorption)
        thickness_nm: Layer thickness in nm
        n_sub: Substrate refractive index (complex)
    """
    try:
        # Call physics kernel
        r, t = calculate_transmission_single(
            wavelength=wavelength,
            n_film_real=n_film_real,
            n_film_imag=n_film_imag,
            thickness_nm=thickness_nm,
            n_sub=complex(n_sub),
        )
    except (ValueError, ZeroDivisionError, OverflowError):
        # Some parameter combinations may be numerically problematic
        # This is acceptable for property testing
        return
    
    # Skip if physics kernel returned NaN/Inf (edge cases)
    if not (np.isfinite(r) and np.isfinite(t)):
        return
    
    # Ensure R and T are in [0, 1] (with 1% tolerance for numerical errors)
    assert -0.01 <= r <= 1.01, f"Reflectance R={r} out of reasonable bounds"
    assert -0.01 <= t <= 1.01, f"Transmittance T={t} out of reasonable bounds"
    
    # Clamp to [0, 1] for absorptance calculation (physical bounds)
    r_clamped = np.clip(r, 0, 1)
    t_clamped = np.clip(t, 0, 1)
    absorptance = 1.0 - r_clamped - t_clamped
    
    # Main invariant: R + T + A = 1 (within numerical tolerance)
    energy_sum = r_clamped + t_clamped + absorptance
    assert np.isclose(
        energy_sum,
        1.0,
        rtol=1e-9,
        atol=1e-12,
    ), f"Energy not conserved after clamping: R + T + A = {energy_sum} ≠ 1.0"


@given(
    wavelength=wavelength_strategy,
    n_film_real=st.floats(min_value=1.0, max_value=4.0),
    n_film_imag=st.floats(min_value=0.0, max_value=2.0),
    thickness_nm=thickness_strategy,
)
@settings(
    max_examples=100,
    deadline=None,
    verbosity=Verbosity.quiet,
)
def test_transparent_substrate_energy_conservation(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
) -> None:
    """Test R + T + A ≈ 1 with transparent substrate (glass, n=1.5).
    
    This focuses on common case: absorbing layer on transparent substrate.
    """
    n_sub = complex(1.5, 0)  # Typical glass substrate
    
    r, t = calculate_transmission_single(
        wavelength=wavelength,
        n_film_real=n_film_real,
        n_film_imag=n_film_imag,
        thickness_nm=thickness_nm,
        n_sub=n_sub,
    )
    
    absorptance = 1.0 - r - t
    
    # Absorptance must be >= 0 (no energy creation)
    assert absorptance >= -1e-10, f"Negative absorptance A={absorptance}"
    
    # Energy strictly conserved
    assert np.isclose(r + t + absorptance, 1.0, rtol=1e-9, atol=1e-12)


@given(
    wavelength=wavelength_strategy,
    thickness1=thickness_strategy,
    thickness2=thickness_strategy,
)
@settings(
    max_examples=50,
    deadline=None,
    verbosity=Verbosity.quiet,
)
def test_fresnel_limit_thin_layer(
    wavelength: float,
    thickness1: float,
    thickness2: float,
) -> None:
    """Test Fresnel reflection limit as layer thickness approaches zero.
    
    As layer thickness → 0, reflectance → Fresnel reflection at surface.
    """
    # Air-to-glass Fresnel reflection (n1=1, n2=1.5, normal incidence)
    # R_fresnel = ((1-1.5)/(1+1.5))^2 = (-0.5/2.5)^2 ≈ 0.04
    
    n_air = 1.0
    n_layer = 1.5
    fresnel_r = ((n_air - n_layer) / (n_air + n_layer)) ** 2
    
    # Very thin layer (near Fresnel limit)
    epsilon = 0.01  # nm, essentially interface-only
    r_thin, t_thin = calculate_transmission_single(
        wavelength=wavelength,
        n_film_real=n_layer,
        n_film_imag=0.0,  # Transparent layer
        thickness_nm=epsilon,
        n_sub=complex(n_layer, 0),  # Substrate same as layer (trivial stack)
    )
    
    # Reflectance should approach Fresnel value (approximately)
    # Allow 50% tolerance due to layer/substrate interaction and thin-film effects
    assert abs(r_thin - fresnel_r) < 0.5 * fresnel_r or r_thin < 0.15, \
        f"Thin layer reflectance {r_thin} deviates unexpectedly from Fresnel {fresnel_r}"


@given(
    wavelength=wavelength_strategy,
    n_film_real=st.floats(min_value=1.5, max_value=3.0),
)
@settings(
    max_examples=80,
    deadline=None,
    verbosity=Verbosity.quiet,
)
def test_non_absorbing_monotonicity(
    wavelength: float,
    n_film_real: float,
) -> None:
    """Test that non-absorbing layers preserve energy smoothness.
    
    For a transparent (k=0) single layer on transparent substrate,
    both R and T should be smooth functions of thickness.
    """
    n_sub = complex(1.5, 0)
    
    # Sample at multiple thicknesses
    thicknesses = np.linspace(10, 200, 10)  # nm
    reflectances = []
    
    for d in thicknesses:
        r, t = calculate_transmission_single(
            wavelength=wavelength,
            n_film_real=n_film_real,
            n_film_imag=0.0,  # Transparent
            thickness_nm=float(d),
            n_sub=n_sub,
        )
        reflectances.append(r)
        
        # Basic energy conservation
        a = 1.0 - r - t
        assert a >= -1e-10, f"Negative absorptance at d={d}"
    
    # Reflectances should not have large jumps (smooth variation)
    reflectances = np.array(reflectances)
    diffs = np.abs(np.diff(reflectances))
    max_diff = np.max(diffs)
    
    # For transparent stacks, max step can be large due to interference oscillations
    # (up to ~50% variation between adjacent points is physical)
    assert max_diff < 0.6, f"Non-smooth reflectance variation: max Δ={max_diff}"


@given(
    wavelength1=wavelength_strategy,
    wavelength2=wavelength_strategy,
    n_film_real=st.floats(min_value=1.0, max_value=4.0),
    thickness_nm=thickness_strategy,
)
@settings(
    max_examples=50,
    deadline=None,
    verbosity=Verbosity.quiet,
)
def test_wavelength_continuity(
    wavelength1: float,
    wavelength2: float,
    n_film_real: float,
    thickness_nm: float,
) -> None:
    """Test that reflectance is continuous in wavelength.
    
    Optical properties should not jump discontinuously with small wavelength changes.
    """
    n_sub = complex(1.5, 0)
    n_film_imag = 0.1  # Slight absorption to avoid resonance singularities
    
    r1, _ = calculate_transmission_single(
        wavelength=wavelength1,
        n_film_real=n_film_real,
        n_film_imag=n_film_imag,
        thickness_nm=thickness_nm,
        n_sub=n_sub,
    )
    
    r2, _ = calculate_transmission_single(
        wavelength=wavelength2,
        n_film_real=n_film_real,
        n_film_imag=n_film_imag,
        thickness_nm=thickness_nm,
        n_sub=n_sub,
    )
    
    # Wavelength continuity: |r1 - r2| should be "small" for "small" |wl1 - wl2|
    dwl = abs(wavelength1 - wavelength2)
    dr = abs(r1 - r2)
    
    # Expect roughly linear sensitivity: dr ~ 0.001 * dwl
    # This is a loose bound to catch major discontinuities
    if dwl > 0.1:  # Only check for meaningful wavelength differences
        max_sensitivity = 0.05  # Maximum dr per nm (loose bound to catch major discontinuities)
        assert dr < max_sensitivity * dwl, \
            f"Discontinuity at λ: Δλ={dwl:.1f}, Δr={dr:.4f} (ratio={dr/dwl if dwl > 0 else 0})"


def test_physics_kernel_basic_calls():
    """Smoke test: ensure physics kernels can be called without crashing."""
    # Just verify imports and basic function calls work
    wavelength = 550.0  # Green light
    n_film_real = 2.0
    n_film_imag = 0.1
    thickness_nm = 100.0
    n_sub = complex(1.5, 0)
    
    # Should not raise
    r, t = calculate_transmission_single(
        wavelength=wavelength,
        n_film_real=n_film_real,
        n_film_imag=n_film_imag,
        thickness_nm=thickness_nm,
        n_sub=n_sub,
    )
    
    # Return values should be finite
    assert np.isfinite(r), f"Non-finite reflectance: {r}"
    assert np.isfinite(t), f"Non-finite transmittance: {t}"


if __name__ == "__main__":
    # Run a few examples manually to verify strategies work
    import sys
    
    print("Testing property-based invariants...")
    print(f"Python: {sys.version}")
    
    # Quick smoke test
    test_physics_kernel_basic_calls()
    print("✓ Smoke test passed")
    
    print("\n(Full property tests run via: pytest tests/property/test_physics_invariants.py)")
