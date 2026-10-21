# STRAT aux réglages par défaut du 2026-10-21 : l'étage de recherche locale sur les trois 75 couches

Code `7a9514b4` : `strat_local_search` actif, recherche et contrôle à ±0,010 d'indice, repli sur un plan intermédiaire
quand le contrôle refuse le plan final ; `tp_hysteresis_floor` = 0,000415. Banc `scripts/probe_blocs_vs_plantage.py <design> deep 0 0 2 0
<graine>` (surcharge `strat_local_search=true`, défaut, étiquette `defauts1021`). Puis jugement du plan classé premier contre le meilleur
plan ELITE du même banc, à ±0,005 et ±0,010, sur graines neuves (3 × 1 000 tirages, `judge_bench.py.txt`, journaux dans `journaux/`).

## Holdout sur graines neuves

| design, graine | étage | ±0,005 : SEEL ELITE → final | arrêts | ΔRMSE² | ±0,010 : SEEL ELITE → final | arrêts | ΔRMSE² |
|---|---|---|---|---|---|---|---|
| 75c, 77 | accepté | 0,2448 → **0,2275** nm | 10 → 0 | −43,1 % | 1,0164 → **0,2680** nm | 391 → 1 | −53,1 % |
| r75x0.5, 101 | repli (25 changements sur 30) | 0,3953 → **0,3635** nm | 0 → 0 | −43,7 % | 0,4452 → **0,3731** nm | 0 → 0 | −61,3 % |
| r75x0.5, 77 | repli (29 sur 32) | 0,4360 → **0,3703** nm | 0 → 0 | −54,8 % | 0,5058 → **0,4105** nm | 0 → 0 | −57,4 % |
| r75x2, 77 | accepté | 0,5411 → **0,4699** nm | 0 → 0 | −43,0 % | 0,7159 → **0,5883** nm | 265 → 9 | −51,2 % |

Erreur type du ΔRMSE² : 0,8 à 1,6 %. Couches Rate du plan final contre ELITE : 12/9, 53/65, 47/56, 37/55.

## Ce que cela établit

- **Quatre cas sur quatre** : aux réglages par défaut, STRAT sort un plan meilleur que son gagnant ELITE, à l'incertitude d'indice nominale
  (SEEL −7 à −15 %) comme au double (−18 à −74 %), sans arrêt ajouté à ±0,005 et avec presque tous les arrêts supprimés à ±0,010.
- **Le repli rattrape le cas refusé de la nuit** (r75x0.5, graine 101 : A5 de Codex, étage refusé pour 19 arrêts) : le plan après 25
  changements passe contrôle et confirmation, SEEL 0,3953 → 0,3635 nm.
- Chercher à ±0,010 coûte peu à ±0,005 : r75x0.5 graine 77 donne 0,3703 nm contre 0,3561 hier avec une recherche à ±0,005.
- Non mesuré : les autres designs du panel (A14), d'autres graines (A10), la dérive de la source (retirée par 👤).
