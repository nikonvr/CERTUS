# Stratégie de dépôt du design Bonne Mère retenu (90 couches, silice) — 2026-10-23/24

Design : [`best_design_needle_swap_90_nominal.json`](../BONNE_MERE_design_2026-10-23/best_design_needle_swap_90_nominal.json).
Réglages de 👤 : corridor d'indice ±0,010, monitoring 430–900 nm, fente fixe 2 nm, leviers Rate/Optique et λ par
couche (ni précouche ni changement de témoin), classement sur le SEEL P95 sans arrêt. STRAT de cet arbre (`9e3887bd`),
mode deep, budgets de l'étude Bonne Mère ([`make_config.py`](make_config.py)).

## Résultats

| étape | plan | SEEL (nm) | arrêts |
|---|---|---|---|
| STRAT complet, graine 77 (20 h 24 → 00 h 04) : meilleur ELITE | 90 blocs, 73 Rate | 0,313 (recherche) | 0 |
| idem, recherche locale intégrée de STRAT | 90 blocs, 61 Rate | 0,210 (recherche) ; **0,2099** au holdout | 0 |
| affinage apparié (mode, λ 430–900 nm), 2 passes, 18 changements | 61 Rate | **0,2046** au holdout (−8,8 % RMSE², ET 0,3 %) | 0 → 0 |

SEEL au sens de STRAT, 2·√(P95 du RMSE²) sur le pire des trois bruits ; holdout : graines 20261022201–203,
3 × 1000 tirages, appariées. Plans : [`winner_strat_s077.json`](winner_strat_s077.json),
[`modelam_s077_refine.json`](modelam_s077_refine.json) (journal `modelam_s077_refine_log.txt`).

## Commandes

- STRAT : `python -X utf8 probe_bm90.py deep 0 0 2 0 77` avec `CERTUS_BENCH_TIMEOUT_S=36000` (le run dure 3 h 40 ;
  la limite par défaut de 30 min rend `ECHEC_RESULT_NONE`) ; sortie `reports/blocs_vs_plantage_bm90_deep_s077.json`
  (19 Mo, non suivie).
- Affinage : `python -X utf8 modelam_bm90.py bm90 TAG OFFSET` (copie de l'outil r75, dossier de travail `%TEMP%\bm90`).
