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
