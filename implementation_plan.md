# Refactoring de `_setup_corridor_context` (Phase 3)

## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.
- Refactoring de `spline_profile_corridors.py` (Phase 3 et Bonus) complété et validé par pytest (1592 tests passed).

### Il reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.

Ce plan de bataille détaille l'approche pour la prochaine session, centrée sur la modularisation de `spline_profile_corridors.py`.

## Contexte
La fonction `_setup_corridor_context` (684 lignes) est le point d'entrée critique de la génération des corridors de tolérance. Elle est responsable de l'évaluation du seuil de RMSE intelligent, de la configuration du profileur, et de l'initialisation des états (callbacks temps réel). 
En raison de sa longueur extrême, le flux d'exécution est dur à lire et difficilement testable de manière unitaire.

## Objectif
Réduire la fonction principale à moins de 150 lignes en déléguant la logique complexe (vérifications de seuils, gestion adaptative du delta absolu, configuration des `live_callbacks`) à une classe dédiée ou à un `Context Builder` avec des helpers.

## Prochaines étapes de l'implémentation

### 1. Extraction du sous-contexte Live Stream
Actuellement, les fonctions `_emit_live_profile` et `_push_live_point` sont des *closures* qui capturent des listes muables (`live_d_vals`, `live_rmse_vals`, etc.) et un `threading.Lock()`.
- **Solution :** Créer une classe `CorridorLiveStreamer` qui encapsule les listes, le lock, et le callable `live_cb`.

### 2. Isolation de l'estimation de tolérance adaptative
Le bloc calculant `adaptive_abs_meta` et gérant le fallback du threshold (env. 200 lignes avec logs intensifs) pollue le flux principal.
- **Solution :** Extraire ce bloc dans un helper statique `_initialize_adaptive_threshold(context)`.

### 3. Structuration globale via `CorridorProfileContext`
La fonction existante prépare des variables pour finalement retourner un grand dictionnaire ou un objet de contexte existant. 
- **Solution :** Reprendre le modèle `REPhase2Context`. On créera un constructeur étape par étape qui validera séquentiellement :
  1. Base geometry & Seeds
  2. Fallback rules & Threshold logic
  3. Pre-run profiling / Center fits

## Déroulement pour le démarrage demain
1. **Lancement du script AST** : Analyser les dépendances (`reads`/`writes`) spécifiques à `_setup_corridor_context`.
2. **Création du `CorridorLiveStreamer`** et injection dans la signature.
3. **Extraction des helpers** de logging massif pour épurer le flux.
4. **Validation via `pytest`** (`pytest tests/unit/ -k "corridor"`).

> [!TIP]
> **Prêt à l'emploi :** Le fichier `task.md` a été réinitialisé avec ces étapes pour lancer la session immédiatement !


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisé.
- Validation des configurations de release et des entrypoints critiques.

### Reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.