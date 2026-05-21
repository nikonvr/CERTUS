
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # CERTUS Physics - Exported Optical Calculation Functions
## For Hypothesis Property-Based Testing (R + T + A ≈ 1 Verification)

---

## STACK STRUCTURE DEFINITION

### Valid Stack for Testing:
```python
# Stack defined via Layer list (certus_physics.structures.Layer):
Layer(mat: str, qwot: float, var: bool = True)
  - mat: Material ID (e.g., 'SiO2', 'TiO2', 'Ag', etc.)
  - qwot: Optical thickness in QWOT units
  - var: Whether layer is variable (optimizable)

# Stack representation in functions:
- d_layers: np.ndarray[float64]         # Layer thicknesses in nm (index 0 = substrate-adjacent)
- n_layers: np.ndarray[complex128]      # Complex refractive indices per layer
- n_substrate: complex128 or np.ndarray # Substrate refractive index (real or complex)
- wls: np.ndarray[float64]              # Wavelength array in nm
```

---

## SINGLE-LAYER FUNCTIONS (R, T, A for one layer on substrate)

### Basic Single-Layer Reflectance
```
calculate_reflection_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float
) -> float
```
**Returns:** Front reflectance R (0-1, no backside)
**Absorptance:** A = 1 - R (approx, for lossless substrate)

---

### Basic Single-Layer Transmittance
```
calculate_transmission_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float
) -> float
```
**Returns:** Total transmittance T including incoherent backside (0-1)
**Note:** Includes backside reflection in Standard Mode

---

### Combined R+T Single-Layer (Most Efficient)
```
calculate_RT_single_layer_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex
) -> tuple[float, float]
```
**Returns:** (R_front, T_total_with_backside)
**Physics Note:** Exact incoherent backside correction included

---

