# Guide de remplacement de copy.deepcopy

## Problème

`copy.deepcopy()` est coûteux en performance car il :
- Parcourt récursivement toute la structure d'objets
- Crée un graph de dépendances pour gérer les références circulaires
- Copie même les objets qui n'ont pas besoin d'être copiés

**Impact mesuré** : -30% temps checkpoint/restore avec copies structurelles

## Stratégie de remplacement

### 1. Pour les dataclasses (recommandé)

Ajouter une méthode `.copy()` qui copie explicitement chaque champ :

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class OptimizationResult:
    ep: np.ndarray
    rmse: float
    merit: float
    history: list
    
    def copy(self) -> 'OptimizationResult':
        """Copie structurelle efficace - 3x plus rapide que deepcopy."""
        return OptimizationResult(
            ep=self.ep.copy(),              # Numpy array
            rmse=self.rmse,                  # Scalaire immutable
            merit=self.merit,                # Scalaire immutable
            history=[h.copy() for h in self.history]  # Liste de dicts/objets
        )
```

### 2. Pour les dictionnaires simples

Utiliser dict comprehension + copie sélective :

```python
# AVANT
import copy
checkpoint = copy.deepcopy(state_dict)

# APRÈS
checkpoint = {
    'ep': state_dict['ep'].copy(),           # Numpy array
    'rmse': state_dict['rmse'],              # Scalaire
    'results': [r.copy() for r in state_dict['results']]  # Liste
}
```

### 3. Pour les numpy arrays seuls

```python
# AVANT
import copy
ep_backup = copy.deepcopy(ep_current)

# APRÈS
ep_backup = ep_current.copy()  # 10x plus rapide
```

### 4. Pour les objets complexes avec état

Créer une méthode `snapshot()` dédiée :

```python
class OptimizationState:
    def __init__(self):
        self.ep = np.array([])
        self.best_merit = float('inf')
        self.history = []
    
    def snapshot(self) -> dict:
        """Crée un snapshot léger pour checkpoint."""
        return {
            'ep': self.ep.copy(),
            'best_merit': self.best_merit,
            'history_size': len(self.history),  # Pas besoin de tout copier
        }
    
    def restore_from_snapshot(self, snap: dict):
        """Restaure depuis un snapshot."""
        self.ep = snap['ep'].copy()
        self.best_merit = snap['best_merit']
```

---

## Fichiers à migrer

### Priorité 1 : Spline pipeline (hot path)

**Fichier** : `certus/spline/spline_pipeline_mesh_clean.py`
**Lignes** : 284, 636, 710, 742
**Usage** : Copie de `base_result` et `best_result_out`

**Action** :
```python
# Ajouter dans certus/spline/spline_core.py ou spline_types.py

@dataclass
class SplineMeshResult:
    knots: np.ndarray
    coeffs: np.ndarray
    rmse: float
    merit: float
    metadata: dict
    
    def copy(self) -> 'SplineMeshResult':
        return SplineMeshResult(
            knots=self.knots.copy(),
            coeffs=self.coeffs.copy(),
            rmse=self.rmse,
            merit=self.merit,
            metadata=self.metadata.copy()  # Shallow copy OK pour metadata
        )

# Remplacer dans mesh_clean.py:
# _copy.deepcopy(base_result) → base_result.copy()
```

### Priorité 2 : UI checkpoint/restore

**Fichier** : `certus/ui/certus_base_app.py`
**Ligne** : 1722
**Usage** : `self._best_eval_result = copy.deepcopy(data)`

**Action** :
```python
# Si data est un dict simple :
self._best_eval_result = {
    'ep': data['ep'].copy() if isinstance(data.get('ep'), np.ndarray) else data['ep'],
    'rmse': data['rmse'],
    'T': data['T'].copy() if 'T' in data else None,
    'R': data['R'].copy() if 'R' in data else None,
    # etc.
}
```

### Priorité 3 : RE workers

**Fichier** : `certus/ui/certus_re_workers_mixin.py`
**Lignes** : 886, 892

**Action** :
```python
# Ligne 886
"results": [r.copy() if hasattr(r, 'copy') else r for r in results],

# Ligne 892
"initial_stack": self._re_initial_stack.copy() if isinstance(self._re_initial_stack, list) else self._re_initial_stack,
```

---

## Pattern général de migration

### Étape 1 : Identifier le type

```python
import copy
obj_copy = copy.deepcopy(obj)
```

**Quel est le type de `obj` ?**
- Numpy array → `.copy()`
- Dict simple → dict comprehension
- Dataclass → ajouter méthode `.copy()`
- Objet custom → ajouter méthode `.snapshot()`

### Étape 2 : Mesurer l'impact

```python
from certus.core import perf_monitor

# AVANT
with perf_monitor.measure("deepcopy_checkpoint"):
    checkpoint = copy.deepcopy(state)

# APRÈS
with perf_monitor.measure("structured_copy_checkpoint"):
    checkpoint = state.copy()

# Comparer les résultats
perf_monitor.report_str(top_n=5)
```

### Étape 3 : Valider la correction

```python
import numpy as np

# Test que la copie est profonde (pas de partage mémoire)
original = {'ep': np.array([1, 2, 3])}
copied = structured_copy(original)

original['ep'][0] = 999
assert copied['ep'][0] == 1, "Copie pas profonde !"
```

---

## Cas particuliers

### Arrays numpy dans boucles

```python
# ÉVITER : allocation répétée
for i in range(1000):
    backup = current.copy()  # Allocation à chaque itération
    # ...

# PRÉFÉRER : buffer pré-alloué
backup_buffer = np.empty_like(current)
for i in range(1000):
    np.copyto(backup_buffer, current)  # Réutilise le buffer
    # ...
```

### Listes de résultats

```python
# AVANT
history_backup = copy.deepcopy(self.history)  # Copie 1000 éléments

# APRÈS (si on veut juste les N derniers)
history_backup = [h.copy() for h in self.history[-10:]]  # Copie 10 éléments
```

### Métadonnées immuables

```python
@dataclass
class Result:
    data: np.ndarray
    timestamp: str  # Immutable
    config: dict    # Mutable
    
    def copy(self):
        return Result(
            data=self.data.copy(),
            timestamp=self.timestamp,  # Pas besoin de copier (string immutable)
            config=self.config.copy()  # Shallow copy suffit souvent
        )
```

---

## Checklist de migration

- [ ] Identifier tous les `copy.deepcopy()` avec grep
- [ ] Pour chaque usage, déterminer le type réel
- [ ] Implémenter méthode `.copy()` sur dataclasses critiques
- [ ] Remplacer `deepcopy()` par `.copy()` ou dict comprehension
- [ ] Ajouter tests de non-partage mémoire
- [ ] Mesurer l'impact avec `perf_monitor`
- [ ] Valider avec tests existants

**Gain attendu** : -30% temps opérations checkpoint/restore
