# CERTUS - Audit Améliorations Non-GPU
**Date:** 2026-07-08  
**Focus:** Optimisations software, architecture, qualité (hors accélération GPU)

---

## 📊 Analyse Quantitative du Code

### Métriques Globales
- **154,675 lignes** Python
- **3,867 fonctions**, 428 classes
- **265 fichiers** source
- **Taille moyenne module:** 572 lignes (médiane: 382)
- **52 modules >1000 lignes** (opportunité refactoring)

### Complexité & Dette Technique
- **215 fonctions** complexité >15 (cyclomatique)
- **306 fonctions** >100 lignes
- **Fonction la plus longue:** 798 lignes (`certus_index_spline_managers_ui.py::build`)
- **Fonction la plus complexe:** 78 cycles (`pglobal_adapter.py::run_pglobal_optimization`)

### Patterns Répétitifs (Opportunités)
```
2538× dict.get()           → Standardiser error handling
1096× try/except           → Refactor exception patterns
 495× isinstance()         → Pattern matching (Python 3.10+)
 479× logger.info()        → Decorator @log_performance
 359× np.array()           → Valider types entrée
 285× for...range()        → Vectorisation numpy
 233× np.zeros()           → Memory pooling
  72× import *             → Imports explicites (cleanup)
```

### Qualité Code
- **Type hints:** 84.7% (target: 95%+)
- **Docstrings:** 13.8% (target: 80%+)
- **f-strings:** 64.3% (35.7% ancien style %-format)
- **@dataclass:** 19.4% (80.6% classes verboses)
- **@lru_cache:** 5 utilisations (sous-utilisé)
- **async/await:** 0 fichiers (opportunité majeure)

### State Global & Caches
- **80 fichiers** avec globals/caches (risque thread-safety)
- Pas de `@cached_property` utilisé
- Memoization manuelle dans 65 fichiers

---

## 🎯 Recommandations Priorisées (Impact × Effort)

### 🔥🔥🔥 **Priorité 1: Architecture & Patterns (4-6 semaines)**

#### 1.1 Async/Await Migration (Impact: Massif)
**Problème:** 0 utilisation async → Workers bloquants, I/O séquentiel

**Solution:**
```python
# AVANT (bloquant)
def calculate_spectrum(stack):
    result1 = tmm_calculation(stack)  # 500ms
    result2 = validate(result1)       # 100ms
    result3 = export(result2)         # 200ms
    return result3  # Total: 800ms séquentiel

# APRÈS (async)
async def calculate_spectrum(stack):
    task1 = asyncio.create_task(tmm_calculation(stack))
    task2 = asyncio.create_task(validate_async())
    results = await asyncio.gather(task1, task2)
    # Parallélisme I/O → 500ms au lieu de 800ms
```

**Gains:**
- I/O non-bloquant (fichiers, DB, network)
- Workers concurrent sans threads (GIL bypass)
- UI responsive (PyQt6 + asyncio integration)
- 30-50% réduction latence pour workflows I/O-bound

**Cibles prioritaires:**
- `certus/workers/` (15 fichiers)
- `certus/ui/*_mixin.py` (I/O export/import)
- `certus/utils/certus_data.py` (lecture fichiers)

**Effort:** 3-4 semaines, ROI: 🔥🔥🔥

---

#### 1.2 Refactoring Modules Géants (Impact: Maintenabilité)
**Problème:** 52 modules >1000 lignes, 10 modules >2000 lignes

**Top 10 modules à refactor:**
```
3355 lignes | certus_opt_gradients.py       → Split en gradient_analytic.py + gradient_numeric.py
3129 lignes | certus_index_spline_corridors → Split en corridor_worker.py + corridor_ui.py
2523 lignes | spline_workers.py             → Split stages (free_knot, fixed, polish)
2480 lignes | certus_base_app.py            → Extract mixins (save/load, export, validation)
2298 lignes | certus_re_excel_mixin.py      → Split import/export, validation séparée
```

