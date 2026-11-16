# Nuit du 2026-11-16 — reprise

Ordre de 👤 (23:07) : « lance tout à la suite en mode automatisé » ; « git push all commit ».

| # | tâche | état |
|---|---|---|
| 1 | Pillow 12.3.0 → 13.0.0 (`uv.lock`, `requirements.lock`), validation complète | validation en cours (`reports/audit_code_2026-11-15/validation_pillow13/`) |
| 2 | avance rapide sur `256f4f01` (tri Dependabot), commit Pillow, `check_publication.py`, push master | à faire |
| 3 | setuptools 84.0.0 → 84.1.0, validation, commit, push | à faire |
| 4 | chantier 46 : 18 entrées reclassées (Fresnel d'une interface, inversion n(R)) ; 3 vraies copies à déléguer à `reflection_amplitudes` : `certus_field_core._calculate_field_single_pol`, `certus_opt_needle.needle_scan_cached`, `certus_opt_tmm.calculate_reflectance_bilayer_vectorized` ; oracle et `c1_diff` avant et après | à faire |
| 5 | chantier 47 : épaisseur du substrat sur tous les chemins DESIGN et STRAT | à faire |
| 6 | sondes : écart ε1/KK de 0,42 sur H800 ; recherche locale finale sans gain après C-L4 | à faire |
| 7 | validation finale, ETAT, push | à faire |

Les commits des tâches 4 à 6 restent locaux tant qu'ils ne sont pas validés ; push seulement après `VALIDATION=GO`.
