# Chantiers restants — revue du 14 novembre 2026

Périmètre demandé : suggestions formulées ou actualisées les **12, 13 et 14 novembre 2026**.
Revue des 209 Markdown présents et suivis, des fichiers non suivis (aucun Markdown), des dates et des
changements Git récents. Le seul Markdown ignoré est celui du cache pytest. Les corrections de liens et les
mentions d'archivage dans des rapports anciens ne constituent pas de nouvelles suggestions.

État vérifié sur `de52e01c`, complété par la correction documentaire Gauss–Newton du 14 novembre.
La liste ci-dessous est la **seule liste active de cette revue**. Une piste reste une expérience à instruire :
son inscription ne prouve ni son gain ni la nécessité de l'intégrer.

## Ordre du plus simple au plus complexe

La complexité est une estimation qualitative, pas une durée mesurée. Les dépendances indiquées priment
sur l'ordre : un noyau, une validation ou une mesure à la fois. Chaque changement de calcul conserve les
défauts actuels tant qu'une activation différente n'est pas décidée sur mesures.

**Priorité proposée** : **P1** = à traiter en premier (fiabilité, preuve scientifique ou fondation nécessaire) ;
**P2** = amélioration utile après les fondations ; **P3** = exploration ou rendement attendu plus faible.
La priorité est indépendante de la difficulté : un P1 complexe peut attendre son préalable plus simple.
Pour les P1, commencer par 10 (contexte DESIGN), 19 (preuve du sélecteur), 04 (RICL à TOT fixée), puis
11 et 12 (gradients existants). Préparer 15 (co-conception A), 27–29 (reprise de calcul) et 33 (essais humains)
en respectant leurs dépendances et les disponibilités requises.
| Ordre | Priorité | Complexité | Chantier restant | État et critère de fin | Source |
|---:|---|---|---|---|---|
| 01 | P2 | Faible | Expliquer les quatre coûts de 120 s des tests d'actions UX | À mesurer : séparer coût de fixture et coût propre, puis corriger le registre sans affaiblir les tests. | Q §5.1 |
| 02 | P3 | Faible | Mutualiser la conversion épaisseur → QWOT de RE et du socle (R9) | Deux méthodes restent distinctes. Une conversion commune, même résultat et colonnes correctes. | A §2.2 |
| 03 | P3 | Faible | Petit utilitaire de styles Excel/HTML (R8) | Piste de faible rendement ; partager les styles utiles si une duplication est démontrée. Les contenus d'export diffèrent. | A §2.2 |
| 04 | P1 | Faible à moyenne | RICL : comparer le raffinement à TOT fixée | La mesure actuelle laisse la TOT libre. Refaire à contrainte identique, juger sur grille résolue et par l'oracle, consigner l'admissibilité. | Q §10 |
| 05 | P2 | Faible à moyenne | Jacobiens Sellmeier manquants (D6) | Plusieurs ajustements restent en différences finies. Brancher les dérivées avec contrôle numérique et mesure du gain. | A §4 |
| 06 | P3 | Faible à moyenne | Instruire les deux choix Nelder–Mead d'INDEX optique (D7) | Piste : déterminer s'ils apportent de la robustesse avant de proposer un remplacement. | A §4 |
| 07 | P2 | Moyenne | Service commun d'amorçage Numba (R2) | Cinq fenêtres ont encore leur méthode. Un service avec mêmes signaux, erreurs et comportement au démarrage. | A §2.2 |
| 08 | P2 | Moyenne | Mutualiser les fenêtres METAL simple/bicouche (R1) | Des groupes de paramètres et traitements de progression restent doublés malgré le socle existant. Préserver les différences physiques. | A §2.2 |
| 09 | P2 | Moyenne | Mutualiser le détachement des graphes (R5) | Quatre définitions subsistent. Préserver courbes, mises à jour, outils et retour à la fenêtre source. | A §2.2 |
| 10 | P1 | Moyenne | Contexte de coût unique pour DESIGN (R3) | Nettoyage, repolissage, jugement et tolérances préparent encore leurs données séparément. Mêmes cibles, indices, poids et géométrie partout ; oracle avant/après. Préalable aux nouveaux mérites robustes. | A §2.2 ; Q §4.6 |
| 11 | P1 | Moyenne | Brancher le gradient METAL dans l'adaptateur PGLOBAL (D3) | Deux L-BFGS-B de `pglobal_adapter` restent sans Jacobien. Contrôle par différences finies et comparaison appariée du coût. | A §4 |
| 12 | P1 | Moyenne | Brancher le gradient INDEX infrarouge, étapes 0 et 2 (D2) | Le gradient existe ; ces deux appels ne l'utilisent pas. Vérifier d'abord le cas limite C13 signalé par cet audit. | A §4 |
| 13 | P3 | Moyenne | Étendre les cas analytiques du repli SPLINE (D5) | Piste : couvrir les cas refusés par `spline_pwl_analytic_grad_supported`, avec contrôle des limites de validité. | A §4 |
| 14 | P3 | Moyenne | Diagnostic Fourier du résidu | Piste non mesurée : relier le contenu en chemin optique à la TOT et éprouver son utilité sur des cas connus. | Q §1.3 |
| 15 | P1 | Moyenne, campagne coûteuse | Co-conception A : classer plusieurs designs par leur dépôt | Les briques existent, la campagne K designs/K plans manque. Juger contre les cibles sur graines indépendantes, rapporter RMSE, arrêts et SEEL. | A §1.4–1.5 |
| 16 | P2 | Moyenne à forte | Classe commune des graphes ordinaires et STRAT (R4) | Deux `CertusScientificPlot` subsistent. Mutualiser sans perdre les interactions propres ; articuler avec R5. | A §2.2 |
| 17 | P2 | Moyenne à forte | Polisseur local partagé (R6) | L'hybride DESIGN est intégré ; les nombreux autres sites ne sont pas consolidés. Préserver bornes, tolérances, annulation et garde « jamais pire ». | A §2.2 |
| 18 | P2 | Moyenne à forte | Migrer SMOOTHER et SUBSTRATE sur le socle (R7) | Les deux fenêtres héritent encore directement de `QMainWindow`. Préserver chargement, calcul et export en ajoutant thème et session communs. | A §2.2 |
| 19 | P1 | Moyenne à forte | Compléter la preuve du sélecteur de tests | `verify_changed.py` et l'audit d'appels existent ; le rejeu historique et la comparaison mutation/suite entière ne sont pas documentés. Zéro régression échappée sur le corpus retenu. | Q §5.3 |
| 20 | P2 | Forte | Comprendre les refus de raffinement en longueurs d'onde complexes | Les départs éloignés du tri-bande sont refusés. Expliquer le domaine de validité avant toute extension ; les grilles résolues sont déjà disponibles. | A §3.3–3.4 |
| 21 | P2 | Forte | Dérivées analytiques des nœuds libres et Smart Init SPLINE (D4) | Les valeurs et surtout les positions de nœuds restent à traiter ; vérifier les changements de base et les cas limites. | A §4 |
| 22 | P2 | Forte | Gradient analytique FIELD (D1) | Synthèse et nettoyage restent sans gradient. Réutiliser la physique existante, valider contre l'oracle et les différences finies, puis mesurer. | A §4 |
| 23 | P2 | Forte | Descente robuste DESIGN, niveau 1 | La sélection robuste est livrée ; la descente minimise encore le mérite nominal. Implémenter et valider le gradient du critère de sensibilité, après R3. | Q §4.2 |
| 24 | P2 | Forte | Optimisation robuste par nuage, niveau 2 | Résidus/Jacobiens empilés sur perturbations déterministes et antithétiques, continuation en sigma, puis validation sur tirages neufs. Pas encore implémenté. | Q §4.3 |
| 25 | P3 | Forte | Germes structurés Fourier pour le mémétique | Piste non mesurée : diversité de phases, conversion H/L compatible avec les contraintes, comparaison au tirage actuel sur trois-raies et cissoïde. | Q §1.3 |
| 26 | P3 | Forte | Invalidation du cache Numba par dépendances de noyaux | Piste à instruire ; l'invalidation reste globale. Prouver qu'aucun code machine périmé ne survit avant de mesurer le gain. | Q §5.4 |
| 27 | P1 | Très forte | Reprise de calcul STRAT robustesse (U12 B) | Non commencée. Journal par tirage, graines identiques, rejet des versions incompatibles, reprise tronquée sûre et union identique au bit à une exécution continue. | U12 §4–5 |
| 28 | P1 | Très forte | Reprise de calcul DESIGN PGLOBAL (U12 B) | Non commencée. Sauver les départs terminés et reconstruire le regroupement sur leur union ; mêmes contrôles d'identité et de compatibilité. | U12 §4–5 |
| 29 | P1 | Très forte | Reprise des corridors INDEX SPLINE (U12 B) | Non commencée. Journal par point RMSE(d), puis preuve interruption/reprise identique au bit et rejet d'un contexte incompatible. | U12 §4–5 |
| 30 | P3 | Très forte | Covariance des erreurs STRAT dans DESIGN | Piste non mesurée : remplacer les erreurs indépendantes par une covariance issue du dépôt, puis réaccorder le plan. Dépend du contexte commun et des expériences de co-conception. | Q §4.5 |
| 31 | P2 | Très forte | Co-conception B : varier épaisseurs et plan ensemble | La recherche locale STRAT varie actuellement le plan. Ajouter les épaisseurs, réaccorder les voisines et confirmer le gain contre les cibles sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Très forte | Co-conception C : critère de contrôlabilité dans DESIGN | Piste conditionnelle à A : corréler d'abord les marges et dynamiques du signal aux résultats réels de STRAT. | A §1.4 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite. Exécuter les essais humains et consigner les observations selon le protocole ; cette ligne requiert les personnes et le matériel. | U13 |

