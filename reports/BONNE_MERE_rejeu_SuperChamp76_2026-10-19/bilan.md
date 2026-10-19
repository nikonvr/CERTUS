# Bonne Mère — rejeu indépendant du plan SuperChamp76 (2026-10-19)

Demande de 👤 : rejouer une cohorte fraîche du plan `SuperChamp76_StrictOT50_HybridMicroWin` (une graine neuve,
1 000 tirages au bruit 0,05) avec le moteur STRAT de CERTUS et comparer aux chiffres annoncés le 2026-10-18 au soir
(`studies/bonne_mere/dossier_final/donnees/resultats_superchamp76.json`, non suivi par Git). Mesures du 2026-10-19,
07 h 35 – 07 h 50, Windows 11, Python 3.14, tête `fce2da34`, arbre `certus/` propre pendant chaque exécution.

## Protocole

- **Banc** : `rejeu_plan.py.txt`, copie ligne à ligne du chemin de notation de la campagne du matin
  (`reports/strat70_lambda4_2026-10-18/attempt_01/replay_code.py`, conservée dans
  `studies/bonne_mere/archives/Bonne_Mere_sources_et_metadonnees.zip`) : croissance native des 98 couches du témoin
  par `certus_strat_robustness_task._test_strategy_robustness_task`, RMSE cible sur 601 points des 96 couches de la pièce
  (face arrière, saphir), SEEL de la pièce calibré, corridor d'indice ±0,005 tiré identiquement en croissance et en
  notation, fente 2 nm, bruits 0,025 / 0,05 / 0,10.
- **Seule différence** : `certus` est l'arbre courant, non la copie figée `code_certus` prise à `7f3edea8` ; depuis,
  `certus/physics` ne diffère que par `cache=False` sur trois répartiteurs (C18).
- Entrées restaurées de l'archive avec contrôle SHA-256 (`design/retenu_96_saphir/design.json` de SHA `c48a60c1…`,
  paramètres effectifs, calibration SEEL, cible historique, matériaux) ; `example/database_index/indices.xlsx`
  inchangé depuis le matin. Plans : `strategie_retenue_superchamp76.json` (id 760050) et `strategie_retenue_452nm.json`
  (id 700131, identique au plan du cas 131 du matin).
- Numba : 4 threads actifs pendant chaque exécution (fixés par `task_numba_threads()`), couche `omp`. Première
  exécution à cache vierge, les suivantes relisent ce cache.

## 1. Le banc reproduit le matin (plan 452 nm, graine 20261012101, cas 131)

| bruit | moyenne matin | moyenne rejeu | P95 matin | P95 rejeu | max \|Δ\| par tirage (RMSE / SEEL) |
|---|---|---|---|---|---|
| 0,025 | 1,6481675079442761 | 1,6481675079442644 | 1,851668635121008 | 1,8516686351212046 | 4,96·10⁻¹³ / 5,72·10⁻¹³ |
| 0,05 | 1,6673614600520228 | 1,6673614600520157 | 1,8791300834024076 | 1,8791300834023381 | 5,17·10⁻¹³ / 6,23·10⁻¹³ |
| 0,10 | 1,7544837670877842 | 1,7544837670877786 | 2,01467185087455 | 2,014671850874384 | 6,15·10⁻¹³ / 7,52·10⁻¹³ |

Mêmes graines d'indice (`8575525203186874`, `…4037381`, `…4887888`), mêmes 1 000 tirages aboutis à chaque bruit,
oracle TMM indépendant à 4,88·10⁻¹⁵ comme le matin. **Pas au bit** : les derniers chiffres de chaque tirage diffèrent
(comparaison aux tirages conservés dans `preuves_appariees_452nm_3graines.npz`).

## 2. Les chiffres annoncés de SuperChamp76 se reproduisent exactement (graine 20261018301)

| bruit | aboutis | moyenne (pp) | P95 (pp) | SEEL P95 (nm) |
|---|---|---|---|---|
| 0,025 | 1 000 / 1 000 | 1,5167070179739812 | 1,5822023670586323 | 0,4363302835089113 |
| 0,05 | 1 000 / 1 000 | 1,5305655262398719 | 1,5983409991466422 | 0,46326406751505705 |
| 0,10 | 1 000 / 1 000 | 1,5870326290584607 | 1,6760639475598265 | 0,5876775950801222 |

Identiques à tous les chiffres aux valeurs annoncées pour cette graine : l'évaluation du soir est une vraie mesure,
faite avec ce protocole et le moteur courant.

## 3. Graine neuve 20261019401 (absente de tout fichier de l'étude)

