# Audit ultra complet de la suite CERTUS

**Version**: 2026-05-20  
**Périmètre**: ensemble de la suite CERTUS dans le dépôt courant  
**Objectif**: dresser un audit technique, produit, scientifique et industriel, avec les améliorations concrètes possibles, classées par priorité.

---

## 1. Résumé exécutif

CERTUS est une suite scientifique très ambitieuse, avec un cœur algorithmique solide, une importante capacité de calcul, une instrumentation riche, et une couverture de tests déjà réelle. La base possède toutefois un problème structurel majeur: trop de logique est concentrée dans de très gros modules UI/métier, avec une forte duplication, beaucoup de blocs `except` trop larges, des fonctions géantes, et des frontières encore floues entre interface, orchestration, calcul et export.

Le diagnostic global est le suivant:

- **Force principale**: qualité numérique et richesse fonctionnelle.
- **Faiblesse principale**: maintenabilité structurelle et séparation des responsabilités.
- **Risque principal**: régressions silencieuses, comportements différents selon les points d’entrée, et difficultés de validation du premier lancement.
- **Potentiel**: très élevé, car une partie importante de la dette est architecturale, donc améliorable sans changer la science sous-jacente.

### Verdict synthétique

- **Qualité algorithmique**: excellente
- **Robustesse d’exécution**: moyenne à bonne, mais hétérogène selon les modules
- **Lisibilité / modularité**: insuffisante pour un socle long terme
- **Tests**: présents et utiles, mais couverture et ciblage encore insuffisants
- **CI/CD**: bonne base, à renforcer sur les invariants et les scénarios critiques
- **Expérience premier lancement**: améliorable, notamment sur les configs JSON, les chemins de fichiers et les valeurs par défaut

---

## 2. Méthodologie d’audit

Cet audit se base sur:

- l’inspection de la structure du dépôt
- les fichiers de documentation déjà présents
- les gros modules métier et UI identifiés comme sensibles
- les workflows CI visibles
- les tests déjà en place
- les logs d’exécution fournis, notamment sur STRAT et les exports RMSE
- les patterns récurrents observés dans les modules principaux

### Ce que cet audit cherche à répondre

1. Est-ce que la suite est scientifiquement crédible ?
2. Est-ce qu’elle est maintenable par une équipe dans la durée ?
3. Est-ce qu’elle démarre correctement dès le premier lancement ?
4. Est-ce que les sorties métier, notamment RMSE, sont cohérentes ?
5. Quelles améliorations ont le meilleur rapport impact/effort ?

---

## 3. Diagnostic global par axes

### 3.1 Architecture générale

La suite CERTUS semble organisée autour de plusieurs familles:

- noyau physique et numérique
- interfaces Qt
- workers / threads / services
- pipeline spectrales et de spline
- export de rapports et observabilité
- utilitaires transverses
- tests unitaires, intégration et UI

Le problème n’est pas l’absence de structure, mais le fait que beaucoup de responsabilités restent encore mélangées dans des fichiers massifs. Cela crée une dette cumulative:

- lecture difficile
- refactor risqué
- tests partiels
- bugs de coordination entre couches
- duplication des garde-fous

### 3.2 Qualité scientifique

Le socle scientifique est le point fort de CERTUS. On voit une vraie sophistication sur:

- les kernels numériques
- les calculs optiques
- la logique de fitting et d’optimisation
- les variations d’indices / couches / substrats
- les stratégies robustes et l’exploration multi-noise
- la validation physique et la stabilité numérique

C’est un point très fort, et il faut absolument préserver ce noyau lors des refactors.

### 3.3 Qualité logicielle

L’architecture logicielle souffre davantage:

- gros fichiers monolithiques
- fonctions trop longues
- lambdas et closures nombreuses
- `except` très larges
- duplication de blocs identiques
- dépendances UI/métier trop proches
- logique d’export et de scoring dispersée

### 3.4 Qualité d’exploitation

Les workflows CI, les fichiers de rapports et les tests donnent une base sérieuse. En revanche:

- le premier lancement peut encore dépendre de fichiers ou configs implicites
- certaines sorties peuvent être trompeuses si les données d’entrée sont incomplètes
- certains logs métier doivent être renforcés pour éviter les conclusions erronées

---

## 4. Points forts majeurs

### 4.1 Socle numérique très solide

CERTUS a une base scientifique sérieuse:

- kernels JIT/Numba
- calculs optiques spécialisés
- stratégies de robustesse
- traitements multi-niveaux
- exploration de solutions
- analyse des signaux et des profils

