# CERTUS - Quick Wins Implementation: @lru_cache Strategic Caching
**Date:** 2026-07-08  
**Sprint:** Quick Wins Week 1

## Objectif

Ajouter `@lru_cache` sur 20-30 fonctions critiques pour gains performance immédiats (+10-50x sur cache hits).

## Fonctions Prioritaires Identifiées

### Catégorie 1: Configuration & Resource Loading (Très haute fréquence)
**Impact:** 50-100x speedup (file I/O → memory cache)

```python
# certus/core/certus_core.py
@lru_cache(maxsize=1)
def get_resource_path(resource_name: str) -> Path:
    """Cache path resolution (appelé 1000+ fois)."""
    
@lru_cache(maxsize=128)
def get_export_config(key: str = "default") -> dict:
    """Cache export config (file I/O → cache)."""
    
@lru_cache(maxsize=1)
def get_safe_worker_count() -> int:
    """Cache worker count (os.cpu_count() → cache)."""
    
@lru_cache(maxsize=8)
def get_logger(name: str) -> logging.Logger:
    """Cache logger instances."""
```

### Catégorie 2: Material Database Lookups (Haute fréquence)
**Impact:** 20-50x speedup (DB lookup → memory cache)

```python
# certus/core/_certus_physics_impl.py
@lru_cache(maxsize=256)
def get_refractive_index(material_id: str, wavelength_nm: float) -> complex:
    """Cache RI lookups (appelé dans loops TMM)."""
    
@lru_cache(maxsize=512)
def get_n_substrate_array_by_id(substrate_id: str, wavelengths: tuple) -> np.ndarray:
    """Cache substrate arrays (convert list to tuple for hashability)."""
```

### Catégorie 3: TMM Calculations Répétitifs (Moyenne fréquence)
**Impact:** 10-30x speedup sur stacks identiques

```python
# certus/physics/certus_tmm_substrate.py
@lru_cache(maxsize=512)
def calculate_bare_substrate_RT_cached(
    wavelengths: tuple[float, ...],  # tuple pour hashability
    n_substrate: tuple[complex, ...]
) -> tuple[float, ...]:
    """Cache substrate RT (même stack → cache hit)."""
    wl_array = np.array(wavelengths)
    n_array = np.array(n_substrate)
    result = calculate_bare_substrate_RT(wl_array, n_array)
    return tuple(result)
```

### Catégorie 4: Geometry & Math Pure Functions
**Impact:** 5-15x speedup

```python
# certus/physics/certus_tmm_matrix.py
@lru_cache(maxsize=2048)
def compute_complex_phase_components(phi_r: float, phi_i: float) -> tuple:
    """Cache phase calculations (trigonometry coûteux)."""
    
# certus/physics/certus_optimizers.py
@lru_cache(maxsize=256)
def compute_critical_distance(n: int, dim: int, alpha: float) -> float:
    """Cache critical distance calculations."""
```

### Catégorie 5: Sellmeier & Dispersion Models
**Impact:** 30-50x speedup (polynomial eval → cache)

```python
# certus/core/certus_substrate_sellmeier.py
@lru_cache(maxsize=1024)
def calculate_sellmeier_n(
    material_id: str,
    wavelength_nm: float,
    coeffs: tuple[float, ...]  # Convert from list to tuple
) -> float:
    """Cache Sellmeier calculations (polynomial coûteux)."""
```

## Plan d'Implémentation

### Phase 1: Low-Hanging Fruit (Jour 1-2)
**Cibles:** Config, resource paths, loggers
- [ ] `get_resource_path()` → maxsize=1
- [ ] `get_export_config()` → maxsize=128
- [ ] `get_safe_worker_count()` → maxsize=1
- [ ] `get_logger()` → maxsize=8
- [ ] `load_theme_config()` → maxsize=4
- [ ] `load_font_config()` → maxsize=4

**Gain attendu:** +50-100x sur ces fonctions

### Phase 2: Material DB (Jour 3-4)
**Cibles:** Refractive index lookups, substrate arrays
- [ ] `get_refractive_index()` → maxsize=256
- [ ] `get_n_substrate_array_by_id()` → maxsize=512
- [ ] `get_n_frosted_glass_array()` → maxsize=128
- [ ] `_get_sapphire_k_on_grid()` → maxsize=64
- [ ] `_get_silicon_k_on_grid()` → maxsize=64

**Gain attendu:** +20-50x sur lookups DB

### Phase 3: TMM Core (Jour 5)
**Cibles:** Substrate calculations, phase components
- [ ] `calculate_bare_substrate_RT()` wrapper avec cache
- [ ] `calculate_single_interface_R()` wrapper avec cache
- [ ] `compute_complex_phase_components()` → maxsize=2048

**Gain attendu:** +10-30x sur calculs répétitifs

### Phase 4: Sellmeier & Polynomials (Jour 6)
**Cibles:** Dispersion models
- [ ] `calculate_sellmeier_n()` → maxsize=1024
- [ ] Autres modèles dispersion

**Gain attendu:** +30-50x sur eval polynomiaux

### Phase 5: Validation & Benchmarking (Jour 7)
- [ ] Tests cache behavior (hit/miss ratio)
- [ ] Benchmarks avant/après
- [ ] Memory profiling (cache overhead acceptable)
- [ ] Documentation cache stats

## Challenges & Solutions

