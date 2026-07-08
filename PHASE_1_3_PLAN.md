# CERTUS - Phase 1+3: Fondations & Architecture DDD
## Plan d'Exécution Intégré

**Objectif:** Établir fondations test solides PENDANT refactoring architectural  
**Durée estimée:** 3-4 semaines  
**Approche:** Incremental refactoring avec test coverage continue

---

## 🎯 Stratégie Intégrée

### Pourquoi combiner Phase 1 + Phase 3 ?

**Synergie:**
- DDD impose boundaries claires → Tests deviennent naturels
- Tests property-based valident invariants domain → Confiance refactoring
- Architecture testable → Coverage monte automatiquement
- Mutation testing expose couplage caché → Guide découpage modules

**Anti-pattern à éviter:** Refactor massif PUIS tester = risque régression  
**Notre approche:** Test-driven refactoring = safety net continu

---

## 📅 Roadmap 4 Semaines

### **Semaine 1: Foundations + Domain Discovery**

#### Jour 1-2: Test Infrastructure (8h)
- [ ] Fixer 2 property tests échouants
- [ ] Ajouter 10 property tests physiques critiques
  - Conservation énergie (R + T + A = 1)
  - Réciprocité optique
  - Kramers-Kronig relations
  - Bounds checking (0 ≤ R,T,A ≤ 1)
- [ ] Run mutation testing baseline
  ```bash
  mutmut run --paths-to-mutate certus/core/certus_core.py
  mutmut run --paths-to-mutate certus/physics/certus_tmm_core.py
  mutmut html  # Visualiser résultats
  ```
- [ ] Coverage rapport complet
  ```bash
  pytest tests/ --cov=certus --cov-report=html --cov-report=term
  # Target: identifier modules <50% coverage
  ```

#### Jour 3-5: Domain Analysis (12h)
- [ ] **Event Storming session** (solo ou équipe)
  - Lister tous les domain events: `SpectrumCalculated`, `DesignOptimized`, `MaterialSelected`
  - Identifier aggregates: `OpticalStack`, `Material`, `OptimizationStrategy`
  - Tracer boundaries naturelles
- [ ] Créer **Context Map**
  ```
  Optical Context ←→ Material Context
       ↓
  Strategy Context ←→ Design Context
  ```
- [ ] **Ubiquitous Language** glossaire
  - Termes métier vs code actuel
  - Ex: "Stack" vs "Design" vs "Structure"

### **Semaine 2: Bounded Context #1 - Optical Domain**

#### Structure Cible
```python
certus/
├── domain/                    # Pure business logic
│   ├── __init__.py
│   ├── optical/              # Bounded Context: Optique
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── stack.py          # OpticalStack aggregate root
│   │   │   ├── layer.py          # Layer entity
│   │   │   └── spectrum.py       # Spectrum value object
│   │   ├── value_objects/
│   │   │   ├── wavelength.py     # Wavelength(nm)
│   │   │   ├── thickness.py      # Thickness(nm)
│   │   │   └── refractive_index.py  # ComplexRI(n, k)
│   │   ├── services/
│   │   │   ├── tmm_calculator.py # Domain service TMM
│   │   │   └── spectrum_analyzer.py
│   │   └── events/
│   │       ├── spectrum_calculated.py
│   │       └── stack_validated.py
```

#### Travail Semaine 2
- [ ] Créer structure `certus/domain/optical/`
- [ ] **Extraire value objects** (3-4h)
  ```python
  # certus/domain/optical/value_objects/wavelength.py
  from dataclasses import dataclass
  
  @dataclass(frozen=True)
  class Wavelength:
      nm: float
      
      def __post_init__(self):
          if not (100 <= self.nm <= 10000):
              raise ValueError(f"Invalid wavelength: {self.nm}nm")
      
      def to_meters(self) -> float:
          return self.nm * 1e-9
  ```
- [ ] **Extraire Layer entity** (4h)
  ```python
  # certus/domain/optical/entities/layer.py
  from dataclasses import dataclass
  from ..value_objects import Thickness, RefractiveIndex
  
  @dataclass
  class Layer:
      material_id: str
      thickness: Thickness
      refractive_index: RefractiveIndex
      
      def optical_thickness(self, wavelength: Wavelength) -> float:
          """QWOT calculation."""
          return self.thickness.nm * self.refractive_index.n_real
  ```
