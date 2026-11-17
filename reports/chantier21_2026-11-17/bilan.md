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