### Challenge 1: NumPy Arrays Non-Hashable
**Problème:** `@lru_cache` nécessite arguments hashables, `np.ndarray` ne l'est pas

**Solution 1:** Wrapper avec conversion tuple
```python
@lru_cache(maxsize=512)
def _calculate_cached(wavelengths_tuple, n_tuple):
    wl = np.array(wavelengths_tuple)
    n = np.array(n_tuple)
    result = calculate(wl, n)
    return tuple(result)

def calculate_with_cache(wavelengths, n_substrate):
    return np.array(_calculate_cached(
        tuple(wavelengths),
        tuple(n_substrate)
    ))
```

**Solution 2:** Hash custom avec `@functools.cache` + wrapper
```python
from functools import wraps

def array_cache(maxsize=128):
    def decorator(func):
        cached_func = lru_cache(maxsize=maxsize)(
            lambda *args: func(*[np.array(a) if isinstance(a, tuple) else a for a in args])
        )
        
        @wraps(func)
        def wrapper(*args):
            hashable_args = tuple(
                tuple(a) if isinstance(a, np.ndarray) else a 
                for a in args
            )
            return cached_func(*hashable_args)
        return wrapper
    return decorator

@array_cache(maxsize=512)
def calculate(wavelengths, n_substrate):
    # Works seamlessly with np.ndarray inputs
    ...
```

### Challenge 2: Cache Invalidation
**Solution:** Documenter quand clear cache
```python
# Après update material DB
get_refractive_index.cache_clear()

# Stats monitoring
print(get_refractive_index.cache_info())
# CacheInfo(hits=980, misses=20, maxsize=256, currsize=20)
# Hit rate: 98% → Excellent!
```

### Challenge 3: Memory Overhead
**Solution:** Profiler + ajuster maxsize
```python
import sys

# Check cache memory usage
cache_size = sys.getsizeof(get_refractive_index.cache_info())
print(f"Cache memory: {cache_size / 1024:.2f} KB")

# Si trop gros → réduire maxsize
```

## Benchmarking Script

```python
# benchmark_cache_impact.py
import time
import numpy as np
from certus.core.certus_core import get_resource_path

# Warm up
get_resource_path("materials_v1.json")

# Benchmark
N = 10000
start = time.perf_counter()
for _ in range(N):
    path = get_resource_path("materials_v1.json")
elapsed = time.perf_counter() - start

print(f"Time for {N} calls: {elapsed*1000:.2f}ms")
print(f"Time per call: {elapsed/N*1e6:.2f}µs")
print(f"Cache info: {get_resource_path.cache_info()}")

# Expected:
# AVANT: ~10ms (file I/O × 10000)
# APRÈS: ~0.1ms (cache hit × 9999)
# Speedup: 100x
```

## Tests Validation

```python
# tests/performance/test_cache_behavior.py
import pytest
from certus.core.certus_core import get_resource_path

def test_cache_hit_rate():
    """Verify cache effectiveness."""
    get_resource_path.cache_clear()
    
    # First call: miss
    path1 = get_resource_path("test.json")
    info = get_resource_path.cache_info()
    assert info.misses == 1
    assert info.hits == 0
    
    # Second call: hit
    path2 = get_resource_path("test.json")
    info = get_resource_path.cache_info()
    assert info.misses == 1
    assert info.hits == 1
    assert path1 == path2

def test_cache_correctness():
    """Ensure cached results are correct."""
    # Clear cache
    get_refractive_index.cache_clear()
    
    # Calculate twice
    n1 = get_refractive_index("TiO2", 550.0)
    n2 = get_refractive_index("TiO2", 550.0)
    
    # Must be identical (cached)
    assert n1 == n2
    assert get_refractive_index.cache_info().hits == 1
```

## Métriques Succès

| Fonction | Appels/sec | Avant (ms) | Après (µs) | Speedup |
|----------|-----------|------------|------------|---------|
| `get_resource_path` | 10k | 10.0 | 0.01 | **1000x** |
| `get_refractive_index` | 5k | 2.0 | 0.1 | **20x** |
| `calculate_sellmeier_n` | 3k | 5.0 | 0.15 | **33x** |
| `get_export_config` | 1k | 8.0 | 0.01 | **800x** |

**Gain global estimé:** +30-50% throughput sur workflows typiques

## Documentation

```python
def get_resource_path(resource_name: str) -> Path:
    """
    Resolve resource file path with LRU caching.
    
    **Performance:** This function is heavily cached (maxsize=1).
    First call: ~1ms (file I/O), subsequent: ~0.01µs (cache hit).
    
    Cache stats: `.cache_info()` for hits/misses ratio.
    Cache clear: `.cache_clear()` after config updates.
    
    Args:
        resource_name: Resource filename
        
    Returns:
        Absolute path to resource
        
    Examples:
        >>> path = get_resource_path("materials.json")
        >>> get_resource_path.cache_info()
        CacheInfo(hits=999, misses=1, maxsize=1, currsize=1)
    """
```

## Next Steps

Après cette semaine:
1. Monitorer cache hit rates en production
2. Ajuster maxsize si nécessaire
3. Étendre à autres hot paths identifiés
4. Week 2: Vectorisation NumPy (complémentaire)

---

**Status:** Ready for implementation  
**Effort:** 1 semaine (7 jours)  
**ROI attendu:** +10-50x speedup, +30-50% throughput global
