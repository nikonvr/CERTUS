# CERTUS Audit Action Plan

## Vision
Faire évoluer CERTUS vers une suite plus modulaire, plus lisible et plus simple à faire évoluer, tout en conservant la précision métier et la robustesse des calculs.

L’audit sert de feuille de route pour orienter les prochains chantiers vers ce qui améliore le plus la stabilité, la maintenabilité, la qualité d’exécution et la vitesse de livraison.

## Cap de transformation
- Réduire progressivement les monolithes critiques pour transformer le code d’orchestration en couche plus légère.
- Clarifier les frontières entre UI, calcul, export, persistance et tests.
- Renforcer les contrats entre modules pour limiter les régressions et simplifier le raisonnement.
- Faire converger les flux critiques vers des parcours plus explicites et plus prédictibles.
- Préparer la suite à des évolutions futures sans augmenter la complexité opérationnelle.

## Périmètre de couverture
Cet audit couvre l’intégralité de la suite CERTUS, avec un regard bout en bout sur :
- les modules d’entrée principaux,
- les modules partagés de base,
- l’UX des parcours utilisateurs,
- la robustesse des tests,
- la CI / release,
- la performance et la maintenabilité,
- les scripts de smoke, les artefacts et la documentation utile à l’exploitation.

## Modules prioritaires à auditer
1. `CERTUS_HUB.py`
2. `CERTUS_DESIGN.py`
3. `CERTUS_STRAT.py`
4. `CERTUS_RE.py`
5. `CERTUS_INDEX.py`
6. `CERTUS_INDEX_SPLINE.py`
7. `CERTUS_METAL_SINGLE.py`
8. `CERTUS_METAL_BILAYER.py`
9. `certus_ui.py`
10. `certus_core.py`

## Axe de progression par domaine

### Architecture
Objectif futur
- Faire de chaque module une unité plus lisible, avec une responsabilité dominante bien identifiable.
- Limiter les dépendances croisées et éviter que l’UI porte la logique métier.
- Déplacer les responsabilités transverses vers des modules ou helpers dédiés quand cela réduit la complexité.
- Préserver des contrats d’entrée/sortie clairs pour chaque composant.

### Qualité Python
Objectif futur
- Maintenir des annotations de type cohérentes et utiles.
- Garder des fonctions courtes, ciblées et faciles à relire.
- Préférer des objets métier explicites aux structures implicites trop dispersées.
- Continuer à améliorer la compatibilité et la clarté du code pour Python 3.14.5+.

### UX
Objectif futur
- Rendre les parcours critiques plus directs et plus compréhensibles.
- Renforcer la visibilité des états d’attente, d’erreur et de succès.
- Harmoniser les libellés, les statuts et les actions principales.
- Réduire les ambiguïtés dans les interactions répétées ou longues.

### Tests
Objectif futur
- Consolider une couverture utile, déterministe et orientée risques.
- Renforcer la séparation entre tests unitaires, d’intégration, UI et perf.
- Prioriser les non-régressions sur les flux les plus sensibles.
- Garder des échecs lisibles et exploitables.

### Release et CI
Objectif futur
- Stabiliser l’environnement de livraison et rendre les checks reproductibles.
- Aligner les workflows sur une chaîne de validation simple à relire.
- Garder des artefacts vérifiables et des versions cohérentes.
- Faire de la CI un filet de sécurité plutôt qu’une source de friction.

### Performance
Objectif futur
- Surveiller le démarrage, les imports et les calculs les plus lourds.
- Réduire les recalculs inutiles et les coûts mémoire évitables.
- Préserver la fluidité de l’interface pendant les traitements longs.
- Favoriser les snapshots réutilisables quand le contexte le permet.

## Roadmap recommandée

### Phase 1 — Socle
- Vérifier en continu les contraintes Python et dépendances.
- Garder les workflows CI / release cohérents et vérifiables.
- Maintenir des scripts de bootstrap et de smoke stables.

### Phase 2 — Cœur applicatif
- Poursuivre l’audit des gros modules d’entrée.
- Identifier à chaque passage les responsabilités encore mélangées.
- Extraire les helpers ou DTO qui clarifient les échanges.

### Phase 3 — UX et validation
- Revoir les parcours utilisateur les plus fréquents et les plus critiques.
- S’assurer que chaque branche d’UI possède ses états vides, erreur et succès.
- Corriger les incohérences visuelles ou fonctionnelles qui compliquent l’usage.

### Phase 4 — Tests et robustesse
- Renforcer la structure des tests sur les zones les plus risquées.
- Vérifier les invariants de domaine et les cas limites.
- Continuer à examiner la stabilité des intégrations et des performances.

### Phase 5 — Refactor guidé
- Classer les chantiers par impact et par dépendance.
- Séparer les corrections rapides des refactors structurants.
- Formaliser les évolutions fichier par fichier pour garder un cap lisible.

## Signaux d’alerte à surveiller
- fichiers trop volumineux,
- orchestration et calcul mélangés,
- UI qui porte de la logique métier,
- tests qui ne protègent pas les chemins critiques,
- conditions CI obsolètes,
- messages d’erreur non actionnables,
- duplication entre modules.

## Livrables attendus
- une cartographie claire des modules critiques,
- une liste des risques classés par priorité,
- un plan d’intervention concret,
- des recommandations UX,
- un backlog de refactor fichier par fichier.

## Règle de décision
Si un sujet améliore à la fois la stabilité, la lisibilité et la capacité de livraison, il doit remonter dans la priorité.

Si un sujet est seulement cosmétique, il passe après les fondations techniques.

## Résultat attendu
À terme, la suite CERTUS doit être :
- plus simple à comprendre,
- plus simple à tester,
- plus simple à livrer,
- plus cohérente pour l’utilisateur,
- plus robuste à long terme,
- mieux préparée pour les évolutions futures.

## Horizon de maintenance
- Transformer progressivement `CERTUS_INDEX_SPLINE.py` en orchestrateur plus léger.
- Continuer à réduire les points de couplage entre UI, calcul et export.
- Faire converger les modules vers des responsabilités plus nettes et plus stables.
- Garder l’audit comme support vivant de priorisation et de décision.
- Utiliser la roadmap pour aligner les refactors, les tests et les livraisons futures.