| bruit | SuperChamp76 moyenne / P95 / SEEL P95 | arrêts | 9 graines annoncées : moyennes min – max (écart-type) | écart en écarts-types | gain apparié sur le 452 nm (pp, ± erreur type) | SuperChamp76 meilleur |
|---|---|---|---|---|---|---|
| 0,025 | 1,518337 / 1,585036 / 0,438872 | 0 | 1,516137 – 1,520026 (0,001341) | +0,21 | 0,129336 ± 0,002641 | 1 000 / 1 000 |
| 0,05 | 1,532729 / 1,602556 / 0,472388 | 0 | 1,530051 – 1,533178 (0,000945) | +1,35 | 0,137679 ± 0,002720 | 997 / 1 000 |
| 0,10 | 1,586168 / 1,678931 / 0,590776 | 0 | 1,585312 – 1,590321 (0,001529) | −1,18 | 0,165037 ± 0,003894 | 974 / 1 000 |

Erreur type d'une moyenne sur 1 000 tirages : 0,0011 pp au bruit 0,05. Au bruit 0,05, le SEEL P95 (0,472 nm) dépasse
de 0,0004 nm le maximum des neuf graines annoncées (0,455881 – 0,471982 nm, +1,95 écart-type) et le P95 du RMSE
(1,602556) est dans leur plage (1,593638 – 1,602704). Plan 452 nm sur les mêmes tirages : 1,670408 / 1,893390 / 0,860519,
0 arrêt. Gains appariés sur les graines de confirmation (452 nm du matin contre SuperChamp76 du soir, bruit 0,05) :
0,135653, 0,136087 et 0,137553 pp.

## 4. La référence 452 nm du holdout 1 citée le soir ne se reproduit pas

Plan 452 nm rejoué sur les graines 20261012201 – 203 (3 000 tirages par bruit) :

| bruit | aboutis | moyenne | P95 | SEEL P95 |
|---|---|---|---|---|
| 0,025 | 3 000 / 3 000 | 1,650169 | 1,855245 | 0,815823 |
| 0,05 | 3 000 / 3 000 | 1,669063 | 1,868813 | 0,831854 |
| 0,10 | 3 000 / 3 000 | 1,751648 | 2,006217 | 0,980493 |

`ideeargon.md` §1.1 (ligne `Retenu_452nm_cloture`, cohorte annoncée `HOLDOUT_12201_203`) donne 1,682468 / 1,797530 /
0,630519 et des arrêts 0 / 0 / 1 : aucun de ces chiffres ne sort du protocole. Le gain de SuperChamp76 sur le holdout 1
vaut donc **0,138143 pp** en moyenne (annoncé : 0,151548), 0,273728 pp en P95 et 0,372843 nm en SEEL P95. La ligne
`Ref70_historique` du même tableau porte la moyenne de la **confirmation** (1,6915151483719795), pas celle du holdout
(1,6934065662546085), et un SEEL P95 de 0,6712 nm contre 0,90 nm mesuré le matin.

## Ce que ce rejeu ne dit pas

- Les chiffres sous dérive de vitesse Rate (1,568220 pp à 1 %) : le protocole du matin ne modélise pas la dérive
  (`rate_drift_modelled: false`), je n'ai pas mesuré.
- Comment le plan a été obtenu : aucun script de l'optimisation du soir n'est dans le dépôt ; seule son évaluation est
  reproduite. Les lignes de `ideeargon.md` §1.1 sans fichier de plan n'ont pas été rejouées.
- L'identité au bit des lois 2 et 3 (`window_laws_comparison_holdout_12201_203`) : pas de plan pour ces variantes.
- Aucune validation expérimentale ni optimum global.

## Rejouer

Restaurer dans un dossier STUDY, par `studies/bonne_mere/dossier_final/outils/restaurer_archive.py --destination STUDY
--prefix P`, les préfixes `scripts/model.py`, `scripts/local_comparisons.py`, `scripts/historical_target.py`,
`scripts/qwot_search.py`, `scripts/robustness.py`, `target/target_historique.csv`, `target/target.csv`,
`materials/H800-Nb2O5.csv`, `materials/H800-SiO2.csv`, `materials/substrate_SiO2.csv`, `design/retenu_96_saphir/`,
`reports/strat_precoat2_compare_2026-10-17/effective_params.json`,
`reports/strat_two_witnesses_2026-10-17/component_seel_calibration.json` et
`reports/strat_single_witness_optical_blocks_2026-10-17/attempt_02/trial_0519/summary.json`.

Copier ensuite hors du dépôt `rejeu_plan.py.txt` et `compare_runs.py.txt` en retirant l'extension `.txt`. Le banc se
lance avec les options d'interpréteur `-X utf8 -X cpu_count=16`, sans `-I` (NumPy est dans le site utilisateur), et
prend `--repo` (racine CERTUS), `--study STUDY`, `--plan` (un JSON de stratégie), `--seed`, `--runs 1000`, `--out`
(dossier neuf) et `--cache` (dossier Numba vide pour une exécution à froid). La comparaison prend le dossier de sortie,
et `--proofs preuves_appariees_452nm_3graines.npz --case 131` pour les tirages conservés du matin ou
`--announced resultats_superchamp76.json --seed 20261018301` pour les valeurs annoncées. Environ 75 s à cache vierge,
15 s ensuite. Sorties brutes par tirage : `runs/*/component_scores.npz`.