### Vectorized Single-Layer R+T (Full Spectrum)
```
calculate_RT_single_layer_backside_array(
    wavelengths: np.ndarray,      # shape (n_wls,)
    n_array: np.ndarray,          # shape (n_wls,) - real part
    k_array: np.ndarray,          # shape (n_wls,) - imag part
    thickness: float,              # single nm value
    n_substrate: np.ndarray        # shape (n_wls,) - complex
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R_array, T_array) each shape (n_wls,)
**Usage:** 2x faster than separate R and T arrays

---

## SUBSTRATE REFERENCE FUNCTIONS

### Bare Substrate Reflectance (Transparent)
```
calculate_R_substrate_array(
    wavelengths: np.ndarray,       # shape (n_wls,)
    n_substrate: np.ndarray        # shape (n_wls,) - complex
) -> np.ndarray
```
**Returns:** R_total shape (n_wls,)
**Formula:** R_total = 2*R_single / (1 + R_single) [includes backside]

---

### Bare Substrate Transmittance (Transparent)
```
calculate_T_substrate_array(
    wavelengths: np.ndarray,       # shape (n_wls,)
    n_substrate: np.ndarray        # shape (n_wls,) - complex
) -> np.ndarray
```
**Returns:** T shape (n_wls,)
**Formula:** T = (1 - R_single) / (1 + R_single)

---

## MULTILAYER FRONT STACK FUNCTIONS (Air → Layers → Substrate)

### Front Stack R+T (No Backside)
```
calc_spectrum_front(
    wls: np.ndarray,               # shape (n_wls,)
    d_layers: np.ndarray,          # shape (n_layers,)
    n_layers: np.ndarray,          # shape (n_wls, n_layers) complex
    n_sub: np.ndarray              # shape (n_wls,) complex
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (T_front, R_front) each shape (n_wls,)
**Note:** Front-only, NO backside reflection included

---

### Front Stack - Wrapper (Standard Signature)
```
calc_spectrum_front_wrapper(
    wls: np.ndarray,
    n: np.ndarray,                 # same as n_layers
    d: np.ndarray,                 # same as d_layers
    ns: np.ndarray                 # same as n_sub
) -> tuple[np.ndarray, np.ndarray]
```

---

## FULL STACK FUNCTIONS (Front + Back Stacks)

### Full Stack - Split Components
```
calc_spectrum_full(
    wls: np.ndarray,               # shape (n_wls,)
    d_front: np.ndarray,           # shape (n_front_layers,)
    n_front: np.ndarray,           # shape (n_wls, n_front_layers) complex
    d_back: np.ndarray,            # shape (n_back_layers,)
    n_back: np.ndarray,            # shape (n_wls, n_back_layers) complex
    n_sub: np.ndarray              # shape (n_wls,) complex
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R_total, T_total) with exact backside
**Note:** Rf', Rb', Tb computed separately; exact Fabry-Perot summation

---

### Full Stack - Wrapper
```
calc_spectrum_full_wrapper(
    wls: np.ndarray,
    nf: np.ndarray,                # n_front
    df: np.ndarray,                # d_front
    ns: np.ndarray,                # n_sub
    nb: np.ndarray,                # n_back
    db: np.ndarray                 # d_back
) -> tuple[np.ndarray, np.ndarray]
```

---

### Full Stack - Exact with Component Returns
```
calc_spectrum_full_exact(
    wls: np.ndarray,               # shape (n_wls,)
    d_front: np.ndarray,
    n_front: np.ndarray,           # shape (n_wls, n_front_layers)
    d_back: np.ndarray,
    n_back: np.ndarray,            # shape (n_wls, n_back_layers)
    n_sub: np.ndarray              # shape (n_wls,)
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]
```
**Returns:** (Rf, Tf, Rf_prime, Rb_prime, Tb)
- Rf, Tf: Front stack (Air → Front → Sub)
- Rf', Rb': Reverse reflectances (Sub-side)
- Tb: Back transmittance (Sub → Back → Air)

**T_total Reconstruction:** T_total = (Tf * Tb) / (1 - Rf_prime * Rb_prime)

---

### Full Stack - Exact Wrapper
```
calc_spectrum_full_exact_wrapper(
    wls: np.ndarray,
    nf: np.ndarray,
    df: np.ndarray,
    ns: np.ndarray,
    nb: np.ndarray,
    db: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]
```

---

## OBLIQUE INCIDENCE FUNCTIONS

### Oblique Single Stack
```
calc_spectrum_oblique_vectorized(
    wls: np.ndarray,               # shape (n_wls,)
    n_layers_T: np.ndarray,        # shape (n_wls, n_layers) complex
    d_layers: np.ndarray,          # shape (n_layers,)
    n_sub: np.ndarray,             # shape (n_wls,) complex
    angle_deg: float,              # incident angle in degrees
    polarization: str              # 's' or 'p'
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R, T) for oblique incidence

---

### Oblique Full Stack (Front + Back)
```
calc_spectrum_oblique_backside_vectorized(
    wls: np.ndarray,
    n_layers_T_front: np.ndarray,  # shape (n_wls, n_front_layers)
    d_layers_front: np.ndarray,
    n_layers_T_back: np.ndarray,   # shape (n_wls, n_back_layers)
    d_layers_back: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    polarization: str
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R_total, T_total) with backside correction

---

### Oblique Full Stack - Exact
```
calc_spectrum_full_oblique_exact(
    wls: np.ndarray,
    n_front: np.ndarray,           # shape (n_wls, n_front_layers)
    d_front: np.ndarray,
    n_back: np.ndarray,            # shape (n_wls, n_back_layers)
    d_back: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    include_backside: bool
) -> tuple[np.ndarray, np.ndarray]
```

---

## MULTILAYER VECTORIZED (Generic)

### Generic R+T Calculation
```
calculate_RT_vectorized_real(
    thicknesses: np.ndarray,       # shape (n_layers,) - nm
    n_layers_all_wls: np.ndarray,  # shape (n_wls, n_layers) complex
    n_substrate_all_wls: np.ndarray, # shape (n_wls,) complex
    wls: np.ndarray,               # shape (n_wls,)
    with_backside: bool = True
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R, T) each shape (n_wls,)
**with_backside=True:** Applies exact incoherent backside correction

---

### High-Level (HL) R+T Variant
```
calculate_RT_vectorized_real_HL(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_substrate_all_wls: np.ndarray,
    wls: np.ndarray,
    with_backside: bool = True
) -> tuple[np.ndarray, np.ndarray]
```

---

## ABSORBING SUBSTRATE VARIANTS

### Single-Layer on Absorbing Substrate
```
calculate_RT_single_layer_absorbing_substrate_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,           # complex, shape (n_wls,)
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,       # complex absorbing
    substrate_thickness_nm: float  # physical thickness of absorbing layer
) -> tuple[np.ndarray, np.ndarray]
```
**Returns:** (R, T) - no backside (substrate absorbs)
**Model:** Beer-Lambert incoherent

---

### Bare Absorbing Substrate Reference - R
```
calculate_R_substrate_absorbing_array(
    wavelengths: np.ndarray,
    n_substrate: np.ndarray,       # complex absorbing
    thickness_nm: float            # physical thickness
) -> np.ndarray
```

---

### Bare Absorbing Substrate Reference - T
```
calculate_T_substrate_absorbing_array(
    wavelengths: np.ndarray,
    n_substrate: np.ndarray,       # complex absorbing
    thickness_nm: float
) -> np.ndarray
```

---

## KEY PHYSICS CONVENTIONS

### Absorptance Calculation
```
A = 1.0 - R - T
```
- **Transparent layers:** A ≈ 0 (small numerical error)
- **Absorbing layers:** A > 0 (energy dissipation)
- **Property test:** R + T + A ≈ 1 (within floating-point tolerance)

### Array Indexing (CRITICAL for Testing)
```
Layer ordering: index 0 = substrate-adjacent, index N-1 = air-adjacent
  d[0] = first layer (closest to substrate)
  d[N-1] = last layer (closest to air)
  n[i, 0] = refractive index at wavelength i, layer 0 (substrate-side)
```

### Backside Treatment
- **Standard Mode:** Transparent substrate → includes incoherent backside
- **Frosted Glass:** No specular backside → single-interface only
- **Absorbing Substrate:** No backside return → absorption dominates

### Wavelength Convention
- All wavelengths in **nanometers (nm)**
- All thicknesses in **nanometers (nm)**
- Refractive indices: `n_complex = n_real - 1j*k` (Macleod convention)

---

## HYPOTHESIS TEST TEMPLATE

```python
from hypothesis import given, strategies as st
import numpy as np

@given(
    wls=st.arrays(
        dtype=np.float64,
        shape=st.integers(10, 50),
        elements=st.floats(300, 1200, allow_nan=False, allow_infinity=False)
    ),
    n_layers=st.lists(
        st.complex_number(min_magnitude=0.1, max_magnitude=4.0),
        min_size=1,
        max_size=20
    ),
    d_layers=st.lists(
        st.floats(1, 500, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20
    ),
    n_substrate=st.complex_number(min_magnitude=1.0, max_magnitude=4.0)
)
def test_energy_conservation(wls, n_layers, d_layers, n_substrate):
    """Test: R + T + A ≈ 1 (energy conservation)"""
    
    # Ensure matching shapes
    n_wls = len(wls)
    n_layers_arr = np.array([n_layers[i % len(n_layers)] for i in range(len(d_layers))]).reshape(1, -1)
    n_layers_arr = np.tile(n_layers_arr, (n_wls, 1))
    
    n_sub_arr = np.full(n_wls, n_substrate, dtype=complex)
    
    R, T = calculate_RT_vectorized_real(
        np.array(d_layers),
        n_layers_arr,
        n_sub_arr,
        np.sort(np.array(wls)),
        with_backside=True
    )
    
    A = 1.0 - R - T
    
    # Property: Energy conservation (within floating-point tolerance)
    np.testing.assert_allclose(
        R + T + A,
        np.ones(n_wls),
        rtol=1e-10,
        atol=1e-12,
        err_msg="Energy conservation violated: R + T + A ≠ 1"
    )
    
    # Additional properties
    assert np.all((R >= 0) & (R <= 1.01)), "R out of range [0, 1]"
    assert np.all((T >= -0.01) & (T <= 1.01)), "T out of range [0, 1]"
    assert np.all((A >= -0.01) & (A <= 1.01)), "A out of range [0, 1]"
```

---

## NOTES FOR PROPERTY-BASED TESTING

1. **Wavelength sorting:** Some functions expect ascending wavelength order
2. **Array shapes:** Validate input dimensions carefully (n_wls vs n_layers)
3. **Complex arithmetic:** Use `np.complex128` for precision
4. **Backside flag:** Set appropriately based on substrate type
5. **Physical bounds:** R, T, A ∈ [0, 1]; sum = 1.0 (absorbing stack)
6. **Numerical tolerance:** Use rtol=1e-10, atol=1e-12 for conservation tests


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.