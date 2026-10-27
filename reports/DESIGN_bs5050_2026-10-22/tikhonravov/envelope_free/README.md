# Enveloppe globale $\text{RMSE}^*(N)$ et accélérations de `CERTUS_DESIGN` — séparatrice 50/50 de Tikhonravov et al. (1996) — 2026-10-26

Problème : séparatrice $T = 0{,}5$ sur $400\text{--}1200\text{ nm}$, $n_L = 1{,}45$, $n_H = 2{,}35$ constants, substrat verre $n_{\text{sub}} = 1{,}52$, air $1{,}00$.
Comparaison sur la grille fixe oracle de 1601 points ($0{,}5\text{ nm}$) entre :
- l'ancienne campagne `curve/curve.csv` (`HL...` seul, réglages précédents),
- l'enveloppe stricte $\text{RMSE}^*_{5\text{nm}}(N)$ ($d_i \ge 5\text{ nm}$, `best_5nm_1.json` à `best_5nm_34.json`),
- l'enveloppe libre $\text{RMSE}^*_{\text{free}}(N)$ ($d_i \ge 0{,}1\text{ nm}$, `best_free_1.json` à `best_free_34.json`).

## 1. Pourquoi `curve/curve.csv` manquait le minimum global et stagnait à $N = 28\dots 34$

1. **Violation du plancher des 5 nm par le polissage final (`run_coord_descent_5cycles`)** : le raffinement final projetait les épaisseurs sur `CFG.MIN_THICKNESS = 0.01 nm` en ignorant le plancher `memetic_floor_nm = 5.0 nm` de l'étape globale, puis `_apply_5nm_minimum` supprimait sans réoptimiser toute couche tombée sous $5\text{ nm}$ (`ALG-19` : 11 runs sur 34 ont perdu des couches dans `curve.csv`, dont $N=21$ tombé à 16 couches avec $\text{RMSE} = 0{,}003317$).
2. **Alternance fixée à `H` sur substrat (`HL...`) et blocage de la transition $N + 1 \to N$** : dès $N \ge 8$, la couche côté air doit être `L` ($\sim 0{,}9\text{--}1{,}0\text{ QWOT}$) ; pour $N$ impair ($9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33$), finir par `L` côté air impose de commencer par `L` sur le substrat (`L..L`), ce qu'obtient naturellement une recherche à $N + 1$ couches `HL...` lorsque la couche $0$ (`H` côté substrat) meurt.
3. **Plafond de couche à `3.0 QWOT` et absence de fusion topologique $N + 2 \to N$ dans `run_memetic`** : lorsqu'une couche interne fine $k$ meurt dans un empilement à $N + 2$ couches, ses deux voisines de même matériau fusionnent en une cavité épaisse de $2{,}8$ à $5{,}2\text{ QWOT}$ ($4{,}56\text{ QWOT}$ à $N=12$, $5{,}22\text{ QWOT}$ à $N=13$, $3{,}64\text{ QWOT}$ à $N=16$, $3{,}15\text{ QWOT}$ à $N=23$).
4. **Évaluateur d'élagage `_prune_to_target` inopérant (`ALG-02`)** : `_evaluate_test_stack` dépaquetait `optim_prepare_stack_nk_back` dans le mauvais ordre et lisait `t.val`/`t.weight` inexistants sur `Target`, renvoyant `inf` dans un `except Exception:` muet.
5. **Polissage local mal conditionné à $N \ge 28$ (`ALG-07`, hypothèse)** : sur les empilements de 28 à 34 couches à cavités épaisses ($\sim 3\text{--}5\text{ QWOT}$), L-BFGS-B stagnait vers $8{,}8 \times 10^{-5} \to 7{,}6 \times 10^{-5}$. Un Gauss-Newton / Levenberg-Marquardt sur la jacobienne analytique $M \times N$ (SVD-GN de `deep_high_n.py`, `gauss_newton_refine_normal`) évite d'élever le conditionnement au carré ($\kappa(J^T J) = \kappa(J)^2$, valeurs non mesurées) ; combiné aux opérateurs $N \pm p$, il divise le RMSE par plus de 2 à $N = 31\dots 34$ (jusqu'à **$3{,}525 \times 10^{-5}$** à $N=34$). La part du seul changement d'optimiseur n'est pas isolée.

