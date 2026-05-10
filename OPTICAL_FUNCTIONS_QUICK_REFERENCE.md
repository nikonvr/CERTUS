# CERTUS Physics Optical Functions - Quick Reference

## CORE FUNCTIONS FOR R+T+A ≈ 1 TESTING

### Single Wavelength, Single Layer
```
calculate_reflection_single(wl: float, n_real: float, n_imag: float, d_nm: float, n_sub: float) -> float
calculate_transmission_single(wl: float, n_real: float, n_imag: float, d_nm: float, n_sub: float) -> float
calculate_RT_single_layer_single(wl: float, n_real: float, n_imag: float, d_nm: float, n_sub: complex) -> (float, float)
```

### Full Spectrum, Single Layer
```
calculate_RT_single_layer_backside_array(wls: ndarray[n_wls], n: ndarray[n_wls], k: ndarray[n_wls], d_nm: float, n_sub: ndarray[n_wls]) -> (ndarray[n_wls], ndarray[n_wls])
```

### Substrate References (Bare Surface)
```
calculate_R_substrate_array(wls: ndarray[n_wls], n_sub: ndarray[n_wls]) -> ndarray[n_wls]
calculate_T_substrate_array(wls: ndarray[n_wls], n_sub: ndarray[n_wls]) -> ndarray[n_wls]
```

### Multilayer Front Stack (Air → Layers → Substrate)
```
calc_spectrum_front(wls: ndarray[n_wls], d_layers: ndarray[n_layers], n_layers: ndarray[n_wls, n_layers], n_sub: ndarray[n_wls]) -> (ndarray[n_wls], ndarray[n_wls])
```

### Multilayer Full Stack (Front + Back + Incoherent Backside)
```
calc_spectrum_full(wls: ndarray[n_wls], d_f: ndarray, n_f: ndarray[n_wls, n_f], d_b: ndarray, n_b: ndarray[n_wls, n_b], n_sub: ndarray[n_wls]) -> (ndarray[n_wls], ndarray[n_wls])
calc_spectrum_full_exact(wls: ndarray[n_wls], d_f: ndarray, n_f: ndarray[n_wls, n_f], d_b: ndarray, n_b: ndarray[n_wls, n_b], n_sub: ndarray[n_wls]) -> (ndarray[n_wls], ndarray[n_wls], ndarray[n_wls], ndarray[n_wls], ndarray[n_wls])
```
Returns from exact: (R_f, T_f, R_f', R_b', T_b) - use to verify exact backside physics

### Generic Multilayer (Any Stack)
```
calculate_RT_vectorized_real(d: ndarray[n_layers], n_all_wls: ndarray[n_wls, n_layers], n_sub_all_wls: ndarray[n_wls], wls: ndarray[n_wls], with_backside: bool) -> (ndarray[n_wls], ndarray[n_wls])
```

### Oblique Incidence
```
calc_spectrum_oblique_vectorized(wls: ndarray[n_wls], n_layers: ndarray[n_wls, n_layers], d_layers: ndarray[n_layers], n_sub: ndarray[n_wls], angle_deg: float, pol: str) -> (ndarray[n_wls], ndarray[n_wls])
calc_spectrum_oblique_backside_vectorized(wls: ndarray[n_wls], n_front: ndarray[n_wls, n_f], d_f: ndarray, n_back: ndarray[n_wls, n_b], d_b: ndarray, n_sub: ndarray[n_wls], angle_deg: float, pol: str) -> (ndarray[n_wls], ndarray[n_wls])
```

### Absorbing Substrates (No Backside Return)
```
calculate_RT_single_layer_absorbing_substrate_array(wls: ndarray[n_wls], n: ndarray[n_wls], k: ndarray[n_wls], d_nm: float, n_sub: ndarray[n_wls], sub_thick_nm: float) -> (ndarray[n_wls], ndarray[n_wls])
calculate_R_substrate_absorbing_array(wls: ndarray[n_wls], n_sub: ndarray[n_wls], thick_nm: float) -> ndarray[n_wls]
calculate_T_substrate_absorbing_array(wls: ndarray[n_wls], n_sub: ndarray[n_wls], thick_nm: float) -> ndarray[n_wls]
```

---

## STACK STRUCTURE (Input Format)

### Definition via Layer Class
```python
from certus_physics.structures import Layer

stack = [
    Layer(mat='SiO2', qwot=1.0, var=True),      # Layer 0 (substrate-adjacent)
    Layer(mat='TiO2', qwot=0.5, var=True),
    # ... more layers ...
    Layer(mat='SiO2', qwot=0.25, var=False),    # Layer N-1 (air-adjacent)
]
```

### Conversion to Function Input
```python
d_layers = np.array([layer.get_thickness(lambda0, n_at_lambda0) for layer in stack])
# n_layers shape: (n_wavelengths, n_layers) complex128
# For single wavelength: reshape to (1, n_layers)
n_sub: complex128 or ndarray[n_wavelengths, complex128]
```

### Valid Stack Configuration
- Min 1 layer, Max ~50 layers (performance depends on wavelength count)
- Layer thicknesses: 0.5 nm to 1000 nm (physically realistic)
- Wavelengths: 200 nm to 2500 nm (VUV to NIR)
- Refractive indices: 0.1 to 4.0 (real), 0.0 to 2.0 (imaginary)

---

## ENERGY CONSERVATION FORMULA

**For any stack (no absorption):**
```
R + T + A = 1.0
A = 1.0 - R - T
```

**Tolerance for property testing (with backside):**
```python
np.testing.assert_allclose(R + T, 1.0, rtol=1e-10, atol=1e-12)
# or
A = 1.0 - R - T
assert np.all(np.abs(A) < 1e-12)
```

**For absorbing layers (A > 0):**
```
R + T + A = 1.0  (exact)
```

---

## KEY DISTINCTIONS FOR TESTS

| Function | Backside? | Absorbing Sub? | Returns |
|----------|-----------|---|---|
| `calculate_reflection_single` | NO | Non-absorbing | R only |
| `calculate_transmission_single` | YES | Non-absorbing | T (includes backside) |
| `calculate_RT_single_layer_single` | YES | Non-absorbing | (R, T) |
| `calc_spectrum_front` | NO | Any | (T, R) |
| `calc_spectrum_full` | YES (exact) | Non-absorbing | (R_total, T_total) |
| `calculate_RT_absorbing_*` | NO | YES (absorbing) | (R, T) no backside |

**Test strategy:** Use `calculate_RT_*` functions with `with_backside=True` for most tests.
