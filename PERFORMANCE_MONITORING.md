# CERTUS Performance Monitoring Guide

## Activation

Le système de monitoring de performance est activé via variable d'environnement :

```bash
# Activer le monitoring
export CERTUS_PERF_LOG=1

# Définir le seuil de logging (par défaut 0.1s)
export CERTUS_PERF_THRESHOLD=0.05

# Lancer l'application
python certus_design.py
```

## Utilisation

### 1. Décorateur automatique

```python
from certus.core import log_perf

@log_perf
def optimize_stack(ep, wls, targets):
    """Cette fonction sera automatiquement monitorée."""
    result = heavy_optimization(ep, wls, targets)
    return result

# Avec paramètres personnalisés
@log_perf(operation="tmm_calculation", threshold=0.5)
def calc_spectrum_full(ep, n_layers, wls):
    """Nom personnalisé et seuil de 0.5s."""
    return tmm_calc(ep, n_layers, wls)
```

### 2. Context Manager

```python
from certus.core import perf_monitor

def complex_workflow():
    with perf_monitor.measure("data_preparation"):
        data = prepare_data()
    
    with perf_monitor.measure("optimization"):
        result = optimize(data)
    
    with perf_monitor.measure("post_processing"):
        final = process_result(result)
    
    return final
```

### 3. Enregistrement manuel

```python
import time
from certus.core import perf_monitor

start = time.perf_counter()
result = expensive_operation()
elapsed = time.perf_counter() - start

perf_monitor.record("expensive_operation", elapsed)
```

## Rapports

### Afficher le rapport

```python
from certus.core import perf_monitor

# Rapport complet
print(perf_monitor.report_str())

# Top 5 opérations par temps total
print(perf_monitor.report_str(top_n=5, sort_by="total"))

# Top 10 par temps moyen
print(perf_monitor.report_str(top_n=10, sort_by="mean"))

# Logger le rapport
perf_monitor.log_report(top_n=10)
```

### Rapport programmatique

```python
# Obtenir les données brutes
report = perf_monitor.report(top_n=10, sort_by="p95")

for op in report["operations"]:
    print(f"{op['operation']}: {op['count']} calls, {op['mean']:.3f}s mean")

# Métriques spécifiques
metrics = perf_monitor.get_metrics("needle_scan")
if metrics:
    print(f"Needle scan - P95: {metrics.p95:.3f}s, Max: {metrics.max:.3f}s")
```

## Exemple d'intégration dans un Worker

```python
from certus.core import perf_monitor, log_perf

class OptimizationWorker:
    @log_perf
    def run_optimization(self, request):
        with perf_monitor.measure("validation"):
            self._validate_request(request)
        
        with perf_monitor.measure("tmm_forward"):
            spectrum = self._calc_spectrum(request.ep, request.wls)
        
        with perf_monitor.measure("gradient_computation"):
            gradients = self._compute_gradients(request.ep, request.wls)
        
        with perf_monitor.measure("optimizer_step"):
            new_ep = self._optimizer_step(request.ep, gradients)
        
        return new_ep
    
    def on_complete(self):
        # Logger les stats de performance à la fin
        perf_monitor.log_report(top_n=10, sort_by="total")
```

## Exemple de sortie

```
================================================================================
CERTUS PERFORMANCE REPORT
================================================================================
Total operations tracked: 15
Total time: 45.234s
Total calls: 1247

Top 10 operations by total:
--------------------------------------------------------------------------------
Operation                                   Count      Total       Mean        P95
--------------------------------------------------------------------------------
certus_physics.calc_spectrum_full             342    23.456s     0.069s     0.120s
certus_opt.compute_gradients                  342    12.345s     0.036s     0.065s
certus_design.needle_scan_cached               28     5.678s     0.203s     0.450s
certus_workers.optimization_step              342     2.345s     0.007s     0.015s
certus_ui.update_plot                         124     0.876s     0.007s     0.012s
================================================================================
```

## Contrôle programmatique

```python
from certus.core import perf_monitor

# Activer/désactiver dynamiquement
perf_monitor.enable()
perf_monitor.disable()

# Réinitialiser les métriques
perf_monitor.reset()

# Vérifier l'état
if perf_monitor.enabled:
    print("Monitoring actif")
```

## Best Practices

1. **Granularité** : Monitorer les opérations significatives (>10ms typiquement)
2. **Nommage** : Utiliser des noms descriptifs et consistants
3. **Hiérarchie** : Utiliser des préfixes pour grouper (ex: `tmm.forward`, `tmm.gradient`)
4. **Rapports** : Logger les rapports à la fin des workflows longs
5. **Production** : Désactiver en production sauf pour debug (`CERTUS_PERF_LOG=0`)

## Zones critiques à monitorer

```python
# TMM calculations
@log_perf(operation="tmm.calc_spectrum_full")
def calc_spectrum_full(...):
    ...

# Gradient computations
@log_perf(operation="tmm.compute_gradients")
def calc_gradient_front(...):
    ...

# Optimization steps
@log_perf(operation="optimizer.lbfgs_step")
def lbfgs_step(...):
    ...

# Needle operations
@log_perf(operation="needle.scan_insert")
def needle_scan_cached(...):
    ...

# UI updates
@log_perf(operation="ui.plot_update", threshold=0.05)
def update_spectrum_plot(...):
    ...
```

## Intégration avec les tests

```python
import pytest
from certus.core import perf_monitor

@pytest.fixture(autouse=True)
def reset_perf_monitor():
    perf_monitor.reset()
    yield
    perf_monitor.reset()

def test_performance_regression():
    """Vérifie que l'optimisation ne dépasse pas 1s."""
    perf_monitor.enable()
    
    result = optimize_stack(ep, wls, targets)
    
    metrics = perf_monitor.get_metrics("optimize_stack")
    assert metrics.mean < 1.0, f"Performance regression: {metrics.mean:.3f}s > 1.0s"
```