- [ ] **Tests property pour value objects** (3h)
  ```python
  @given(nm=st.floats(min_value=100, max_value=10000))
  def test_wavelength_roundtrip_meters(nm):
      wl = Wavelength(nm)
      assert np.isclose(wl.from_meters(wl.to_meters()).nm, nm)
  ```
- [ ] **Mutation testing sur domain/** (2h)
  ```bash
  mutmut run --paths-to-mutate certus/domain/optical/
  # Target: 90%+ mutation score (domain logic critique)
  ```

#### Coverage Target Semaine 2
- `certus/domain/optical/value_objects/`: **100%** (simple, pas d'excuse)
- `certus/domain/optical/entities/`: **95%+**
- Property tests: **+15 tests** (total 22+)

### **Semaine 3: Event Sourcing + Application Layer**

#### Event Bus Implementation
```python
# certus/infrastructure/event_bus.py
from typing import Callable, Dict, List
from dataclasses import dataclass
import asyncio

@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_id: str
    timestamp: float
    event_type: str
    payload: dict

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._store: List[DomainEvent] = []
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe handler to event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: DomainEvent):
        """Publish event to all subscribers."""
        self._store.append(event)  # Event sourcing
        
        handlers = self._handlers.get(event.event_type, [])
        await asyncio.gather(*[
            handler(event) for handler in handlers
        ])
    
    def replay(self, aggregate_id: str) -> List[DomainEvent]:
        """Replay all events for aggregate (event sourcing)."""
        return [e for e in self._store if e.aggregate_id == aggregate_id]
```

#### Application Services
```python
# certus/application/optical/calculate_spectrum_use_case.py
from dataclasses import dataclass
from certus.domain.optical.entities import OpticalStack
from certus.domain.optical.services import TMM_Calculator
from certus.infrastructure.event_bus import EventBus, DomainEvent

@dataclass
class CalculateSpectrumRequest:
    stack_id: str
    wavelength_range: tuple[float, float]
    num_points: int

class CalculateSpectrumUseCase:
    def __init__(self, tmm_calculator: TMM_Calculator, event_bus: EventBus):
        self._tmm = tmm_calculator
        self._bus = event_bus
    
    async def execute(self, request: CalculateSpectrumRequest) -> dict:
        """Use case: calculate optical spectrum."""
        # 1. Load aggregate (from repo)
        stack = self._load_stack(request.stack_id)
        
        # 2. Domain logic
        spectrum = self._tmm.calculate(stack, request.wavelength_range)
        
        # 3. Publish domain event
        await self._bus.publish(DomainEvent(
            event_id=generate_id(),
            aggregate_id=request.stack_id,
            timestamp=time.time(),
            event_type="SpectrumCalculated",
            payload={"rmse": spectrum.rmse, "points": len(spectrum)}
        ))
        
        return spectrum.to_dict()
```

#### Travail Semaine 3
- [ ] Implémenter EventBus (4h)
- [ ] Créer 3 use cases critiques (8h)
  - CalculateSpectrum
  - OptimizeStack
  - ValidateDesign
- [ ] Tests integration use cases (6h)
- [ ] Property tests event sourcing (3h)
  ```python
  @given(events=st.lists(domain_event_strategy()))
  def test_event_replay_deterministic(events):
      bus = EventBus()
      for e in events:
          bus.publish(e)
      
      replayed = bus.replay(events[0].aggregate_id)
      # Replay doit être déterministe
      assert replayed == [e for e in events if e.aggregate_id == events[0].aggregate_id]
  ```

#### Coverage Target Semaine 3
- `certus/infrastructure/event_bus.py`: **100%**
- `certus/application/`: **90%+**
- Property tests: **+10 tests** (total 32+)

### **Semaine 4: Migration Progressive + Documentation**

#### Anti-Corruption Layer (ACL)
```python
# certus/application/adapters/legacy_physics_adapter.py
"""Adapter pour isoler domain des anciens modules physics."""

class LegacyPhysicsAdapter:
    """Anti-corruption layer vers certus.physics legacy."""
    
    def __init__(self):
        # Import lazy pour éviter contamination
        from certus.physics import certus_tmm_core
        self._legacy_tmm = certus_tmm_core
    
    def to_domain_spectrum(self, legacy_result: dict) -> Spectrum:
        """Convert legacy dict to domain Spectrum."""
        return Spectrum(
            wavelengths=[Wavelength(w) for w in legacy_result["lambda_nm"]],
            reflectance=legacy_result["R"],
            transmittance=legacy_result["T"]
        )
    
    def from_domain_stack(self, stack: OpticalStack) -> dict:
        """Convert domain Stack to legacy dict."""
        return {
            "n_list": [layer.refractive_index.n_real for layer in stack.layers],
            "d_list": [layer.thickness.nm for layer in stack.layers],
            # ...
        }
```

#### Migration Strategy
**Strangler Fig Pattern:** Nouveau code wraps ancien progressivement

```
Phase 1: certus.domain.optical + ACL → certus.physics (legacy)
         ↓ (tests passent)
Phase 2: certus.application uses domain
         ↓ (UI continue sur legacy)
Phase 3: certus.ui → certus.application (découplé)
         ↓
Phase 4: Retire certus.physics legacy (optional)
```

#### Travail Semaine 4
- [ ] Implémenter ACL pour physics (6h)
- [ ] Migrer 1 feature complète end-to-end (8h)
  - Ex: "Calculate AR coating spectrum"
  - Domain → Application → ACL → Legacy physics
  - UI appelle nouveau use case
- [ ] Documentation Architecture (6h)
  ```markdown
  docs/architecture/
  ├── 001-bounded-contexts.md    # ADR
  ├── 002-event-sourcing.md      # ADR
  ├── 003-strangler-fig.md       # ADR
  └── diagrams/
      ├── context-map.mmd        # Mermaid
      └── event-flow.mmd
  ```
- [ ] Jupyter Book setup (4h)
  ```bash
  pip install jupyter-book
  jupyter-book create docs/
  # Tutorials interactifs avec architecture
  ```

#### Coverage Final Semaine 4
- **Global:** 60% → **75%+**
- **Domain:** **95%+** (critique)
- **Application:** **90%+**
- **Property tests:** **40+ tests**
- **Mutation score:** **85%+** (domain + application)

---

## 🎯 Livrables 4 Semaines

### Code
- ✅ `certus/domain/optical/` (bounded context complet)
- ✅ `certus/infrastructure/event_bus.py`
- ✅ `certus/application/optical/` (use cases)
- ✅ Anti-corruption layer
- ✅ 40+ property tests
- ✅ 1 feature migrée end-to-end

### Tests & Qualité
- ✅ Coverage: 75%+ global, 95%+ domain
- ✅ Mutation score: 85%+ domain/application
- ✅ Type hints: 95%+ (strictification progressive)

### Documentation
- ✅ 3 ADRs (Architecture Decision Records)
- ✅ Context map + Event flow diagrams
- ✅ Jupyter Book initialisé
- ✅ API documentation (Sphinx autodoc)

---

## 📊 Métriques Succès

| Métrique | Avant | Après 4 sem | Top 1% |
|----------|-------|-------------|--------|
| **Coverage global** | 15-47% | 75%+ | 95%+ |
| **Coverage domain** | N/A | 95%+ | 98%+ |
| **Property tests** | 7 | 40+ | 100+ |
| **Mutation score** | ? | 85%+ | 90%+ |
| **Type hints** | 84.7% | 95%+ | 98%+ |
| **Bounded contexts** | 0 | 1 (optical) | 4+ |
| **Event sourcing** | Non | Oui | Oui |
| **Documentation** | Minimal | Jupyter Book | Classe mondiale |

---

## 🛠️ Outils & Setup

### Installation
```bash
# Testing
pip install pytest pytest-cov pytest-xdist hypothesis mutmut

# Documentation
pip install jupyter-book sphinx sphinx-rtd-theme

# Type checking
pip install mypy types-all

# Code quality
pip install ruff black isort
```

### Scripts Utiles
```bash
# Fast test loop (TDD)
pytest tests/domain/ -x --ff  # Fail fast, failed first

# Coverage watch
pytest-watch -- --cov=certus/domain --cov-report=term-missing

# Mutation testing domain
mutmut run --paths-to-mutate certus/domain/optical/ --tests-dir tests/domain/

# Type checking strict
mypy certus/domain/ --strict --show-error-codes

# Doc build
jupyter-book build docs/
```

---

## 🚀 Session Suivante: Démarrage Phase 1+3

### Checklist Démarrage
- [ ] Review ce plan
- [ ] Setup outils (pytest, mutmut, jupyter-book)
- [ ] Event storming: lister domain events sur whiteboard
- [ ] Créer `certus/domain/optical/` structure vide
- [ ] Commencer par value objects les plus simples

### Temps Estimé Session Suivante
**4-6h** pour établir fondations domain + premiers tests property

---

Prêt à démarrer quand vous voulez ! 🎯
