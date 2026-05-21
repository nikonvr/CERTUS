
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # CERTUS Audit Action Plan

## Objectif
Conduire un audit large et priorisé de la suite CERTUS afin d’aligner le code, l’architecture, l’UX, les tests et la release sur un standard Python 3.14.5+ moderne et exploitable en 2026.

## Périmètre
Cet audit couvre :
- les 9 à 10 modules d’entrée principaux,
- les modules partagés de base,
- l’UX des parcours utilisateurs,
- la robustesse des tests,
- la CI / release,
- la performance et la maintenabilité.

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

## Critères d’audit

### 1. Architecture
- responsabilités séparées,
- orchestration claire,
- limites de module lisibles,
- dépendances minimales,
- pas de logique métier enfouie dans l’UI.

### 2. Qualité Python
- annotations de type cohérentes,
- fonctions courtes et ciblées,
- objets métier explicites,
- erreurs gérées proprement,
- compatibilité Python 3.14.5+.

### 3. UX
- navigation claire,
- feedback visible,
- états d’erreur explicites,
- parcours critiques simples,
- libellés cohérents,
- pas d’ambiguïté dans les actions principales.

### 4. Tests
- couverture utile,
- tests déterministes,
- bonne séparation unit / intégration / UI / perf,
- échecs lisibles,
- faible flakiness.

### 5. Release et CI
- environnement reproductible,
- checks de release fiables,
- workflows cohérents,
- versioning aligné,
- artefacts vérifiables.

### 6. Performance
- démarrage,
- imports,
- calculs lourds,
- cache,
- parallélisation,
- coût mémoire.

## Ordre d’exécution recommandé

### Phase 1 — Socle
1. Vérifier les contraintes Python et dépendances.
2. Auditer les workflows CI / release.
3. Valider les scripts de bootstrap et de smoke.

### Phase 2 — Cœur applicatif
4. Auditer les gros modules d’entrée un par un.
5. Identifier les responsabilités mélangées.
6. Extraire les helpers ou DTO manquants.

### Phase 3 — UX et validation
7. Auditer les parcours utilisateur.
8. Vérifier les états vides, erreurs et feedback.
9. Relever les incohérences visuelles ou fonctionnelles.

### Phase 4 — Tests et robustesse
10. Auditer la qualité et la structure des tests.
11. Vérifier les invariants de domaine.
12. Examiner la stabilité des intégrations et des performances.

### Phase 5 — Plan de refactor
13. Classer les chantiers par priorité.
14. Distinguer les corrections rapides des refactors lourds.
15. Formaliser un plan d’action fichier par fichier.

## Signaux d’alerte
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
À la fin de l’audit, la suite CERTUS doit être :
- plus simple à comprendre,
- plus simple à tester,
- plus simple à livrer,
- plus cohérente pour l’utilisateur,
- plus robuste à long terme.


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.