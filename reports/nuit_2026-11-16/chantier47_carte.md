# Chantier 47 — carte des chemins de l'épaisseur du substrat (2026-11-17)

Relevé par `rg` sur les fichiers suivis ; rien n'est modifié. `DEFAULT_SUBSTRATE_THICKNESS_NM` = 1000000.0, en nm
(`certus/physics/certus_substrate_absorption.py`).

## Noyaux qui prennent déjà `substrate_thickness_nm`

`calculate_RT_with_backside_fused`, `calculate_RT_vectorized_real`, `calc_spectrum_full_exact` (`certus_tmm_matrix.py`) ;
`calc_spectrum_oblique_backside_vectorized`, `calc_spectrum_full_oblique_exact` (`certus_tmm_oblique.py`) ;
`precompute_oblique_optical_terms` (`design_fast_oblique.py`) ; `compute_oblique_backside_bundle_analytic`
(`gradient_oblique.py`) ; `calculate_RTRback_incoherent_vectorized` (`certus_opt_tmm.py`) ; `apply_plate_loss`.

## Appels qui ne la transmettent pas (prennent 1 mm)

| zone | appels |
|---|---|
| DESIGN, cœur | `core/certus_design_core.py:483` (`apply_plate_loss`), `:632`, `:717` (`calc_spectrum_full_exact`) ; `workers/certus_design_engine.py:169` |
| DESIGN, utilitaires | `core/certus_design_worker_utils.py:51`, `:63`, `:973` |
| DESIGN, workers | `workers/certus_design_workers_strat.py:444` ; `workers/certus_design_workers_needle_strat.py:57` ; `workers/certus_spectral_workers.py:496`, `:518`, `:529` |
| gradients | `physics/design_fast_normal.py:869` ; `physics/gradient_oblique.py:1176` ; `physics/gradient_utils.py:118` |
| enveloppes | `physics/certus_tmm_hl.py:114` ; `physics/certus_tmm_matrix.py:345`, `:625` ; `core/_certus_physics_impl.py:1213` (fichier `DO NOT SPLIT`) |
| RE | `utils/certus_re_helpers.py:276`, `:1915` |
| METAL simple | `metal/certus_metal_single_physics.py:196`, `:408` ; `ui/certus_metal_single_gui.py:253`, `:781`, `:969` |

## STRAT

Les noyaux STRAT (`certus_strat_batch.py`, `certus_strat_growth.py`) ne lisent que `n_sub.real` pour la face arrière :
le substrat y est **non absorbant**, l'épaisseur n'y agit pas. L'y exposer, c'est d'abord ajouter la perte de la plaque
aux noyaux STRAT, un changement de modèle (C1 : inactif par défaut, bits identiques).

## Ordre proposé (un commit chacun, C1 au bit par `c1_diff.py`)

1. Une clé de configuration DESIGN `substrate_thickness_mm` (vide = 1 mm), lue une fois et passée en `substrate_thickness_nm`.
2. Les enveloppes et gradients ; 3. les workers DESIGN et l'affichage (même valeur, sinon optimisation et affichage divergent) ;
4. le champ dans l'interface DESIGN ; 5. RE et METAL simple ; 6. STRAT, après décision de 👤 sur le modèle.

Décisions de 👤 : unité et place du champ ; STRAT dans ce chantier ou à part ; METAL et RE dans ce chantier ou à part.
