# CERTUS_DESIGN — Plan de travail des prochaines actions

## Objectif

Poursuivre la modernisation de `certus_design` sans casser les chemins historiques, en consolidant les améliorations déjà réalisées sur les phases 2 et 3, puis en préparant les étapes suivantes de manière progressive et testée.

---

## État actuel

### Hypothèse de travail

On repart de zéro pour le prochain cycle d’exécution. Considère que rien n’est acquis tant qu’il n’a pas été revalidé dans cette session.

### Zones à traiter en priorité

- `certus/workers/certus_design_workers.py`
- `certus/workers/certus_design_engine.py`
- `certus/utils/certus_design_services.py`
- les contrats legacy appelés par l’IHM PyQt
- les chemins obliques et les calculs analytiques

---

## Plan détaillé CERTUS vers top 1% partout

### Objectif global
Transformer la base actuelle, déjà très forte, en une plateforme :
- plus homogène
- plus lisible
- plus DRY
- plus maintenable
- plus cohérente en UX
- plus simple à faire évoluer sans casse
Le but n’est pas de “refactorer pour refactorer”, mais de réduire la complexité réelle tout en conservant la robustesse.

---

### 1) Stabiliser et figer les contrats fondamentaux
**But** : S’assurer que les objets et flux de base ont un contrat unique, explicite, et stable.
**Cibles** : RunContext, RunManifest, services headless, DTO de requests/responses, payloads de trace, statuts.
- **1.1 Standardiser les payloads de trace** : Créer une convention unique (run_id, created_at, initiated_by, metadata).
- **1.2 Réduire les dicts implicites** : Remplacer progressivement les payloads libres par des DTO typés et dataclasses.
- **1.3 Normaliser les statuts** : Faire converger statuts UI, service, validation, finaux.
- **1.4 Consolider les tests de contrat** : Garantir la compatibilité descendante et l'absence de mutation accidentelle.

---

### 2) Unifier l’UX globale
**But** : Faire en sorte que l’utilisateur ressente une expérience cohérente partout.
**Cibles** : progress widgets, dialogs de fin/annulation, empty states, toasts, onboarding, overlays.
- **2.1 Créer une grammaire UX CERTUS** : Définir des conventions globales (titres, progression, erreurs).
- **2.2 Harmoniser la progression** : Vocabulaire, structure d’état, format de temps, comportements de fin.
- **2.3 Harmoniser empty/error states** : Mise en page standard, hiérarchie visuelle, ton standard.
- **2.4 Uniformiser la hiérarchie visuelle** : Polices, espacements, contrastes, boutons primaires/secondaires.
- **2.5 Tester la cohérence UX** : Créer des tests orientés UX pour valider labels et transitions.

---

### 3) Appliquer du DRY intelligent
**But** : Réduire les répétitions qui augmentent la dette de maintenance, sans nuire à la lisibilité.
**Cibles prioritaires** : formatage de statuts/durées, zoom, handling des états worker, patterns de boutons.
- **3.1 Extraire les helpers transverses** : Durée formatée, statut formaté, clamp de valeurs UI.
- **3.2 Éviter les helpers trop génériques** : Garder un helper par responsabilité ("pas de mega utils").
- **3.3 Réduire les duplications dans les widgets** : Extraire le noyau commun (start, update, stop, reset, cancel).
- **3.4 Réduire les répétitions dans les services** : Partager la normalisation des requests et la génération de manifest.

---

### 4) Découper les modules historiquement trop denses
**But** : Réduire la complexité cognitive et rendre le code plus facile à maintenir.
**Cibles à haute valeur** : gros mixins UI, gros workers, gros orchestrateurs.
- **4.1 Identifier les zones coûteuses** : Prioriser les modules combinant UI, état, worker orchestration, export.
- **4.2 Découper par responsabilité** : Séparer l'état du rendu, l'événement des règles métier.
- **4.3 Refactorer par petites étapes** : Extraire une fonction ou un sous-module en gardant la suite verte.
- **4.4 Garder le contrat public stable** : Ne pas changer les APIs externes si non nécessaire.

---