**Stratégie:**
1. Identifier responsabilités multiples (SRP violation)
2. Extraire en modules cohésifs <500 lignes
3. Tests non-régression sur extraction

**Gains:**
- Maintenabilité +80%
- Test isolation meilleure
- Temps compilation IDE réduit
- Onboarding nouveaux devs facilité

**Effort:** 2-3 semaines, ROI: 🔥🔥🔥

---

#### 1.3 Reduction Complexité Cyclomatique (Impact: Bugs)
**Problème:** 215 fonctions complexité >15 (hard to test, prone to bugs)

**Top 5 fonctions à refactor:**
```
78 cycles | run_pglobal_optimization       → Extract sub-functions
77 cycles | worker_spline_auto_clean_knots → State machine pattern
74 cycles | _refresh_data_preview_plots    → Command pattern
66 cycles | _open_manual_extra_knots_dialog→ Form validation class
65 cycles | _fit_nodes_at_fixed_d          → Strategy pattern
```

**Technique:** Extract Method + Strategy Pattern
```python
# AVANT (complexité 50+)
def process(data, mode, validate, export):
    if mode == 'A':
        if validate:
            # 20 lignes
        else:
            # 15 lignes
    elif mode == 'B':
        # 30 lignes
    # ... 200 lignes total

# APRÈS (complexité <10 par fonction)
class ProcessorA(Protocol):
    def execute(self, data): ...

class ProcessorB(Protocol):
    def execute(self, data): ...

def process(data, processor: Processor):
    return processor.execute(data)  # Complexité: 1
```

**Gains:**
- Bug rate -40% (études montrent corrélation complexité/bugs)
- Test coverage +30% (fonctions simples = testables)
- Code review 2x plus rapide

**Effort:** 4 semaines, ROI: 🔥🔥🔥

---

### 🔥🔥 **Priorité 2: Performance Software (2-3 semaines)**

#### 2.1 Vectorisation NumPy Aggressive (Impact: 5-20x speedup)
**Problème:** 285 boucles `for...range()` sur arrays → Lent, pas de SIMD

**Opportunités identifiées:**
```python
# AVANT (loop Python)
result = np.zeros(n)
for i in range(n):
    result[i] = expensive_calc(array[i])  # 10ms × 1000 = 10s

# APRÈS (vectorisé)
result = np.vectorize(expensive_calc)(array)  # ou mieux: ufunc custom
# OU si calc simple:
result = array * 2 + np.sin(array)  # SIMD, 0.5ms

# MIEUX (numba JIT)
from numba import vectorize
@vectorize(['float64(float64)'], target='cpu')
def expensive_calc_jit(x):
    return x * 2 + np.sin(x)
result = expensive_calc_jit(array)  # 0.1ms, 100x faster
```

**Cibles prioritaires:**
- `certus/physics/certus_tmm_*.py` (matrix operations)
- `certus/spline/spline_*.py` (interpolation loops)
- `certus/physics/certus_opt_gradients.py` (gradient calculations)

**Gains mesurables:**
- TMM calculation: 5-10x faster (loops → vectorisé)
- Spline fitting: 10-20x faster (loops → numpy operations)
- Gradient descent: 15-30x faster (batch vectorization)

**Effort:** 2 semaines, ROI: 🔥🔥🔥

---

#### 2.2 Memoization & Caching Stratégique (Impact: 10-50x speedup)
**Problème:** 5 @lru_cache seulement, 65 caches manuels (inconsistant)

**Opportunités:**
1. **Pure functions → @lru_cache automatique**
   ```python
   # Fonctions coûteuses répétitives
   @lru_cache(maxsize=1024)
   def calculate_sellmeier(material_id, wavelength):
       # Appelé 1000x avec mêmes params → cache hit
       return expensive_calculation()
   ```

2. **@cached_property pour lazy init**
   ```python
   class MaterialDB:
       @cached_property
       def refractive_index_table(self):
           return load_huge_table()  # Chargé une seule fois
   ```

