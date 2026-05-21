# CERTUS — Plan d’action complet

## Objectif
Transformer les audits du jour en un plan d’action exécutable, priorisé, et compatible avec l’exigence de **zéro régression fonctionnelle, scientifique et UX**.

---

## 1. Principes de pilotage

### Règles absolues
1. **Zéro régression** : aucun changement ne doit casser un workflow existant, un calcul scientifique, un export, un preset ou un comportement UI.
2. **Compatibilité descendante** : les anciens JSON, presets, rapports et habitudes de lancement doivent continuer à fonctionner.
3. **Une seule couche à la fois** : ne pas mélanger correction du hub, refactor métier et rework UI dans la même étape.
4. **Tests avant/après** : chaque étape doit être verrouillée par un test de non-régression ou une comparaison d’artefacts.
5. **Vocabulaire métier stable** : substrat, couche mince, RMSE, score, robustesse doivent garder leur sens propre.

---

## 2. Objectifs de cohérence à conserver partout

### Distinctions métier à ne jamais brouiller
- **Substrat** = support physique.
- **Couche mince** = couche déposée / modélisée.
- **RMSE** = métrique d’erreur.
- **Score** = coût, classement ou indicateur décisionnel.
- **Robustesse** = comportement sous perturbation.

### Architecture cible
- `CERTUS_HUB.py` = routeur / launcher.
- Modules cœur métier = calcul + résultats + export.
- Modules spécialisés = physique dédiée.
- Services / utils = fonctions pures ou quasi pures.

---

## 3. Priorités P0, P1, P2

## P0 — Bloquer les régressions les plus critiques

### 3.1 `CERTUS_HUB.py`
**But** : garder le hub cohérent, sans logique métier cachée.

**Actions**
- Garder le hub strictement launcher / routeur.
- Maintenir les catégories de modules dans le catalogue.
- Propager le contrat de lancement dans les logs.
- Distinguer clairement : `core_workflow`, `materials_specialized`, `support_tool`.
- Vérifier que les modules appelés sont correctement catégorisés.

**Critère de sortie**
- Le hub lance toujours les bons modules, avec le bon contrat, sans ambiguïté de vocabulaire.

---

### 3.2 `CERTUS_STRAT.py`
**But** : sécuriser le calcul, l’export et le choix de la meilleure stratégie.

**Actions**
- Séparer clairement `RMSE`, `rmse_p95`, `rmse_mean`, `robustness_score`.
- Garantir que le RMSE des exports est une vraie métrique d’erreur.
- Éviter tout placeholder `0.0` pris comme résultat de référence.
- Conserver le post-check `T_min`.
- Stabiliser le nommage de rapports et les colonnes d’export.

**Critère de sortie**
- Aucun export STRAT ne doit afficher un faux RMSE ou confondre robustesse et erreur.

---

### 3.3 `CERTUS_INDEX.py`
**But** : maintenir la séparation entre substrat et couches minces.

**Actions**
- Conserver la normalisation de config pour la compatibilité historique.
- Ne jamais déduire un champ de film à partir d’un champ de substrat.
- Garder les alias de migration strictement sémantiques.
- Stabiliser le premier lancement et les exports.

**Critère de sortie**
- Un ancien JSON charge la même physique, sans réinterprétation abusive.

---

### 3.4 `CERTUS_RE.py`
**But** : préserver la structure physique des reconstructions.

**Actions**
- Conserver la séparation entre substrat, stack et données RE.
- Garder les alias de compatibilité comme ponts de migration בלבד.
- Préserver la logique de chargement de workbook et de config.

**Critère de sortie**
- Le RE reste physiquement lisible et compatible avec les anciens formats.

---

## P1 — Consolider les gros modules métier

### 3.5 `CERTUS_INDEX_SPLINE.py`
**But** : garder le substrat comme base physique, sans confusion avec les offsets.

**Actions**
- Maintenir le substrat nominal comme référence.
- Garder les offsets comme corrections explicites.
- Conserver la traçabilité entre contexte, correction et résultat.
- Éviter de mélanger optimisation, calcul et export.

**Critère de sortie**
- Le modèle spline reste physiquement cohérent et traçable.

---

### 3.6 `CERTUS_DESIGN.py`
**But** : stabiliser la cohérence du design de pile.

**Actions**
- Garder les matériaux alignés avec le design réel.
- Vérifier l’ordre des couches et les métadonnées d’export.
- Éviter toute ambiguïté entre design conceptuel et design exporté.

**Critère de sortie**
- Le design exporté reflète exactement la pile modélisée.

---

