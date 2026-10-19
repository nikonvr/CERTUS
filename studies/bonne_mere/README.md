# Bonne Mère

96 couches H800 (Nb₂O₅ / SiO₂) sur saphir, un témoin, deux précouches : `dossier_final/donnees/design_retenu_96_saphir.json`, cible `cible_retenue_601points.csv`, plancher nominal 1,459069 pp (design adopté par 👤 : couche 1 du design de 100 couches supprimée, plafond 1,47 pp).

## Meilleur plan mesuré (2026-10-19)

`dossier_final/donnees/strategie_optimale.json`, table `monitoring_optimal_98operations.csv` : 21 couches pièce en Rate (toutes OT ≤ 50 nm), les autres en Optique, op 1 à 3 à 455 nm. Au bruit 0,05, graines neuves : SEEL P95 0,446 nm, RMSE 1,528 pp, 0 arrêt sur 3 000 ; dérive de la source non modélisée (valeur attendue de 👤, A6).

| plan | SEEL P95 (nm) | RMSE (pp) | rapport |
|---|---|---|---|
| 452 nm (clôture du 18 au matin) | 0,832 | 1,669 | `reports/BONNE_MERE_rejeu_SuperChamp76_2026-10-19/` |
| SuperChamp76 (18 au soir) | 0,461 | 1,531 | idem |
| optimal | 0,446 | 1,528 | `reports/BONNE_MERE_phase2_tete_et_cumul_2026-10-19/` |

## Comment on arrive à l'optimum

1. **Mesurer avant de chercher** : le budget d'erreur (`reports/BONNE_MERE_phase1_budget_SuperChamp76_2026-10-19/`) montre où est la marge. Ici l'erreur d'indice porte 61 % du SEEL², le Rate 1 %, le bruit optique 10 %.
2. **Le grand gain (452 → SC76, −45 % de SEEL P95)** accompagne le changement de partition (plus de couche Rate épaisse : 354 nm → 31 nm au plus) et des λ réoptimisés par fenêtres ; la part de chacun n'est pas mesurée, les étapes du soir n'étant pas rejouables (scripts absents).
3. **Puis un affinage local, couche par couche, jugé sur le SEEL apparié** : λ d'une couche, bascule Optique / Rate d'une couche, tête. Trois leviers, −4,8 % de SEEL² ; l'optimum local est alors atteint (neuf couches sur dix déjà au mieux).
4. **Discipline** : graines réservées par usage (recherche, sélection, confirmation, holdout ouvert une fois), comparaison tirage à tirage, zéro arrêt aux trois bruits.

Prochaine marge : réduire la sensibilité à l'erreur d'indice (plusieurs couches à la fois) ou mieux connaître l'indice. Défaut du modèle d'arrêt : l'hystérésis suit le bruit, donc à bruit faible la fente fabrique des points tournants (op 88 échoue) ; à corriger dans STRAT.

## Rejouer

Banc `scan.py.txt` dans `reports/BONNE_MERE_phase2_balayage_lambda_2026-10-19/` ; ses entrées se restaurent de `archives/Bonne_Mere_sources_et_metadonnees.zip` (hors Git) par `dossier_final/outils/restaurer_archive.py` (liste dans `reports/BONNE_MERE_rejeu_SuperChamp76_2026-10-19/bilan.md`).