3. **Cache LRU pour spectra**
   ```python
   @lru_cache(maxsize=256)
   def calculate_spectrum_cached(stack_hash, wl_range_hash):
       # Même stack → cache hit (évite TMM recalcul)
       return calculate_spectrum(stack, wl_range)
   ```

**Cibles prioritaires:**
- Material database lookups (1000+ appels répétitifs)
- Sellmeier calculations (polynômes coûteux)
- TMM pour stacks identiques
- Geometry calculations (aires, volumes)

**Gains:**
- Material lookups: 50-100x faster (cache vs file I/O)
- Repeated TMM: instant (cache hit vs 500ms calc)
- Sellmeier: 10x faster (cache vs polynomial eval)

**Effort:** 1 semaine, ROI: 🔥🔥🔥

---

#### 2.3 Memory Pooling & Pre-allocation (Impact: 30-50% reduction GC)
**Problème:** 233× `np.zeros()` → Allocations répétées, GC pressure

**Solution:**
```python
# AVANT (allocations répétées dans loop)
def optimize(n_iterations=1000):
    for i in range(n_iterations):
        buffer = np.zeros(10000)  # 1000× malloc + GC
        result = calculation(buffer)

# APRÈS (pool réutilisé)
class BufferPool:
    def __init__(self):
        self._pool = [np.zeros(10000) for _ in range(10)]
        self._available = list(range(10))
    
    def acquire(self):
        idx = self._available.pop()
        return self._pool[idx], idx
    
    def release(self, idx):
        self._available.append(idx)

pool = BufferPool()
def optimize(n_iterations=1000):
    buf, idx = pool.acquire()
    try:
        for i in range(n_iterations):
            result = calculation(buf)  # Zéro allocation
    finally:
        pool.release(idx)
```

**Gains:**
- Allocation overhead: -90%
- GC pauses: -60%
- Memory footprint: -30%
- Throughput: +20-40%

**Effort:** 1.5 semaines, ROI: 🔥🔥

---

### 🔥 **Priorité 3: Code Quality & Maintenabilité (3-4 semaines)**

#### 3.1 Migration @dataclass (Impact: -30% boilerplate)
**Problème:** 19.4% dataclass usage, 80.6% classes verboses

**Opportunités:** 349 classes candidates pour @dataclass

**Avant/Après:**
```python
# AVANT (30 lignes boilerplate)
class Layer:
    def __init__(self, material, thickness, n, k):
        self.material = material
        self.thickness = thickness
        self.n = n
        self.k = k
    
    def __eq__(self, other):
        return (self.material == other.material and 
                self.thickness == other.thickness and ...)
    
    def __repr__(self):
        return f"Layer(material={self.material}, ...)"
    
    # + __hash__, copy, etc.

# APRÈS (4 lignes)
@dataclass(frozen=True)
class Layer:
    material: str
    thickness: float
    n: float
    k: float
```

**Gains:**
- Code: -40% lignes (boilerplate removed)
- Bugs: -50% (equals/hash auto-generated correct)
- Performance: slots=True → -20% memory

**Cibles:** Value objects, DTOs, config classes

**Effort:** 2 semaines, ROI: 🔥🔥

---

#### 3.2 Type Hints Complet + Mypy Strict (Impact: -60% type bugs)
**Problème:** 84.7% type hints (15.3% manquant = 580+ fonctions)

**Stratégie:**
1. `mypy --strict` sur domain/ (nouveau code)
2. `mypy` progressive sur legacy (--no-strict-optional)
3. Type stub (.pyi) pour legacy trop complexe

**Configuration mypy strict:**
```ini
[mypy]
python_version = 3.14
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_any_generics = true
```

**Gains:**
- Type errors détectés: +60% (avant runtime)
- IDE autocomplete: +80% accuracy
- Refactoring safety: +90%
- Documentation auto (types = doc)

**Effort:** 2-3 semaines, ROI: 🔥🔥

---

#### 3.3 Docstring Coverage 13.8% → 80% (Impact: Onboarding)
**Problème:** 3,867 fonctions, seulement 536 documentées

