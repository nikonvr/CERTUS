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

Commande : `python reports/BONNE_MERE_design_2026-10-23/reoptimize.py --study STUDY --max-layers 110 --budget-min 45
--substrate-id 0 --tag _silica_cached` (8 fils). La stratégie de dépôt STRAT n'est pas refaite pour ce design.
