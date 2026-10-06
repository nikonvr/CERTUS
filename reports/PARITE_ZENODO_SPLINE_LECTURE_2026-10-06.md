# INDEX SPLINE contre la version publiée — lecture des écarts de moins de 30 lignes, 2026-10-06

Suite de `PARITE_ZENODO_SPLINE_2026-10-05.md`. Méthode : pour chaque fonction qui diffère (sans docstring ni
commentaire, `ast.unparse`), le diff publié → courant est lu quand il fait au plus 30 lignes. Ce n'est **pas** la
lecture des 58 fonctions de calcul : les écarts plus longs (`SplinePWLObjective._compute_analytic_gradient`,
`worker_spline_auto_clean_knots`, `worker_spline_autoshift_delta_ns`, `_spectral_polish_node_mesh_profile`,
`SmartInitPreviewManager.open_curve_editor` et d'autres) restent à lire. Rien ici n'a été exécuté : c'est une lecture
de code, sans mesure.

## Remaniements sans effet sur le calcul (la grande majorité)

Annotations (`'SplineOptConfig'` → `SplineOptConfig`), `int(round(x))` → `round(x)`, `int(len(x))` → `len(x)`, ordre des
imports, variables inutilisées préfixées `_`, `setattr(cfg, 'a', v)` → `cfg.a = v`, `QSettings` → `certus_settings`,
`open(path, 'w')` → `atomic_open(path, 'w')` (règle du dépôt), français → anglais dans les journaux et les infobulles,
`k_clip_hi` par défaut passé par `_K_CLIP_HI_DEFAULT` (même valeur : `min(0.99, K_MAX_LIMIT)`).

## Changements de comportement, par ordre d'intérêt

| fonction | ce qui change | lecture |
|---|---|---|
| `_detect_corridor_spike` (`certus_corridor_utils.py`) | tolérance `max(tol, 3σ)` au lieu de `4σ` ; un saut compte comme pic dès un rapport de 2,5 (3,0 publié) **ou** si `rm > prédit + max(2·tol, 4σ)` ; rend aussi σ | détecte plus de pics : retouche d'un réglage heuristique du parcours du corridor, pas une correction |
| `_corridor_profile_walk_side` (`certus_corridor_exploration.py`) | si σ dépasse 1,5 fois la tolérance, pousse `maxfun` ×1,5 (jusqu'à 2 000) et `n_starts` +1 ; relance avec `n_starts` ≥ 4 au lieu de 3 ; retire le point rejeté de l'historique | plus de calcul par point douteux ; même famille que le précédent |
| `enforce_min_k_corridor_half_width` (`certus_corridor_utils.py`) | un k de référence plus court que le corridor est complété par NaN, un plus long est tronqué, et les NaN restants sont remplacés par le milieu du corridor | correction : la version publiée pouvait laisser des NaN dans la référence |
| `SmartInitPreviewManager.recalculate` | l'échelle du tracé couvre l'expérience et la théorie, avec une marge minimale | affichage |
| `SmartInitPreviewManager.run_fast_local_search` | `_run_single_spline_stage` reçoit un événement d'arrêt et un rappel de progression factices | adaptation à une signature qui a changé ; non vérifié que l'arrêt est bien inerte |
| `_RunMixin._on_run` | `self._save_undo_state()` n'est plus appelé au lancement | l'état d'annulation n'est plus sauvegardé à chaque calcul : à confirmer comme voulu |
| `_eval_adaptive_abs_tolerance` | une affectation locale de `rmse_thresh_active` est supprimée | probablement une variable morte ; non vérifié |
| `_log_index_spline_best_config` | le journal ajoute les longueurs d'onde des nœuds | journal |

## Ce que cette lecture ne dit pas

Si le retour à 3σ / 2,5 et les relances plus généreuses améliorent le corridor : seul un run sur un cas réel le
dirait. Le gradient analytique (désactivé dans la version publiée), le nettoyage des nœuds et le décalage de Δn sont
dans les écarts longs, non lus.