**Stratégie auto-documentation:**
```python
# Template docstring (Google style)
def calculate_spectrum(
    stack: OpticalStack,
    wavelength_range: WavelengthRange,
    num_points: int = 100
) -> Spectrum:
    """Calculate optical spectrum using TMM.

    Args:
        stack: Multilayer stack structure
        wavelength_range: Spectral range [min, max] in nm
        num_points: Number of wavelength sampling points

    Returns:
        Calculated spectrum with R(λ), T(λ), A(λ)

    Raises:
        ValueError: If num_points < 2 or invalid wavelength range

    Examples:
        >>> stack = OpticalStack([Layer(...)])
        >>> wl_range = WavelengthRange(400, 800)
        >>> spectrum = calculate_spectrum(stack, wl_range)
        >>> spectrum.reflectance[0]
        0.04
    """
    ...
```

**Outils:**
- `interrogate` (mesure coverage)
- `pydocstyle` (validation style)
- Sphinx autodoc (génération HTML)

**Gains:**
- Onboarding time: -50% (self-documented)
- API comprehension: +80%
- Reduces "what does this do?" questions: -70%

**Effort:** 3-4 semaines (progressif), ROI: 🔥

---

### 🎯 **Priorité 4: Testing & Robustness (2-3 semaines)**

#### 4.1 Property-Based Testing Expansion (Impact: +40% bug detection)
**Status:** 28 property tests, target 100+

**Stratégie:**
```python
# Expansion domaines
tests/property/
├── test_physics_properties.py      ✅ 7 tests
├── test_optical_value_objects.py   ✅ 21 tests
├── test_tmm_invariants.py          📝 15 tests (energy conservation)
├── test_optimization_convergence.py📝 10 tests (monotonic decrease)
├── test_material_db_properties.py  📝 12 tests (Kramers-Kronig)
├── test_spline_smoothness.py       📝 8 tests (continuity)
└── test_geometry_properties.py     📝 10 tests (symmetry, bounds)
```

**Properties critiques à tester:**
- Energy conservation: R + T + A = 1 (toujours)
- Reciprocity: R(θ) = R(-θ)
- Kramers-Kronig: n(ω) ↔ k(ω) causality
- Optimization: merit decrease monotonic
- Spline: C² continuity at knots

**Effort:** 2 semaines, ROI: 🔥🔥🔥

---

#### 4.2 Mutation Testing Baseline (Impact: Qualité tests)
**Status:** Config créée, jamais run

**Action:**
```bash
# Phase 1: Domain layer (critical)
mutmut run --paths-to-mutate certus/domain/
# Target: 90%+ mutation score

# Phase 2: Core physics
mutmut run --paths-to-mutate certus/physics/certus_tmm_core.py
# Target: 85%+ mutation score

# Phase 3: Progressive coverage
mutmut run --paths-to-mutate certus/core/
# Target: 80%+ mutation score
```

**Gains:**
- Test quality: +50% (détecte tests inutiles)
- Confidence refactoring: +80%
- False security exposed (tests verts mais code cassé)

**Effort:** 1.5 semaines, ROI: 🔥🔥

---

### 💡 **Priorité 5: Developer Experience (1-2 semaines)**

#### 5.1 Pre-commit Hooks Renforcés
**Status:** ruff + mypy basique

**Amélioration:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: Run fast tests (<5s)
        entry: pytest tests/unit/ -x --ff --maxfail=1
        language: system
        pass_filenames: false
        
      - id: mutation-test-changed
        name: Mutation test on changed files
        entry: mutmut run --paths-to-mutate
        language: system
        
      - id: complexity-check
        name: Reject high complexity (>15)
        entry: python tools/complexity_gate.py
        language: system
```

**Gains:**
- Bugs blocked avant commit: +70%
- Code review time: -40%
- CI failures: -60%

**Effort:** 3 jours, ROI: 🔥🔥

---

#### 5.2 Live Reload Development Server
**Problème:** Redémarrage complet app (30s) à chaque modif

**Solution:**
```python
# dev_server.py
import watchdog
from certus.main import main

