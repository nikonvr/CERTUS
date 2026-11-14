# Chantiers restants — revue du 14 novembre 2026

Périmètre demandé : suggestions formulées ou actualisées les **12, 13 et 14 novembre 2026**.
Revue des 209 Markdown présents et suivis, des fichiers non suivis (aucun Markdown), des dates et des
changements Git récents. Le seul Markdown ignoré est celui du cache pytest. Les corrections de liens et les
mentions d'archivage dans des rapports anciens ne constituent pas de nouvelles suggestions.

La liste initiale est suivie depuis `b6fb1939`. Les identifiants sont conservés pour la traçabilité du
[contre-audit du 14 novembre](../reports/contre_audit_chantiers_2026-11-14/bilan.md).
Les P1 restants sont 15 et 33.

## Ordre du plus simple au plus complexe

La complexité est une estimation qualitative, pas une durée mesurée. Les dépendances indiquées priment
sur l'ordre : un noyau, une validation ou une mesure à la fois. Chaque changement de calcul conserve les
défauts actuels tant qu'une activation différente n'est pas décidée sur mesures.

**Priorité proposée** : **P1** = à traiter en premier (fiabilité, preuve scientifique ou fondation nécessaire) ;
**P2** = amélioration utile après les fondations ; **P3** = exploration ou rendement attendu plus faible.
La priorité est indépendante de la difficulté : un P1 complexe peut attendre son préalable plus simple.
Traiter 15 (co-conception A).
Les essais humains 33 suivent leur propre calendrier. Le profilage précède les modifications de gradients.
| Ordre | Priorité | Complexité | Chantier restant | État et critère de fin | Source |
|---:|---|---|---|---|---|
| 05 | P3 | Faible à moyenne | Jacobiens Sellmeier manquants (D6) | Mesurer la part des ajustements concernés. Valider un éventuel gradient par différences finies et mesurer le gain à paramètres identiques. | A §4 |
| 07 | P3 | Moyenne | Amorçage Numba (R2) | Le socle possède déjà le gestionnaire. Mutualiser les comportements communs en préservant signaux, erreurs et durée de vie des fils Qt. Vérifier le démarrage à froid des cinq fenêtres. | A §2.2 |
| 08 | P2 | Moyenne | Mutualiser les fenêtres METAL simple/bicouche (R1) | Des groupes de paramètres et traitements de progression restent doublés malgré le socle existant. Préserver les différences physiques. | A §2.2 |
| 11 | P2 | Moyenne | Gradient METAL dans PGLOBAL (D3) | Profiler les deux polissages. L'adaptateur reçoit un scalaire et le gradient monocouche disponible concerne les paramètres à eM fixé. Vérifier la couverture et l'accord coût/gradient avant branchement. | A §4 |
| 12 | P2 | Moyenne | Gradient INDEX infrarouge, étapes 0 et 2 (D2) | Profiler, puis traiter D112, le cas `arg == 0` de `dk5` dans `_njit_ir_global_gradient_fused`. Cas de régression, différences finies et comparaison appariée avant activation. | A §4 |
| 14 | P3 | Moyenne | Diagnostic Fourier du résidu | Piste non mesurée : relier le contenu en chemin optique à la TOT et éprouver son utilité sur des cas connus. | Q §1.3 |
| 15 | P1 | Moyenne, campagne coûteuse | Co-conception A et covariance observée (30a) | Vérifier le transfert des cibles à STRAT. Comparer au moins six designs nominaux et robustes, appariés en N, avec un plan par design et des graines de notation disjointes. Rapporter RMSE contre cibles, arrêts et SEEL, puis comparer la prédiction par covariance aux erreurs observées. | A §1.4–1.5 et Q §4.5 |
| 16 | P3 | Moyenne à forte | Graphes et détachement (R4/R5, ancien 09) | Après arbitrage du périmètre UI, préserver les interactions propres à STRAT, les mises à jour et le retour à la fenêtre source. | A §2.2–2.3 |
| 18 | P3 | Moyenne à forte | Socle de SMOOTHER et SUBSTRATE (R7) | Après arbitrage du périmètre UI, préserver chargement, calcul et export en ajoutant thème et session communs. | A §2.2–2.3 |
| 19 | P2 | Moyenne à forte | Éprouver le sélecteur de tests | Compléter l'audit d'appels et le rejeu historique avec comparaison aux mutations de la suite intégrale. La validation complète reste la référence. | Q §5.3 |
| 20 | P3 | Forte | Raffinement en longueurs d'onde complexes | Le polissage adaptatif à TOT fixée laisse un MF résolu de 0,10983 %. Comparer le raffinement complexe à ce témoin et vérifier sa tenue sur des départs éloignés. | A §3.3–3.4 et Q §10 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5, ancien 13) | Profiler nœuds libres et Smart Init. Vérifier les dérivées des valeurs et positions aux cas limites, y compris les replis. | A §4 |
| 22 | P2 | Forte | Gradient analytique FIELD (D1) | Profiler. Vérifier la dépendance au gradient absorbant D113 avant de le réutiliser. Contrôler par l'oracle et les différences finies, puis comparer sur graines fixées. | A §4 |
| 24 | P2 | Forte | Mérite robuste (anciens 23, 24 et 30b) | Si 15 le justifie, essayer d'abord le nuage avec les Jacobiennes existantes et des tirages appariés. Tester ensuite la descente de sensibilité ou la covariance si les mesures le justifient. Confirmer sur des tirages disjoints et par STRAT. | Q §4.2–4.5 |
| 25 | P3 | Forte | Germes structurés Fourier pour le mémétique | Piste non mesurée : diversité de phases, conversion H/L compatible avec les contraintes, comparaison au tirage actuel sur trois-raies et cissoïde. | Q §1.3 |
| 27 | P3 | Très forte | Reprise de calcul STRAT (U12 B) | Mesurer le coût des étapes du pipeline avant de choisir les points de reprise. Vérifier la compatibilité des réglages, graines, noyaux et ouvriers, ainsi que l'identité au bit. | U12 §4–5 |
| 28 | P3 | Très forte | Reprise de calcul DESIGN (U12 B) | Mesurer séparément le mémétique et PGLOBAL. Pour le mémétique, inclure population, générateur, lot et nombre d'ouvriers dans l'état de reprise. Pour PGLOBAL, vérifier la reconstruction du regroupement. | U12 §4–5 |
| 29 | P3 | Très forte | Reprise des corridors INDEX SPLINE (U12 B) | Mesurer le coût d'un corridor réel avant de spécifier le point de reprise. Exiger un résultat identique au bit à contexte et ouvriers compatibles. | U12 §4–5 |
| 31 | P2 | Très forte | Co-conception B : varier épaisseurs et plan ensemble | La recherche locale STRAT varie actuellement le plan. Ajouter les épaisseurs, réaccorder les voisines et confirmer le gain contre les cibles sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Très forte | Co-conception C : critère de contrôlabilité dans DESIGN | Piste conditionnelle à A : corréler d'abord les marges et dynamiques du signal aux résultats réels de STRAT. | A §1.4 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite. Exécuter les essais humains et consigner les observations selon le protocole ; cette ligne requiert les personnes et le matériel. | U13 |

## Sources conservées

- **A** : [audit du 13 novembre : co-conception, refactoring, vitesse et dérivées](../reports/audits_2026-11-13/bilan.md).
- **Q** : [questions DESIGN du 13 novembre et mesures du 14](../reports/questions_design_2026-11-13/bilan.md).
- **U12** : [spécification de reprise, actualisée le 13 novembre](../reports/refactor_corridors_2026-11-11/U12_specification.md).
- **U13** : [protocole des essais humains](../reports/refactor_corridors_2026-11-11/U13_protocole.md).

Les chantiers 03, 06 et 17 sortent de la liste active pour rendement insuffisant. Le 26 est gelé
tant que les écarts et plantages du cache Numba restent ouverts. Les regroupements conservent les
identifiants 16, 21, 24 et 15.

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
