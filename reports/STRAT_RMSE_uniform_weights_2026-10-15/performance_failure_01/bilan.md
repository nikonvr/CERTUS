# Échec de performance — diagnostic et correctif du harnais, 15 octobre2026

La première validation termine le groupe restant avec358 tests réussis et un échec : `TestParallelPerformance::test_concurrent_calculationations`, ratio2,323725647 contre plafond1,82. Les suites oracle1143, unité5433 etUI1324 passent. Le [rapport initial](../full_validation_01/validation.json) reste inchangé etFAILED ; aucun R0/R2 n’était engagé lors de cet échec. L’état actuel après correction figure à la fin de ce rapport.

## Contre-épreuves et portée

Quatre interpréteurs neufs, quatre cachesNumba distincts, une expérience à la fois, affinité24/0xffffff/Normal. Le test, le harnais et le moduleTMM ont les mêmes octets dans les worktrees d’origine/courant. Leur comparaison àGitHEAD doit tenir compte deCRLF/LF : l’AST et le contenu après normalisation sont identiques, contrairement aux hachages bruts Git/checkout. [Preuve](source_identity_02.json).

| Sources | PlafondNumba | Masque principal pendant le contrôle | Masques observés dans le pool | Résultat |
|---|---:|---:|---|---|
| old23 | 23 | 1 | [23] | échec, ratio2.262084 |
| current23 | 23 | 1 | [23] | échec, ratio2.176705 |
| old1 | 1 | 1 | [1] | échec, ratio1.946256 |
| current1 | 1 | 1 | [1] | passe, ratio non exporté |

[Résultats et limites](diagnosis_and_fix.json), [logs/provenance des quatre cas](diagnostic_01/diagnostic.json).

L’échec existe aussi dans les sources d’origine. Ces mesures ne prouvent pas une régression due au correctifRMSE. Elles montrent une incohérence réelle : le benchmark définit une référence à un threadNumba ; son contexte dans le principal laisse les nouveaux workers à23. L’ancien cas à plafond1 échoue encore une fois : la correction du contrat de threads n’explique donc pas à elle seule toute la dispersion temporelle. Aucun gain de vitesse du code physique n’est déduit.

## Correction et vérifications

Le seul changement du test est l’importNumba local et `initializer=numba.set_num_threads, initargs=(1,)` pour le pool. Les quatre workers, les dix calculs, l’objectif et le seuil1,82 restent identiques. Aucun fichier physique, formule ou paramètre scientifique n’est modifié par cette correction de test.

[Contrat de threads avant/après](harness_fix_02/contract.json) : la même méthode de test est exécutée avec un calcul factice et un coût factice, puis les masques réels de chaque appel sont contrôlés. Le contrat échoue avant, passe après ; les dictionnairesBASELINE sont égaux. Ce contrôle **ne mesure aucun temps ni gain physique**.

La vraie suite de performance est ensuite exécutée avec Python/Numba à caches neufs : **18 passed en20,93s**, sans changer les seuils. [Journal](../full_validation_02/performance_after.log). La continuation [full_validation_02](../full_validation_02/validation.json) relance le groupe restant complet, puis Ruff/documentation/C1 ; elle conserve les résultats des suites inchangées avec leur provenance plutôt que de les présenter comme de nouveaux passages. Les anciens huit fichiers suivis par la première validation sont toujours aux mêmesSHA ; seul le test de performance est ajouté aux entrées surveillées.

Préparation du vérificateur : une version est refusée parRuff pour captures de boucle non liées ; la copie est conservée. Une première exécution échoue avant calcul faute de racine danssys.path ; [échec conservé](harness_fix_01/verification_failed.json). L’ajout de la racine et des captures liées permet le contrôle vert ci-dessus. Aucune de ces tentatives ne touche un résultat scientifique ni une réservationR0/R2.

La continuation est **terminéeGO le15 octobre à9 h06 Paris** :359 tests restants réussis, Ruff/documentation verts, **C1froid8008 tableaux identiques au bit**. Les gardes R0/R2 lisentfull_validation_02 ; la première tentativeFAILED reste une preuve historique, jamais réécrite. Les cinq sources scientifiques sont copiées dans un contexte séparé avec leur provenance exacte ; R0 et observateur sont vérifiésGO, R2 engagé à9 h25. [État actuel et preuves de transition](../../STRAT_Rate_suite_2026-10-15/bilan_R0_R2_transition_20261015.md).
