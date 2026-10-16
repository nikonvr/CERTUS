# Reprise Rate — validation terminée, R0 vérifié, R2 engagé — 15 octobre2026

## Action à la reprise

**Ce rapport décrit la transition datéeR0→R2. R2 est depuis terminé et audité ; h01 est terminé sans gain.**
Lire le [bilan h01](R3_h01_widths/bilan_R3_h01_20261015.md), la [reprise h02](R3_h02_wavelengths/reprise_et_protocole.md),
puis `R3_h02_wavelengths/pair_controller.json` et les processus ; l’état vivant figure dans [ETAT§0](../../docs/ETAT.md).

Lire `R2_native_base/etat.json`, les processus et les verrous. La base native unique est engagée depuis **9 h25 Paris**, PID32588 au lancement, tag `r2_rmse24_20261015_v1`. Ne pas la doubler, lancer des tests ni toucher ses sources pendant qu’elle vit. Les réservationsR0/R2 sont déjà consommées ; un échec de contrôleur se répare après audit, jamais par une répétition silencieuse. A2 reste terminée24/24.

## Validation et contexte

[Validation incrémentaleGO](../STRAT_RMSE_uniform_weights_2026-10-15/full_validation_02/validation.json), terminée à9 h06 :359 tests restants réussis,18 tests de performance ciblés, Ruff/documentation verts et **C1froid8008 tableaux identiques au bit**. Les suites inchangées déjà passées (oracle1143, unité5433/UI1324) sont reprises explicitement avec leurs provenances ; elles ne sont pas présentées comme de nouveaux passages. L’échec précédent est conservé. [Diagnostic du benchmark et correction du contrat des workers](../STRAT_RMSE_uniform_weights_2026-10-15/performance_failure_01/bilan.md), sans changer ses seuils ni la physique.

[Descripteur du contexte réel](reference_context.json) : worktree géré `C:\Users\Lemarchand\.codex\worktrees\rate-rmse-r0\certus0310`, HEADda1af082, cinq sources exactes validées, preflight avant/aprèsGO. [Sources et diff](context_snapshot/copy_verification.json). Les24 autres différences d’octets sont uniquementCRLF/LF, texte normalisé etAST identiques ; aucun fichier figé supplémentaire n’est modifié. Cette différence ouvre une clé réelle de cache2250a2bfa0bd, distincte de583fdb3c906c dans l’arbre de validation. [Empreintes complètes des paquets](context_snapshot/package_identity.json). Les contextes historiques restent inchangés.

## R0 — trois points fixes reproduits

[R0 auditéGO](R0_verified.json), [résultat complet et paramètres](R0_control/control.json). Douze appels effectivement observés : trois plans × graines101/41/42/43, chacun300tirages. Consensus complet de trois scores par plan ; `n_samples=3` n’est pas une profondeur de trois tirages. Tous les plans conservent blocs, masquesRate, fente et témoins.

| Plan | Score de base101 | Score consensus41/42/43 | Score consensus attendu |
|---|---:|---:|---:|
| 9900006 — fenêtre interne688 | 0.027573191157578242 | 0.029057302267737437 | 0.029057302267738155 |
| 9900008 — préfixe613 après fenêtre | 0.03053006875746744 | 0.027975237667200847 | 0.027975237667200829 |
| 900951015 — référence | 0.039901993285953202 | 0.039345655797984144 | 0.039345655797984144 |

Tolérances de contrôle inchangées :rel1e-7/abs1e-10. Ce résultat valide la reprise des références ; il ne constitue pas un nouveau gain Rate. La durée de162,75s du premier rejeu dans ce contexte de cache ne se compare pas comme un gain ou une régression de code aux anciens replays chauds.

**Observation utile, causalité encore à établir :** la base101 préfère9900006 à9900008, tandis que le consensus inverse ce classement. Cela justifie de tracer la sélection avant/après consensus. Ce n’est pas une preuve que ce mécanisme explique l’absence du bon plan dans le natif ; sa génération et sa grille doivent aussi être examinées.

## Observation passive R2

[VérificationGO](observer_verification/verification.json), aux empreintes exactes du lanceur, observateur, générateur, helper et garde. Scénarios de factory réelle avec/sans observation, ordre/IDs/curseur et parents inchangés ; arguments/résultats délégués, NumPy copié et restauration après exception vérifiés. Aucun dépôt n’est simulé par cette vérification.

[État R2](R2_native_base/etat.json), [commande réelle](R2_native_base/launch.json). Recette : `r75x0.5 deep 0 0 2 0 101 0`, conjoint480, Rate240, six tours, équilibragefalse, préfixe0. Les journaux sont `R2_native_base/stdout.log` et `stderr.log`, les cinq scripts exacts sont copiés dans ce dossier. Le contrôleur exporte la trace complète en fin de calcul ; ne pas déduire un pourcentage d’avancement du seul silence de stdout.

Affinité effective0xffffff (24 processeurs autorisés), prioritéNormal, plafonds de bibliothèque23. La bannière32threads décrit le poste et n’est pas une preuve d’utilisation de32cœurs : l’affinité du PID est contrôlée. Pour les futurs lanceurs, déclarer aussi la limiteCPU dès le démarrage de Python et figer la même configuration entre contrôle/variante ; ne pas modifier ce calcul vivant. Le nombre effectif de workers est distinct de ces plafonds.

## Audit et choix de la suite après la fin de R2

1. Vérifier fin du processus, verdict, sourceSHA, scriptsSHA et intégrité des copies exportées. Préserver toute sortie partielle/erreur. Un artefact comporte une provenance enregistrée pendant l’exécution ; l’état final du contrôleur fait foi pour la fin effective.
2. Relier génération, contrats, screening, plein, consensus et parents par scope/tour et **plan complet**. Ne pas joindre seulement sur unID provisoire ni sur l’ordre de fin des tâches. Distinguer cache de consensus, appels nouveaux, profondeur physique et nombre de scores.
3. Construire le tableau des géométries utiles : proposée ou absente, λ légale et présente ou non, puis lieu exact d’élimination. Se limiter à ce que les traces observent ; les sorties privées de déduplication/budget ne sont pas toutes tracées.
4. Choisir un seul facteurR3 après ce diagnostic et figer un protocole. Au plus trois paires natives ; mêmes budgets/profondeurs/bruits entre contrôle et variante. Aucun plan local gagnant codé en dur comme recherche native.
5. Figer les gagnants et les groupes réellement frais avant inspection.202–3535 déjà utilisés ne sont pas frais ; auditer les prochaines réservations. Une variante sans gain de recherche homogène ne reçoit pas une longue confirmation.
6. Continuer les limites du [guide](../../docs/STRAT_Rate_suite_chantier.md) :R4au plus deux passes/faisceau4/1200propositions ;R5intégration/validation ;R6au plus six paires conditionnelles. R7 attend les mesures quantitatives machine. Aucun nouveau défaut activé, aucun commit/push/publication.

La référence historique reste0,3967147882nm et le meilleur plan local0,3345159946nm, confirmé contre la référence sur neuf groupes historiques. Le gain de découverte native automatique reste à démontrer. Les ETA précédents sont des estimations conditionnelles ; l’incident du harnais a décalé le premier créneau. Le temps de R2 à24cœurs permettra la prochaine estimation utile.
