# Plan de refactor CERTUS par fichier

## Objectif
Définir un ordre d’exécution concret pour réduire la dette technique fichier par fichier, avec **zéro régression fonctionnelle, scientifique ou UX**.

---

## Principes de sécurité

1. **Aucune régression de calcul** : les résultats scientifiques doivent rester identiques à tolérance numérique égale.
2. **Aucune régression d’UX** : les écrans, flux et raccourcis ne doivent pas se dégrader.
3. **Aucune régression de contrat** : les signatures publiques, formats JSON, exports et workflows doivent rester compatibles.
4. **Une seule zone à la fois** : ne jamais refactoriser simultanément plusieurs couches couplées.
5. **Tests avant et après** : chaque étape doit être verrouillée par des tests de non-régression.
6. **Rollback possible** : toute étape doit rester revertible proprement.

---

## Ordre recommandé

### Phase 0 — Verrouillage du socle

#### 1. `certus_core.py`
**But :** stabiliser le noyau partagé avant tout refactor profond.

**Actions :**
- figer les helpers publics,
- vérifier les contrats d’initialisation,
- extraire les dépendances implicites,
- ajouter des tests de bootstrap.

**Pourquoi maintenant :** tout le reste dépend de la stabilité du socle.

**Contrôle zéro régression :**
- exécuter les tests unitaires du noyau,
- comparer les chemins de démarrage avant/après,
- vérifier que les valeurs par défaut et logs restent cohérents.

---

### Phase 1 — Réduction du risque sur les points d’entrée

#### 2. `CERTUS_INDEX.py`
**But :** sécuriser le premier lancement, le chargement JSON et l’export.

**Actions :**
- isoler la normalisation de configuration,
- découpler init UI / init métier / export,
- formaliser le calcul du RMSE affiché,
- tester les fichiers anciens et les configs partielles.

**Contrôle zéro régression :**
- le même JSON doit produire le même état final,
- les exports doivent rester compatibles,
- les cas de premier lancement et de config vide doivent fonctionner.

#### 3. `CERTUS_STRAT.py`
**But :** fiabiliser la sélection des stratégies et les scores.

**Actions :**
- créer une fonction unique de sélection du meilleur résultat,
- séparer les scores et les métriques,
- sortir les règles d’export,
- couvrir le cas RMSE nul / placeholder.

**Contrôle zéro régression :**
- aucun fichier exporté ne doit afficher un RMSE trompeur,
- les stratégies retenues doivent rester identiques à configuration égale,
- les scénarios historiques doivent être rejoués avant validation.

#### 4. `CERTUS_INDEX_SPLINE.py`
**But :** attaquer le plus gros God module.

**Actions :**
- découper en sous-modules,
- extraire UI / workers / plots / config,
- réduire les closures,
- transformer les longues fonctions en unités plus courtes.

**Contrôle zéro régression :**
- procéder par extraction pure sans changement de logique,
- figer les sorties graphiques et les flux de calcul,
- comparer les rapports générés avant/après.

---

### Phase 2 — Découpage des gros orchestrateurs

#### 5. `CERTUS_RE.py`
**But :** séparer l’orchestration RE des calculs et de l’UI.

**Actions :**
- créer des sous-fonctions métier,
- normaliser les contextes d’exécution,
- isoler les exports.

**Contrôle zéro régression :**
- mêmes résultats sur les mêmes entrées,
- mêmes exports,
- mêmes erreurs attendues.

#### 6. `CERTUS_DESIGN.py`
**But :** réduire la taille du pipeline design.

**Actions :**
- factoriser les helpers partagés,
- extraire les scénarios d’exécution,
- aligner le format des résultats avec STRAT et INDEX.

**Contrôle zéro régression :**
- compatibilité stricte des fichiers de design existants,
- conservation des métriques et des exports.

#### 7. `CERTUS_HUB.py`
**But :** faire du hub une vraie couche de navigation minimale.

**Actions :**
- supprimer la logique métier,
- externaliser le routing,
- standardiser les actions disponibles.

**Contrôle zéro régression :**
- tous les raccourcis et menus doivent continuer à ouvrir les bons modules,
- aucun changement de comportement utilisateur non souhaité.

#### 8. `certus_ui.py`
**But :** isoler la présentation des comportements.

**Actions :**
- extraire les composants visuels,
- isoler les contrôleurs,
- centraliser les états de feedback.

**Contrôle zéro régression :**
- même rendu fonctionnel,
- même navigation,
- même ergonomie de base.

---

### Phase 3 — Services et workers

#### 9. `certus_services.py`
**But :** découper les services transverses.

**Actions :**
- séparer logging, I/O, settings, orchestration,
- documenter les effets de bord,
- retirer les dépendances UI.

**Contrôle zéro régression :**
- mêmes chemins de services,
- mêmes formats de sortie,
- mêmes effets secondaires autorisés.

