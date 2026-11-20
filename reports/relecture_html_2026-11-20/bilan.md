# Relecture des 15 pages HTML de `pages/` (2026-11-20)

Demande de 👤 : « relecture poussée de tous les html ». Trois passes, outils dans ce dossier (bibliothèque standard).

## 1. Mécanique — [`audit_html.py`](audit_html.py) ([sortie](audit_html.txt))

Identifiants en double, ancres sans cible, images sans `alt`, balises mal fermées, liens vides : **aucun** sur les 15
pages (toutes `lang="en"`). Sauts de niveau de titre : 2 dans `CERTUS_Optical_Theory_Guide.html` (h2 → h4), **corrigés**
(4 titres passés en h3). Les « mots répétés » relevés sont des juxtapositions de navigation, de diagrammes Mermaid et de
légendes SVG.

## 2. Code cité — [`code_names.py`](code_names.py) ([sortie](code_names.txt))

Chaque nom en `<code>` cherché dans les sources suivies. Noms disparus, **corrigés** :

| page | cité | réalité, correction |
|---|---|---|
| INDEX-SPLINE | `PGlobalOptimizer`, Basin-Hopping, `_pglobal_bounds_trust_region`, ρ 0,5 → 0,12, bornes ×2,5 aux bords | SOL 2 est **une étape L-BFGS-B locale** (`_run_single_spline_stage`) ; les champs `pglobal_trust_*` existent mais ne sont lus nulle part. §3 (diagramme), §5, §5.1 réécrits sur le pipeline réel (`PIPELINE [NN/09]`) |
| INDEX-SPLINE | SOL 3 et SOL 3b phases 03-04, « Photometric Scale Refinement [0,995 ; 1,005] » | `[03/09] Legacy free-knot stage removed` : SOL 3 ne tourne qu'en passe 2 d'Auto-Best (budgets ¼ depuis ce jour), SOL 3b n'a plus d'appelant, l'échelle photométrique n'existe plus. Notes de statut §6, §7 ; §15 et tableau §17 réécrits |
| INDEX-SPLINE | `compute_spline_pwl_objective_analytic_gradient`, `spline_photometric_scale` | `SplinePWLObjective._compute_analytic_gradient` ; ligne supprimée |
| INDEX | `SplineOptimizationWorker`, `PointwiseIRSolver` (`certus_pointwise_ir.py`), 15 + 15 + 6 nœuds | disparus : la seule spline d'INDEX est la phase 2.3 (k en log, 8 nœuds, `IRGlobalModelStrategy._run_phase23_spline_refinement`). Ligne du tableau remplacée, note de statut en tête de §7 (lue comme historique) |
| INDEX | `log_indices`, `calculate_reflection_infinite_substrate_array` | `log_clues` ; `calculate_reflection_infinite_substrate_single` |
| RE | modes batch (`full`, `refine30`, `pipeline`, `BATCH_WINNER_BASE`, `re_batch_*.json`) | aucun outil batch dans les sources (`BATCH_WINNER_BASE` n'a jamais existé que dans la page) : paragraphe, tableau et liste de contrôle réécrits |

Faux positifs vérifiés : variables d'exemples de code du guide théorique (`r_plate`, `t_plate`, `safe_cos_theta_vectorized`),
anciens noms cités comme tels dans STRAT (`strategy_idx`, `robustness_score_functional`), proposition « à mesurer »
(`crash_map`), préfixes (`RE_RE_DEADZONE_`, `k_spline_knots_`), noms CamelCase coupés par l'extracteur.

## 3. Faits et physique

| page | constat | correction |
|---|---|---|
| STRAT | tableau des repères du 21/10 | valeurs du 20/11 (`7a6fca38`) avec la colonne d'octobre et la cause des écarts 35c/36c |
| STRAT | « `strat_local_search_fresh_id=False` par défaut » | vrai depuis le 19/11 (lot 2b) |
| HUB | dépôt multiple : « ouvre le premier fichier » | demande lequel ouvrir et nomme chaque fichier écarté (UX-2) ; « batch RMSE* ranking » → classement RMSE* des runs |
| HUB, INDEX, METAL ×2 | pied « v26-04 » | v26.05 (`pyproject.toml` : 26.05.0) |
| SUBSTRATE | pôle IR par défaut | ajout de la validation sur indices mesurés (lot 2c) |
| métrologie | facteur d'amplification (n²+1)²/(2\|n²−1\|) « de 3,8 à 4,4 » pour le saphir | **faux** : minimum 4 en n = √3, 4,000 à 4,013 sur n = 1,67–1,78 ; Δnₛ ±0,0040 / ±0,0040 / ±0,0080 (au lieu de 0,0038 / 0,0040 / 0,0088). Note sous le budget §7 : sa colonne Δnₛ et ses Δn, Δk dérivés ne sont **pas recalculés** |
| guide théorique | exemple de l'argent : « NumPy donne 0,118 + 3,519i, signe faux » | **faux** : NumPy donne 0,1176 − 3,5216i, déjà la racine amortie (Im z = −2nκ < 0 en n − iκ). Le cas qui exige la correction est une couche sans pertes au-delà de l'angle critique (z réel < 0 : NumPy +0,663i pour z = −0,44). Paragraphe, exemple, tableau des risques et légende SVG corrigés ; le code de correction était juste |

Vérifié exact : exemple de référence à 5 couches du guide théorique (12 valeurs R, T et l'absorbé 0,08466 reproduits au
6ᵉ chiffre par le code actuel) ; convention n − iκ partout (15 mentions, aucune n + iκ) ; chiffres des pages
« rapport complet » et « Swanepoel » ; rapport R/T 0,15, R ≈ 14 %, formules de Swanepoel et facteurs de dégradation de la
métrologie ; défauts DESIGN (polisseur `lbfgs_then_lm`, 200 tirages, σ = 2 nm, D = 1 mm), FIELD
(`analytic_gradient`, `min_field_active` faux), METAL (nœuds [0, 10], pas 0,5 nm, `analytic_polish` faux).

## Limites

Lecture intégrale : HUB, SUBSTRATE, métrologie, « rapport complet », Swanepoel, parties citées des autres. Pour DESIGN,
FIELD, METAL, RE, INDEX, INDEX-SPLINE, STRAT (487 Ko), APPLIED_OPTICS : contrôles ciblés (noms de code, défauts,
repères, convention), pas une relecture phrase à phrase. Le rapport du 14/08 cité en provenance dans STRAT
(`reports/Report_STRAT_JSON-strat-bandpass-5cav-99c_20260814_…`) n'est pas dans le dépôt. Rendu Mermaid et MathJax
non vérifié dans un navigateur.
