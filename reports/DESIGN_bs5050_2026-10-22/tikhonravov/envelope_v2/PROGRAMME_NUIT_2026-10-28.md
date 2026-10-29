# Programme de la nuit du 2026-10-28 au 29 (autonomie de 12 h, jusqu'à ≈ 08:30)

But de 👤 : CERTUS meilleur que Tikhonravov et Trubetskov sur chaque problème publié. Une étape à la fois, 7 processus
à un fil OpenBLAS. Script : `campaign13.sh` (en cours) puis `campaign8.sh`. Heures prévues, non mesurées.

| fin prévue | étape | référence à battre | sortie |
|---|---|---|---|
| ≈ 22:20 | trois raies, 7 trajectoires graduelles (K 1–3, pas de TOT 60–150 nm) | Trubetskov 2020 Fig. 5 | `gradual_*_beam*` |
| ≈ 23:50 | cissoïde OIC 2016 B1, cible exacte, aiguilles sur 9 matériaux puis nettoyage ≤ 50 couches ≥ 3 nm | 0,0139 (concours), 0,0238 (2020) | `cissoid_opt_*` |
| ≈ 01:20 | trois raies, 51 couches, épaisseur optique 100–350 nm | 0,464 (2012, Table 1) | `constrained_threeline_N51.*` |
| ≈ 02:50 | miroir chaud, 40 couches, épaisseur optique 100–350 nm | 0,865 (2012, design A) | `constrained_hotmirror_N40.*` |
| ≈ 04:50 | trois raies, les 7 trajectoires prolongées jusqu'à 11 500 nm | Fig. 5, 0,058 vers 11 000 nm | `gradual_*_cont_beam*` |
| ≈ 06:20 | trois raies, départs quart d'onde à TOT imposée 11 000 nm, N 75–95 | idem | `*_qw_foc75-95_tot11000_*` |
| ≈ 06:50 | EF1–EF10 : robustesse, erreurs aléatoires d'épaisseur optique 1 et 2 nm | Table 4 (rendements) | `ef2012_analyse.txt` |
| ≈ 08:30 | 50/50 : diagnostics H1–H3 | — | `diag5050_*` |

Résultats (programme fini à 06:30 ; détail et preuves : `AUDIT_2026-10-28.md`, section 7) : trajectoires jusqu'à
11 300 nm, 0,126 ; cissoïde 0,182 ; 51 couches 0,875 avec leur procédure, puis 0,6062 et, repris le 29, 0,4597 ;
miroir chaud = leurs designs A et B ; quart d'onde à 11 000 nm 0,338 ; EF : rendements accordés à leur fabrication ;
50/50 H2 : la convergence n'est pas en cause.

Déjà acquis le 28/10 au soir :
- cible exacte de la cissoïde : 2a = 100 nm, arrondie à 4 décimales ; leur design d'exemple redonne MF 0,89721320429466 (14 chiffres) ;
- définition de la Table 3 des EF : 45° seul, moyenne commune de R et T (rapport 0,976 ± 0,012) ;
- sensibilité du trois raies à la grille : sur 270 points ou 263 points, nos designs perdent 20 à 30 % de MF.
  La grille a depuis été fixée à 277 points (29/10, `grid_test.py`).
