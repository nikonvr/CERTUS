# Vérification du travail d'Antigravity Argon du 2026-10-26 (Claude Opus 5.5, nuit du 26 au 27)

Objet : l'arbre de travail non commité sur `687ebe0b`, décrit par `reports/DESIGN_bs5050_2026-10-22/PASSATION_2026-10-26.md`.
Ce que l'agent a fait, d'après ses md (`docs/ETAT.md` §0, `docs/AUDITS.md` ALG-02/07/08/19/20/25/30, `bilan.md` du 50/50) :
**accélérer les calculs DESIGN** (noyaux `float64` sans perte, face arrière normale précalculée, oblique précalculé,
Gauss-Newton) et **pousser l'enveloppe Tikhonravov 50/50** (3,53e-5 à 34 couches libres, hors fenêtre). Ici, ce qui est mesuré.

## 1. Validation CLAUDE.md §2 (Python 3.15.1, arbre de travail)

| étape | résultat |
|---|---|
| preflight · ruff | GO · propre |
| oracle | 1160 passed |
| unit | **1 failed**, 5723 passed — `test_the_architecture_debt_only_shrinks[fichiers_longs]` : `design_fast_kernels.py` 1972 lignes > 1500 |
| ui | 1342 passed |
| reste | **1 failed**, 349 passed — `test_code_duplication::test_no_ultra_fine_duplicates` : bloc copié de `gradient_oblique.py` dans `design_fast_kernels.py` |
| coherence_md · check_claude_md · check_docs | 0 · 0 · 0 |
| `c1_diff.py HEAD` (tous corpus) | C1 TENU, 9092 tableaux identiques au bit |

La passation dit « validation complète non faite » : exact, et elle n'est pas verte. **Non commitable en l'état.**

## 2. Exactitude des nouveaux noyaux, contre l'oracle indépendant `tests/oracle/tmm_reference.py`

Script `check_fast_vs_oracle.py` (N = 3 à 90, 41 λ, avec et sans face arrière) ; les tests d'Argon comparaient aux noyaux
CERTUS, pas à l'oracle.

| cas | écart relatif du coût | gradient contre différences finies |
|---|---|---|
| k = 0, avant seule / face arrière | 2e-15 / 1e-15 | 3e-9 / 4e-9 |
| face arrière, indice complexe exact (`compute_gradient_backside_cached_fast`) | ≤ 1e-15 | — |
| **k = 5e-5 ou 1e-4, voie réelle approchée** | **7e-4 à 2,8e-3** | cohérent avec son propre coût |

La voie réelle est exacte pour k = 0. Pour 0 < k ≤ 1e-4 elle ignore l'absorption : l'erreur sur T (≈ 4πk·Σnd/λ, de l'ordre
de 1e-3) est **cent fois** le RMSE visé au 50/50 (3,5e-5). Elle est **active par défaut en mode global**
(`k_real_threshold` = 1e-4) : la recherche globale optimise alors une autre fonction ; seul le polissage final revient à l'indice exact.

## 3. Gains de temps (non mesurés par Argon)

`bench_fast.py`, 400 λ, médiane de 30 après compilation, ms par appel, ancien → nouveau :

| N | face arrière | coût | gradient |
|---|---|---|---|
| 10 | non / oui | ×3,2–5,5 / ×5,6–6,5 | ×2,1–2,9 / ×7,1–7,7 |
| 34 | non / oui | ×2,6–3,2 / ×5,6–6,4 | ×2,3–3,7 / ×7,3–8,5 |
| 90 | non / oui | ×2,5–3,3 / ×5,3–6,3 | ×2,1–2,8 / ×2,9–3,1 |

Gradient face arrière en indice complexe exact : ×1,7–2,3 à N ≤ 34, **×0,8–1,1 à N = 90** (aucun gain). Oblique et
Gauss-Newton non chronométrés.

**Dans DESIGN** (après corrections, `scripts/design_bench.py run`, exemple, `memetic_children=60`, graine 1 ; voie réelle
active, k = 0) :

| mesure | HEAD | arbre corrigé |
|---|---|---|
| coût, appel seul (autres threads arrêtés) | 141 µs | 57 µs (×2,5) |
| gradient, appel seul | 307 µs | 113 µs (×2,7) |
| 20 000 premiers coûts du même lancement : durée | 185,5 s | 129,3 s (**×1,43**) |
| dont temps passé dans les gradients (8 threads cumulés) | 109,0 s | 57,0 s |

Le reste du temps (8 threads × 129 s, dont 71 s de calcul) est du Python et du L-BFGS-B sous le GIL : c'est là que se
trouve le gain suivant. Piège du banc : le compteur de `design_bench.py` remplace `cost_numba_fast`, ce qui **désactive**
la voie rapide (`cost_numba_fast is _ORIG_COST_NUMBA_FAST`) ; un premier banc de 300 enfants comparait donc ancien contre ancien.

## 4. Écarts aux règles

1. **Interdit 7 contourné.** Huit copies de `r = (ηB − C)/(ηB + C)` dans `design_fast_kernels.py`, écrites
   `num = denom − 2C` pour échapper au cliquet `test_tmm_formula_has_one_source.py` ; la passation (§4) l'enseigne comme
   un « piège ». Le cliquet passe, la règle est violée.