#### 10. `certus_strat_context.py`
**But :** renforcer le contrat de contexte.

**Actions :**
- rendre les contextes explicites et stables,
- limiter le nombre de champs,
- ajouter des validations.

**Contrôle zéro régression :**
- aucune perte de champ utilisé,
- compatibilité avec les appels existants.

#### 11. `certus_strat_service.py`
**But :** formaliser le service métier stratégique.

**Actions :**
- découper par phase,
- clarifier les entrées/sorties,
- ajouter des tests de scénarios.

**Contrôle zéro régression :**
- mêmes classements, mêmes scores, mêmes exports,
- tests de comparaison sur cas réels.

#### 12. `certus_re_workers.py`
**But :** scinder les grosses phases worker.

**Actions :**
- extraire les étapes du pipeline,
- réduire les méthodes géantes,
- rendre les retours structurés.

**Contrôle zéro régression :**
- les workers doivent produire les mêmes résultats et signaux.

#### 13. `certus_spectral_workers.py`
**But :** clarifier le pipeline spectral.

**Actions :**
- séparer calcul pur et coordination,
- expliciter le cache,
- renforcer les tests unitaires.

**Contrôle zéro régression :**
- mêmes valeurs numériques à tolérance égale,
- mêmes timings de workflow globalement acceptables.

---

### Phase 4 — Utilitaires et mutualisation

#### 14. `certus_index_utils.py`
**But :** cadrer les helpers index.

**Actions :**
- typage fort,
- fonctions pures,
- tests unitaires ciblés.

**Contrôle zéro régression :**
- même normalisation,
- mêmes conversions,
- aucune modification des sorties attendues.

#### 15. `certus_re_helpers.py`
**But :** formaliser les helpers RE.

**Actions :**
- clarifier le contrat de chaque helper,
- limiter les dépendances,
- éviter la duplication avec d’autres utilitaires.

**Contrôle zéro régression :**
- vérifier que tous les chemins consommateurs passent encore.

#### 16. `certus_design_worker_utils.py`
**But :** garder un utilitaire léger et stable.

**Actions :**
- restreindre le périmètre,
- documenter les conversions,
- tester les cas limites.

**Contrôle zéro régression :**
- mêmes conversions sur les entrées existantes.

#### 17. `certus_spline_report.py`
**But :** unifier le reporting.

**Actions :**
- calculs de métriques centralisés,
- exports cohérents,
- tests de cohérence des rapports.

**Contrôle zéro régression :**
- même contenu de rapport à donnée identique,
- même nommage des fichiers si le contrat l’exige.

---

### Phase 5 — UX et composants secondaires

#### 18. `certus_shortcuts_overlay.py`
#### 19. `certus_toast_stack.py`
#### 20. `certus_splash.py`
#### 21. `certus_skeleton.py`

**But :** stabiliser les composants secondaires sans bloquer le cœur métier.

**Actions :**
- centraliser les textes,
- standardiser les états visuels,
- réduire la duplication des patterns UI.

**Contrôle zéro régression :**
- pas de changement de comportement visible non documenté,
- raccourcis et notifications inchangés dans leur intention.

---

### Phase 6 — Métal et modules spécialisés

#### 22. `CERTUS_METAL_SINGLE.py`
#### 23. `CERTUS_METAL_BILAYER.py`

**But :** factoriser le socle métal.

**Actions :**
- extraire les invariants communs,
- aligner les signatures,
- mutualiser les calculs partagés.

**Contrôle zéro régression :**
- comparer les sorties numériques avant/après,
- valider que les cas simples et bilayer restent conformes.

---

### Phase 7 — Tests et validation continue

#### 24. `tests/unit/test_certus_core.py`
#### 25. `tests/unit/test_certus_index.py`
#### 26. `tests/unit/test_certus_strat_service.py`
#### 27. `tests/integration/test_example_pipelines.py`
#### 28. `scripts/smoke/run_examples_headless.py`
#### 29. `tools/release_checks.py`

**But :** transformer les tests et checks en garde-fous actifs.

**Actions :**
- ajouter les cas de premier lancement,
- couvrir les configurations anciennes,
- verrouiller les résultats stratégiques,
- empêcher les régressions de release.

**Contrôle zéro régression :**
- exécuter les tests avant et après chaque refactor,
- comparer les artefacts critiques,
- bloquer toute dégradation fonctionnelle ou numérique.

---

## Règle de pilotage

Ne pas refactoriser tous les fichiers à la fois.

L’ordre conseillé est :
1. socle,
2. points d’entrée,
3. gros orchestrateurs,
4. services/workers,
5. utilitaires,
6. UX secondaire,
7. modules spécialisés,
8. tests et checks.

Cet ordre minimise le risque de casser la science tout en nettoyant progressivement l’architecture.