## 2. Courbe complète $\text{RMSE} = f(N)$ (`curve_free.csv`, juge oracle 1601 points)

| $N$ | `curve.csv` (ancien) | Couches gardées | $\text{RMSE}^*_{5\text{nm}}(N)$ ($d \ge 5\text{ nm}$) | Struct. $5\text{ nm}$ ($d_{\min}$) | $\text{RMSE}^*_{\text{free}}(N)$ ($d \ge 0{,}1\text{ nm}$) | Struct. libre ($d_{\min}$, QWOT) |
|---:|---:|---:|---:|:---:|---:|:---:|
| 1 | `2.29037e-01` | 1 | `2.25272e-01` | `H..H` (69,5 nm) | `2.25272e-01` | `H..H` (69,5 nm, 1,31) |
| 2 | `2.29037e-01` | 1 | `2.03720e-01` | `L..H` (69,0 nm) | `2.03720e-01` | `L..H` (69,0 nm, 3,63) |
| 3 | `1.45475e-01` | 3 | `1.45936e-01` | `H..H` (68,4 nm) | `1.42195e-01` | `H..H` (61,8 nm, 5,78) |
| 4 | `1.44715e-01` | 3 | `1.38874e-01` | `L..H` (68,1 nm) | `1.35972e-01` | `L..H` (68,3 nm, 7,53) |
| 5 | `7.63667e-02` | 5 | `7.16955e-02` | `H..H` (59,0 nm) | `7.16955e-02` | `H..H` (59,0 nm, 11,06) |
| 6 | `7.63639e-02` | 5 | `7.17436e-02` | `L..H` (5,0 nm) | `7.16956e-02` | `L..H` (0,1 nm, 11,06) |
| 7 | `6.30368e-02` | 7 | `5.31082e-02` | `H..H` (29,6 nm) | `5.31082e-02` | `H..H` (29,6 nm, 10,91) |
| 8 | `3.44935e-02` | 8 | `3.07063e-02` | `H..L` (31,2 nm) | `3.07063e-02` | `H..L` (31,2 nm, 10,50) |
| 9 | `3.41837e-02` | 9 | `2.05156e-02` | `L..L` (50,4 nm) | `2.05156e-02` | `L..L` (50,4 nm, 14,50) |
| 10 | `1.50820e-02` | 10 | `1.16687e-02` | `H..L` (6,0 nm) | `1.16687e-02` | `H..L` (6,0 nm, 14,97) |
| 11 | `1.19027e-02` | 10 | `1.08272e-02` | `L..L` (12,8 nm) | `1.08272e-02` | `L..L` (12,8 nm, 19,11) |
| 12 | `8.57409e-03` | 12 | `7.99088e-03` | `H..L` (6,2 nm) | `7.99088e-03` | `H..L` (6,2 nm, 16,23) |
| 13 | `8.74684e-03` | 12 | `3.59214e-03` | `L..L` (6,0 nm) | `3.59214e-03` | `L..L` (6,0 nm, 19,02) |
| 14 | `4.13824e-03` | 14 | `3.92957e-03` | `H..L` (10,3 nm) | `3.58397e-03` | `L..H` (1,2 nm, 18,99) |
| 15 | `4.10825e-03` | 14 | `2.30427e-03` | `L..L` (5,0 nm) | `2.24103e-03` | `L..L` (3,4 nm, 16,08) |
| 16 | `3.09257e-03` | 16 | `2.11376e-03` | `H..L` (13,8 nm) | `2.11376e-03` | `H..L` (13,8 nm, 19,08) |
| 17 | `3.19492e-03` | 17 | `1.87144e-03` | `L..L` (5,9 nm) | `1.87144e-03` | `L..L` (5,9 nm, 20,26) |
| 18 | `1.48675e-03` | 18 | `1.12569e-03` | `H..L` (11,4 nm) | `1.12569e-03` | `H..L` (11,4 nm, 19,03) |
| 19 | `1.90955e-03` | 18 | `1.12569e-03` | `L..L` (5,0 nm) | `1.12569e-03` | `L..L` (4,8 nm, 19,10) |
| 20 | `4.65885e-04` | 20 | `4.45522e-04` | `H..L` (8,6 nm) | `4.45522e-04` | `H..L` (8,6 nm, 19,78) |
| 21 | `3.31706e-03` | 16 | `4.45529e-04` | `L..L` (5,0 nm) | `4.31010e-04` | `L..L` (6,4 nm, 21,92) |
| 22 | `4.09847e-04` | 22 | `2.41425e-04` | `H..L` (5,1 nm) | `2.37687e-04` | `H..L` (2,4 nm, 22,55) |
| 23 | `6.02555e-04` | 22 | **`1.71163e-04`** | `L..L` (6,8 nm) | **`1.71163e-04`** | `L..L` (6,8 nm, 21,86) |
| 24 | `2.08954e-04` | 24 | `2.00652e-04` | `H..L` (5,6 nm) | `1.60100e-04` | `H..L` (3,5 nm, 22,89) |
| 25 | `2.64182e-04` | 22 | `1.65649e-04` | `L..L` (5,0 nm) | `1.12452e-04` | `L..L` (2,3 nm, 24,33) |
| 26 | `1.93704e-04` | 26 | `1.24267e-04` | `H..L` (5,0 nm) | `1.12497e-04` | `L..H` (0,1 nm, 24,32) |
| 27 | `2.38922e-04` | 24 | `1.24321e-04` | `L..L` (5,0 nm) | `1.08920e-04` | `L..L` (2,5 nm, 24,41) |
| 28 | `1.55541e-04` | 28 | **`7.97587e-05`** | `H..L` (5,0 nm) | **`7.95876e-05`** | `H..L` (3,1 nm, 26,89) |
| 29 | `1.74422e-04` | 29 | `9.08796e-05` | `L..L` (5,0 nm) | **`7.94769e-05`** | `L..L` (2,1 nm, 27,15) |
| 30 | `1.16366e-04` | 30 | `7.54347e-05` | `H..L` (5,1 nm) | **`6.57448e-05`** | `H..L` (4,6 nm, 26,79) |
| 31 | `1.10822e-04` | 31 | **`4.02755e-05`** | `L..L` (5,0 nm) | **`3.72416e-05`** | `L..L` (1,5 nm, 28,73) |
| 32 | `1.07923e-04` | 32 | `7.40598e-05` | `H..L` (5,0 nm) | **`3.66292e-05`** | `H..L` (1,3 nm, 29,11) |
| 33 | `1.16658e-04` | 33 | `5.53115e-05` | `L..L` (5,0 nm) | **`3.80255e-05`** | `L..L` (4,4 nm, 29,24) |
| 34 | `9.03236e-05` | 34 | **`6.46560e-05`** | `H..L` (5,0 nm) | **`3.52543e-05`** | `H..L` (1,8 nm, 29,82) |

