# STRAT aux réglages par défaut, campagne A10 (2026-10-21, code `6af2cc5b`)

Lanceur `reports/STRAT_etage_defauts_2026-10-21/run_etage_panel.py.txt`. Jugement : plan classé premier contre le meilleur plan ELITE du même banc, 3 × 1 000 tirages sur graines neuves, mêmes tirages pour les deux. Chiffres bruts : `cas.json`.

| cas | étage | ±0,005 : SEEL ELITE → final (nm) | arrêts | ΔRMSE² | ±0,010 : SEEL ELITE → final (nm) | arrêts | ΔRMSE² |
|---|---|---|---|---|---|---|---|
| 75c_deep_s202 | accepté | 0.2467 → 0.2081 | 0 → 0 | -61.0 % | 0.9125 → 0.2480 | 233 → 7 | -64.0 % |
| r75x0.5_deep_s202 | repli | 0.4007 → 0.3564 | 0 → 0 | -33.3 % | 0.4450 → 0.3962 | 0 → 0 | -36.2 % |
| r75x2_deep_s101 | accepté | 0.5383 → 0.5959 | 0 → 0 | -33.7 % | 0.6854 → 0.6738 | 0 → 2 | -39.7 % |
| r75x2_deep_s202 | refusé | — | — | — | — | — | — |

Interprétation : à faire par Claude (ETAT_actions.md, répartition). Ce lanceur ne conclut pas.
