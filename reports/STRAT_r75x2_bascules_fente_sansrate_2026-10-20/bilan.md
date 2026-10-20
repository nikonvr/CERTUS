# r75x2 : plus de couches en optique, fente, STRAT sans Rate (2026-10-20)

Point de départ : le gagnant ELITE de r75x2, graine de banc 77, fente 2 nm, 55 couches en Rate
(`reports/STRAT_r75_budget_et_affinage_2026-10-20/`). Même évaluateur natif et mêmes règles d'appariement.

## 1. Basculer des couches Rate en optique

On fait un balayage avec une graine de recherche de 300 tirages : chaque couche Rate passe seule en optique, avec λ de
450 à 750 nm par pas de 5 nm (3 355 évaluations). **42 des 55** couches Rate ont une bascule qui baisse le score sans
arrêt. Ensuite viennent la sélection appariée, la combinaison gloutonne, le gel, puis la confirmation et le holdout
(1 000 tirages × 3 graines chacun). Journal : `journal_bascules.txt`.

| | SEEL STRAT | RMSE² | arrêts |
|---|---|---|---|
| confirmation | 0,5482 → 0,5039 nm | −31,1 % (ET 0,8 %) | 0 → 0 |
| holdout | 0,5438 → **0,4981 nm** (−8,4 %) | −29,7 % (ET 0,8 %) | 1 → 1 |

9 bascules sont gardées (couches 18, 21, 27, 30, 32, 33, 37, 41, 49), ce qui laisse 46 couches en Rate. Seules 9 des
25 bascules sélectionnées seules survivent à la combinaison : leurs gains ne s'additionnent pas. C'est le meilleur SEEL
mesuré sur r75x2, au-dessus de l'affinage des λ seul (−2 à −4 %). Les bascules partent du gagnant brut : je n'ai pas
mesuré si elles se cumulent avec l'affinage des λ.

## 2. Fermer la fente

Le modèle multiplie le bruit photométrique par 2 à 1 nm et par 5 à 0,5 nm
(`certus_strat_robustness_noise.py::RESOLUTION_NOISE_FACTOR`). Trois graines de 1 000 tirages par plan.
Journal : `journal_fente.txt`.

| fente | gagnant : P95 max, taux d'arrêt (pire niveau) | avec bascules |
|---|---|---|
| 2 nm | 0,072–0,075, 0 | 0,062–0,064, 0 |
| 1 nm | arrêts 67–68 % | arrêts 67–68 % |
| 0,5 nm | arrêts 100 % | arrêts 100 % |

Dans le modèle, fermer la fente est perdant. Le verdict tient entièrement à cette loi de bruit, qui est une estimation
sur quatre points : il s'inverse si la machine réelle perd moins de signal.

## 3. STRAT avec le Rate interdit

Surcharges `allow_rate=false,elite_rate_moves=false,rate_rescue=false`, banc deep, graine 77. Artefact :
`blocs_vs_plantage_r75x2_deep_s077_sansrate.json` (3 Mo, local, non commité) ; journal : `journal_banc_sansrate.txt`.

- **444 stratégies sur 444 éliminées** par les arrêts. La couche critique est la 55 dans 51 % des cas, avec la cause
  « niveau d'arrêt hors d'atteinte ».
- Sur la meilleure stratégie, le taux d'arrêt vaut 100 % au bruit 0,025, 100 % à 0,05 et **77 % à 0,10**. Les arrêts
  diminuent quand le bruit augmente : c'est la signature du défaut de comptage des points tournants à bruit faible,
  pas une limite physique.
- Conclusion provisoire : on n'a pas de plan tout-optique déposable **avec l'hystérésis actuelle**. Le banc qui
  l'éprouve, avec `tp_hysteresis_floor=0.000415`, est en file.

## Ce qu'on en tire pour STRAT

- Sur un design épais, le choix Rate / optique est le premier levier, avant le choix des λ. STRAT met trop de couches
  en Rate. Un étage de bascules progressives, appariées et inactives par défaut, est le candidat à l'intégration.
- Non mesuré : les graines de banc 101 et 202, le cumul avec l'affinage des λ, la dérive de la source (A6).
