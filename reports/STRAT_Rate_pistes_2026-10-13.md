# Rate : essais successifs sur r75x0.5 (2026-10-13)

État : `complete` ; 3 essai(s) sauvegardé(s).
Graine 101, mode deep, mêmes sources que le A/B ; paramètres effectifs et SHA256 dans `etat.json`.
16 processeurs logiques, affinité 0xffff, priorité normale, 15 threads de bibliothèque ; une mesure à la fois.
A2 sauvegarde son calcul courant avant les essais ; sa reprise est conservée.

| essai | surcharges | meilleur SEEL nm | écart à la référence | déposables | durée min |
|---|---|---:|---:|---:|---:|
| référence A/B | équilibrage désactivé, budget 120 | 0.396715 | — | 4069 | 46,75 |
| budget_240 | `elite_rate_balanced_moves=False, elite_rate_max_candidates=240` | 0.382810 | -3.50 % | 4134 | 39.95 |
| raffinement_6 | `elite_rate_balanced_moves=False, elite_rounds=6` | 0.387351 | -2.36 % | 5113 | 43.79 |
| budget_360 | `elite_rate_balanced_moves=False, elite_rate_max_candidates=360` | 0.382810 | -3.50 % | 4191 | 41.34 |

Artefact `budget_240` : [blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_budget_240.json](STRAT_Rate_pistes_2026-10-13/blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_budget_240.json).
Rate L7-L10, L15-L31, L36-L75 ; optique L1-L6, L11-L14, L32-L35 ; 8 blocs (1-9 a 630 nm, 10-20 a 451 nm, 21-30 a 691 nm, 31-40 a 706 nm, 41-50 a 741 nm, 51-65 a 733 nm, 66-70 a 742 nm, 71-75 a 580 nm)

Artefact `raffinement_6` : [blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_raffinement_6.json](STRAT_Rate_pistes_2026-10-13/blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_raffinement_6.json).
Rate L7-L10, L13-L34, L37-L75 ; optique L1-L6, L11-L12, L35-L36 ; 9 blocs (1-9 a 630 nm, 10-20 a 451 nm, 21-30 a 691 nm, 31-40 a 705 nm, 41-50 a 741 nm, 51-60 a 705 nm, 61-65 a 708 nm, 66-70 a 742 nm, 71-75 a 580 nm)

Artefact `budget_360` : [blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_budget_360.json](STRAT_Rate_pistes_2026-10-13/blocs_vs_plantage_r75x0.5_deep_s101_rate_pistes_budget_360.json).
Rate L7-L10, L15-L31, L36-L75 ; optique L1-L6, L11-L14, L32-L35 ; 10 blocs (1-9 a 630 nm, 10-20 a 451 nm, 21-30 a 691 nm, 31-40 a 706 nm, 41-50 a 741 nm, 51-55 a 733 nm, 56-60 a 705 nm, 61-65 a 708 nm, 66-70 a 742 nm, 71-75 a 580 nm)

Un seul composant et une graine de recherche ; un gain exige un contrôle indépendant.
Profondeurs conservées : 300 tirages complets, 50 au screening, consensus à 300.
Les durées comprennent des états de cache différents ; elles ne prouvent pas seules un gain de vitesse.
Aucun défaut modifié et aucun commit. Suite complète du code expérimental antérieur encore à faire.
