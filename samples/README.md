
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
- Renforcer les tests des helpers, invariants et flux # CERTUS sample data

Minimal demo files used by the UX onboarding layer (`certus_sample_data`)
and the "Load sample data" buttons injected into empty states across the
suite.

Layout expected by :func:`certus_sample_data.list_samples` :

```
samples/
    config/        *.json        - ready-to-load app configurations
    spectrum/      *.csv, *.txt  - measured or synthetic spectra
    substrate/     *.csv         - substrate n,k tables
    profile/       *.json, *.csv - d-profile or optimiser profiles
    project/       *.json, *.zip - bundled project archives
```

Each sample may ship an optional ``<name>.txt`` sidecar whose first line
is used as a short human description in the sample picker.

## What's here today

| File | Category | Purpose |
|---|---|---|
| `config/demo_single_layer.json` | config | Starter CERTUS-DESIGN configuration (1 layer) |
| `spectrum/demo_flat_95pct.csv` | spectrum | Flat T=0.95 reference spectrum, 400-800 nm |
| `substrate/demo_glass_nk.csv` | substrate | Generic glass n,k table (400-1100 nm) |

Additional demos can be dropped in the matching folder at any time - they
are discovered automatically.


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