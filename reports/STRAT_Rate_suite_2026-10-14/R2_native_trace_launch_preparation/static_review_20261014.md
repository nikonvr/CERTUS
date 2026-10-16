# R0/R1/R2 — revue statique du 14 octobre 2026

Revue en lecture seule pendant A2. Aucun vérificateur runtime, test, aperçu de CLI ou dépôt
supplémentaire exécuté. Les lanceurs préparés restent non validés à l'exécution. La santé A2
est conservée dans [le contrôle de 11 h 10 Paris](../../STRAT_A2_continuation_2026-10-14/health_20261014_1100_wake.json).

## Identités et ordre : précautions pour l'analyse R2

`_generate_elite_candidate_strategies` n'incrémente `next_id` qu'après validation du contrat
et ajout dans `out`. Une tentative qui échoue au contrat peut donc porter le même ID provisoire
qu'une tentative différente ensuite acceptée. **Ne jamais attribuer un rejet de contrat à un
candidat accepté par son ID seul.** Joindre contexte, plan complet et ordre des événements ;
conserver les tentatives rejetées séparément des candidats effectivement alloués.

La signature `_plan_signature` employée par cette factory décrit blocs et masque Rate.
La fente et les resets des témoins restent à comparer dans le plan complet : une signature de
dédoublonnage n'est pas, à elle seule, la preuve d'identité du protocole physique.

Les tâches sont soumises à `ThreadPoolExecutor`. L'observateur enregistre leur résultat à la
fin de chaque appel, tandis que la boucle ELITE lit ses futures dans l'ordre de soumission.
**L'ordre des événements de fin de tâche n'est pas l'ordre de classement.** Pour les égalités,
utiliser l'ordre des candidats générés puis celui conservé par l'étape précédente, et vérifier
la liste effectivement appelée à l'étape suivante. Ne pas départager par heure de fin ni par ID
croissant si cela ne reproduit pas cet ordre. La remise en ordre des résultats du pool ordinaire
par index doit aussi être distinguée de l'ordre des fins de tâches.

Une identité acceptée doit être suivie avec son contexte de génération et son plan complet.
Les échecs de contrat peuvent répéter des ID ; les événements de notation d'un même candidat
répètent normalement son ID à plusieurs profondeurs et graines. Aucune de ces répétitions
n'est à confondre avec une collision d'identité entre deux plans acceptés.

## Lire les étapes ELITE sans inventer des rejets

Dans `_apply_elite_refinement_if_enabled`, les budgets sont résolus par
`_resolve_elite_refinement_cfg`, puis deux étapes utilisent `elite_num_runs` et la moitié de
`ctx.num_runs`. Le nombre déclaré `n_screen_runs=50` du rejeu ne prouve pas la profondeur ELITE.
Lire les arguments réels des événements `physical_task_result`/`physical_task_error`, avec leur
bruit, graine et contexte ; conserver les valeurs absentes comme inconnues.

Le seuil nominal est calculé avant `_log_elite_parents`. L'observateur lui laisse donc
`round=null`. Associer ce seuil au prochain événement `parents` **du même scope**, uniquement
si sa paire de seuils existe. Un seuil `None` conduit à une sortie sans nouveau tour : ne pas
l'associer au tour d'un autre scope.

Les portes se lisent dans cet ordre :

1. À chaque étape de halving : RMSE nominal fini et strictement inférieur au seuil cible.
2. Si l'étape possède des survivants : tri nominal, puis moitié conservée avec le minimum
   `elite_max_full_evals`. L'étape pleine prend au plus ce plafond.
3. Si l'étape ne possède aucun survivant : `break` laisse la liste précédente intacte.
   Un rejet au seuil peut donc être suivi d'un appel plein. Distinguer « échoue à une porte »
   de « éliminé du calcul ».
4. À profondeur pleine : porte nominale, puis score fini ; les résultats admis reçoivent
   `elite_round` et `elite_nominal_score` avant classement/consensus/diversités.
5. Le consensus sélectionne une tête de liste ; les parents réellement utilisés au tour
   suivant sont ceux de l'événement `parents`, après le classement et les diversités.

Les erreurs de tâche ont leur événement propre. Un candidat non appelé à l'étape suivante
peut avoir échoué à un seuil, dépassé un quota ou rencontré une exception : établir la cause
avec les résultats et les journaux, pas avec la seule absence d'un ID.

## Matrice des preuves disponibles et manquantes

| Transition | Preuve préparée | Limite à garder visible |
|---|---|---|
| Entrée du voisinage | `generation_inputs` : grille, parents et réglages ; `generation_outputs` : plans et curseur | Le budget conjoint 480 appartient à l'adaptateur et à sa provenance ; il ne remplace pas le plafond legacy |
| Contrat | `contract_rejection` avec plan et raison | ID provisoire ; refus privés de doublon/plafond non exhaustivement observés |
| Screening vers plein | Appels/résultats réels, seuil et listes générées | Reconstituer l'ordre de sélection, respecter le fallback de l'étape vide |
| Plein vers consensus | Score avant mutation, niveaux de bruit, `consensus_selection` et configuration | Un score fini n'implique pas une notation de consensus complète |
| Consensus vers parent | `consensus_applied`, cache, puis liste réelle de `parents` | Un score base exporté peut être le score précédant le dernier passage, déjà issu d'un consensus antérieur |
| Sortie | `elite_exit`, `finalized_results`, artefact natif et sources | Vérifier qu'une erreur d'export n'a pas perdu la trace ; aucune attribution de gain de temps à l'observateur |

Le compteur `retained_draw_count` décrit uniquement les tableaux présents. La profondeur se
vérifie par les tâches appelées ; un cache de consensus doit être relié à ses événements et au
contexte qui l'a rempli. Ne pas annoncer un nouveau tirage lorsqu'il s'agit d'une réutilisation.

## Portée de la revue

R0 : lecture du moteur, des gardes et du protocole des trois plans ; la preuve AST déjà sauvée
porte sur le corps scientifique identique à v11. Elle ne valide ni les points fixes ni l'I/O
atomique à l'exécution. L'ancien moteur et le helper A2 restent inchangés.

R1 : lecture de l'export et du test préparé. `score` reste inchangé, les métadonnées sont copiées,
les absences restent `None`. Le test actuel puis son échec sur la source d'avant R1 restent à
exécuter hors A2, ainsi que la validation complète en attente.

R2 : lecture des wrappers, de leur raccordement et du vérificateur. Les pools observés sont
des pools de threads ; aucun noyau numérique n'est recopié. Délégation, ordre, identités,
immutabilité, sérialisation et restauration après exception restent à éprouver avec le
vérificateur préparé. Son contrôle substitue les tâches et ne constitue pas un dépôt mesuré.

Aucune nouvelle cause scientifique n'est déclarée prouvée. La prochaine action reste de
terminer A2, valider le code hors mesure, réussir R0 puis mesurer une seule trace native R2.