### 5) Renforcer les patterns workers/services
**But** : Avoir une orchestration plus uniforme et plus simple à faire évoluer.
**Cibles** : workers d’optimisation, de RE, de STRAT, de FIELD, services d’orchestration.
- **5.1 Standardiser le cycle de vie** : Contrat unifié (init, start, cancel, stop, finish, error).
- **5.2 Normaliser les logs de progression** : Journal cohérent (début, jalons, fin, annulation).
- **5.3 Séparer calcul et orchestration** : L'orchestrateur valide et déclenche, le worker calcule.
- **5.4 Réduire les couplages UI/workers** : L'UI ignore les détails de calcul, les workers ignorent l'UI.

---

### 6) Nettoyer les grandes surfaces UI restantes
**But** : Amener toutes les familles UI à un niveau homogène de qualité.
**Cibles** : STRAT, RE, INDEX, dialogs métier, panels avancés.
- **6.1 Standardiser les layouts** : Uniformiser marges, espacements, alignements.
- **6.2 Standardiser les états de feedback** : idle, loading, running, paused, cancelled, done, error.
- **6.3 Harmoniser les composants récurrents** : cartes, badges, toasts, tooltips.
- **6.4 Uniformiser les wording patterns** : Libellés courts, clairs, cohérents et orientés action.

---

### 7) Mettre un garde-fou qualité “top 1%”
**But** : Empêcher toute régression pendant les améliorations.
- **7.1 Maintenir la suite complète verte** : Chaque refactor suivi de tests ciblés puis suite complète.
- **7.2 Ajouter des tests de non-régression** : Priorité sur traces, manifests, progress, export.
- **7.3 Ajouter des tests de cohérence UX** : Vérifier labels, états visibles, transitions.
- **7.4 Ajouter des tests de stabilité structurelle** : Pas de changement de contrat sans test.

---

### 8) Priorisation concrète des prochains chantiers
- **P0 immédiat** : Continuer à garder la suite complète verte. Ne pas casser les contrats de trace/progress. Consolider les helpers partagés déjà introduits.
- **P1 fort ROI** : Harmoniser les grands patterns UX. Extraire les répétitions restantes sur status/duration/trace. Uniformiser les workers lifecycle.
- **P2 architectural** : Décomposer les modules les plus denses. Séparer orchestration et rendering. Réduire les gros mixins.
- **P3 polish final** : Repasser l’UX complète pour rendre le tout irréprochable.

---

### 9) Ordre d’exécution recommandé
Afin de maximiser le ROI sans régression :
1. Contrats
2. UX unifiée
3. DRY intelligent
4. Workers/services
5. Décomposition des gros modules
6. Polish final
7. Tests de cohérence

---

### 10) Définition du “but final” atteint
CERTUS sera “top 1% partout” quand on aura simultanément :
- une suite de tests très large et stable
- des contrats de données explicites et cohérents
- une UX unifiée dans toutes les applications
- peu de duplication inutile
- des modules plus petits et bien séparés
- une architecture plus lisible
- zéro régression pendant les améliorations

## Point d’avancement actuel

### Micro-actions déjà réalisées

- **UX-1** : amélioration du widget de progression `EnhancedProgressWidget`
  - ajout d’un affichage ETA basé sur un budget de temps
  - message de fin plus lisible et plus premium
  - état initial du bouton cancel rendu plus propre
- **DTO-1** : ajout d’un champ `run_id` au contrat headless partagé
  - meilleure traçabilité des workflows
  - préparation du chaînage vers les logs et rapports
- **Tests** : ajout d’un test ciblé sur le DTO headless
  - validation du champ `run_id`
  - validation de l’héritage du contrat par `IndexFitRequestModel`
- **DTO-2** : Propagation du `run_id` de bout en bout
  - Assignation d'un `run_id` unique par workflow d'optimisation
  - Transmission dans les config de tous les Workers (Optim, Needle, Color)
  - Injection dans la requête IndexFitRequest et apparition dans le rapport Excel
- **UX-2** : Feedback visuel dynamique des sous-phases d'optimisation
  - Remplacement de l'étiquette "PGLOBAL" en dur par un nom dynamique selon le mode (HEALING, NEEDLE POLISH, DECIMATION, etc.)
