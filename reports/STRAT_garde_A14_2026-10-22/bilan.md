# Étage avec garde au corridor configuré, campagne A14 (2026-10-22, code `7b175249`)

Lanceur `reports/STRAT_etage_defauts_2026-10-21/run_etage_panel.py.txt`. Jugement : plan classé premier contre le meilleur plan ELITE du même banc, 3 × 1 000 tirages sur graines neuves, mêmes tirages pour les deux. Chiffres bruts : `cas.json`.

| cas | étage | ±0,005 : SEEL ELITE → final (nm) | arrêts | ΔRMSE² | ±0,010 : SEEL ELITE → final (nm) | arrêts | ΔRMSE² |
|---|---|---|---|---|---|---|---|
| 48c_premium_s42 | repli | 0.1699 → 0.1569 | 0 → 0 | -59.7 % | 0.2314 → 0.1722 | 0 → 0 | -76.5 % |
| 35c_deep_s42 | refusé | — | — | — | — | — | — |
| r75x1.5_deep_s77 | repli | 0.4820 → 0.4507 | 0 → 0 | -51.7 % | 0.6118 → 0.5019 | 0 → 0 | -55.4 % |
| r75x1.75_deep_s77 | repli | 0.4805 → 0.4099 | 4 → 0 | -48.2 % | 0.6243 → 0.5522 | 5 → 0 | -44.8 % |
| r75x2-2nm_deep_s77 | accepté | 0.5468 → 0.4726 | 0 → 0 | -45.8 % | 0.6684 → 0.5624 | 3 → 2 | -55.7 % |
| 75c_deep_s101 | accepté | 0.2429 → 0.2400 | 10 → 0 | -44.6 % | 1.0080 → 0.2749 | 297 → 2 | -57.4 % |

Interprétation : à faire par Claude (ETAT_actions.md, répartition). Ce lanceur ne conclut pas.
