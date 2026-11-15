# Lot 1 — `certus/physics`, `certus/domain`, `certus/metal`, `certus_physics` (revue du 2026-11-15)

Lecture seule : rien exécuté. Un chiffre marqué « à la main » est estimé, non mesuré.

## 1. Périmètre lu

- **En entier** : `certus_opt_tmm.py`, `certus_tmm_backside.py`, `certus_substrate_absorption.py`, `certus_oblique_substrate.py`, `certus_inputs.py`, `certus_strat_math.py`, `certus_strat_dp.py`, `certus_optical_models.py`, `domain/constants.py`, `domain/spectral_weights.py`, `refractive_index.py`.
- **En partie** : `certus_tmm_matrix.py` (95 %), `certus_tmm_single_layer.py` (50 %), `certus_tmm_oblique.py` (35 %), `design_fast_normal.py` (30 %), `certus_optimizers.py` (25 %), `certus_colorimetry.py` (calculs), `certus_material_db.py`, `certus_metal_single_physics.py`, `materials_data.py` ; moins de 10 % de `gradient_analytic.py`, `certus_strat_growth.py`, `certus_strat_readings.py`, `gradient_metal.py`.
- **Survolé** (fonctions, grep) : le reste, dont `gradient_oblique.py`, `certus_strat_batch.py`, `certus_opt_needle.py`, les `*_app.py` de `metal/`.
- **≈ 25 % des 22 800 lignes lues** ; structure de ≈ 60 %.

## 2. Notes

- **Exactitude numérique — 7/10 (moyenne).** + `certus_opt_tmm.py::compute_RT_from_matrix` est bien la source unique (appelée par `compute_TMM_generic`, `certus_tmm_oblique.py::_oblique_rt_absorbing_exit`) ; + `certus_oblique_substrate.py::oblique_exit_admittance` prend l'admittance complexe d'un substrat absorbant (racine dans le bon quadrant pour k > 0) ; + `certus_optical_models.py::extinction_from_epsilon` évite la cancellation sur k ; − ε1 Tauc-Lorentz écrêté dans le coût seulement (M1).
- **Tests — 7/10 (moyenne).** + `tests/oracle/test_tmm_oracle.py` contre une référence indépendante : s/p, absorbants, conservation, absentee ; + gradients contre différences finies (`test_gradients_vs_finite_differences.py`, `test_metal_gradient_vs_fd.py`) ; − aucun test ne compare `epsilon1_TL_analytic` à `_compute_epsilon1_gradient_kernel` ; − angle mort du cliquet (m1).
- **Architecture — 5/10 (moyenne).** − `certus_metal_common.py` importe PyQt6 et porte `elevate_spline_knots` ; − `certus_optimizers.py::PGlobalOptimizer._dispatch_and_collect` importe `certus_physics.structures`, qui importe `certus.core.certus_core` ; − `certus/domain/optical/` (≈ 850 lignes) n'a aucun importeur hors tests ; − la combinaison incohérente de face arrière est réécrite dans cinq fonctions (`calculate_RTRback_incoherent_vectorized`, `calculate_RT_with_backside_fused`, `_apply_exact_backside_generic`, `apply_exact_backside_combination` sans appelant, `_calculate_RT_absorbing_sub_single`).
- **Lisibilité — 6/10 (moyenne).** + docstrings qui donnent la raison et la mesure (`certus_strat_math.py::calculate_level_margins_to_extrema`, `certus_strat_growth.py::detect_turning_points`) ; − fichiers de 1 800 lignes ; − constantes magiques (`4096 + m` dans `certus_strat_readings.py::_machine_grid_signal`, `min(10, bl_count)` dans `certus_strat_dp.py::_dp_kernel`) ; − commentaires de doute restés (`certus_tmm_single_layer.py::calculate_transmission_single`).
- **Robustesse — 7/10 (moyenne).** + `certus_inputs.py` refuse à la porte polarisation inconnue, angle > 90°, NaN, couche en dépassement ; + `gradient_utils.py::FASTMATH_SAFE` préserve les tests de finitude des coûts ; − R et T écrêtés dans [0, 1] sans trace (`calculate_RT_with_backside_fused`) ; − `PGlobalOptimizer._evaluate_batch` avale trois exceptions sans journal.
- **Performance — 8/10 (moyenne).** + forme close par lecture (`certus_strat_readings.py::layer_scan_coeffs`) ; + `SplineBasisCache` LRU borné ; + `PGlobalOptimizer._inner_numba_threads` contre la sursouscription ; − allocations dans des `prange` (`calculate_RT_with_backside_fused`, `calculate_level_margins_to_extrema`).
- **Reproductibilité — 6/10 (moyenne).** + `certus_strat_math.py::_seeded_noise_sample` est pure, indexée par couche et lecture : C2 tenu dans ce que j'ai lu ; − `PGlobalOptimizer` (m5) ; − `materials_data.py::_load_si_data` préfère un classeur local non versionné au classeur versionné.

