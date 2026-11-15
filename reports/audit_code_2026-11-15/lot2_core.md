# Lot 2 — `certus/core/` (revue du 2026-11-15)

Lecture seule, rien exécuté. VÉRIFIÉ = établi en lisant le code ; aucune ampleur mesurée.

## 1. Périmètre lu

- **En entier** : `certus_strat_robustness_task.py`, `certus_strat_robustness_noise.py`, `..._diagnostics.py`, `..._gate.py`, `..._wrappers.py`, `certus_design_memetic.py`, `certus_strat_index_share.py`.
- **En partie** : `certus_strat_local_search.py` (90 %), `certus_strat_consensus.py` (50 %, dont ELITE), `certus_re_objectives.py` (45 %), `certus_strat_config.py` (45 %), `certus_strat_robustness_slit.py` (40 %), `certus_strat_robustness.py` (35 %), `certus_core.py` (25 % : Numba, TBB, pools), `certus_index_objectives.py` (17 %), `certus_design_orchestrator.py` (8 %).
- **Survolé** (grep) : le reste.
- **≈ 16 % des 30 500 lignes lues.**

## 2. Notes

- **Exactitude — 6/10 (moyenne).** + C2 tenu partout où j'ai lu : tirages fonction de (graine, niveau) seuls, mélange multiplicatif (`certus_strat_robustness_noise.py::_get_cached_sobol_noise`, `_signal_noise_stream_seed`) ; + borne de Clopper-Pearson exacte (`certus_strat_robustness_gate.py::crash_rate_lower_bound`) ; − M1, m1, m2.
- **Tests — 7/10 (moyenne).** + 206 fichiers de test citent `certus.core` ; + `tests/unit/test_strat_local_search.py` piège la malédiction du vainqueur avec un évaluateur synthétique ; − les tests du consensus (`test_certus_strat_coherence.py`, cache hit/miss) n'essaient jamais une graine à score infini ; − rien sur `_critical_layer` hors facteurs par défaut.
- **Architecture — 5/10 (moyenne).** + aucun import PyQt6 ni `certus.ui` dans `core` (grep) ; − `certus_design_orchestrator.py::DesignOrchestrator`, dit « headless », lit `self.ui.` 150 fois et tient son état par 106 `hasattr/getattr/delattr` ; − `NUMERICAL_FAULT_EXCEPTIONS` défini trois fois, contenus différents (`certus_core.py` sans `TypeError`) ; − `_validate_phase_a_bridge_lock` déclaré dans quatre modules, utilisé dans un.
- **Lisibilité — 5/10 (moyenne).** + chaque décision porte sa date et sa mesure (`_filter_finite_robustness_scores`, `_crash_gate_rejects`) ; − `_test_strategy_robustness_task` : 794 lignes, 15 arguments, moitié récit ; − commentaires faux : « Threshold at 1% » face à `CRASH_RATE_TOLERANCE = 0.05` ; `_worst_layer_swing` dit lire le niveau nominal et lit le premier (0,5×).
- **Robustesse — 6/10 (moyenne).** + `_filter_finite_robustness_scores` ne rend jamais vide et annonce le régime dégénéré ; + `_resolution_noise_factor` refuse une fente inconnue au lieu d'interpoler ; − M1, m3, m4, m5.
- **Performance — 7/10 (faible).** + `build_M_before_cache` partagé, `compute_layer_profile=False` au consensus et au halving ; + sélecteurs-vues dans `_global_evaluate_oblique_physics` ; − pools incohérents : `cpu_count()//2` dans `_execute_robustness_tasks`, `cpu−2` au consensus et à ELITE, chacun × 4 fils Numba (`task_numba_threads`).
- **Reproductibilité — 8/10 (moyenne).** + graines de la recherche locale disjointes et décalées à chaque tour (`SEARCH_SEED_OFFSET`, `ROUND_SEED_STEP`) ; + cache Numba nommé par ses sources (`certus_core.py::numba_cache_key`) ; − `_slit_bias_profiles` met `id(db_local)` dans sa clé de cache (adresse réutilisable).

## 3. Défauts

**Critique : aucun trouvé.**

**Majeur (1)**

