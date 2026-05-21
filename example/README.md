
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
- Renforcer les tests des helpers, invariants et flux # CERTUS Example Data

This directory contains example input files for each CERTUS application module.

## Directory Structure

| Directory | CERTUS Module | Contents |
|---|---|---|
| `example_index/` | CERTUS INDEX | Spectral data (.xlsx, .csv, .xls) for single-layer index determination |
| `example_index_spline/` | CERTUS INDEX SPLINE | Total spectral data for spline-based n,k extraction |
| `example_design/` | CERTUS DESIGN | JSON design configs (coatings, targets, oblique) |
| `example_strat/` | CERTUS STRAT | JSON stratification configs (sweep, benchmark, verification) |
| `example_metal_single/` | CERTUS METAL SINGLE | Metal optical constants target data |
| `example_metal_bilayer/` | CERTUS METAL BILAYER | Bilayer metal characterization data |
| `example_RE/` | CERTUS RE | Reverse engineering sample data |
| `database_index/` | Substrate Library | Reference substrate optical indices |
| `IR/` | IR Spectral Data | Extended infrared spectral measurements |

## Quick Start

Each CERTUS module can be launched with its example file:

```bash
python CERTUS_INDEX.py          "example/example_index/CSV-index-example.csv"
python CERTUS_INDEX_SPLINE.py   "example/example_index_spline/TOTAL.xlsx"
python CERTUS_DESIGN.py         "example/example_design/JSON-design-example.json"
python CERTUS_STRAT.py          "example/example_strat/JSON-strat-example.json"
python CERTUS_METAL_SINGLE.py   "example/example_metal_single/Target_Titane_Simu_20nm.xlsx"
python CERTUS_METAL_BILAYER.py  "example/example_metal_bilayer/CSV-metal-example.csv"
python CERTUS_RE.py             "example/example_RE/reverse_sample.xlsx"
```

## Special Files

- `sapphire fresnel.xlsx` — Authoritative sapphire substrate optical data (used by CERTUS INDEX internals)


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