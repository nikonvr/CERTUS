# Migration vers Lazy Imports - Guide

## Problème

Les imports de bibliothèques lourdes au début des fichiers ralentissent le démarrage de l'application :
- `scipy` : ~100ms
- `matplotlib` : ~200ms  
- `openpyxl` : ~50ms

Total : **~350ms** de temps de démarrage économisés avec lazy imports.

## Solution

Utiliser `certus_lazy_imports` pour différer le chargement jusqu'à l'utilisation réelle.

---

## Exemples de migration

### 1. scipy.optimize

**AVANT** :
```python
# certus/core/certus_index_solvers.py
import scipy
import scipy.optimize

def optimize_refractive_index(n0, target):
    result = scipy.optimize.minimize(cost_func, n0)
    return result
```

**APRÈS** :
```python
# certus/core/certus_index_solvers.py
from certus.core.certus_lazy_imports import lazy_scipy_optimize

def optimize_refractive_index(n0, target):
    # Import ne se produit que lors de l'appel de cette fonction
    opt = lazy_scipy_optimize()
    result = opt.minimize(cost_func, n0)
    return result
```

### 2. matplotlib dans utilitaires de rapport

**AVANT** :
```python
# certus/utils/certus_reports.py
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

def generate_plot(data):
    fig = plt.figure()
    # ...
    return fig
```

**APRÈS** :
```python
# certus/utils/certus_reports.py
from certus.core.certus_lazy_imports import lazy_matplotlib_pyplot

def generate_plot(data):
    # matplotlib n'est chargé que si on génère effectivement un plot
    plt = lazy_matplotlib_pyplot()
    fig = plt.figure()
    # ...
    return fig
```

### 3. openpyxl pour export Excel

**AVANT** :
```python
# certus/ui/certus_re_excel_mixin.py
import openpyxl
from openpyxl.styles import Font, Alignment

def export_to_excel(data, filepath):
    wb = openpyxl.Workbook()
    # ...
    wb.save(filepath)
```

**APRÈS** :
```python
# certus/ui/certus_re_excel_mixin.py
from certus.core.certus_lazy_imports import lazy_openpyxl

def export_to_excel(data, filepath):
    # openpyxl n'est chargé que lors d'un export réel
    xl = lazy_openpyxl()
    wb = xl.Workbook()
    # Pour les imports depuis sous-modules
    Font = xl.styles.Font
    Alignment = xl.styles.Alignment
    # ...
    wb.save(filepath)
```

### 4. Vérification de disponibilité

**AVANT** :
```python
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
```

**APRÈS** :
```python
from certus.core.certus_lazy_imports import check_openpyxl_available

# Vérification sans import (ultra-rapide)
OPENPYXL_AVAILABLE = check_openpyxl_available()
```

---

## Stratégie de migration

### Phase 1 : Fichiers à fort impact (export/reporting)

Ces fichiers sont rarement utilisés au démarrage mais importent des dépendances lourdes.

1. **certus/utils/certus_reports.py** - matplotlib
2. **certus/utils/certus_live_visualizer.py** - matplotlib  
3. **Tous les mixins Excel** (`*_excel_mixin.py`) - openpyxl

### Phase 2 : Workers (chargés dynamiquement)

Ces modules sont instanciés uniquement lors de calculs :

4. **certus/workers/certus_index_workers.py** - scipy
5. **certus/workers/certus_index_workers_ir_strat.py** - scipy
6. **certus/workers/certus_index_workers_opt_strat.py** - scipy
7. **certus/workers/certus_re_workers_phase4.py** - scipy.optimize

### Phase 3 : UI modules (conditionnels)

Certaines fonctions UI ne sont appelées que sur action utilisateur :

8. **certus/ui/certus_design_ui_optimization.py:894** - scipy.optimize (déjà local)
9. **certus/ui/certus_index_ui_*.py** - scipy.optimize

### Phase 4 : Core modules (à évaluer)

⚠️ Attention : certains modules core utilisent scipy intensivement.

10. **certus/core/certus_index_solvers.py** - scipy
11. **certus/core/certus_index_objectives.py** - scipy

**Décision** : Laisser en import direct si utilisé systématiquement au démarrage.

---

## Pattern de migration automatique

Pour automatiser la migration, utiliser ce pattern de recherche/remplacement :

### Regex find:
```
^import scipy\.optimize$
```

### Replace with:
```python
from certus.core.certus_lazy_imports import lazy_scipy_optimize
# Note: remplacer scipy.optimize.XXX par lazy_scipy_optimize().XXX dans le code
```

---

## Tests après migration

1. **Vérifier que l'import fonctionne** :
```python
def test_lazy_scipy_optimize():
    from certus.core.certus_lazy_imports import lazy_scipy_optimize
    opt = lazy_scipy_optimize()
    # Devrait avoir les mêmes attributs que scipy.optimize
    assert hasattr(opt, 'minimize')
    assert hasattr(opt, 'differential_evolution')
```

2. **Mesurer le gain de performance** :
```python
import time

# Avant migration
start = time.perf_counter()
import certus.core.certus_index_solvers  # Import avec scipy direct
elapsed_before = time.perf_counter() - start

# Après migration  
start = time.perf_counter()
import certus.core.certus_index_solvers  # Import avec lazy_scipy
elapsed_after = time.perf_counter() - start

print(f"Gain: {(elapsed_before - elapsed_after) * 1000:.1f}ms")
```

---

## Exemple complet : Migration d'un worker

**Fichier : certus/workers/certus_index_workers.py**

**AVANT** :
```python
import numpy as np
import scipy
import scipy.optimize
from certus.core import get_logger

class IndexOptimizationWorker:
    def __init__(self):
        self.logger = get_logger()
    
    def run(self, n0, targets):
        self.logger.info("Starting optimization")
        result = scipy.optimize.differential_evolution(
            self.cost_func, bounds=[(1.0, 3.0)]
        )
        return result
```

**APRÈS** :
```python
import numpy as np
from certus.core import get_logger
from certus.core.certus_lazy_imports import lazy_scipy_optimize

class IndexOptimizationWorker:
    def __init__(self):
        self.logger = get_logger()
        # scipy n'est pas encore chargé ici - démarrage instantané
    
    def run(self, n0, targets):
        self.logger.info("Starting optimization")
        # scipy est chargé uniquement maintenant, lors de l'appel à run()
        opt = lazy_scipy_optimize()
        result = opt.differential_evolution(
            self.cost_func, bounds=[(1.0, 3.0)]
        )
        return result
```

**Gain** : Le worker peut être importé sans charger scipy (~100ms économisés). scipy n'est chargé que si `run()` est réellement appelé.

---

## Ordre de migration recommandé

1. ✅ **Créer certus/core/certus_lazy_imports.py**
2. ✅ **Migrer certus/utils/certus_reports.py** (matplotlib)
3. ✅ **Migrer tous les *_excel_mixin.py** (openpyxl)
4. ✅ **Migrer certus/workers/certus_index_workers*.py** (scipy)
5. ⚠️ **Évaluer core modules** (cas par cas)

**Gain total estimé** : -40% temps de démarrage (~350ms sur ~900ms total).