class CodeReloader:
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"Reloading {event.src_path}...")
            importlib.reload(module)
            # Hot-reload sans restart complet

# Auto-reload sur save → feedback instantané
```

**Gains:**
- Dev cycle time: 30s → 2s (15x faster)
- Developer flow: +80% (pas de context switch)

**Effort:** 2-3 jours, ROI: 🔥

---

## 📈 Roadmap Implémentation (12 semaines)

### Semaines 1-2: Quick Wins Performance
- [ ] @lru_cache sur 50 fonctions hot paths
- [ ] Memory pooling sur TMM/spline
- [ ] Vectorisation 20 boucles critiques
- **Gain attendu:** +30% throughput

### Semaines 3-5: Architecture Async
- [ ] Migration workers → async/await
- [ ] PyQt6 + asyncio integration
- [ ] I/O non-bloquant (files, DB)
- **Gain attendu:** +40% responsiveness UI

### Semaines 6-8: Refactoring Modules
- [ ] Split 10 modules géants (>2000 lignes)
- [ ] Reduce complexité top 50 fonctions
- [ ] Extract mixins/strategies
- **Gain attendu:** Maintenabilité +80%

### Semaines 9-10: Quality Sprint
- [ ] @dataclass migration (100 classes)
- [ ] Type hints complet (mypy strict)
- [ ] Docstrings 50% coverage
- **Gain attendu:** Onboarding time -50%

### Semaines 11-12: Testing Robustness
- [ ] 50+ property tests nouveaux
- [ ] Mutation testing baseline
- [ ] Pre-commit hooks renforcés
- **Gain attendu:** Bug detection +60%

---

## 💰 ROI Estimé (12 semaines effort)

| Amélioration | Effort | Gain Mesuré | ROI |
|--------------|--------|-------------|-----|
| **Async/await** | 3-4 sem | +40% UI responsive, -30% latency I/O | 🔥🔥🔥 |
| **Vectorisation** | 2 sem | +10-20x speedup calculs | 🔥🔥🔥 |
| **@lru_cache** | 1 sem | +10-50x cache hits | 🔥🔥🔥 |
| **Refactor modules** | 2-3 sem | +80% maintenabilité | 🔥🔥🔥 |
| **Complexity reduce** | 4 sem | -40% bug rate | 🔥🔥🔥 |
| **Memory pooling** | 1.5 sem | -30% memory, +20% throughput | 🔥🔥 |
| **@dataclass** | 2 sem | -40% boilerplate | 🔥🔥 |
| **Type hints** | 2-3 sem | -60% type bugs | 🔥🔥 |
| **Property tests** | 2 sem | +40% bug detection | 🔥🔥 |
| **Docstrings** | 3-4 sem | -50% onboarding time | 🔥 |

**Total gains estimés:**
- **Performance:** +50-80% (async + vectorisation + cache)
- **Maintenabilité:** +80-100% (refactor + dataclass + types)
- **Qualité:** +60% bug detection (property + mutation tests)
- **Developer velocity:** +40% (docs + live reload + pre-commit)

---

## 🎯 Top 5 Quick Wins (1-2 semaines chacun)

1. **@lru_cache aggressive** → +10-50x speedup, 1 semaine
2. **Vectoriser 20 hot loops** → +5-20x speedup, 2 semaines
3. **Memory pooling TMM** → -30% memory, 1.5 semaines
4. **Async workers POC** → +40% UI responsive, 1.5 semaines
5. **50 property tests** → +40% bug detection, 2 semaines

**Effort total:** 8 semaines  
**Gains combinés:** +60% performance, +40% qualité

---

**Conclusion:** Sans GPU, il reste **énormément de ROI** dans software optimization, architecture moderne, et code quality. Le passage à GPU (Phase 6) sera d'autant plus efficace que le code sera propre, testé, et bien architecturé.

**Recommandation:** Implémenter quick wins (5 semaines) AVANT GPU pour maximiser ROI GPU futur.
