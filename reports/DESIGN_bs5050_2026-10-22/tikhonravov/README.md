# Comparaison avec Tikhonravov, Trubetskov et DeBell, Appl. Opt. 35, 5493 (1996), fig. 4

Leur problème : séparatrice T = 0,5 sur 400–1200 nm, n_L = 1,45, n_H = 2,35 constants, verre 1,52, air ; leur design :
34 couches, 31,39 QWOT à 500 nm, couche la plus fine 3,78 nm, MF publié 1,2767e-2 (MF = 100 × RMSE sur 80 points, éq. 3).
Problème et design publié (avec l'autorisation des auteurs) : `example/example_design/JSON-design-reference-tikhonravov-1996.json`
et `JSON-design-reference-tikhonravov-1996-published-design.json` (RMSE 1,765e-4 sur 1601 points, chargé dans DESIGN).

Juge commun : `judge_like_the_article.py` (oracle indépendant, même code pour les deux designs).

| | article | DESIGN, `config_tikhonravov_bs.json` → `best_tikh_r1.json` |
|---|---|---|
| MF sur 80 points | 1,2767e-2 publié (1,446e-2 recalculé) | **8,53e-3** |
| RMSE grille fixe 1601 points | 1,765e-4 | **8,64e-5** |
| écart max à 0,5 (1601 points) | 0,193 % | **0,024 %** |
| couches · QWOT · plus fine | 34 · 31,39 · 3,78 nm | 34 · 26,43 · 5,09 nm |

DESIGN au réglage par défaut du 2026-10-23 (mémétique 1000 enfants, champion conforme, relances), plafonds du fichier
`max_layers` 34 et `max_total_qwot` 31,39 ; un tour puis arrêt des relances (gain < 1 %), 47 min sur machine chargée.

**Courbe RMSE = f(couches)** (`curve/`, DESIGN par défaut, sans plafond de QWOT, un run par N de 1 à 34, N = nombre
de couches autorisé, `run_curve.sh`) : 1 c. 0,229 · 5 c. 0,076 · 10 c. 0,0151 · 14 c. 0,0041 · 20 c. 0,00047 ·
24 c. 0,00021 · 28 c. 0,000156 · 34 c. 0,000090 (grille de 1601 points, oracle ; chaque ligne de `curve.csv` donne
son `best_N.json` et sa ligne `tcurveN` de `curve.jsonl`). Un seul run par N : 11 runs gardent moins de couches
qu'autorisé (points creux), et N = 21 finit à 16 couches (0,0033). N = 1–9, 11–13, 15–17, 19–21, 23–25, 27–29,
31–33 le 2026-10-24 (code `43c5a957`, 8 fils, limite 3 h puis 12 h dès N = 24, aucun run arrêté) ; dès 28 couches DESIGN est sous leur design à 34 couches (0,000156 contre 0,000177 sur la même grille).
Sous des erreurs d'épaisseur de 0,1 % + 0,2 nm à 2σ (80 points), leur design et celui de DESIGN à 34 couches se valent :
RMSE moyen 0,00304 ± 0,00136 contre 0,00307 ± 0,00148 ; les deux sont limités par la tolérance de fabrication. Sur la
courbe, ce RMSE moyen est au plus bas entre 22 et 28 couches (0,00219 à 28 couches) et remonte à 0,0031 à 34 : au-delà,
une couche de plus baisse le RMSE nominal et monte le RMSE sous erreurs (colonne `mean_80` de `curve.csv`, un run par N).
Graphe `curve/curve.png`, tableau `curve/curve.csv`.
