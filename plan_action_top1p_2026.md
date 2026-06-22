# CERTUS — Plan d’action concret pour viser le top 1% mondial en 2026

## Objectif
Améliorer sensiblement le code et l’UX de CERTUS en travaillant d’abord sur les zones à plus fort impact : contrats de données, séparation des responsabilités, feedback utilisateur, observabilité et tests de non-régression.

---

## Règles de travail

- Une tâche = un résultat testable.
- Une tâche = un seul objectif principal.
- Ne pas mélanger refactor, feature et redesign dans la même étape.
- Après chaque modification importante, lancer les tests ciblés et le lint.
- Garder les chemins legacy tant qu’ils sont couverts par des tests.

---

## Phase 1 — Sécuriser la base technique

### Tâche 1 — Formaliser les contrats de données critiques
**But** : réduire les `dict[str, Any]` fragiles sur les frontières importantes.

**À faire**
- Identifier les payloads qui traversent les workers, le core et l’UI.
- Remplacer les structures implicites par des `dataclasses` ou modèles dédiés.
- Ajouter des champs explicites pour les résultats de workflow, les paramètres et les états.
- Conserver les adaptateurs legacy si nécessaire.

**Critère de fin**
- Les payloads critiques sont typés et validés.
- Les tests de contrat passent.

**Impact attendu**
- Moins de bugs silencieux.
- Refactor plus sûr.
- Meilleure lisibilité.

---

### Tâche 2 — Séparer clairement calcul, orchestration et UI
**But** : empêcher les modules de faire trop de choses à la fois.

**À faire**
- Vérifier que `physics` contient uniquement des calculs purs.
- Déplacer l’orchestration dans les workers ou services.
- Retirer toute logique métier cachée de l’UI.
- Identifier les fichiers monolithiques à découper en sous-modules.

**Critère de fin**
- Chaque module a une responsabilité principale claire.
- Les imports circulaires sont évités.

**Impact attendu**
- Architecture plus claire.
- Maintenance plus facile.
- Debug plus rapide.

---

### Tâche 3 — Standardiser les erreurs et le logging
**But** : rendre les échecs compréhensibles et actionnables.

**À faire**
- Harmoniser le format des logs.
- Ajouter ou renforcer les `run_id` / `session_id`.
- Séparer messages techniques et messages utilisateur.
- Limiter les `except Exception` non justifiés.
- Ajouter des logs de contexte dans les chemins critiques.

**Critère de fin**
- Un bug peut être localisé rapidement à partir des logs.
- Les erreurs utilisateur ont des messages clairs.

**Impact attendu**
- Meilleure observabilité.
- Moins de temps perdu en diagnostic.

---

### Tâche 4 — Ajouter des validations métier au plus tôt
**But** : bloquer les états impossibles avant qu’ils ne se propagent.

**À faire**
- Valider les bornes numériques.
- Valider les unités et formats.
- Valider les préconditions de workflow.
- Refuser les entrées incohérentes immédiatement.

**Critère de fin**
- Les entrées invalides sont détectées tôt.
- Les erreurs de validation sont explicites.

**Impact attendu**
- Fiabilité plus forte.
- Moins de comportements bizarres.

---

## Phase 2 — Fiabiliser les workflows critiques

### Tâche 5 — Ajouter des tests de non-régression ciblés
**But** : protéger les parcours les plus sensibles.

**À faire**
- Lister les flux critiques de l’application.
- Ajouter des tests unitaires pour les contrats centraux.
- Ajouter des tests d’intégration pour les workflows critiques.
- Couvrir les cas limites les plus risqués.

**Critère de fin**
- Les chemins critiques sont couverts.
- Les tests protègent les comportements historiques.

**Impact attendu**
- Régressions plus rares.
- Déploiements plus sereins.

---

### Tâche 6 — Rendre les workflows observables de bout en bout
**But** : que l’utilisateur comprenne ce qui se passe.

**À faire**
- Exposer la phase actuelle.
- Afficher une progression lisible.
- Montrer les sous-étapes importantes.
- Fournir un résumé final clair.
- Ajouter des traces de décision dans les opérations longues.

**Critère de fin**
- L’utilisateur sait toujours où il en est.
- Les longs calculs ne semblent plus opaques.

**Impact attendu**
- Confiance utilisateur plus forte.
- UX beaucoup plus premium.

---

### Tâche 7 — Renforcer la reproductibilité
**But** : pouvoir rejouer et comparer les résultats.

**À faire**
- Standardiser la gestion des seeds.
- Conserver les métadonnées d’exécution.
- Versionner les paramètres importants.
- Rendre les exports plus traçables.

**Critère de fin**
- Un run important peut être rejoué proprement.
- Les comparaisons entre runs sont fiables.

**Impact attendu**
- Meilleure crédibilité technique.
- Meilleur contrôle des résultats.

---

## Phase 3 — Améliorer l’UX de manière visible