- **M1 — `certus_strat_robustness.py::run_final_simulation_block` (`_apply_consensus_ranking_inplace`) avec `certus_strat_consensus.py::_store_and_consume_consensus_score`.** Une graine au score `inf` (rejet par la porte de plantage) est jetée ; moyenne, écart-type et « worst » portent sur les graines restantes et remplacent `robustness_score`. Si toutes sont `inf`, le candidat garde son score de base, comparé à des scores de consensus alourdis de 0,35 σ. Scénario : plantage 4 % à la graine 42, 6 % à la 43 (rejetée), 4 % à la 44 → score fini sur deux graines, classé, possiblement premier ; `n_samples = 2` n'est lu que par l'option `certus_strat_rate_post.py::rank_complete_first`. Consensus actif par défaut. VÉRIFIÉ ; fréquence non mesurée.

**Mineur (6)**

- **m1 — ELITE** : `certus_strat_ranking.py::_resolve_elite_nominal_and_target_threshold` et la porte `full_rmse` de `_apply_elite_refinement_if_enabled` prennent le p95 du niveau de bruit absolu le plus proche (`_extract_rmse_p95_for_noise`), alors que la tâche multiplie les niveaux par le facteur de fente de la stratégie (A18, actif par défaut). Enfant à 1 nm : on lit son niveau 0,5× ; le halving lisait son 1×. Admission biaisée ; score final intact. VÉRIFIÉ.
- **m2 — `_test_strategy_robustness_task`** normalise `critical_layer` et `margin_by_layer` par `noise_levels[len//2] / 100` : faux en mode `thickness_tolerance_nm` (bruit en nm, champ de l'UI) et si les facteurs ne sont pas croissants (« 1,0.5,2 » → marge doublée, verdict « impossible » à tort). Trois définitions du nominal coexistent (`nominal_level_index`, `_resolve_nominal_noise_level`, le milieu). VÉRIFIÉ.
- **m3 — `certus_strat_robustness.py::_attach_slit_profiles`** : `except Exception` muet, la stratégie est jugée sans biais de fente, donc « meilleure que le même plan jugé comme les autres » (sa propre docstring) ; seul un compte agrégé en INFO. Chemin VÉRIFIÉ, déclenchement non observé.
- **m4 — politiques d'exception divergentes** : `_execute_robustness_tasks` attrape `Exception` (stratégie perdue, journal), consensus et ELITE n'attrapent que `NUMERICAL_FAULT_EXCEPTIONS` de `certus_core` : une longueur d'onde absente de `clues_at_wl` (`_IdxWrapper` rend `None`, d'où `TypeError`) arrête tout le run dans ELITE. VÉRIFIÉ.
- **m5 — `certus_re_objectives.py::_global_compute_re_mse_gradient`** remet à zéro `ctx.grad_raw_buf`, partagé entre les fils de différences finies, à chaque appel même sans gradient ; sans effet tant que tout appel concurrent jette `grad`. SOUPÇONNÉ (latent).
- **m6 — `crash_rates_by_noise`** est clé par la valeur absolue, re-échelonnée, du bruit ; `ui/certus_strat_table_ui.py` lit la clé `"1"` : avec `trigger_tolerance` 0,05 le taux nominal n'est jamais affiché ; avec 0,5 (défaut du code) il afficherait le niveau 2× sous l'étiquette 1×. VÉRIFIÉ.

## 4. Bien fait

- Recherche locale : règle appariée, contrôle sur graines fraîches, repli confirmé sur d'autres graines (`certus_strat_local_search.py::joint_local_search`, `_judge`).
- Porte de plantage fondée sur l'incertitude du comptage, inactive par défaut (`_crash_gate_rejects`, C1).
- Tranche de bruit bornée, refus explicite hors bornes (`_test_strategy_robustness_task`).
- Mémétique parallèle sans état partagé hors un compteur verrouillé (`certus_design_memetic.py::run_memetic`) ; tampon par fil côté DESIGN (`certus_design_core.py::_EP_BUFFER_TLS`).

## 5. Recommandations

1. **M1** : une graine `inf` rend le consensus `inf`, ou incomplet et classé après les complets sur le chemin par défaut ; test qui échoue sur le code actuel. ~2 h, décision du propriétaire.
2. **Un seul « nominal »** : l'index du facteur 1 partout (tâche, ELITE, clé de `crash_rates_by_noise`), lu par index, jamais par valeur. ~½ jour (m1, m2, m6).
3. **Une seule politique d'exception** : un seul `NUMERICAL_FAULT_EXCEPTIONS` ; tout `except` large de STRAT journalisé en WARNING et marqué dans le résultat (m3, m4). ~3 h.