### 4.2 Tests déjà structurés

La suite dispose déjà:

- de tests unitaires
- de tests d’intégration
- de tests UI
- de tests de performance
- de tests orientés invariants

C’est une excellente base pour stabiliser les refactors.

### 4.3 CI et sécurité déjà bien amorcées

Les workflows visibles montrent une maturité appréciable:

- lint
- release Windows
- sécurité
- outillage de vérification

### 4.4 Instrumentation et observabilité

Les exports de rapports, fichiers de logs et artefacts intermédiaires montrent que la suite est pensée pour être auditée. C’est un très bon point pour un logiciel scientifique.

---

## 5. Problèmes critiques

## 5.1 RMSE à `0.00000` dans les rapports STRAT

### Symptôme observé

Dans les logs STRAT, certaines exports finissent avec:

- `RMSE_0.00000`
- `Avg RMSE: 0.0000 nm`

Alors que ce n’est pas crédible dans tous les contextes, notamment si le calcul réel doit être tiré d’un score robuste ou d’une mesure non nulle.

### Cause probable

Le problème vient probablement d’une combinaison de plusieurs facteurs:

1. **mauvaise source de RMSE dans l’export**
   - l’export prend parfois le premier item d’une liste
   - cet item peut être un placeholder, ou un résultat non représentatif

2. **fallback trop permissif**
   - si le champ attendu est absent, le code retombe sur `0.0`
   - cela produit un faux signal de réussite

3. **ambiguïté entre plusieurs champs métier**
   - `robustness_score`
   - `rmse`
   - `rmse_mean`
   - `rmse_p95`
   - `final_rmse`

4. **mauvaise hiérarchie de choix**
   - l’export doit être basé sur la métrique de référence réelle, pas sur un champ opportuniste

### Risque

- faux report de performance
- nommage des fichiers trompeur
- validation visuelle biaisée
- difficulté à comparer OLD vs refactor

### Recommandation

- définir une **seule métrique canonique** pour les exports STRAT
- interdire le fallback à `0.0` si des candidats existent
- logguer explicitement la source de la valeur exportée
- ajouter un test de non-régression sur les cas où le premier candidat est un placeholder

---

## 5.2 Comportement premier lancement encore fragile

### Symptômes possibles

- JSON incomplet
- clés anciennes encore présentes
- fichiers de référence absents
- valeurs UI non initialisées
- chemins de données non universels

### Risque

Le premier lancement ne doit jamais dépendre d’un état local préexistant, sinon l’expérience est cassée dès le départ.

### Recommandation

- centraliser les defaults applicatifs
- normaliser toutes les configs entrantes
- rendre l’auto-détection de fichiers facultative et non bloquante
- protéger les widgets UI contre les valeurs manquantes

---

## 5.3 Trop de blocs `except` trop larges

Le code contient de nombreux blocs du style:

- `except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError)`

Ce pattern est trop permissif.

### Problèmes

- il masque de vrais bugs
- il réduit la qualité de diagnostic
- il encourage le copier-coller défensif
- il rend les erreurs silencieuses

### Recommandation

- créer des exceptions métier explicites
- remplacer les `except` fourre-tout par des handlers ciblés
- garder un seul mécanisme de fallback visible et tracé

---

## 5.4 God modules encore trop présents

Certains fichiers restent trop gros et trop centraux. Cela inclut plusieurs entrypoints, modules de workers, et composants UI.

### Risques

- compréhension difficile
- refactor lent
- couplage fort
- tests plus coûteux
- risque de régressions croisées

### Recommandation

- découper en sous-modules par responsabilité
- extraire les builders, les contextes, les adapters, les exporters, les policies
- garder les classes UI comme orchestrateurs minces

---

## 5.5 Duplication de code

La duplication est encore visible dans:

- handling d’erreurs
- splash / démarrage
- chargement de config
- export de rapport
- logging de démarrage
- packaging de paramètres physiques

### Risque

Quand un bug est corrigé dans une version d’un bloc dupliqué, les autres copies restent potentiellement cassées.

### Recommandation

- extraire des helpers communs
- éviter les copies de blocs d’initialisation
- créer des fonctions de normalisation réutilisables

---

## 6. Audit par domaines

## 6.1 Noyau scientifique / physique

### Évaluation

Très bon.

### Observations

- calculs optiques spécialisés cohérents
- attention portée aux invariants physiques
- structure adaptée à des workflows de recherche
- présence de tests et de validations numériques

