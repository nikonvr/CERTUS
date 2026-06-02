# CERTUS_DESIGN — Plan de travail des prochaines actions

## Objectif

Poursuivre la modernisation de `certus_design` sans casser les chemins historiques, en consolidant les améliorations déjà réalisées sur les phases 2 et 3, puis en préparant les étapes suivantes de manière progressive et testée.

---

## État actuel

### Déjà accompli

- **Phase 2** : extraction d’un moteur physique partagé via `DesignPhysicsBridge`
- **Phase 3** : introduction d’un service headless via `DesignStrategyService`
- **DTOs** : frontières de données déjà en place pour les workers
- **Tests** : suite de tests renforcée sur les contrats, les cas limites et les chemins legacy
- **Documentation** : ajout de docstrings et garde-fous dans les zones sensibles
- **Nettoyage** : réduction de certaines duplications et imports inutiles

### Zones encore sensibles

- `certus/workers/certus_design_workers.py`
- `certus/workers/certus_design_engine.py`
- `certus/utils/certus_design_services.py`
- les contrats legacy appelés par l’IHM PyQt
- les chemins obliques et les calculs analytiques

---

## Priorités recommandées

### 1. Stabilisation finale des contrats

**But** : empêcher qu’un futur refactor casse les signatures ou les payloads attendus.

Actions proposées :
- Ajouter des tests de contrat supplémentaires sur les objets publics de `certus_design`.
- Vérifier systématiquement les valeurs par défaut des DTOs et des services.
- Valider la compatibilité des payloads legacy et des payloads normalisés.

Livrable attendu :
- Une suite de tests de contrat complète et stable.

---

### 2. Consolidation du moteur physique

**But** : garder un seul point d’entrée logique pour les calculs sensibles.

Actions proposées :
- Maintenir `DesignPhysicsBridge` comme source unique pour l’objectif et le gradient.
- Ajouter des tests ciblés si de nouveaux cas limites apparaissent.
- Éviter toute duplication de logique oblique ou analytique dans les workers.

Livrable attendu :
- Un moteur central bien documenté et suffisamment couvert.

---

### 3. Préparation d’un découplage progressif de `OptimWorker`

**But** : faire évoluer l’orchestration vers une structure plus propre sans casser l’IHM.

Actions proposées :
- Introduire un adaptateur très léger entre `OptimWorker` et `DesignStrategyService`.
- Garder le comportement actuel comme référence pendant la migration.
- Ne déplacer que des briques très stables et bien testées.

Livrable attendu :
- Un chemin de migration clair vers davantage de headless, sans rupture.

---

### 4. Nettoyage contrôlé du monolithe

**But** : réduire la dette technique sans réécrire le module d’un coup.

Actions proposées :
- Identifier les helpers encore dupliqués mais non critiques.
- Supprimer uniquement les doublons strictement redondants.
- Conserver les wrappers et alias tant qu’ils servent de transition.

Livrable attendu :
- Un fichier `certus_design_workers.py` progressivement allégé.

---

### 5. Documentation de sécurité pour futures refactorisations

**But** : éviter qu’une future IA ou un futur refactor casse les zones critiques.

Actions proposées :
- Maintenir une section “points sensibles” à jour.
- Documenter clairement les chemins à ne pas casser.
- Lister les préconditions avant toute extraction de code.

Livrable attendu :
- Une documentation interne explicite pour guider les prochaines modifications.

---

## Plan d’exécution recommandé

### Court terme

1. Renforcer encore les tests de contrat.
2. Vérifier que les chemins legacy restent parfaitement compatibles.
3. Documenter les points sensibles de l’orchestration.

### Moyen terme

1. Introduire un adaptateur entre worker et service headless.
2. Continuer à réduire les doublons non critiques.
3. Ajouter des tests supplémentaires sur les cas limites obliques.

### Long terme

1. Poursuivre le découplage progressif de l’IHM.
2. Préparer la réutilisation CLI / headless plus large.
3. Éventuellement extraire d’autres helpers purs si la couverture de tests est suffisante.

---

## Règles de prudence à respecter

- Ne jamais modifier un calcul scientifique sans test ciblé.
- Ne jamais supprimer un chemin legacy tant qu’il peut encore être consommé.
- Ne pas mélanger extraction structurelle et changement fonctionnel dans la même étape.
- Vérifier le lint et les tests après chaque micro-modification.
- Favoriser les petites migrations réversibles.

---

## Critère de succès

On considérera la suite comme réussie si :

- les tests restent verts,
- les comportements historiques ne changent pas,
- les doublons critiques sont encore réduits,
- la documentation protège les zones sensibles,
- et `certus_design` devient plus simple à maintenir sans perte de fiabilité.

---

## Inventaire des éléments déjà en place

### Fichiers de code

- `certus/workers/certus_design_engine.py`
  - moteur partagé pour l’objectif, le gradient et les chemins obliques
- `certus/utils/certus_design_services.py`
  - service headless `DesignStrategyService`
- `certus/workers/certus_design_workers_dto.py`
  - frontières DTO pour les workers design
- `certus/workers/certus_design_workers.py`
  - workers historiques conservés avec compatibilité legacy

### Fichiers de tests

- `tests/unit/test_certus_design_engine.py`
  - couverture des chemins critiques du bridge physique
- `tests/unit/test_certus_design_services.py`
  - couverture des contrats et normalisations du service headless
- `tests/unit/test_certus_design_workers_dto.py`
  - couverture des DTOs design

### Points documentés et sécurisés

- normalisation des requêtes headless
- assemblage du payload worker
- sentinelles de sécurité sur les calculs
- compatibilité legacy des payloads
- chemins obliques et gradient analytique
- contrat public des classes headless

### Ce qu’il faut éviter de casser

- les signaux PyQt et leur ordre d’émission
- les chemins legacy basés sur `dict[str, Any]`
- les kernels TMM et leurs hypothèses numériques
- les cas obliques multi-configurations
- les retours `ok / ep / rmse` et `ok / lab_nom / labs`
