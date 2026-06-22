# CERTUS — Tests Headless

Tests d'intégration headless pour valider chaque module CERTUS sans interaction UI.

## Structure

```
tests/headless/
├── README.md
├── run_all.py              ← Runner global
├── test_metal_single.py   ← CERTUS METAL SINGLE
├── test_metal_bilayer.py  ← CERTUS METAL BILAYER
├── test_field.py          ← CERTUS FIELD
├── test_re.py             ← CERTUS RE
├── test_design.py         ← CERTUS DESIGN
└── test_spline.py         ← CERTUS INDEX SPLINE
```

## Utilisation

### Tous les tests
```powershell
.\.venv\Scripts\python.exe tests/headless/run_all.py
```

### Un test individuel
```powershell
.\.venv\Scripts\python.exe tests/headless/test_metal_single.py
.\.venv\Scripts\python.exe tests/headless/test_metal_bilayer.py
.\.venv\Scripts\python.exe tests/headless/test_field.py
.\.venv\Scripts\python.exe tests/headless/test_re.py
.\.venv\Scripts\python.exe tests/headless/test_design.py
.\.venv\Scripts\python.exe tests/headless/test_spline.py
```

## Valeurs de référence attendues

| Module         | Métrique          | Valeur attendue |
|----------------|-------------------|-----------------|
| METAL_SINGLE   | RMSE              | ~1.5%           |
| METAL_BILAYER  | RMSE              | ~1.5%           |
| FIELD          | success           | True            |
| RE             | RMSE              | ~0.015          |
| DESIGN         | Best RMSE         | < 0.010         |
| SPLINE         | RMSE              | ~0.003–0.005    |

## Données utilisées

| Module         | Fichier exemple                                    |
|----------------|----------------------------------------------------|
| METAL_SINGLE   | `example/example_metal_single/`                    |
| METAL_BILAYER  | `example/example_metal_bilayer/`                   |
| FIELD          | `example/example_field/test_hr_mirror.json`        |
| RE             | `example/example_RE/reverse_sample.xlsx`           |
| DESIGN         | `example/example_design/JSON-design-optimized.json`|
| SPLINE         | `example/example_index_spline/TSIO2-1700-1.xlsx`  |

## Notes

- **SPLINE** : substrat Al2O3, mesures T relative, épaisseur ~1700 nm, n(550nm)~1.475, n(2000nm)~1.43
- **DESIGN** : mode `global` (~30-60s), RMSE < 0.010 attendu
- **FIELD** : calcul multicouche 1064/532/355 nm
- Tous les tests sont autonomes (pas de GUI, pas d'interaction utilisateur)