### Tâche 8 — Harmoniser la hiérarchie visuelle
**But** : rendre l’interface plus nette et plus premium.

**À faire**
- Uniformiser titres, sous-titres et espacements.
- Standardiser les boutons primaires, secondaires et dangereux.
- Harmoniser les cartes, panneaux et tableaux.
- Vérifier la cohérence des couleurs de statut.

**Critère de fin**
- Les vues principales ont le même langage visuel.
- Les écrans paraissent appartenir au même produit.

**Impact attendu**
- UX plus élégante.
- Meilleure lisibilité.

---

### Tâche 9 — Améliorer les états de chargement et de progression
**But** : réduire la sensation d’attente floue.

**À faire**
- Ajouter ou améliorer les loaders.
- Afficher les phases en cours.
- Donner une estimation quand c’est possible.
- Faire évoluer les messages de progression selon l’étape réelle.

**Critère de fin**
- Aucun workflow long ne reste “muet”.

**Impact attendu**
- Perception de vitesse plus forte.
- Moins de frustration.

---

### Tâche 10 — Rendre les erreurs utilisateur guidées
**But** : transformer les erreurs en aide utile.

**À faire**
- Reformuler les erreurs pour qu’elles expliquent le problème.
- Ajouter une action suivante claire quand c’est possible.
- Distinguer erreur technique et erreur de saisie.
- Éviter les messages trop secs ou trop techniques côté UI.

**Critère de fin**
- Une erreur donne une direction.
- L’utilisateur sait quoi faire ensuite.

**Impact attendu**
- Confiance et satisfaction plus fortes.

---

## Phase 4 — Mettre un vrai design system en place

### Tâche 11 — Centraliser les tokens UI
**But** : éviter l’effet patchwork.

**À faire**
- Figer les couleurs.
- Figer les tailles.
- Figer les rayons.
- Figer les espacements.
- Figer les styles de boutons et de statut.

**Critère de fin**
- Les composants importants utilisent les mêmes règles de base.

**Impact attendu**
- Cohérence visuelle durable.

---

### Tâche 12 — Standardiser les composants de feedback
**But** : avoir une expérience homogène partout.

**À faire**
- Uniformiser toasts, alertes, modales et loaders.
- Réutiliser les mêmes composants dans les écrans clés.
- Éviter les variations locales non justifiées.

**Critère de fin**
- Le feedback visuel a un style unique et reconnaissable.

**Impact attendu**
- Impression de produit mature.

---

## Phase 5 — Réduire la taille et le risque des modules critiques

### Tâche 13 — Alléger les gros fichiers centraux
**But** : diminuer la complexité locale.

**À faire**
- Identifier les modules les plus longs et les plus couplés.
- Extraire les helpers purs.
- Regrouper les responsabilités par sous-module.
- Garder des wrappers de compatibilité si besoin.

**Critère de fin**
- Les fichiers critiques sont plus petits et plus lisibles.

**Impact attendu**
- Moins de dette technique.
- Refactor plus simple.

---

### Tâche 14 — Protéger les chemins legacy
**But** : éviter les ruptures lors des refactors.

**À faire**
- Conserver les adaptateurs tant que les tests le demandent.
- Vérifier les signatures publiques.
- Ne pas casser les ordres d’émission de signaux ou les conventions historiques.

**Critère de fin**
- Les anciens chemins restent compatibles.

**Impact attendu**
- Refactor plus serein.
- Moins de régressions.

---

## Ordre recommandé d’exécution

### Semaine 1
- Tâche 1 : formaliser les contrats de données.
- Tâche 3 : standardiser les erreurs et le logging.
- Tâche 4 : ajouter les validations métier.

### Semaine 2
- Tâche 5 : ajouter les tests de non-régression.
- Tâche 6 : rendre les workflows observables.
- Tâche 7 : renforcer la reproductibilité.

### Semaine 3
- Tâche 8 : harmoniser la hiérarchie visuelle.
- Tâche 9 : améliorer les chargements et progressions.
- Tâche 10 : guider les erreurs utilisateur.

### Semaine 4
- Tâche 11 : centraliser les tokens UI.
- Tâche 12 : standardiser les composants de feedback.
- Tâche 13 : alléger les modules critiques.
- Tâche 14 : protéger les chemins legacy.

---

## Critères de réussite globaux

Le plan est réussi si :

- les contrats critiques sont explicites,
- les workflows sensibles sont testés,
- les erreurs sont plus lisibles,
- l’UI est plus cohérente,
- l’utilisateur comprend mieux ce qui se passe,
- et les refactors deviennent moins risqués.

---

## Règle de décision pour la suite

Après chaque tâche terminée, décider immédiatement :

- soit on enchaîne sur la tâche suivante du même lot,
- soit on corrige une régression,
- soit on ajoute un test avant d’aller plus loin.

Aucune étape importante ne doit rester non protégée.
