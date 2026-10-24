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
| STRAT complet, graine 202 (01 h 13 → 04 h 21), recherche locale intégrée | 90 blocs, 65 Rate | 0,211 (recherche) | 0 |
| **règle du saphir** (👤, 24/10) : pas de Rate avant la couche 10, Rate seulement si n·d ≤ 50 nm ; 44 couches passées en optique (meilleure λ chacune), 2 passes, 37 changements | **15 Rate, 83 % d'optique** | **0,2608** au holdout (+125 % RMSE² contre le plan libre) | 0 au holdout, 1 sur 9 000 à la confirmation |
| idem + 2 passes (passes 3–4), 14 changements, 14 Rate | 14 Rate, 84 % d'optique | 0,2626 au holdout (RMSE² moyen −5,1 %, ET 0,4 %, mais SEEL P95 +0,7 %) | 0 au holdout, 1 sur 9 000 à la confirmation |

SEEL au sens de STRAT, 2·√(P95 du RMSE spectral) sur le pire des trois bruits ; holdout : graines 20261022201–203,
3 × 1000 tirages, appariées. Plans : [`winner_strat_s077.json`](winner_strat_s077.json),
[`modelam_s077_refine.json`](modelam_s077_refine.json) (journal `modelam_s077_refine_log.txt`), règle du saphir
[`modelam_s077_sapphire_rule.json`](modelam_s077_sapphire_rule.json) (`FORCE_OPTICAL` = toutes les couches hors des 17 fines
au-delà de la couche 9 ; journal `modelam_s077_sapphire_rule_log.txt`).

**Plan retenu sous les règles de 👤** : [`modelam_s077_sapphire_rule.json`](modelam_s077_sapphire_rule.json), 15 Rate, SEEL
0,2608 nm (critère SEEL P95 ; les passes 3–4 baissent le RMSE² moyen mais pas le P95). Plan libre, meilleur absolu : 0,2046 nm
avec 61 Rate. Part de l'indice (mêmes tirages de holdout, corridor 0 contre ±0,010, [`index_share_bm90.py`](index_share_bm90.py)) :
69 % du RMSE² moyen pour le plan retenu (SEEL 0,2339 → 0,2608 nm), 81 % pour le plan libre (0,1688 → 0,2046 nm) ; 0 arrêt.
Le leviers STRAT des 23–24/10 (branche `claude/2026-10-22`) n'apportent rien ici : la garde contrôle au corridor configuré,
déjà ±0,010 ; A12 et A13 sont refusés sur leur branche.

## Cible projetée (levier saphir), essayée sur le plan retenu

Fenêtres de 8 couches optiques (pas de 4), λ ±60 nm, chaque choix jugé en supposant zéro erreur au-delà de la fenêtre + 4
couches ([`windows_bm90.py.txt`](windows_bm90.py.txt), autotest PASS) : 77 changements, puis jugement sur la cible
complète (graines 20261020501–503) : **perd**, SEEL 0,2595 → 0,3093 nm, RMSE² +97,5 % (ET 1,6 %), arrêts 1 → 41
([`windows_projected_b4_result.json`](windows_projected_b4_result.json)). Même verdict que sur les trois designs r75 :
en supposant l'aval parfait, l'optimiseur retient des λ que les erreurs réelles de l'aval rendent mauvaises.

## Sensibilité au corridor d'indice

Mêmes tirages de holdout (graines 20261022201–203, 3 × 1000), seul le corridor change ; RMSE moyen de T de la pièce déposée
contre le design nominal, au bruit nominal, en pp ([`corridor_0.005_result.json`](corridor_0.005_result.json),
[`index_share_result.json`](index_share_result.json)) :

| corridor d'indice | plan retenu, 15 Rate : SEEL / RMSE | plan libre, 61 Rate : SEEL / RMSE |
|---|---|---|
| 0 | 0,2339 nm / 0,55 pp | 0,1688 nm / 0,29 pp |
| ±0,005 | **0,2392 nm / 0,69 pp** | 0,1792 nm / 0,43 pp |
| ±0,010 | **0,2608 nm / 0,98 pp** | 0,2046 nm / 0,66 pp |

0 arrêt partout. Le RMSE contre la cible ajoute à ce RMSE l'écart nominal du design (1,5495 pp).

## Dossier de réalisation

[`Bonne_Mere_90c_silice_realisation.xlsx`](Bonne_Mere_90c_silice_realisation.xlsx), pour programmer le dépôt sur Helios 800
et OMS 5100 : paramètres (vitesses provisoires à renseigner), stratégie couche par couche (mode, λ, niveau d'arrêt, sens,
points tournants), signaux attendus, spectres, indices, cible ; généré par [`make_xlsx.py.txt`](make_xlsx.py.txt) (à lancer avec Python, le nom du classeur en argument) (RMSE nominal
recalculé 1,5495 pp, égal au design).

## Commandes

- STRAT : `python -X utf8 reports/BONNE_MERE_strat_90c_2026-10-23/probe_bm90.py deep 0 0 2 0 77` avec `CERTUS_BENCH_TIMEOUT_S=36000` (le run dure 3 h 40 ;
  la limite par défaut de 30 min rend `ECHEC_RESULT_NONE`) ; sortie `reports/blocs_vs_plantage_bm90_deep_s077.json`
  (19 Mo, non suivie).
- Affinage : `python -X utf8 reports/BONNE_MERE_strat_90c_2026-10-23/modelam_bm90.py bm90 TAG OFFSET` (copie de l'outil r75, dossier de travail `%TEMP%\bm90`).
