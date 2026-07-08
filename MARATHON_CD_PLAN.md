# Marathon C+D - Session 3

**Session:** Nouvelle (contexte frais 0%)  
**Objectif:** Options C (Async) + D (Refactoring)  
**Estimation:** 14-18h

---

## 🎯 Option C: Async/Await Migration

### Analyse Workers (Phase 1)

**Fichiers workers identifiés:** 20 fichiers
**ThreadPoolExecutor usage:** 18 occurrences

**Fichiers principaux:**
```
certus/workers/
├── certus_base_workers.py          (base infrastructure)
├── certus_design_engine.py         (design optimization)
├── certus_design_workers.py        (main design workers)
├── certus_field_workers.py         (field calculations)
├── certus_index_workers.py         (index optimization)
├── certus_re_workers.py            (reverse engineering)
└── certus_spectral_workers.py      (spectral calculations)
```

### Stratégie Migration Async

**Approche recommandée:**

#### Phase 1: POC Async (2-3h)
1. Créer worker async de base
2. PyQt6 + asyncio integration
3. 1 worker simple converti
4. Tests validation

#### Phase 2: Migration Batch (3-4h)
1. Convertir 3-5 workers critiques
2. I/O async (fichiers, DB)
3. Error handling async
4. Tests complets

#### Phase 3: UI Integration (1-2h)
1. Signals/slots async
2. Progress reporting async
3. Cancellation support

**Total Option C:** 6-9h

---

## 🎯 Option D: Refactoring Module

### Cible Prioritaire

**certus_opt_gradients.py:** 3355 lignes ⚠️

**Plan split:**
1. `gradient_analytic.py` - Analytical gradients
2. `gradient_numeric.py` - Numerical gradients  
3. `gradient_utils.py` - Shared utilities

### Stratégie Refactoring

#### Phase 1: Analyse (1h)
1. Identifier dépendances
2. Tracer call graph
3. Définir boundaries

#### Phase 2: Split (3-4h)
1. Extract fonctions par catégorie
2. Créer nouveaux modules
3. Update imports

#### Phase 3: Tests (2h)
1. Tests non-régression
2. Validation complète
3. Coverage maintenu

**Total Option D:** 6-7h

---

## 💡 Décision: Commencer par Quoi?

### Option 1: C puis D (Recommandé) ✅
- Async = feature immediate value
- UI responsive = user visible
- Puis refactoring (internal quality)

### Option 2: D puis C
- Refactoring d'abord = code cleaner
- Puis async sur code propre
- Moins urgent user-wise

**Ma recommandation: Option 1 (C→D)**

---

**Validation pour démarrer Option C ?** 🚀