- **Dès $N = 23$ couches (`L..L`, $d_{\min} = 6{,}79\text{ nm}$)**, $\text{RMSE}^*(23) = 1{,}712 \times 10^{-4}$ bat le design publié à 34 couches de Tikhonravov et al. 1996 ($1{,}765 \times 10^{-4}$).
- **Rupture du palier haut ($N = 28\dots 34$)** :
  - dès $N = 28$, le RMSE passe sous $8 \times 10^{-5}$ ($7{,}959 \times 10^{-5}$ libre, $7{,}976 \times 10^{-5}$ avec $d \ge 5\text{ nm}$) ;
  - à $N = 31$, le design $d \ge 5\text{ nm}$ (`L..L`) descend à **$4{,}028 \times 10^{-5}$** ($3{,}724 \times 10^{-5}$ en épaisseurs libres) ;
  - à $N = 34$, le design libre (`H..L`, $29{,}82\text{ QWOT}$) atteint **$3{,}525 \times 10^{-5}$** (soit **5 fois plus bas** que le design publié de Tikhonravov 1996 à $1{,}765 \times 10^{-4}$, et **2,56 fois plus bas** que l'ancien point à 34 couches `9.032e-05`).

## 3. Améliorations algorithmiques et accélérations intégrées dans `CERTUS_DESIGN`

### 3.1. Convergence vers le minimum global ($N + p \to N$ et préservation du plancher)
1. **Préservation du plancher dans `run_coord_descent_5cycles`** (`certus/core/certus_design_worker_utils.py`, `certus/workers/certus_design_workers.py`) : le raffinement final respecte `lower_bounds` (`memetic_floor_nm` / `layer_floor_nm`) et annule les composantes de gradient poussant sous le plancher.
2. **Réparation de l'évaluateur d'élagage `_prune_to_target` (`ALG-02`)** (`certus/ui/certus_design_ui_optimization.py`) : `_prune_trial_rmse` et `_best_prune_candidate` évaluent chaque suppression de couche candidate (avec fusion des couches adjacentes de même matériau) via `prepare_targets_vectorized` et `cost_numba_fast`.
3. **Opérateur topologique `_prune_merge_shift_child` ($N + 2 \to N$) et plafond `5.0 QWOT` dans `run_memetic`** (`certus/core/certus_design_memetic.py`, `certus/workers/certus_design_workers.py`) : supprime une couche interne fine, fusionne ses deux voisines de même matériau en une cavité épaisse et décale l'empilement en conservant la parité des matériaux.
4. **Repolissage automatique après `_apply_5nm_minimum` (`ALG-19`)** (`certus/ui/certus_design_ui_optimization.py`) : `_polish_remaining_layers_above_floor` réoptimise par L-BFGS-B les couches variables restantes au-dessus de leur plancher dès qu'une couche fine est retirée.
5. **Basculement automatique d'alternance au substrat (`HL...` $\leftrightarrow$ `LH...`, $N + 1 \to N$) lors des relances** (`_maybe_flip_boundary_alternation` dans `certus/ui/certus_design_ui_optimization.py` et `certus/ui/certus_design_ui_core.py`) : lorsqu'une couche de bord ($0$ ou $N-1$) est plaquée contre le plancher des $5\text{ nm}$, la relance tente l'alternance opposée et restaure l'état initial si le tour n'améliore pas le meilleur RMSE.

### 3.2. Gains de temps de calcul (`certus/physics/design_fast_kernels.py`, `certus_design_core.py`, `certus_design_workers_strat.py`)
1. **Voie purement réelle (`float64`) pour indices réels ou à extinction faible ($k \le 10^{-4}$) avec polissage final sur l'indice complexe exact** (`prepare_normal_fast_context`, `cost_lossless_front_fast`, `compute_gradient_lossless_front_fast`) :
   - En incidence normale sans absorption forte ($\max |\text{Im}(n)| \le 10^{-4}$, substrat transparent), la matrice caractéristique d'une couche a ses termes diagonaux réels ($\cos\phi_k$) et ses termes hors-diagonale purement imaginaires ($-i\sin\phi_k / n_k$, $-i n_k \sin\phi_k$).
   - Toute l'arithmétique `complex128` ($\cosh/\sinh$ complexes + $\cos/\sin$ complexes) est remplacée par 4 flottants réels `float64` par couche et un seul appel `cos/sin` réel par couche, avec précalcul de $k_0(\lambda) = 2\pi/\lambda$ et $1/n_k(\lambda)$.
   - Lorsque $0 < k \le 10^{-4}$ (`has_weak_k=True`), toute la recherche globale exhaustive tourne sur le noyau réel rapide (`k_real_threshold=1e-4`), puis `OptimWorker.run` bascule automatiquement sur l'indice complexe exact (`k_real_threshold=1e-14`) avant le raffinement local final (`run_coord_descent_5cycles`).
   - Gain attendu $\times 4$ à $\times 6$ sur le coût et le gradient en incidence normale : **estimation, non chronométrée** (exactitude vérifiée par `tests/unit/test_design_fast_physics_kernels.py`).
2. **Face arrière en incidence normale (`ALG-25`) en une seule passe avec `(Rb_prime, Tb)` précalculés** (`cost_lossless_backside_fast`, `compute_gradient_lossless_backside_fast`, `compute_gradient_backside_cached_fast`) :
   - Au lieu d'appeler 3 fois la machinerie oblique à $0^\circ$ (`compute_oblique_rt_and_grads_analytic` aller, retour et face arrière) à chaque itération, `(Rb_prime, Tb)` de la face arrière sont précalculés une seule fois hors boucle.
   - Pour une pile avant sans perte ($k \le 10^{-4}$), la conservation de l'énergie $R'_f = 1 - T_f$ et $\partial R'_f/\partial d_k = -\partial T_f/\partial d_k$ donne le coût et le gradient avec face arrière en **une seule passe réelle** (quasi au même coût que sans face arrière).
   - Pour une pile avant absorbante ($k > 10^{-4}$), l'identité exacte de transposition des matrices caractéristiques $M_{\text{rev},00} = M_{\text{fwd},11}$, $M_{\text{rev},11} = M_{\text{fwd},00}$ donne $(T_f, \nabla T_f, R'_f, \nabla R'_f)$ en **une seule passe** aller/retour au lieu de 3 passes obliques.
   - Gain attendu $\times 3$ (trois passes réduites à une) à davantage avec face arrière active : **estimation, non chronométrée**.
3. **Précalcul optique et passe unique en incidence oblique (`ALG-08`)** (`precompute_oblique_optical_terms`, `compute_oblique_gradient_contrib_precomputed`, `compute_oblique_backside_contrib_precomputed`) :
   - Les angles de Snell, déphasages $\beta_{m,k}$, admittances polarisées $\eta_{m,k}$, $1/\eta_{m,k}$, $\eta_{\text{inc}}$, $\eta_{\text{sub}}$, facteurs de flux $t_{\text{gain}}$ et `(Rb_prime, Tb)` obliques ne dépendent pas des épaisseurs : ils sont précalculés une seule fois dans `_initialize_runtime_state_for_optimization`, et les tampons de travail `M_before`, `M_after`, `L_mats` sont alloués hors du `prange(n_wls)`.
   - Gain en incidence oblique : **non chronométré** (le précalcul est câblé dans `_initialize_runtime_state_for_optimization` ; la grille densifiée de `maybe_upgrade_grid_tikhonravov` ne le reconstruit pas, voir ALG-03).
4. **Raffinement local analytique de Gauss-Newton / Levenberg-Marquardt en Numba (`ALG-07`)** (`gauss_newton_refine_normal` intégré au début de `run_coord_descent_5cycles`) :
   - Calcule simultanément le vecteur des résidus pondérés $r_m$ et la jacobienne analytique $J_{m,i} = \sqrt{w_m}\,\partial T(\lambda_m)/\partial d_i$ en une seule passe réelle et résout les pas amortis $(J^T J + \lambda \text{diag}(J^T J))\,\delta d = -J^T r$ sous contrainte de boîte $d_i \ge d_{\min,i}$.
