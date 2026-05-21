# To-Do List : Refactoring `spline_profile_corridors.py`

## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 & Objectif Bonus) complété et validé par pytest.

### Il reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.

## Phase 3 : `_setup_corridor_context` (684 lignes)
- `[x]` **Analyse AST :** Exécuter le script d'analyse sur `_setup_corridor_context` pour extraire les dépendances de `_emit_live_profile` et `_push_live_point`.
- `[x]` **Extraction Live Stream :** Créer la classe `CorridorLiveStreamer` pour encapsuler `live_d_vals`, `live_rmse_vals` et le `live_cb`.
- `[x]` **Extraction Adaptive Threshold :** Déplacer la logique massive de fallback `adaptive_abs_meta` vers une méthode statique dédiée.
- `[x]` **Refactoring Main :** Remplacer les blocs de la fonction principale et réduire sa taille sous les 200 lignes.
- `[x]` **Verification**
  - `[x]` Run `pytest tests/unit/test_certus_index_callbacks.py`.
  - `[x]` Run entire unit test suite.

## Objectif bonus si avance rapide : `compute_regular_grid_rmse_profile` (950 lignes)
- `[x]` Identifier les 6 closures internes.
- `[x]` Créer une Dataclass pour injecter le contexte.
- `[x]` Déporter les closures en méthodes statiques.


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