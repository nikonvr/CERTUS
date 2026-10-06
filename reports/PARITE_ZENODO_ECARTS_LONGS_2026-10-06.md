# Parité avec les versions publiées — écarts longs de l'INDEX SPLINE et capacités du RE, 2026-10-06

Suite de `PARITE_ZENODO_SPLINE_2026-10-05.md`, `PARITE_ZENODO_SPLINE_LECTURE_2026-10-06.md` et
`PARITE_ZENODO_RE_2026-10-05.md`. Versions publiées : `certus_index_spline` « 1.1-revised » (licence MIT,
`optics continuum/05_CODE_ET_ZENODO/zenodo_release`) et `certus_re` 1.2.0.dev0 (`publication_reverse/07_PAQUET_ZENODO`).
Code courant : `certus0310`, branche de la PR #7 (`a4a48fe5`). Les diffs sont faits sur `ast.unparse`, sans docstrings
ni commentaires. Les chiffres marqués « mesuré » sortent d'une exécution du 2026-10-06 ; le reste est de la lecture.

## INDEX SPLINE

| écart | ce que fait chaque version | lecture |
|---|---|---|
| gradient analytique de l'objectif (`spline_pwl_analytic_grad_supported`, `SplinePWLObjective._compute_analytic_gradient`) | publiée : toujours `False`, différences finies partout ; courante : analytique, sauf avec `n_mono_band_nm` | **juste dans la version courante, mesuré** : la différence finie centrée converge vers le gradient analytique quand le pas grandit (écart relatif de 4e-9 à 6e-6 à h = 1e-3 et 1e-4) en transmission, réflexion et R + T, K = 3 (`pwl`), 4 et 6 (`smooth`), d = 120 et 380 nm. À h = 1e-7, l'arrondi domine (coût de 50 à 120 sur ces données synthétiques, composantes de 1e-6 à 1e-4) : c'est ce pas qui faisait croire à des écarts de 1e-4 à 8e-3. `tests/oracle/test_spline_gradient_vs_fd.py` ne couvre que la transmission à d = 120 nm |
| `_run_single_spline_stage` | publiée : descente locale obligatoire puis polissage L-BFGS-B ; courante : la même chose | **même comportement** : `local_only = True` est écrit en dur dans la version courante, le bloc `if local_only:` se termine toujours par un `return`, et la branche PGlobal qui le suit (43 instructions, 274 lignes du fichier : PGlobal, polissage, repli) est inatteignable ; la version publiée l'a retirée |
| `_spectral_polish_node_mesh_profile` | même logique ; la version courante l'a extraite dans `_run_mesh_polish_minimizer` | remaniement ; avec le gradient analytique, la version courante polit à `ftol` 1e-11 et `gtol` 1e-8 (1e-9 et 1e-6 avec les différences finies, le seul chemin de la version publiée) |
| nettoyage, décalage de Δn et insertion de nœuds (`worker_spline_auto_clean_knots`, `worker_spline_autoshift_delta_ns`, `insert_manual_sigma_nodes` et dix autres) | publiée : fonctions vides (`pass`) ; courante : implémentées | capacités retirées de la publication ; rien à reprendre de la version publiée |
| six fonctions de la seule version publiée | `_plot_corridor_tab` et `_build_corridor_tab_rmse_controls` existent dans la version courante, déplacées (`certus_index_spline_corridor_tab.py`, mixin des corridors) ; `_emit_live_profile`, `nonlinear_alpha_view`, `w2s`, `_prepare_free_knot_problem` ne sont appelées nulle part dans la version publiée | rien ne manque |
| éditeur de courbes de Smart Init (`SmartInitPreviewManager.open_curve_editor`) | publiée : boîte modale qui rend n, k et l'épaisseur ; courante : édition en direct par rappels sur les curseurs, n entre 1,0 et 3,3 | deux conceptions ; l'épaisseur a son propre curseur dans l'aperçu courant |
| `CorridorContextBuilder._process_center_solution` | même calcul, fonctions extraites | remaniement (échantillon du 2026-10-05) |

**Conclusion pour l'INDEX SPLINE.** Aucune amélioration de la version publiée ne manque au code courant. Le code courant
garde les capacités que la version publiée a coupées ; parmi elles, le gradient analytique est vérifié ici contre les
différences finies, dans des cas que le test oracle ne couvre pas.

## RE

| capacité de `certus_re` | dans `certus0310` | lecture |
|---|---|---|
| substrat silicium, formule de Li (1980), refusée hors de 1,2–6 µm (`dispersion.silicon_li1980`) | table `Si-substrate` d'`indices.xlsx` : au-delà de 1200 nm, la formule de Salzberg et Villa (1957) | **mesuré** : la table de CERTUS moins la formule de Li vaut de −2,0e-3 à +4,5e-3 (moyenne −2,7e-4) sur 1200–5200 nm, 246 points ; +4,5e-3 à 1200 nm, −1,8e-3 à 4000 nm. `certus_re` chiffre lui-même un écart de cet ordre à 0,02 point rms sur ses spectres calculés |
| substrat saphir, rayon ordinaire (`dispersion.sapphire_malitson`) | mêmes coefficients (`certus_substrate_db.py`, n° 3) | même indice. **La citation de `certus_re` est fausse** : ses coefficients (1,4313493 ; 0,65054713 ; 5,3414021) sont ceux de Malitson et Dodge (1972) ; il cite Malitson, *J. Opt. Soc. Am.* 52, 1377 (1962), dont le jeu est autre (1,023798 ; 1,058264 ; 5,280792 ; base refractiveindex.info, lue le 2026-10-06) |
| a priori procédé (MAP) de 0,5 % (`solve.invert`, `process_prior_pct`) | pénalité QWOT : Q = (4/λ_ref)(n·d − n_nom·d_nom) par couche, zone morte de ±0,01 QWOT, poids α = 0,05 dans √(RMSE_sp² + α·RMSE_QWOT²) | deux régularisations vers le nominal, de formes différentes : l'a priori de `certus_re` est gaussien, relatif, sans zone morte, et s'ajoute aux résidus des mesures. Il n'est pas porté ; le porter changerait les résultats du RE |
| échantillon revêtu sur les deux faces (`physics.assemble_plate`) ; résidus par voie (`report.text_report`) | absents | non portés (inventaire du 2026-10-05) |

## Ce qui reste à décider, à 👤

1. Retirer la branche PGlobal inatteignable de `_run_single_spline_stage` (aucun bit ne bouge, elle ne s'exécute
   jamais), ou la garder pour la rebrancher un jour.
2. Porter l'a priori MAP de `certus_re` dans le RE de CERTUS, à la place ou à côté de la pénalité QWOT.
3. Corriger la citation du saphir dans le paquet `certus_re` publié (hors de ce dépôt).
