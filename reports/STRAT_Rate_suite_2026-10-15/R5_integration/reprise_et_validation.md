# R5 — intégration inactive, validation généraleGO

R3_h03 est terminée et confirmée sur trois groupes réellement nouveaux : gain moyen5,2130% contre
sa recherche propre,3/3victoires, minimum4,0078%. Le meilleur local9900008 reste devant3/3. Trois
pairesR3 consommées, prototypeR4 et ses confirmations clos ; aucun de ces calculs ne doit être relancé.

## Changement intégré à vérifier

Deux paramètres indépendants et inactifs par défaut sont déclarés dans le registre existant :
`elite_rate_joint_candidates=0` et `rate_post_refinement=False`. Le premier ajoute le flux de
fenêtres/λ fines du prototype, avec le constructeur natif existant et un plafond480. Le second
raffine la sortie globale de la seule recherche courante : deux parents de consensus complet,
deux passes au plus, faisceau2,300propositions/passe et600au total. `allow_rate=0` désactive les deux.
La combinaison à mesurer pour reproduireh03 reste480conjoints/240Rate/six tours, sans autre changement.

Les mouvements purs sont portés dans certus/core/certus_strat_rate_moves.py, l’orchestration pure dans
certus/core/certus_strat_rate_post.py et l’adaptation du worker dans certus/workers/certus_strat_workers_rate.py.
Le worker utilise son SharedIndicesWorkerfloat32 existant, la notation complète existante et un nouvel
argument `refine=False` de run_final_simulation_block pour supprimer la génération dans une notation
de plans fixés. Aucun patch temporaire des fonctions scientifiques n’entre dans cette voie de production.
Aucun noyau, bruit, objectif ou formule physique modifié depuis le correctifRMSE validé.

Les trois ancres historiques servent à la vérification de campagne, jamais de parents ni d’ancres
injectées dans le logiciel livré. La voie intégrée note≤9propositions par groupe ; tous ont accès au
consensus configuré. Le coût de ces ancres de contrôle n’est donc pas présenté comme une accélération
de code. Les résultats incomplets sont conservés mais, sur la voie active seulement, restent après
les consensus complets. La voie inactive garde le classement historique. Le payload final et la sonde
conservent le journal des parents, plans, groupes, rejets et compteurs du raffinement.

## Preuves déjà exécutées

- Avant modification : oracle1143passed19,90s. Première invocation bloquée avant les tests par un
  refus de préférences temporaires du bac à sable Windows ; journal conservé, relance avec accès normal.
- Tests ciblés finaux :78passed6,73s, incluant les deux routes, quota/arrêt/incumbent, héritage,
  absence de parents injectés, registre des défauts, export du journal et cliquet d’architecture.
- Les plafonds existants restent1500lignes pour consensus,300pour ELITE et1748pour le worker ; aucun
  registre de dette relevé. Premiers diagnostics de dépassement conservés dans architecture_01/02.log.
- Mypy des trois nouveaux modules :GO. Annotations de collections corrigées, tentatives01/02 conservées.
- Équivalence sans nouvelle simulation :123contextes natifs et78546candidats, route inactive strictement
  identique en candidats/ordre/curseur, route active identique au prototype mesuré, parents non mutés.
  Régression active rouge sur l’ancienne source (argumentjoint absent), verte après intégration.
- Replay algorithmique des seules issues physiques enregistrées :37groupes305propositions et gagnant
  complet reproduits, score exactement0,029431526325033333. Cela ne remplace pas la mesure native intégrée.
  La source exécutée avec deux diagnostics de style de harnais est archivée dans equivalence_source_01.py.txt ;
  seules l’ordre des imports et la forme du contrôle d’exception sont ensuite corrigés. Rapport01 immuable.

## Validation générale et reprise

scratch/run_rate_R5_validation.py est un nouveau contrôleur séquentiel fini : Ruff, Mypy ciblé,
oracle, unité, UI, reste, trois contrôles documentaires, C1froid et gitdiff--check. Chaque commande
vérifie la limite16octobre06:00UTC et les sources figées ; arrêt au premier échec. Les sources exécutées,
commandes, sorties et temps sont conservés dans full_validation_01. Le parent/son enfant réel et
validation.json font foi ; ne pas doubler les tests, ni modifier les sources validées pendant son travail.

AprèsGO : créer une nouvelle provenance et un nouveau contexte de mesure géré R5, en conservant
rate-rmse-r0 et les worktrees historiques figés. Ne pas réécrire les anciens protocoles/SHA. Préparer
une copie de lanceur bornée pour la validation native intégrée, sans monkeypatch scientifique :
réglagesh03, post actif, graine101, même profondeur. Vérifier les points fixes et le raccordement réel
jusqu’aux consensus ; comparer les plans complets et paramètres au prototype. R6 est ensuite
conditionnel,≤6paires selon le guide, sans nouveau lancement après16octobre06:00UTC.

État de cette note : code écrit et vérifié de façon ciblée ; validation générale et mesure native
intégrée encore à exécuter. Aucun défaut scientifique activé, commit, push ou publication.


Validation généraleGO à22h29Paris :5450unité,1324UI,359reste,1143oracle et C1froid8008identiques. Nouveau contexte et revue : measurement_launch_review.md ; les états vivants font foi pour les deux nouveaux slots.