## Sources conservées

- **A** : [audit du 13 novembre : co-conception, refactoring, vitesse et dérivées](../reports/audits_2026-11-13/bilan.md).
- **Q** : [questions DESIGN du 13 novembre et mesures du 14](../reports/questions_design_2026-11-13/bilan.md).
- **U12** : [spécification de reprise, actualisée le 13 novembre](../reports/refactor_corridors_2026-11-11/U12_specification.md).
- **U13** : [protocole des essais humains](../reports/refactor_corridors_2026-11-11/U13_protocole.md).

Les fichiers des candidats R1/R2/R4/R5/R7/R9 et D1–D7 n'ont pas changé depuis le commit de l'audit
`09c3f7a7`. Leurs points d'entrée ont été recoupés dans le code actuel. R3 et R6 sont qualifiés séparément,
car DESIGN a évolué depuis cet audit. La recherche locale STRAT expose toujours des candidats de plan,
et la robustesse mémétique ajoute sa pénalité au classement après un polissage nominal.

## Éléments sortis de la liste car réalisés

U1–U11, refactoring des corridors, reprise des sessions U12 A, reprise STRAT multi-graines, partie machine
d'U13, tours supplémentaires STRAT, aperçu INDEX TLU, rangement des journaux, contrôle des liens,
polisseur hybride, poids des bandes disjointes, estimateur N/TOT, grille automatique et sélection robuste
sont intégrés. Les mesures appariées et l'oracle sont dans les sources ci-dessus.

L'imprécision de la docstring de `second_order_robust_rmse` est corrigée : il s'agit de l'approximation
Gauss–Newton, qui omet le terme diagonal de courbure du résidu. Cette correction ne change aucun calcul.
