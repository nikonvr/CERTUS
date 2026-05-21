
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # Determinism Guarantee

## Scope

This document defines the determinism contract for CERTUS runs.

## Bit-identical conditions

Two runs are expected to be bit-identical only when all conditions below are matched:

- same CERTUS source revision
- same Python runtime and dependency set
- same `requirements.lock` resolution
- same materials database version and hash (`materials_db_hash`)
- same input files (fingerprints/sha256)
- same seed for stochastic paths
- same CPU family / SIMD path
- same OS release and locale/runtime threading layer

## Epsilon-close conditions

If environment differs (CPU vendor, OS patch level, BLAS/threading implementation), results may differ at floating-point LSB level.  
In this case, validation must rely on documented epsilon thresholds from `docs/NUMERICAL_TOLERANCES.md`.

## Required manifest fields

A run is considered reproducible only if its manifest includes, at minimum:

- `run_id`
- `started_at_utc`
- `app_id`
- `app_version`
- `params_hash`
- `materials_db_hash`
- `numpy_version`
- `numba_version`
- `threading_layer`
- `os_release`


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.