## 3. Défauts

**Critique : aucun trouvé.**

**Majeur (1)**

- **M1 — `certus_optical_models.py::epsilon1_TL_analytic`** rend `max(val, 1.0)` ; `gradient_analytic.py::_compute_epsilon1_gradient_kernel` rend ε1 brut. Le coût TLU de `certus_index_objectives` lit le premier, son gradient (`_compute_tlu_derivatives_kernel`) le second. Scénario : oscillateur fort au-dessus de E0 (le matériau « absorbing » du test TL à 5,5 eV a, à la main, un ε1 négatif) → n, k du coût calculés sur ε1 = 1, Kramers-Kronig rompu, courbe tracée et exportée fausse, gradient d'une autre fonction. VÉRIFIÉ (deux chemins lus) ; ampleur non mesurée. Annexe SOUPÇONNÉE : le repli `np.isfinite(val)` de cette fonction est sous `fastmath=True`, que le dépôt dit capable de le supprimer (E = Eg exactement).

**Mineur (6)**

- **m1** — `test_tmm_formula_has_one_source.py::functions_with_the_reflection_pair` exige un produit à gauche : `num = term1 - term2 ; den = term1 + term2` lui échappe. Copies non listées : `certus_opt_tmm.py::calculate_reflectance_bilayer_vectorized`, `gradient_metal.py::_compute_metal_tmm_gradient_kernel` (justes aujourd'hui, test oracle bilayer). Les copies de T seul (`certus_strat_math.py::_calc_T_from_matrix`) ne relèvent d'aucun cliquet. VÉRIFIÉ.
- **m2** — `design_fast_normal.py::cost_lossless_front_fast` rend 1e12 sous 5 points et saute les cibles non finies ; `_compute_gradient_lossless_front_kernel` ne fait ni l'un ni l'autre. Cible de 4 points → coût constant, gradient non nul, recherche linéaire en échec. VÉRIFIÉ ; latent, car `prepare_targets_vectorized` produit des cibles finies.
- **m3** — `gradient_analytic.py::prepare_targets_vectorized` : deux cibles qui se chevauchent, la dernière écrase l'autre sans message. VÉRIFIÉ ; garde de l'UI non vérifiée.
- **m4** — `DEFAULT_SUBSTRATE_THICKNESS_NM` (1 mm) imposé à DESIGN et STRAT : k = 4,4e-6 à 550 nm donne τ = 0,905 (1 mm) contre 0,549 (6 mm), à la main. Documenté, invisible dans le résultat. VÉRIFIÉ.
- **m5** — `certus_optimizers.py::PGlobalOptimizer` : `random_seed` vaut None par défaut ; `_dispatch_and_collect` consomme les recherches locales par `as_completed`, donc l'ordre de `add_cluster_result` et le meilleur à égalité dépendent des fils ; les réductions `prange` (`cost_lossless_front_fast`) dépendent du nombre de fils Numba, fixé par machine. SOUPÇONNÉ au bit.
- **m6** — `epsilon2_TLU_array` : la queue d'Urbach se raccorde à Eg + δ mais ne s'applique que sous Eg → saut en Eg et creux sur ]Eg, Eg + δ]. Petit (≈ 1e-4 sur ε2 à la main). VÉRIFIÉ.

Hors production : `refractive_index.py::RefractiveIndex` refuse n < 1 (métaux).

## 4. Bien fait

- Source unique R/T et cliquet structurel (`reflection_amplitudes`, `test_tmm_formula_has_one_source.py`).
- Modèle de plaque absorbante unique, continu en k (`certus_substrate_absorption.py`), exact à τ = 1.
- Validation à la porte, hors des noyaux `fastmath` (`certus_inputs.py`).
- Bruit STRAT pur et indexé physiquement (`_seeded_noise_sample`, commentaire C2 de `certus_strat_readings.py`).
- Historique mesuré dans le code (`calculate_reflection_infinite_substrate_single` : 82 points d'erreur corrigés contre l'oracle).

## 5. Recommandations

1. **Aligner ε1 TL** : une seule fonction de valeur pour coût, gradient et tracé, plus un test oracle sur un oscillateur fort (ε1 < 1). Une demi-journée ; change des bits sur le chemin actif : décision de 👤, puis `c1_diff.py`.
2. **Rendre PGlobal reproductible** : consommer les résultats dans l'ordre de soumission, graine par défaut journalisée. Une demi-journée.
3. **Durcir le cliquet** : suivre les noms liés à `E*P`, ajouter un motif `2/(B+C)` pour T. Une demi-journée.
