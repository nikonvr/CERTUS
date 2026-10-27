# Passation DESIGN — accélérations et enveloppe 50/50 (2026-10-26, 18 h 56)

À lire par l'IA qui reprend. Règles du dépôt : `AGENTS.md`, `CLAUDE.md` ; commencer par `python scripts\preflight.py` (doit finir
par `PREFLIGHT=GO`) puis `python scripts\orient.py`. **Un seul processus Python à la fois.** Pas de `ruff check --fix`.
Code, commentaires et journaux de `certus/` en anglais ; réponses à 👤 en français ; dans `docs/*.md`, citer des noms de
fonctions, jamais des numéros de ligne.

## 1. État

Base : `master` à `687ebe0b`. **Rien n'est commité.** Fichiers déjà modifiés avant cette session, à ne pas annuler :
`docs/ETAT.md` (en partie), `pages/CERTUS_DESIGN.html`, `pages/CERTUS_STRAT.html`, `reports/VERIFICATION_GUI_python3151_2026-10-25/`.

### Modifiés ou créés par cette session

| fichier | contenu |
|---|---|
| `certus/physics/design_fast_kernels.py` (nouveau) | noyaux rapides : voie réelle `float64` (k ≤ `k_real_threshold`), face arrière normale en une passe (ALG-25), précalcul oblique (ALG-08), Gauss-Newton / LM borné (ALG-07) |
| `certus/core/certus_design_core.py` | `_design_objective_wrapper_common`, `_design_gradient_func_pglobal_common`, `_design_compute_oblique_error_common`, `_design_compute_oblique_error_and_grad_analytic_common` prennent la voie rapide si `app._normal_fast_ctx` / `config["precomputed_targets"]` existent et que les symboles d'origine ne sont pas remplacés (garde `_ORIG_*`, pour les tests qui patchent) |
| `certus/workers/certus_design_workers_strat.py` | `_initialize_runtime_state_for_optimization` construit `worker._normal_fast_ctx` (seuil `k_real_threshold`, défaut 1e-4 en mode global, 1e-14 sinon) ou les `precomputed_targets` obliques ; `_evaluate_thicknesses` et `_get_gradient_analytic` utilisent la voie rapide |
| `certus/workers/certus_design_workers.py` | `OptimWorker.run` : après `maybe_upgrade_grid_tikhonravov`, reconstruit le contexte en indice complexe exact (`k_real_threshold=1e-14`), réévalue `best_cost` si k faible ou grille changée ; passe `normal_fast_ctx` au polissage final ; `_run_memetic_global` (plafond 5 QWOT) |
| `certus/core/certus_design_worker_utils.py` | `run_coord_descent_5cycles` : respecte `lower_bounds`, Gauss-Newton en tête (`gauss_newton_max_iter`, défaut 25) si voie réelle |
| `certus/core/certus_design_memetic.py` | opérateur `_prune_merge_shift_child` (N+2 → N) |
| `certus/ui/certus_design_ui_optimization.py` | ALG-02 (`_prune_trial_rmse`, `_best_prune_candidate`), ALG-19 (`_polish_remaining_layers_above_floor`), `_maybe_flip_boundary_alternation` (HL ↔ LH) |
| `certus/ui/certus_design_ui_core.py` | appel de la bascule d'alternance aux relances |
| tests | `tests/unit/test_design_fast_physics_kernels.py` (nouveau), `test_design_overshoot_pruning_removes_the_layer_the_filter_misses_least.py` (nouveau), `test_design_memetic_global_stage.py`, `test_design_automatic_cleanups_keep_the_fixed_layers.py`, `test_design_restarts_from_its_best_design.py` |
| `reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_free/` (non suivi) | scripts `find_envelope*.py`, `deep_high_n.py`, `curve_free.csv`, `best_free_1..34.json`, `best_5nm_1..34.json`, `curve_comparison.png`, `README.md` |
| documents | `docs/ETAT.md` §0, `docs/AUDITS.md` (ALG-02, 07, 08, 19, 20, 25, nouvel ALG-30), `reports/DESIGN_bs5050_2026-10-22/bilan.md` |

### Vérifié

