# Event Storming: CERTUS Optical Domain
**Date:** 2026-07-08  
**Participant:** Domain analysis pour DDD refactoring

---

## 🎯 Objectif

Identifier les **domain events**, **aggregates**, **commands**, et **bounded contexts** du système CERTUS.

---

## 📋 Domain Events (Orange Stickies)

### Optical Events
1. **SpectrumCalculated**
   - When: Après calcul TMM
   - Data: stack_id, wavelengths[], R[], T[], A[], rmse
   
2. **OpticalStackValidated**
   - When: Validation contraintes physiques
   - Data: stack_id, is_valid, violations[]

3. **LayerAdded**
   - When: Ajout couche au stack
   - Data: stack_id, layer_id, material, thickness

4. **LayerRemoved**
   - When: Suppression couche
   - Data: stack_id, layer_id

5. **ThicknessOptimized**
   - When: Optimisation épaisseurs terminée
   - Data: stack_id, old_thicknesses[], new_thicknesses[], improvement

### Strategy Events
6. **OptimizationStarted**
   - When: Début optimization strategy
   - Data: strategy_id, algorithm, params

7. **OptimizationCompleted**
   - When: Convergence atteinte
   - Data: strategy_id, result, iterations, duration

8. **StrategyEvaluated**
   - When: Évaluation robustesse
   - Data: strategy_id, robustness_score, monte_carlo_results

### Material Events
9. **MaterialSelected**
   - When: Choix matériau pour couche
   - Data: material_id, n(λ), k(λ), sellmeier_coeffs

10. **MaterialDataLoaded**
    - When: Chargement database matériaux
    - Data: material_count, source

### Design Events
11. **TargetSpectrumDefined**
    - When: Définition objectif optimization
    - Data: target_id, wavelength_ranges[], R_targets[], T_targets[]

12. **DesignExported**
    - When: Export vers fichier/report
    - Data: design_id, format, filepath

---

## 🎭 Aggregates (Yellow Stickies)

### 1. **OpticalStack** (Aggregate Root)
**Entities:**
- Stack (root)
- Layer (entity)

**Value Objects:**
- Wavelength
- Thickness
- RefractiveIndex
- Spectrum

**Invariants:**
- Au moins 1 couche (substrate)
- Épaisseurs > 0
- Indices réfractaires n ≥ 1.0

**Commands:**
- AddLayer(material, thickness)
- RemoveLayer(layer_id)
- OptimizeThicknesses(target_spectrum)
- CalculateSpectrum(wavelength_range)

### 2. **Material** (Aggregate Root)
**Value Objects:**
- MaterialId
- RefractiveIndexFunction(λ)
- SellmeierCoefficients

**Invariants:**
- n(λ) continuous
- k(λ) ≥ 0

**Commands:**
- LoadMaterialData(material_id)
- InterpolateRI(wavelength)

### 3. **OptimizationStrategy** (Aggregate Root)
**Value Objects:**
- StrategyId
- AlgorithmType
- ConstraintSet

**Invariants:**
- Algorithm parameters valid
- Convergence criteria defined

**Commands:**
- StartOptimization(initial_stack)
- EvaluateRobustness(strategy)
- AbortOptimization()

### 4. **DesignTarget** (Aggregate Root)
**Value Objects:**
- TargetId
- SpectralRange
- ReflectanceTarget
- TransmittanceTarget

**Invariants:**
- 0 ≤ R_target ≤ 1
- 0 ≤ T_target ≤ 1
- R_target + T_target ≤ 1 (physique)

**Commands:**
- DefineTarget(wavelengths, R_targets)
- ValidateTarget()

---

## 🗺️ Bounded Contexts

### 1. **Optical Context** (Core Domain)
**Responsibility:** Calculs physiques optiques, TMM, spectra

**Entities:** OpticalStack, Layer, Spectrum

**Domain Services:**
- TMM_Calculator
- SpectrumAnalyzer
- ValidationService

**Dependencies:** Material Context (read)

### 2. **Material Context** (Supporting)
**Responsibility:** Database matériaux, propriétés optiques

**Entities:** Material, MaterialDatabase

**Domain Services:**
- MaterialRepository
- SellmeierCalculator
- DataInterpolator

**Dependencies:** Aucune (leaf context)

### 3. **Strategy Context** (Core Domain)
**Responsibility:** Algorithmes optimization, search strategies

**Entities:** OptimizationStrategy, StrategyResult

**Domain Services:**
- StrategyExecutor
- RobustnessEvaluator
- ConvergenceChecker

**Dependencies:** Optical Context, Material Context

### 4. **Design Context** (Supporting)
**Responsibility:** User designs, targets, exports

**Entities:** Design, DesignTarget

**Domain Services:**
- DesignRepository
- ExportService
- ValidationService

**Dependencies:** Optical Context

---

## 🔗 Context Map

```
┌─────────────────┐
│  Material       │
│  Context        │
│  (Supporting)   │
└────────┬────────┘
         │ Supplier
         ▼
┌─────────────────┐      ┌─────────────────┐
│  Optical        │◄─────┤  Strategy       │
│  Context        │      │  Context        │
│  (Core Domain)  │      │  (Core Domain)  │
└────────┬────────┘      └─────────────────┘
         │ Supplier
         ▼
┌─────────────────┐
│  Design         │
│  Context        │
│  (Supporting)   │
└─────────────────┘
```

**Relationships:**
- **Supplier-Consumer:** Material → Optical → Design
- **Partnership:** Optical ↔ Strategy (collaboration étroite)
- **Anti-Corruption Layer:** Legacy `certus.physics` wrappé par Optical Context

---

## 📝 Ubiquitous Language

| Term | Definition | Code Mapping |
|------|------------|--------------|
| **Stack** | Ensemble de couches optiques | `OpticalStack` |
| **Layer** | Couche mince d'un matériau | `Layer` |
| **Substrate** | Support de base (verre, saphir) | `Substrate extends Layer` |
| **Spectrum** | R(λ), T(λ), A(λ) calculé | `Spectrum` |
| **TMM** | Transfer Matrix Method | `TMM_Calculator` service |
| **QWOT** | Quarter-Wave Optical Thickness | `Layer.optical_thickness()` |
| **Strategy** | Algorithme optimization | `OptimizationStrategy` |
| **Robustness** | Stabilité aux perturbations | `RobustnessScore` |
| **Design** | Configuration stack + target | `Design` |
| **Material** | Substance avec n(λ), k(λ) | `Material` |

---

## 🎯 Next Steps

1. **Implémenter Optical Context** en premier (core domain)
2. **Créer value objects** (Wavelength, Thickness, RefractiveIndex)
3. **Définir OpticalStack aggregate** avec invariants
4. **Event bus** pour découplage
5. **Tests property-based** sur invariants domain

---

## 🔍 Questions Ouvertes

- **Q:** Où placer workers async (ThreadPoolExecutor) ?  
  **A:** Infrastructure layer, pas domain. Application services orchestrent.

- **Q:** PyQt6 UI dans quel context ?  
  **A:** Presentation layer séparée, consomme Application services via adapter.

- **Q:** Numba JIT dans domain ?  
  **A:** Non, infrastructure detail. Domain définit contrats (Protocol), infra implémente.

---

**Ready for implementation!** 🚀