### 3.7 `CERTUS_METAL_SINGLE.py`
**But** : préserver la hiérarchie support / couche mince.

**Actions**
- Conserver le substrat transparent comme support.
- Conserver la couche métal comme couche mince.
- Maintenir la séparation physique dans les configs et exports.

**Critère de sortie**
- Le substrat n’est jamais réinterprété comme une couche mince.

---

### 3.8 `CERTUS_METAL_BILAYER.py`
**But** : préserver l’ordre physique du système bilayer.

**Actions**
- Conserver la hiérarchie : substrat / couche métal / couche intermédiaire.
- Ne jamais renommer une couche intermédiaire en substrat.
- Garder paramètres physiques et matériau séparés.

**Critère de sortie**
- La hiérarchie physique reste intacte dans le code, les logs et les exports.

---

## P2 — Harmoniser les couches transverses

### 3.9 Services, workers, utils
Fichiers concernés :
- `certus_services.py`
- `certus_index_utils.py`
- `certus_re_helpers.py`
- `certus_design_worker_utils.py`
- `certus_strat_context.py`
- `certus_strat_service.py`
- `certus_re_workers.py`
- `certus_spectral_workers.py`
- `certus_design_workers.py`

**Actions**
- Cadrer le périmètre de chaque utilitaire.
- Garder des fonctions pures ou quasi pures.
- Clarifier les contrats de contexte et de worker.
- Limiter l’état implicite.
- Éviter les mini-god-modules cachés.

**Critère de sortie**
- Les helpers et services sont fiables, testables, et n’introduisent pas de logique parasite.

---

### 3.10 UX secondaire
Fichiers concernés :
- `certus_shortcuts_overlay.py`
- `certus_toast_stack.py`
- `certus_splash.py`
- `certus_skeleton.py`

**Actions**
- Standardiser le vocabulaire.
- Harmoniser l’affichage et les comportements secondaires.
- Éviter les duplications visuelles et textuelles.

**Critère de sortie**
- L’UX secondaire reste cohérente sans perturber les workflows principaux.

---

## 4. Plan de travail opérationnel par étapes

### Étape A — Stabilisation immédiate
1. Verrouiller les contrats du hub.
2. Verrouiller la distinction RMSE / score / robustesse.
3. Verrouiller la distinction substrat / couche mince.
4. Conserver la compatibilité des configs anciennes.

### Étape B — Sorties et visibilité
5. Auditer les noms de fichiers exportés.
6. Auditer les titres de rapports.
7. Auditer les colonnes exportées.
8. Auditer les logs de fin d’exécution.
9. Corriger les formulations ambiguës.

### Étape C — Compatibilité descendante
10. Tester les JSON anciens.
11. Tester les presets / workbooks historiques.
12. Valider les alias de migration.
13. Vérifier qu’aucun champ n’est re-sémantisé.

### Étape D — Non-régression scientifique
14. Lancer des cas représentatifs par module.
15. Comparer avant / après sur les résultats clés.
16. Vérifier que les exports ne changent pas de sens.
17. Bloquer toute modification non justifiée scientifiquement.

### Étape E — Consolidation structurelle
18. Cadrer services / workers / utils.
19. Réduire les responsabilités mélangées.
20. Standardiser le vocabulaire métier dans toute la suite.

---

## 5. Checklist de validation finale

Pour considérer une étape comme terminée, il faut répondre oui à toutes les questions suivantes :

- Le module continue-t-il à fonctionner comme avant ?
- Les anciens fichiers restent-ils lisibles ?
- Le vocabulaire métier reste-t-il exact ?
- Les exports disent-ils la bonne chose ?
- Les logs disent-ils la bonne chose ?
- La science a-t-elle changé sans raison ?
- Les tests de non-régression passent-ils ?

Si une réponse est non, l’étape n’est pas validée.

---

## 6. Ordre d’exécution recommandé

### Ordre 1
- `CERTUS_HUB.py`
- `CERTUS_STRAT.py`
- `CERTUS_INDEX.py`
- `CERTUS_RE.py`

### Ordre 2
- `CERTUS_INDEX_SPLINE.py`
- `CERTUS_DESIGN.py`
- `CERTUS_METAL_SINGLE.py`
- `CERTUS_METAL_BILAYER.py`

### Ordre 3
- services
- workers
- utils
- UX secondaire

---

## 7. Verdict final

CERTUS a une base scientifique forte. Le vrai travail maintenant est de verrouiller la cohérence transversale, la compatibilité des formats historiques, et la lisibilité des sorties.

Le mot d’ordre est simple :
**corriger sans réécrire la science, clarifier sans casser l’existant, et améliorer sans aucune régression.**
