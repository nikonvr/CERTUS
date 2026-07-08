# CERTUS - Quick Wins Implementation Plan

## Session actuelle: Baseline & Quick Wins

### ✅ Complété
1. **Audit code complet** - Aucun bug bloquant détecté
2. **Analyse métriques actuelles**:
   - 154,675 lignes Python
   - 3,867 fonctions, 428 classes
   - 265 fichiers source, 211 tests
   - Type hints: 84.7% coverage
   - Docstrings: 13.8% coverage
   - 48 marqueurs TODO/FIXME
   - CI/CD: GitHub Actions (lint, security)
3. **Benchmark baseline** créé (numpy ops: 31ms)

### 🔄 En cours
4. **Code coverage mesure** - pytest-cov configuré, besoin run complet

### 📋 Prochaines étapes immédiates

#### A. Compléter baseline (10 min)
- [ ] Fixer benchmark TMM (trouver fonction correcte)
- [ ] Mesurer code coverage: `pytest tests/ --cov=certus --cov-report=term`
- [ ] Documenter résultats dans BASELINE.md

#### B. Mutation testing (15 min)
```bash
pip install mutmut
mutmut run --paths-to-mutate certus/core/certus_core.py
mutmut results  # Target: >80% mutation score
```

#### C. Type hints strict (20 min)
```bash
mypy certus/ --strict --show-error-codes > mypy_strict.txt
# Fix les 15% manquants prioritaires
```

#### D. Documentation index (15 min)
- [ ] Créer `docs/index.md` avec architecture overview
- [ ] Diagramme architecture actuelle (mermaid)
- [ ] Quick start guide

#### E. Property-based testing POC (30 min)
```python
# tests/property/test_tmm_properties.py
from hypothesis import given, strategies as st

@given(wavelength=st.floats(min_value=400, max_value=800))
def test_tmm_energy_conservation(wavelength):
    # R + T + A = 1.0
    pass
```

### 🎯 Objectifs session
- [x] Baseline performance établi
- [ ] Code coverage >80% mesuré
- [ ] Mutation testing configuré
- [ ] 5 property tests créés
- [ ] Documentation structure initialisée

### 📊 Métriques à tracker
```json
{
  "code_coverage": "~60% → 80%+",
  "mutation_score": "? → 80%+",
  "type_hints": "84.7% → 95%+",
  "docstrings": "13.8% → 50%+",
  "benchmark_tmm": "? ms → baseline"
}
```

## Prochaine session: Architecture DDD

### Préparation
1. Identifier bounded contexts (optical, material, strategy)
2. Mapper aggregate roots
3. Définir domain events
4. Prototype event bus

### Livrables attendus
- `certus/domain/` structure
- Event sourcing POC
- Architecture Decision Record (ADR)

---

**Note**: Focus session actuelle = Quick wins mesurables
**Durée estimée**: 90 minutes restantes
**Priorité**: Établir baseline solide avant refactoring majeur
