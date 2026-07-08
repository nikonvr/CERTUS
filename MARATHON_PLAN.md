# CERTUS Marathon: Options A→B→C→D
**Démarrage:** 2026-07-08  
**Estimation:** 20-30h total  
**Modèle:** Sonnet 5 (tous agents)

---

## 🎯 Plan d'Exécution

### ✅ Phase Préparatoire (Fait)
- Audit complet
- DDD foundation (value objects)
- 28 property tests
- 3 fonctions @lru_cache
- Documentation complète

### 🔥 Option A: Quick Wins Performance (4-6h)
**Status:** IN PROGRESS

**Objectifs:**
1. @lru_cache sur 20+ fonctions Material DB/Config
2. Vectoriser 10 hot loops NumPy
3. Memory pooling sur TMM
4. Benchmarks avant/après

**Livrables:**
- 20+ fonctions optimisées
- 10+ loops vectorisés
- Benchmark report
- +30-40% throughput global

### 🏗️ Option B: DDD Entities (4-6h)
**Status:** PENDING

**Objectifs:**
1. Layer entity avec invariants
2. OpticalStack aggregate root
3. Domain events implementation
4. 15+ property tests nouveaux
5. Domain services protocols

**Livrables:**
- certus/domain/optical/entities/
- 15+ nouveaux tests
- Event bus POC
- 100% coverage maintenu

### ⚡ Option C: Async/Await POC (6-8h)
**Status:** PENDING

**Objectifs:**
1. Convertir 3-5 workers en async
2. PyQt6 + asyncio integration
3. I/O non-bloquant
4. Tests async

**Livrables:**
- Workers async (certus/workers/)
- UI responsive
- +40% responsiveness
- Async patterns documented

### 🔧 Option D: Refactoring Module (6-8h)
**Status:** PENDING

**Objectifs:**
1. Split certus_opt_gradients.py (3355 → 3 modules)
2. Extract strategy patterns
3. Réduire complexité top 20 fonctions
4. Tests non-régression

**Livrables:**
- 3 nouveaux modules cohésifs
- Complexité réduite
- Maintenabilité +100%
- Documentation refactoring

---

## 📊 Métriques Cibles Finales

| Métrique | Baseline | Post-Marathon | Gain |
|----------|----------|---------------|------|
| **Throughput** | 100% | 150-180% | +50-80% |
| **UI Responsive** | Baseline | +40% | Async |
| **Fonctions @lru_cache** | 8 | 30+ | +275% |
| **Loops vectorisés** | 0 | 10+ | New |
| **Domain entities** | 0 | 3+ | New |
| **Modules >1000L** | 52 | 51 | -1 |
| **Complexité avg** | Baseline | -30% | Refactor |

---

## ⏱️ Timeline Estimée

```
Heure 0-6:   Option A (Quick Wins)
Heure 6-12:  Option B (DDD Entities)  
Heure 12-20: Option C (Async/Await)
Heure 20-28: Option D (Refactoring)
```

**Total:** 20-28h selon rythme

---

## 🎯 Checkpoints

Après chaque option:
- [ ] Tests passent (100%)
- [ ] Benchmarks validés
- [ ] Documentation updated
- [ ] Commit clean
- [ ] Pause 10-15min

---

**Status:** 🚀 MARATHON DÉMARRÉ - Option A en cours
