# Chantiers restants — 19 novembre 2026

Seuls les chantiers ouverts figurent ici ; un chantier clos sort de la page (son bilan reste dans `reports/`).
Les identifiants viennent des audits successifs et ne sont pas classés par complexité.

## Ordre du plus simple au plus complexe

La complexité est une estimation qualitative, pas une durée mesurée. Les dépendances indiquées priment
sur l'ordre : un noyau, une validation ou une mesure à la fois. Chaque changement de calcul conserve les
défauts actuels tant qu'une activation différente n'est pas décidée sur mesures.

**Priorité proposée** : **P1** = à traiter en premier (fiabilité, preuve scientifique ou fondation nécessaire) ;
**P2** = amélioration utile après les fondations ; **P3** = exploration ou rendement attendu plus faible.
La priorité est indépendante de la difficulté : un P1 complexe peut attendre son préalable plus simple.
Le profilage précède les modifications de gradients.

**Décisions de 👤 du 15 novembre** : les graphes
restent tels quels ; le modèle de dépôt de référence est celui de
`example/example_strat/JSON-strat-example.json` (31, 32) ; 41 se trie en local (liste fusionner/fermer pour 👤,
rien sur GitHub).
Le chantier 31 se traite dans une session dédiée.
**Bloqué** : la date des essais humains (33).

**Remaniement du 17 novembre au soir** ([audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md)) : chaque chantier commence par un premier pas d'une session, mesurable, et porte un critère d'arrêt qui l'archive
si la mesure est défavorable. 31 et 32 se décident sur les chiffres du [bilan 49](../reports/chantier49_2026-11-18/bilan.md) (Bonne Mère, graine STRAT 42) ;
05, 21 et 41 sont indépendants.

| Ordre | Priorité | Complexité | Chantier | Premier pas (une session) | Fin, ou arrêt | Source |
|---:|---|---|---|---|---|---|
| 31 | P2 | Très forte | Co-conception B : varier épaisseurs et plan ensemble | Décision de 👤 : le [bilan 49](../reports/chantier49_2026-11-18/bilan.md) trouve une erreur d'épaisseur presque toute aléatoire, le biais par couche pèse 6,9 % (nominal) et 2,6 % (robuste) de l'erreur quadratique. `native_evaluator` fige les épaisseurs nominales : chaque pas d'épaisseur reconstruit l'évaluateur, et le gain se juge contre les cibles du problème de 49. Réglage inactif par défaut (C1). | Archivé si 49 ne montre pas de marge ; sinon gain confirmé sur trois graines, sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Moyenne | Co-conception C : critère de contrôlabilité dans DESIGN | Décision de 👤 : le [bilan 49](../reports/chantier49_2026-11-18/bilan.md) ne donne que deux plans, trop peu pour corréler marges et dynamiques au SEEL. | Archivé si la corrélation est faible ; sinon un critère proposé à 👤. | A §1.4 |
| 05 | P3 | Moyenne | Ajustement Sellmeier de SUBSTRATE (D6) | Option `sellmeier_ir_pole` (pôle infrarouge de catalogue), inactive par défaut ([bilan](../reports/chantier05_2026-11-18/bilan.md)) : sur les substrats du catalogue, l'écart suit le bruit (2,8e-6 au lieu de 2,5e-4 à 3,6e-3), +0,1 à +3,5 s. Pas : 👤 décide de l'activer et de l'exposer dans SUBSTRATE ; mesurer sur un indice mesuré ; puis le Jacobien analytique de la variante standard (88 % du temps, arrêtée sur son budget). La variante A seule ne converge pas. | Jacobien gardé s'il réduit la durée ; les deux changent des indices ajustés. | A §4 |
| 41 | P3 | Faible (👤) | PR Dependabot | Cinq PR ouvertes sur GitHub (#10 à #14), toutes des actions CI : `codeql-action` (autobuild, init, analyze), `upload-artifact`, `setup-uv`. | Fin : 👤 les fusionne ou les ferme (rien sur GitHub par une IA, décision du 15). | G §2.8 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5) | Deux options éteintes : `spline_mono_analytic_gradient` (gradient analytique, vérifié contre les différences finies) et `spline_polish_fd_prefix_maxfun` (différences finies d'abord). Ensemble, préfixe 3 000 : RMSE meilleur que le défaut sur les deux exemples, en moins d'évaluations (TOTAL 0,05128 contre 0,05284, TSIO2 0,00195 contre 0,00283 ; [bilan](../reports/chantier21_2026-11-19/bilan.md)). Pas : chronométrer sur une machine libre, puis 👤 décide de l'allumage. Nœuds libres et Smart Init non couverts. | Dérivées vérifiées aux cas limites, replis compris ; gardé s'il réduit la durée. | A §4 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite ; protocole `U13_protocole.md`. | Bloqué : date, personnes et matériel. | U13 |

## Sources conservées

- **A** : [audit du 13 novembre : co-conception, refactoring, vitesse et dérivées](../reports/audits_2026-11-13/bilan.md).
- **Q** : [questions DESIGN du 13 novembre et mesures du 14](../reports/questions_design_2026-11-13/bilan.md).
- **U13** : [protocole des essais humains](../reports/refactor_corridors_2026-11-11/U13_protocole.md).
- **G** : [audit général du 14 novembre](../reports/audit_general_2026-11-14/bilan.md).

Le 26 est gelé tant que les écarts et plantages du cache Numba restent ouverts.
