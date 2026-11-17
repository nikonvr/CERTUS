# Chantier 21 — profil de SPLINE : les différences finies dominent-elles ? (2026-11-17)

Code `4da85264`. [`p21_profile_spline.py`](p21_profile_spline.py) ([sortie](p21_profile_spline.txt)) appelle
`tests/headless/test_spline.py::test_spline_headless` sous cProfile : exemple `TSIO2-1700-1.xlsx`, réglages du fichier
(`n_seg=13`, d ∈ [1600, 1800] nm, `local_only=True`), cache Numba chaud. Résultat : RMSE 0,00283, d = 1699,4 nm.

| | s (sous cProfile) | appels |
|---|---:|---:|
| exécution entière (imports, fenêtre, calcul) | 6,5 | |
| `worker_spline_optimization` | 3,21 | 1 |
| `minimize` (L-BFGS-B, `spline_workers.py:148::_polish_lbfgsb_chunked`) | 2,85 | 2 |
| dont `approx_derivative` (différences finies) | **2,65** | 336 gradients, 9 744 évaluations |
| fonction de coût (`spline_objective.py:994`) | 2,38 | 10 024 |

**Les différences finies font 93 % du temps de `minimize` et 82 % de celui du calcul** : environ 29 évaluations par
gradient (un paramètre par nœud, n et ln k, plus l'épaisseur). La condition d'archivage du chantier (« sinon archivé ») n'est
pas remplie : un gradient analytique de `spline_objective` réduirait l'essentiel de ces 2,65 s sur cet exemple.

Limites : un seul exemple, en mode local ; l'étape à nœuds libres (`spline_workers.py:544`, `_lbfgsb_phase_with_progress`)
n'a pas tourné ici. Smart Init (`optimize_smart_init_nkd_packet`, `maxfun=150`, sept paramètres) n'est pas profilé ; à
0,24 ms par évaluation de coût mesurée ici, son plafond vaudrait de l'ordre de 40 ms par clic (estimation, coût de
`rmse_at_spline_stage_x0_init` non mesuré).

Suite : un gradient analytique de `spline_objective` (nœuds PWL n, ln k, épaisseur, à travers la TMM), derrière une option
inactive par défaut (C1), vérifié contre les différences finies aux cas limites et dans les replis. Complexité forte.

## Gradient analytique à travers la reparamétrisation monotone (2026-11-17, soir)

**Pourquoi les différences finies.** `SplinePWLObjective` avait déjà un gradient analytique (nœuds n, ln k, épaisseur,
vérifié par `tests/oracle/test_spline_gradient_vs_fd.py`), mais `spline_pwl_analytic_grad_supported` le refusait dès que
`n_mono_band_nm` est posé : les nœuds n y sont des ξ, décodés chaîne par chaîne par une récurrence sigmoïde
(`decode_xi_n_to_physical_n`). La fenêtre INDEX SPLINE pose cette bande depuis le spectre (ici (249,99 ; 2000) nm) : le
gradient analytique ne servait donc jamais dans le cas courant.

**Ce qui change.** Option `SplineOptConfig.spline_mono_analytic_gradient`, **éteinte par défaut**. Allumée, le bloc n du
gradient (d coût / d n physique) passe par le produit vecteur-jacobien du décodage
(`certus/spline/spline_mono_gradient.py`) : les trois branches de la récurrence (bridage de ξ à ±60, portée saturée sous
1e-14, écrêtage final) sont rejouées puis remontées le long de chaque chaîne. Aucune formule TMM ajoutée. Tous les
appelants qui consultent `spline_pwl_analytic_grad_supported` en profitent (polissage `_polish_lbfgsb_chunked`, polissage du
maillage σ, couloirs) ; l'étape à nœuds libres (`_lbfgsb_phase_with_progress`) reste en différences finies.

**Vérifié** ([test](../../tests/oracle/test_spline_mono_gradient_vs_fd.py), 16 cas, différences centrées du coût de
l'objectif lui-même, par bloc, rtol 1e-4) : le décodage seul sur ses trois branches ; l'objectif en T (K = 3 `pwl`, 6, 14,
d = 120 à 1700 nm), plancher de k atteint, T en rapport, R, R+T, pénalité n(λ) active à une rupture de chaîne ; un garde-fou
(gradient en n physique donné pour un gradient en ξ : refusé) ; le polissage n'appelle le gradient qu'option allumée, départ
sur la borne ξ = 14 compris. Sur le code sans la ligne qui applique la règle de chaîne, 9 des 16 cas échouent.

**C1.** Option éteinte : SPLINE de bout en bout sur l'exemple, HEAD (`git archive`) contre l'arbre, caches Numba vierges,
42 tableaux identiques au bit ([sonde](p21_c1_default_path.py), [sortie](p21_c1_default_path.txt)) ;
`scripts\c1_diff.py HEAD` : 9 172 tableaux identiques ([sortie](c1_diff_HEAD.txt)).

**Durée** ([sonde](p21_gradient_on_off.py), [sortie](p21_gradient_on_off.txt) ; même processus, cache chaud, cinq paires
alternées, machine sans autre processus python) :

| option | médiane (min–max) | évaluations de coût | gradients analytiques | RMSE | d (nm) |
|---|---:|---:|---:|---:|---:|
| éteinte (différences finies) | 2,49 s (2,22–2,93) | 10 024 | 0 | 0,0028304 | 1699,43 |
| allumée | 2,06 s (2,01–2,40) | 2 549 | 2 549 | 0,0019482 | 1667,49 |

La durée baisse peu (−17 % en médiane) parce que le calcul ne fait plus le même travail : éteinte, L-BFGS-B s'arrête sur
son budget (`polish_maxfun` = 10 000, environ 336 gradients à 29 évaluations) ; allumée, il converge en 2 545 itérations.
Un gradient coûte environ 0,8 ms contre 7 ms par différences finies (dérivé des durées et des comptes ci-dessus).

🔴 **Le résultat change : d = 1667,5 nm au lieu de 1699,4, RMSE 0,00195 au lieu de 0,00283.** Contrôle
([sonde](p21_budget_check.py), [sortie](p21_budget_check.txt)) : éteinte avec un budget ×5 (50 044 évaluations, 11,8 s),
les différences finies vont dans le même sens sans y arriver (d = 1685,8 nm, RMSE 0,00219). Les trois points ont la même
épaisseur optique n(1000 nm)·d ≈ 2481–2483 nm : la vallée n–d, que les différences finies descendent lentement. Le résultat
publié par défaut sur cet exemple n'est donc pas un minimum convergé ; laquelle des épaisseurs est physique, l'ajustement
seul ne le dit pas. Les 12 NaN de `n_lam` (sur 903) sont identiques option éteinte et allumée.

**Limites.** Un exemple, en mode local ; étape à nœuds libres et Smart Init non couverts. **Allumer l'option par défaut
change le résultat de l'exemple : décision de 👤.**

**Validation** (`scripts\validate_parallel.py`, arbre final sur `2a5443ba`) : ruff et contrôles documentaires verts ; oracle
1 231, ui 1 670, reste 322, performance 30 verts ; unit 6 373 verts et 2 rouges, rejoués seuls en série : le cliquet
`test_the_architecture_debt_only_shrinks.py` sur `certus/core/certus_substrate_sellmeier.py::_fit_model_sellmeier3poles`
(389 → 411 lignes) et `certus/core/certus_substrate_index.py` (1 945 → 1 962), grandis par le commit `2a5443ba`
(chantier 05) que ce chantier ne touche pas : `VALIDATION=NO-GO` hérité de HEAD.