### Améliorations possibles

- découper les calculs en couches plus petites
- documenter davantage les hypothèses physiques
- ajouter des tests de régression sur cas limites
- isoler les constantes et seuils dans des objets de configuration typés

---

## 6.2 STRAT / exploration / optimisation

### Évaluation

Bon sur le fond, fragilisé par l’agrégation et les sorties.

### Observations

- les stratégies sont riches et sophistiquées
- l’auto-optimisation semble fonctionner
- l’export final doit être fiabilisé
- les logs de progression sont utiles, mais peuvent être trompeurs si la métrique n’est pas bien choisie

### Améliorations possibles

- définir une structure de résultat standard
- séparer score interne / score d’export / score de tri
- faire remonter l’origine de chaque métrique dans les logs
- ajouter une validation finale de cohérence des résultats avant export

---

## 6.3 INDEX / SPLINE / DESIGN / RE / METAL

### Évaluation

Fonctionnel mais trop compacté.

### Observations

- présence de nombreuses variantes métier
- logique commune dispersée
- certains modèles et workers semblent répliquer les mêmes patterns
- l’UI porte encore trop de logique métier

### Améliorations possibles

- extraire les services partagés
- factoriser les loaders / exporters
- regrouper les helpers de validation
- introduire des DTOs et contextes métier

---

## 6.4 UI Qt

### Évaluation

Expérimentée mais trop lourde.

### Observations

- beaucoup de widgets et handlers
- orchestration de threads embarquée
- logique métier et affichage trop proches
- effets de bord difficiles à tester

### Améliorations possibles

- pattern MVP/MVVM léger
- widgets “bêtes”
- presenters / controllers testables
- états UI centralisés
- isolation des side effects

---

## 6.5 Services, workers et headless

### Évaluation

Base correcte, mais l’hygiène de service doit être renforcée.

### Observations

- services présents
- workers nombreux
- coordination multi-thread non triviale
- risques de conditions de course et d’état partagé

### Améliorations possibles

- contrats explicites pour les workers
- annulation propre
- états sérialisés
- logs de cycle de vie standardisés
- retour d’erreurs typé au lieu de `None` implicites

---

## 6.6 Tests

### Évaluation

Bonne quantité, mais encore insuffisante sur les zones à risque.

### Observations

- bonne diversité
- bon socle d’intégration
- présence de tests UI
- encore trop de zones critiques non verrouillées par des tests de non-régression

### Améliorations possibles

- tests sur l’export STRAT et ses noms de fichier
- tests de premier lancement
- tests de compatibilité JSON ancienne version
- tests de cohérence entre OLD et refactor
- tests d’invariants sur les scores et RMSE

---

## 6.7 CI/CD

### Évaluation

Solide.

### Observations

- lint et sécurité présents
- release Windows existante
- bonne base d’automatisation

### Améliorations possibles

- ajout d’un job de vérification des invariants métier
- exécution d’un mini scénario de lancement au CI
- smoke test de chargement config + export
- contrôle de non-régression sur les rapports générés

---

## 7. Lecture du cas RMSE / STRAT

Le cas du `RMSE_0.00000` mérite une attention particulière car il touche à la crédibilité des sorties.

### Ce que cela signifie probablement

- la valeur exportée n’est pas toujours la valeur métier réelle
- une métrique de substitution est parfois utilisée sans garde-fou
- un fallback à zéro masque le problème au lieu de l’exposer

### Ce qu’il faut corriger

1. **ne jamais exporter une RMSE à 0 par défaut si des stratégies existent**
2. **forcer un contrôle de validité de la valeur choisie**
3. **logguer le chemin de calcul de la RMSE exportée**
4. **normaliser le contrat des résultats**

### Critère de validation

Un rapport valide doit pouvoir répondre à la question:

> “D’où vient cette RMSE ? Est-ce un score interne, un score robuste, un score p95, ou une moyenne de validation ?”

Si la réponse n’est pas immédiate, le contrat de sortie est insuffisant.

---

## 8. Matrice de risques

| Risque | Probabilité | Impact | Sévérité |
|---|---:|---:|---:|
| Export RMSE trompeur | Élevée | Élevé | Critique |
| Premier lancement cassé | Moyenne | Élevé | Critique |
| Régression silencieuse après refactor | Moyenne | Élevé | Critique |
| Bugs masqués par `except` larges | Élevée | Moyen | Élevée |
| Maintenance lente | Élevée | Moyen | Élevée |
| Couplage UI/métier | Élevée | Élevé | Critique |
| Tests insuffisants sur les flux critiques | Moyenne | Élevé | Élevée |