- **Architecture-1** : Découplage de l'orchestration du Healing
  - Extraction de `_handle_healing_workflow` hors de `certus_design_ui_optimization.py` (Mixin UI) pour le déplacer dans `certus_design_orchestrator.py`
  - L'orchestrateur pilote désormais les appels asynchrones (QTimer) de la boucle de guérison, et non plus la vue.
- **Architecture-2** : Découplage du routage de la décimation intelligente
  - Extraction de `_handle_decimation_polish_completion` et `_handle_smart_decimation_followup` hors de l'IHM vers `DesignOrchestrator`
- **UX-3** : Gestion guidée des erreurs d'optimisation
  - Remplacement de l'erreur générique silencieuse par une `QMessageBox` avec explication et appel à l'action.
- **Architecture-3** : Fiabilisation des contrats (NeedleWorker & ColorWorker)
  - Extraction directe du payload structuré `NeedleWorkerRequest.params` et `ColorWorkerRequest.params` (DesignParamsDTO) dans le calcul `run()` au lieu d'utiliser un dictionnaire brut `self.cfg`.
- **UX-4** : Centralisation des tokens UI (Début)
  - Création de `CertusTheme.get_hint_text_style()` et remplacement des f-strings de styles locaux éparpillés dans `certus_index_spline_rendering.py`, `certus_metal_common.py`, `certus_design_ui_layout.py` et `certus_index_spline_corridors.py`.
- **Amélioration Test** :
  - Ajout d'un test unitaire spécifique (`test_certus_design_orchestrator_ux.py`) pour pérenniser le comportement d'erreur guidée (`QMessageBox.warning`) instauré lors de l'étape UX-3.
- **Architecture-4** : Centralisation de l'état asynchrone (Healing & Overshoot)
  - Déplacement des flags (`_healing_phase`, `_overshoot_active`, `_overshoot_done`, `_original_target_count`) des mixins UI (`certus_design_ui_core.py`, etc.) vers le `DesignOrchestrator` centralisé.


- **Architecture-5** : Découplage Final de l'état asynchrone
  - Déplacement de `_target_layer_count` et `_is_in_needle_cycle()` vers le `DesignOrchestrator` avec succès.
  - L'Orchestrateur pilote maintenant de façon autonome la totalité des flags d'état (1625 tests passés).
- **UX-5** : Découplage UX (Centralisation boutons)
  - Remplacement des styles de boutons "en dur" par `CertusTheme.get_button_style` dans `certus_field_state_mixin.py` pour unifier l'apparence.
- **DTO-3** : Refactoring Type-Safety
  - Extraction du dictionnaire brut en vrai DTO (`StratParamsDTO` / `WorkerThreadRequest`) sans reconversion dans le `WorkerThread` de STRAT. Les DTO remplacent définitivement les dictionnaires bruts pour les requêtes workers.
- **UX-6** : Élimination des CSS inline parasites (Top Premium)
  - Suppression des surcharges locales agressives (`font-size`, `background-color`) sur les boutons critiques (`log_btn`, `pareto_btn`) dans `certus_design_ui_layout.py`.
  - Fix de la fonction manquante `_format_progress_duration` qui faisait crasher les imports de tests.


- Le plan n’est pas seulement théorique : il commence à produire des améliorations visibles et des contrats plus solides.
- La direction retenue est bonne pour viser une UX plus rassurante et une architecture plus maîtrisée.
- La prochaine étape doit rester de petite taille et à fort impact.

---

## Tableau explicite — fait / à faire

| Domaine | Fait | À faire | Priorité | Impact attendu |
|---|---|---|---|---|
| Contrats de données | `run_id` ajouté au DTO headless et testé | Brancher `run_id` dans les points d’appel réels et la traçabilité | Très haute | Traçabilité de bout en bout, meilleure observabilité |
| Tests contrats | Test ciblé ajouté pour `run_id` | Étendre les tests aux services/workers qui consomment ce champ | Haute | Réduction des régressions silencieuses |
| UX progression | ETA ajoutée dans `EnhancedProgressWidget`, message de fin amélioré, cancel plus propre | Harmoniser les autres composants de progression/feedback | Haute | Expérience plus premium et rassurante |
| Architecture orchestration | Début de découplage UI/orchestration, flags asynchrones centralisés | Continuer à extraire les responsabilités restantes des gros workers | Très haute | Code plus lisible, moins couplé, plus maintenable |
| UX cohérence | Début de centralisation de tokens UI et styles | Étendre l’unification des boutons, toasts, loaders, tableaux et erreurs | Haute | Cohérence visuelle forte, sensation produit premium |
| Observabilité | Logs et manifests renforcés dans la direction du `run_id` | Exposer davantage les phases, sous-étapes et résumés lisibles | Très haute | Compréhension claire des workflows |
| Robustesse | Compatibilité legacy préservée sur les premières micro-actions | Vérifier et consolider la non-régression sur chaque nouveau pas | Très haute | Stabilité durable du système |
| Documentation | Plan de travail enrichi et checklist IA ajoutée | Compléter avec les points sensibles au fur et à mesure des avancées | Moyenne | Reprise de travail plus fiable par une autre IA |