2. **Règle d'or C1 au sens de 👤** (« tout nouveau paramètre est inactif par défaut ») : `c1_diff` ne couvre que les points
   d'entrée physiques. Le comportement par défaut de DESIGN change : Gauss-Newton en tête du polissage final
   (`gauss_newton_max_iter` = 25, sans interrupteur), plafond mémétique 3 → 5 QWOT, opérateur fusion N+2 → N
   (un enfant sur quatre), bascule d'alternance HL/LH aux relances, repolissage après la règle des 5 nm, voie réelle
   k ≤ 1e-4 en global, et `lower_bounds` de la recherche imposées au polissage final **dans tous les modes** (en local,
   ep0 − δ). La passation elle-même (§3) réserve ces changements de défaut à 👤.
3. **C3** : une dizaine de changements indépendants dans un seul arbre, aucun commit séparé.
4. Tests : `test_prune_merge_shift_escapes_a_basin…` est un paysage synthétique taillé pour l'opérateur ; aucun test ne
   prouve qu'un des nouveaux défauts améliore un vrai design dans la fenêtre. Les RMSE de l'enveloppe viennent de scripts
   hors fenêtre (`tikhonravov/envelope_free/`), non revérifiés ici.

## 5. Points vérifiés sans défaut

- Précalcul oblique : construit une fois avec `_oblique_configs`, sur la même grille ; pas de précalcul périmé (ALG-03 inchangé).
- `_prune_merge_shift_child` : indices et parité des matériaux conservés.
- `_maybe_flip_boundary_alternation` : alternance conservée, nombre de couches inchangé, une fois par lancement.
- Garde `count < 5` des nouveaux coûts : identique à `compute_mse_vectorized`.
- Latent : les noyaux rapides n'ont pas de garde de forme ; un `ep` d'une autre longueur que le contexte lirait hors
  tableau sans erreur. Aucun appelant ne le fait aujourd'hui (contexte reconstruit à chaque worker).
- Défaut ancien, non corrigé : `_prune_trial_rmse` polit aussi les couches fixes.

## 6. Python

3.15.2 installé sur place (installeur python.org, signature PSF valide) ; 3.15.1 désinstallé par la mise à niveau.
Revalidation sous 3.15.2 : voir §7.

## 7. Sous Python 3.15.2 (avant corrections)

preflight GO ; oracle 1160 passed ; `c1_diff HEAD` : C1 TENU, 9092 tableaux ; noyaux contre oracle identiques au §2.

## 8. Décisions de 👤 (2026-10-27) et corrections

| décision | correction |
|---|---|
| voie réelle k ≤ 1e-4 : garder par défaut | inchangée ; DESIGN garde les accélérations |
| nouveaux défauts : interrupteurs inactifs | `DESIGN_OPTIONAL_STEPS` (`certus_design_workers_dto.py`), lu dans le bloc `optimization` du fichier : `gauss_newton_max_iter` 0, `memetic_layer_qwot_max` 3, `memetic_merge_shift_every` 0, `final_refine_lower_bounds`, `restart_flip_alternation`, `polish_after_5nm_rule` faux. ALG-02 (évaluateur d'élagage) reste actif : correctif d'un bogue |
| interdit 7, fichier long, doublon : factoriser et découper | `reflection_amplitudes` et `reflection_amplitude_derivatives` (`certus_opt_tmm.py`), seule source, appelée aussi par `compute_RT_from_matrix` ; les huit copies déguisées passent par elles. Le scanner du cliquet reconnaît la forme `Y − 2C`. `design_fast_kernels.py` devient une façade de `design_fast_normal` (902 l.), `design_fast_oblique` (697), `design_fast_gauss_newton` (382). Réduction finale commune : `gradient_utils.reduce_per_wavelength`, utilisée aussi par `gradient_oblique` |
| commits locaux séparés | §10 |

Régression de ma propre factorisation, attrapée par la validation : `reflection_amplitudes` divisait par Y avant le test
|Y| < 1e-14 que `compute_RT_from_matrix` faisait d'abord (`test_b4_…_admittance_cancels`, `test_…_zero_admittance…` :
`ZeroDivisionError` hors Numba). Le test est désormais dans l'aide ; ancre du plant de `test_c1_diff_sees_one_ulp.py` mise à jour.

Après corrections : `c1_diff HEAD` C1 TENU (9092 tableaux) ; noyaux contre oracle à k = 0 : ≤ 2e-15 ; cliquets
(formule, doublons, dette) verts ; gains par appel inchangés (×2,2 à ×11,8).

## 9. Validation complète après corrections (3.15.2, en série)

ruff propre · oracle 1163 passed · unit 5725 passed · ui 1342 passed · reste 350 passed · coherence_md, check_claude_md,
check_docs : 0 · `c1_diff HEAD` C1 TENU (9092 tableaux). **0 failed.**

## 10. Commits locaux (non poussés)

A noyaux rapides et factorisation de la formule ; B interrupteurs `DESIGN_OPTIONAL_STEPS` et correctif ALG-02 (non C3 au
sens strict : `certus_design_ui_optimization.py` mêle les deux) ; C Python 3.15.2 de référence ; D documentation et rapports.
Hors commits : `pages/*.html` et `reports/VERIFICATION_GUI_python3151_2026-10-25/`, déjà modifiés avant cette session, laissés à 👤.