---

## 9. Priorisation des améliorations

### P0 — Critique, à faire en premier

1. **Fix RMSE STRAT**
   - choisir la bonne métrique de sortie
   - éliminer le fallback trompeur à 0
   - ajouter un test de non-régression

2. **Stabiliser le premier lancement**
   - defaults centralisés
   - normalisation JSON
   - gestion robuste des chemins et fichiers

3. **Introduire un contrat de résultat métier unique**
   - modèle de sortie standard pour STRAT / INDEX / DESIGN / RE
   - champs obligatoires / optionnels clairement définis

### P1 — Très important

4. **Réduire les `except` trop larges**
5. **Extraire les helpers communs de chargement / export / logging**
6. **Ajouter des tests de compatibilité OLD vs refactor**
7. **Verrouiller les résultats exportés par des assertions métier**

### P2 — Structurant

8. **Découper les gros modules en sous-modules**
9. **Isoler UI, services et logique métier**
10. **Ajouter des exceptions métier dédiées**
11. **Refondre la duplication la plus coûteuse**

### P3 — Qualité long terme

12. **Augmenter la couverture sur les flux critiques**
13. **Renforcer la documentation des API publiques**
14. **Monter progressivement vers un typage strict**
15. **Standardiser les patterns d’orchestration et de reporting**

---

## 10. Plan de refactor recommandé

### Phase 1 — Sécurisation des sorties

- corriger STRAT RMSE
- verrouiller les exports
- ajouter les tests de régression métier
- sécuriser le premier lancement

### Phase 2 — Extraction des responsabilités transverses

- normalisation de config
- helpers d’export
- helpers de logging
- helpers de sélection de métriques
- gestion commune des erreurs applicatives

### Phase 3 — Découpage architectural

- modules UI minces
- workers séparés
- services dédiés
- contextes et DTOs
- réduction de la taille des fichiers principaux

### Phase 4 — Industrialisation

- mypy ou équivalent progressif
- tests métier sur les cas limites
- contrat de compatibilité OLD
- smoke tests de lancement complet

---

## 11. Améliorations concrètes possibles

### Niveau code

- créer `safe_ui_action`
- créer des exceptions métiers
- factoriser les loaders JSON/Excel/CSV
- centraliser les defaults de démarrage
- standardiser les dataclasses de configuration
- isoler les métriques exportables
- rendre les workers plus déclaratifs

### Niveau architecture

- séparer `model`, `service`, `ui`, `export`, `worker`
- faire remonter les états par objets de résultats
- supprimer les couplages implicites entre modules
- réduire les dépendances circulaires

### Niveau qualité

- tests sur premier run
- tests sur export RMSE
- tests de compatibilité des anciens JSON
- tests de sécurité des chemins
- tests sur les versions de configuration

### Niveau exploitation

- logs plus explicites
- messages d’erreur orientés utilisateur
- validation finale des artefacts
- rapports traçables et reproductibles

---

## 12. Conclusion

CERTUS est une base **très forte scientifiquement**, mais encore **trop coûteuse à maintenir** dans son état actuel. Le plus inquiétant n’est pas le manque de fonctionnalités; au contraire, la suite a déjà beaucoup de capacités. Le risque vient surtout de la concentration de responsabilité dans trop peu de fichiers, de l’ambiguïté des métriques exportées, et de certaines politiques d’erreurs trop permissives.

### Conclusion en une phrase

**CERTUS a un excellent moteur, mais la carrosserie logicielle doit encore être allégée, normalisée et sécurisée pour devenir vraiment industrielle.**

---

## 13. Livrables recommandés à produire ensuite

1. un audit ciblé par module principal
2. un plan de refactor P0/P1/P2
3. une spécification du contrat de résultat STRAT
4. un guide de démarrage “first launch safe”
5. une batterie de tests de non-régression pour les exports et configs

---

## 14. Annexe — Check-list de validation rapide

- [ ] RMSE exportée expliquée et vérifiable
- [ ] aucun fallback silencieux à zéro
- [ ] premier lancement sans dépendance cachée
- [ ] config JSON normalisée
- [ ] fichiers OLD utilisés comme référence
- [ ] tests de compatibilité présents
- [ ] erreurs métier distinctes des erreurs techniques
- [ ] modules principaux raccourcis progressivement
- [ ] logs suffisamment explicites pour l’audit
- [ ] rapports reproductibles