### Lecture du tableau

- **Fait** = ce qui est déjà présent et vérifié dans le plan de travail.
- **À faire** = la prochaine action concrète à mener.
- **Priorité** = l’ordre recommandé d’exécution.
- **Impact attendu** = le bénéfice principal recherché.

---

## TODO explicite pour l’autre IA

### Règle générale

L’autre IA doit exécuter **une seule étape à la fois**, dans l’ordre ci-dessous, sans improviser une autre tâche avant validation complète.

### Liste d’actions step by step

#### Étape 1 — Lire et comprendre le contexte
- Lire ce fichier en entier.
- Identifier la micro-action la plus rentable.
- Ne pas modifier de code avant d’avoir localisé la cible.

#### Étape 2 — Choisir une seule micro-action
- Choisir soit un contrat de données, soit un point UX visible.
- Ne jamais mélanger deux objectifs différents dans la même modification.
- Noter explicitement le fichier cible et l’objectif.

#### Étape 3 — Modifier un seul bloc logique
- Modifier un seul fichier ou un seul bloc cohérent.
- Garder le comportement existant autant que possible.
- Si la modification touche un contrat, conserver la compatibilité legacy.

#### Étape 4 — Relire immédiatement la modification
- Vérifier le résultat juste après l’édition.
- Confirmer que la modification correspond au but prévu.
- S’assurer qu’aucune autre partie sensible n’a été cassée.

#### Étape 5 — Ajouter ou adapter un test ciblé
- Ajouter un test qui couvre précisément la micro-action.
- Si le comportement change, le test doit refléter le nouveau contrat.
- Le test doit être simple, isolé et lisible.

#### Étape 6 — Lancer les tests anti-régression
- Lancer immédiatement le test ciblé après la modification.
- Si nécessaire, compléter avec une suite plus large.
- Ne pas passer à autre chose tant que le résultat n’est pas connu.

#### Étape 7 — Vérifier la compatibilité des chemins existants
- Vérifier que les chemins legacy restent utilisables.
- Vérifier que les appels publics n’ont pas été cassés.
- Si le contrat est modifié, confirmer la rétrocompatibilité.

#### Étape 8 — Mettre à jour la documentation si nécessaire
- Ajouter une note si la modification introduit un nouveau contrat ou un nouveau comportement.
- Clarifier les points sensibles si un nouveau risque apparaît.
- Garder la documentation courte, précise et actionnable.

#### Étape 9 — Écrire un bilan d’étape
- Résumer ce qui a été fait.
- Indiquer le fichier modifié.
- Indiquer les tests lancés.
- Indiquer le résultat.
- Indiquer le prochain pas exact.

#### Étape 10 — Passer seulement ensuite à la micro-action suivante
- Ne jamais enchaîner plusieurs modifications sans validation.
- Reprendre au point 2 avec une nouvelle micro-action.

### Exemple de séquence attendue

1. Cibler un contrat de données critique.
2. Le modifier de façon minimale.
3. Relire la modification.
4. Ajouter un test ciblé.
5. Lancer le test.
6. Vérifier la compatibilité legacy.
7. Noter le résultat.
8. Passer à la micro-action suivante.

### Ce que l’autre IA ne doit pas faire

- Ne pas mélanger UX, architecture et tests dans une seule étape.
- Ne pas modifier plusieurs fichiers d’un coup.
- Ne pas sauter la relecture.
- Ne pas sauter les tests.
- Ne pas considérer une action terminée sans preuve.

### Prochaine micro-action recommandée

