# Bonne Mère : design réoptimisé avec les leviers de la campagne DESIGN (2026-10-23)

Optique de l'étude (restaurée de `studies/bonne_mere/archives` par `dossier_final/outils/restaurer_archive.py`) : H800
Nb₂O₅ / SiO₂, face arrière incohérente, cible retenue de 601 points ; elle redonne exactement le plancher de référence
1,4590693866 pp du design retenu (96 couches, saphir). Script : [`reoptimize.py`](reoptimize.py) ; lignes brutes
`results*.jsonl` et journaux `*.log` locaux (ignorés par git).

Leviers appliqués, chacun jugé sur le RMSE de l'étude (pp) : polissage libre (borne basse 0 au lieu de 5 nm), plancher de
5 nm appliqué en fin, croissance par aiguilles jusqu'à 110 couches (balayage `needle_scan_cached_backside`, tous les 2 nm,
la moins nuisible quand aucune n'aide), sauts de bassin autour du meilleur design.

| substrat | départ | meilleur design conforme (couches ≥ 5 nm) |
|---|---|---|
| saphir (id 3) | 1,459069 pp, 96 couches | aucun gain : le design retenu est déjà un optimum local, sans plancher actif (couche la plus fine 7,7 nm) et sans aiguille utile |
| silice fondue (id 0) | 3,41 pp (design saphir posé sur silice) | **1,434353 pp**, 102 couches, plus fine 5,000 nm : `best_design_silica_cached.json` |

Silice : polissage libre 1,4643 pp (96 couches) ; croissance + plancher en fin 1,4592–1,4595 pp à 98–102 couches ; au-delà
de 102 couches le plancher coûte plus que les couches n'apportent (1,4635 pp à 110). Sans plancher, 110 couches donnent
1,4585 pp : ajouter des couches ne gagne que quelques millièmes de pp ; le gain vient des sauts de bassin (ci-dessous).

Meilleur design (silice) : croissance jusqu'à 102 couches puis 747 sauts de bassin (épaisseurs × (1 + 0,03 N(0,1)),
polissage libre, plancher de 5 nm en fin) en 45 min sur 8 fils ; le gain vient des sauts (1,4592 → 1,4344 pp). Vérifié
dans un processus neuf : modèle de l'étude 1,434353 pp, oracle indépendant (lame incohérente,
`tests/oracle/tmm_reference.py`) 1,434353 pp, écart de T 1,3e-14 ; alternance H/L, ≤ 110 couches.

Sans précoat (souhait de 👤) : les 4 premières couches retirées (1,711 pp après polissage), puis 45 min de sauts de bassin
à 98 couches (`--max-layers 98 --start start_98_first4_removed.json`) : **1,513930 pp**, premières couches 100,2 · 87,4 ·
14,4 · 37,6 nm, plus fine 5,000 nm : `best_design_silica_98.json`, vérifié (modèle de l'étude et oracle, écart de T 7e-15).

## Robustesse aux erreurs d'épaisseur (critère de choix de 👤)

Erreur gaussienne indépendante par couche, 2σ = 0,4 nm, 500 tirages communs à tous les designs ([`robustness.py`](robustness.py),
47 candidats conformes des trois runs sur silice) :

| design | nominal | RMSE moyen sous erreurs | 95 % des tirages sous |
|---|---|---|---|
| `best_design_silica_robust.json` (102 couches, run de croissance, saut 30) | 1,4584 pp | **1,7138 pp** | 1,913 pp |
| `best_design_silica_cached.json` (102 couches) | 1,4344 pp | 1,7167 pp | 1,934 pp |
| `best_design_silica_98.json` (98 couches, sans précoat) | 1,5139 pp | 1,7833 pp | 1,980 pp |

Comparaison appariée : les deux designs à 102 couches sont à égalité (+0,0029 ± 0,0052 pp à 2 erreurs-types) ; le design
sans précoat est plus mauvais de 0,070 ± 0,006 pp. Sous erreurs, l'écart nominal de 0,024 pp entre les deux 102 couches
disparaît ; le classement suit le nominal à l'intérieur de chaque run.

Optimisation directe du RMSE moyen sous erreurs ([`robust_optimize.py`](robust_optimize.py) : moyenne sur 128 tirages
d'entraînement d'une autre graine, gradient exact, sans plancher par décision de 👤). Couche 16 du design à 98 couches
(0,27 nm) retirée et couches 15 et 17 fusionnées par 👤 (`start_96_layer16_removed.json`, 1,7821 pp) ; puis 45 min de
sauts de bassin gardés sur la moyenne d'entraînement (1474 sauts) et polissage robuste : `best_design_robust_opt_96_hops.json`,
96 couches, nominal 1,5054 pp, **1,7697 pp** sous erreurs (95 % sous 1,955 pp) ; vérifié par l'oracle (écart de T 1e-14).
Sa couche 90 (SiO₂) est à 0,000 nm : retirée par 👤, couches 89 et 91 fusionnées (523,3 nm), **94 couches**
`best_design_94_layer90_removed.json` : nominal identique, 1,7698 pp sous erreurs (95 % sous 1,960 pp), plus fine 5,47 nm, vérifié
par l'oracle. Ses deux couches les plus fines (72 : 5,47 nm, 42 : 6,50 nm) retirées par 👤, voisines fusionnées : 90 couches,
3,84 pp sans polissage ; polissage robuste (400 itérations) : `best_design_robust_opt_90.json`, nominal 1,5723 pp, **1,8184 pp**
sous erreurs (95 % sous 1,987 pp), plus fine 7,92 nm, vérifié par l'oracle. Polissage robuste seul, sans sauts : 1,7833 → 1,7798 pp.

Commande : `python reports/BONNE_MERE_design_2026-10-23/reoptimize.py --study STUDY --max-layers 110 --budget-min 45
--substrate-id 0 --tag _silica_cached` (8 fils). La stratégie de dépôt STRAT n'est pas refaite pour ce design.
