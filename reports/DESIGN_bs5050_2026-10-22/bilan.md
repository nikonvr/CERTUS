# DESIGN plus performant — séparatrice 50/50 400–1200 nm (2026-10-22/23)

Contraintes de 👤 : H/L seulement, indices inchangés, ≤ 34 couches, ≤ 30 QWOT. RMSE de T sur grille fixe de 0,5 nm,
recoupé par l'oracle indépendant. Détail de chaque levier, commandes et défauts : [`journal.md`](journal.md).

| | RMSE (grille fixe) | couches · QWOT | temps |
|---|---|---|---|
| DESIGN par défaut (PGLOBAL), 3 runs | 0,0018 – 0,0042 | 21 – 27 · ~19 | 1,5 – 2,5 min |
| **DESIGN, réglage mémétique**, 3 runs | **0,000147 – 0,000215** (médiane 0,000172) | 34 · 25,8–26,8, couches ≥ 5 nm | 7 – 9 min |
| sonde hors fenêtre (sans plancher de 5 nm) | 0,000168 | 32 · 25,6 | ~1 h |

**Réglage** : `run_optim("global", memetic_children=1000, memetic_population=30, memetic_qwot_max=30)` et, sur la
fenêtre, `_pareto_champion_respects_5nm = True` ; départ 34 lignes QWOT (croissance active : le `allow_growth` faux du fichier n'était pas lu, voir `a813fa64`). Depuis le 2026-10-23, sur
décision de 👤, le mémétique (1000 enfants, population 30) et le champion conforme sont actifs par défaut ; le plafond de
QWOT reste à fixer par design.

**Esquisse RMSE / couches** (10 à 35 couches de départ, un run DESIGN chacune, réglage mémétique) :
[`sweep/best_by_layers.png`](sweep/best_by_layers.png), tableau [`sweep/best_by_layers.csv`](sweep/best_by_layers.csv).
DESIGN passe sous 1e-3 dès 22 couches réelles ; la dispersion d'un run à l'autre est de ±20 % ou plus.

**Plancher** : redémarrer depuis le meilleur design donne un gain puis plus rien (0,000189 → 0,000149 → 0,000148 ×2) ;
mémétique, sonde, redémarrages et répétitions finissent tous vers 1,5e-4 à 34 couches et 30 QWOT. Leviers essayés sans
gain : grille plus dense, mouvement de paires, encombrement, 3000 enfants (détail au journal).

**Défauts de DESIGN trouvés** : bornes globales à 1,2 QWOT par couche ; règle finale des 5 nm sans réoptimisation ;
champion Pareto qui ignore cette règle (option corrigée) ; export qui écrivait un autre design dans le tableau (corrigé,
`76349415`).

**Décisions de 👤** : mémétique et champion conforme activés par défaut (2026-10-23) ; reste la réoptimisation
après la règle des 5 nm (`_polish_after_5nm_rule`, défaite aujourd'hui par la restauration du champion).

**Validation** (CLAUDE.md §2, `validate_parallel.py`, `34febabe` + ETAT) : ruff, oracle 1149, unit 5608, ui 1324, reste 319,
performance 40 réussis ; un seul échec réel, la taille de la section 0 d'ETAT.md (corrigée, test vert ensuite) ;
`coherence_md` échoue sur une commande morte antérieure (`ETAT_actions.md:67`, script STRAT absent).

**Face à la littérature** : sur le problème exact de Tikhonravov et al. (1996, indices 1,45/2,35 constants, 34 couches),
DESIGN obtient MF 8,53e-3 contre 1,2767e-2 publié, RMSE 8,6e-5 contre 1,8e-4 sur grille fixe, avec 26,4 QWOT contre
31,4 et aucune couche sous 5 nm ([`tikhonravov/README.md`](tikhonravov/README.md)).