1. **Architecture-6 (cf. point 5.3 du plan Top 1%)** : Extraire la logique de déclenchement asynchrone (`QTimer.singleShot` dispersés dans `certus_design_ui_optimization.py`) pour la confier exclusivement au `DesignOrchestrator` afin de consolider l'isolation UI/calcul.
2. **DTO-4 (cf. point 1.1 du plan Top 1%)** : Standardiser un `run_id` ou un payload de trace commun pour le journal de progression.
3. Toujours accompagner la modification d'une validation locale (test complet anti-régression).

---

## Plan d’exécution recommandé

### Règle de départ

Aucune étape ne doit être considérée comme acquise sans revalidation explicite dans la session en cours.

### Ordre obligatoire

1. Vérifier les contrats publics.
2. Vérifier les points d’entrée sensibles.
3. Déplacer ou corriger les données critiques.
4. Ajouter ou corriger un test dédié.
5. Reprendre seulement ensuite la zone suivante.

### Séquence de travail imposée

1. Contrat de données.
2. Test ciblé.
3. Vérification du point d’appel réel.
4. Mise à jour de la documentation.
5. Passage à la micro-action suivante.

---

## TODO LIST EXPLICITE POUR L’AUTRE IA

### À faire dans cet ordre strict

- [ ] Lire intégralement ce fichier avant toute modification.
- [ ] Choisir une seule micro-action à la fois.
- [ ] Prioriser un contrat de données ou un point UX visible.
- [ ] Modifier un seul fichier ou un seul bloc logique.
- [ ] Relire immédiatement la modification.
- [ ] Ajouter ou mettre à jour un test ciblé.
- [ ] Lancer le test correspondant immédiatement.
- [ ] Vérifier qu’aucune compatibilité legacy n’est cassée.
- [ ] Mettre à jour la documentation de sécurité si nécessaire.
- [ ] Écrire un résumé final de l’action réalisée.
- [ ] Ne pas passer à une autre zone avant validation complète.
- [ ] Si un test échoue, diagnostiquer avant de continuer.
- [ ] Si une action touche l’UX, vérifier le feedback visuel réel.
- [ ] Si une action touche un DTO, vérifier les champs et valeurs par défaut.
- [ ] Si une action touche un worker, vérifier le contrat et le logging.

### Règle de fin de session

Avant de terminer, l’autre IA doit écrire explicitement :

- les fichiers modifiés,
- la micro-action réalisée,
- les tests lancés,
- les résultats obtenus,
- les risques restants,
- la prochaine micro-action recommandée.

---

## Règles de prudence à respecter

- Ne jamais modifier un calcul scientifique sans test ciblé.
- Ne jamais supprimer un chemin legacy tant qu’il peut encore être consommé.
- Ne pas mélanger extraction structurelle et changement fonctionnel dans la même étape.
- Vérifier le lint et les tests après chaque micro-modification.
- Favoriser les petites migrations réversibles.
- Lancer les tests anti-régression dès qu’une modification est appliquée.
- Ne pas considérer une action comme terminée tant que son check n’a pas été écrit explicitement.
- Ne jamais sauter la phase de vérification même si la modification semble mineure.
- Quand une nouvelle IA prend le relais, elle doit repartir du document comme d’une page blanche.

---

## Mode d’emploi obligatoire pour toute IA qui applique ce document

Cette section rend le plan exécutable par une IA basique, sans interprétation libre.

### Règles non négociables

1. **Lire tout le document avant d’agir**
   - L’IA doit lire l’intégralité du document avant toute modification.
   - Elle ne doit pas commencer par écrire du code ou modifier un fichier.
   - Elle doit d’abord identifier la section à traiter.

2. **Faire une seule micro-action à la fois**
   - Une micro-action = une modification unique, petite et vérifiable.
   - Exemple : modifier une seule fonction, ajouter un seul test, enrichir une seule section de documentation.
   - Interdit : regrouper plusieurs changements de nature différente dans la même étape.

3. **Vérifier immédiatement chaque action**
   - Après chaque micro-action, l’IA doit vérifier que le résultat correspond exactement au but prévu.
   - Elle doit relire le fichier concerné juste après la modification.
   - Elle doit s’assurer qu’aucune autre partie sensible n’a été cassée.

