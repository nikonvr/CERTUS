# Rate : répartition des mouvements — A/B sur un exemple (2026-10-13)

État : `complete` ; **2/2 exécutions terminées**.

`r75x0.5 deep 0 0 2 0 101 0`, défauts de production, 120 candidats Rate par tour.
Seule surcharge : `elite_rate_balanced_moves=false`, puis `true`. Option inactive par défaut.
Base `da1af0825d5e09e8d0a5ff4f1cf42b802e0e30e7` + instantané volontairement non committé, identique pour les deux variantes.
Patch : [source.patch](STRAT_Rate_equilibre_AB_2026-10-13/source.patch), SHA256 `ab94c4091dae4c33219940428c9f168df0fe0061d5be4cad37b66d2c80c530b4` ; empreintes des deux sources dans `etat.json`.
16 processeurs logiques par affinité, priorité normale, 15 threads de bibliothèque ; une mesure à la fois.

| variante | SEEL nm | déposables | durée min |
|---|---:|---:|---:|
| actuel | 0.396715 | 4069 | 46.75 |
| equilibre | 0.479488 | 3777 | 37.80 |

`actuel` : Rate L7-L10, L13-L34, L37-L75 ; optique L1-L6, L11-L12, L35-L36 ; 9 blocs (1-9 a 630 nm, 10-20 a 451 nm, 21-30 a 691 nm, 31-40 a 706 nm, 41-50 a 741 nm, 51-60 a 705 nm, 61-65 a 708 nm, 66-70 a 742 nm, 71-75 a 580 nm)
Artefact : [blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_off.json](STRAT_Rate_equilibre_AB_2026-10-13/blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_off.json).


`equilibre` : Rate L4-L10, L15-L69, L74-L75 ; optique L1-L3, L11-L14, L70-L73 ; 3 blocs (1-20 a 451 nm, 21-50 a 691 nm, 51-75 a 732 nm)
Artefact : [blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_on.json](STRAT_Rate_equilibre_AB_2026-10-13/blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_on.json).


Écart équilibré / actuel : **+20.86 %**.

Un composant, une graine : aucune généralisation ni activation du défaut.
Le modèle Rate ne comporte pas de dérive de vitesse au cours du dépôt. SEEL et RMSE par bruit sont conservés dans les artefacts.
Vérifications avant mesure : Ruff, 72 tests ciblés (routage, plafond, fenêtres et architecture), oracle 1 143 passed. Validation complète non terminée ; aucun commit.

Contrôleur de reprise A2 lancé : PID `30048`.
