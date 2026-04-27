# Project-level Antigravity rules

## Contexte
- Gros codebase (>50k lignes) avec fort risque de régression.
- Priorité absolue : aucun changement de comportement non voulu.
- Refactorings visés : simplification, découplage, lisibilité, performance locale.

## Comportement attendu
- Refactor incrémental : micro-changements, pas de réécriture massive.
- Toujours commencer par :
  - identifier la zone impactée,
  - lire les tests associés,
  - proposer un plan court (3 à 6 puces).
- Appliquer le plan étape par étape et s’arrêter après chaque groupe de changements significatif.

## Contraintes fortes
- Ne jamais :
  - renommer des fonctions / classes / modules publics sans validation,
  - changer les signatures ou types d’arguments sans validation,
  - supprimer du code sans être sûr qu’il est mort et couvert par des tests.
- Si une modification implique :
  - plus de 3 fichiers, ou
  - plus de 80–100 lignes de diff,
  alors s’arrêter et proposer un découpage.

## Tests
- Avant modification : chercher et lire les tests pertinents.
- Après modification :
  - lister les tests à exécuter (commandes précises),
  - si un comportement n’est pas testé, proposer un test ciblé au lieu de deviner.

## Style de sortie
- Réponses concises, orientées diff :
  - résumé du plan,
  - diff ou extraits de code,
  - commande(s) de test.
- Éviter les explications longues ou la documentation non demandée.
- Poser au maximum une question à la fois en cas d’ambiguïté.