4. **Lancer les tests anti-régression ASAP**
   - Dès qu’une action touche un comportement, une signature, un payload, un calcul, un worker ou une UI critique, l’IA doit lancer les tests anti-régression immédiatement après la modification.
   - Si plusieurs suites de tests existent, lancer d’abord la plus ciblée, puis la suite plus large.
   - Ne jamais repousser les tests à la fin si le changement peut impacter le comportement.

5. **Ne jamais déclarer une action terminée sans preuve**
   - Une action n’est considérée comme terminée que si :
     - la modification a été faite,
     - la modification a été relue,
     - les tests associés ont été lancés,
     - et le résultat des tests est connu.

6. **Documenter chaque action faite**
   - Après chaque étape, l’IA doit écrire un compte-rendu court et précis.
   - Ce compte-rendu doit mentionner :
     - la modification réalisée,
     - la raison,
     - la vérification effectuée,
     - les tests lancés,
     - et le résultat obtenu.

7. **Si un test échoue, diagnostiquer avant de continuer**
   - L’IA ne doit pas enchaîner une autre modification sans comprendre l’échec.
   - Elle doit identifier la cause probable, corriger si possible, puis relancer les tests.

### Format attendu pour chaque action

Pour chaque micro-action, l’IA doit suivre cet ordre :

- **Étape 1** : annoncer la micro-action choisie.
- **Étape 2** : réaliser la modification.
- **Étape 3** : relire le résultat modifié.
- **Étape 4** : lancer les tests anti-régression adaptés.
- **Étape 5** : noter clairement le résultat.
- **Étape 6** : seulement ensuite passer à l’action suivante.

### Check-list obligatoire après chaque action

L’IA doit pouvoir répondre explicitement à toutes les questions suivantes :

- La bonne section a-t-elle été ciblée ?
- Une seule micro-action a-t-elle été faite ?
- Le fichier modifié correspond-il au but prévu ?
- Une vérification a-t-elle été faite juste après ?
- Les tests anti-régression ont-ils été lancés ?
- Le résultat des tests est-il connu ?
- Peut-on passer à l’étape suivante sans risque majeur ?

### Ordre recommandé d’exécution pour un agent basique

1. Lire le plan.
2. Identifier la priorité la plus haute.
3. Sélectionner une micro-action.
4. Modifier un seul fichier ou un seul bloc logique.
5. Vérifier la modification.
6. Lancer les tests anti-régression immédiatement.
7. Noter le résultat.
8. Répéter.

### Règle spéciale sur les tests

Les tests anti-régression doivent être lancés :

- immédiatement après toute modification de code métier, de worker, de contrat, de payload, de calcul ou de UI critique,
- avant toute tentative de changer une autre zone,
- même si le changement semble petit,
- même si l’IA pense que la modification est sûre.

### Règle spéciale sur les changements de comportement

Si l’IA modifie un comportement existant, elle doit systématiquement :

- comparer l’ancien et le nouveau comportement,
- vérifier qu’aucun contrat public n’a été brisé,
- confirmer que les chemins legacy restent valides,
- relancer les tests ciblés,
- puis relancer la suite plus large si nécessaire.

### Sortie attendue d’une IA qui suit ce document

À la fin de son travail, l’IA doit être capable de dire clairement :

- quelles actions ont été faites,
- dans quel ordre,
- quels fichiers ont été touchés,
- quels contrôles ont été réalisés,
- quels tests anti-régression ont été lancés,
- quels résultats ont été obtenus,
- et s’il reste des risques ouverts.

---

## Check final obligatoire à la fin de chaque session de travail

Avant de conclure une session, l’IA doit vérifier et écrire explicitement :

- les actions réalisées,
- les fichiers modifiés,
- les tests lancés,
- les tests réussis ou échoués,
- les régressions éventuelles,
- et la prochaine action exacte à entreprendre.

---

## Critère de succès

On considérera la suite comme réussie si :

- les tests restent verts,
- les comportements historiques ne changent pas,
- les doublons critiques sont encore réduits,
- la documentation protège les zones sensibles,
- `certus_design` devient plus simple à maintenir sans perte de fiabilité,
- et chaque étape du plan peut être exécutée par une IA basique sans ambiguïté.