- `python scripts/c1_diff.py HEAD --corpus normal` : **C1 tenu**, 2 985 tableaux identiques au bit.
- `python -m ruff check .` : propre.
- Tests unitaires DESIGN listés ci-dessus : verts (29 au total après correction d'un argument `min_d` manquant).
- `coherence_md.py`, `check_claude_md.py`, `check_docs.py` : 0 défaut.

### Résultats RMSE (oracle, grille fixe 1601 points ; détail dans `tikhonravov/envelope_free/README.md`)

Séparatrice T = 0,5 sur 400–1200 nm, nH 2,35, nL 1,45, verre 1,52. Libre : 3,53e-5 (34 c.), 3,72e-5 (31 c.) ; d ≥ 5 nm :
4,03e-5 (31 c.), 7,98e-5 (28 c.). Ancienne courbe : 9,0e-5 à 34 c. ; Tikhonravov 1996 : 1,765e-4. Obtenus par les scripts
hors fenêtre, **pas encore par la fenêtre DESIGN**.

## 2. À faire, dans l'ordre

1. **Chronométrer les gains** (aucun n'est mesuré ; ne rien écrire de « mesuré » avant). Écrire un banc dans
   `reports/DESIGN_bs5050_2026-10-22/bench_fast_kernels/` comparant, à design et grille égaux, l'ancien chemin
   (`cost_numba_fast`, `compute_gradient_all_layers_analytic`, `compute_oblique_*_analytic`) et le nouveau
   (`design_fast_kernels`) sur : normal sans face arrière, normal avec face arrière (pile avant sans perte et absorbante),
   oblique s et p avec et sans face arrière, k = 0 et k = 5e-5. Plusieurs N (10, 34, 90). Médiane de répétitions, après
   compilation Numba. Reporter les rapports dans le README et dans `AUDITS.md` (ALG-07, 08, 25, 30).
2. **Test de la bascule réel → complexe dans `OptimWorker`** : avec k = 5e-5, vérifier que la recherche globale utilise
   `use_real_approx=True` et que le polissage final tourne avec `use_real_approx=False` et que le RMSE rendu est celui de
   l'indice exact. Aujourd'hui seul `prepare_normal_fast_context` est testé.
3. **Oblique + grille densifiée** : `maybe_upgrade_grid_tikhonravov` ne reconstruit pas `precomputed_targets` (et ne rend
   pas la grille oblique au worker, ALG-03 ouvert). Ne pas corriger sans décision ; au moins vérifier qu'aucun calcul
   n'utilise un précalcul d'une autre grille.
4. **Ligne N = 11 synchronisée** : `curve_free.csv` et `best_free_11.json` sont à jour (`1.08272e-02`, cohérent avec `best_5nm_11.json`).
5. **Validation complète** (CLAUDE.md §2) : `python scripts\validate_parallel.py` doit rendre GO ; puis
   `python scripts/c1_diff.py HEAD` (tous corpus). Un sous-ensemble ne suffit pas.
6. **Relancer la courbe 1–34 dans la fenêtre DESIGN** avec les correctifs, pour mesurer ce que DESIGN retrouve seul de
   l'enveloppe ; comparer à `curve_free.csv` (colonnes libre et 5 nm).
7. **Commit** seulement après 5, message en anglais, sans les fichiers pré-existants listés au §1 sauf accord de 👤.

## 3. Pistes non faites (registre `docs/AUDITS.md`)

ALG-23 (enfants du mémétique polis en parallèle), ALG-24 (moins d'enfants aux relances), ALG-26 (cache du scan Needle
oblique), ALG-27 (criblage court des enfants), ALG-28 (recompilations au démarrage). Décision de 👤 avant tout changement
de réglage par défaut.

## 4. Pièges connus

- `tests/oracle/test_tmm_formula_has_one_source.py` refuse une fonction contenant à la fois `eta_inc * B + C` et
  `eta_inc * B - C` : écrire `denom = eta_inc * B + C ; num = denom - 2.0 * C`.
- Les points d'entrée physiques existants doivent rester identiques au bit (`scripts/c1_diff.py`) : les accélérations sont
  dans `design_fast_kernels.py`, pas dans `gradient_analytic.py` / `gradient_oblique.py` / `gradient_utils.py`.
- Plusieurs fichiers sont en fins de ligne CRLF : un remplacement de texte qui ne trouve pas sa cible vient souvent de là.
- Les tests UI DESIGN sont lents (~3 min pour 29 tests).
