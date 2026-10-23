# DESIGN plus performant — séparatrice 50/50 400–1200 nm (2026-10-22/23)

Contraintes de 👤 : H/L seulement, indices inchangés, ≤ 34 couches, ≤ 30 QWOT. RMSE de T sur grille fixe de 0,5 nm,
recoupé par l'oracle indépendant. Détail de chaque levier, commandes et défauts : [`journal.md`](journal.md).

| | RMSE (grille fixe) | couches · QWOT | temps |
|---|---|---|---|
| DESIGN par défaut (PGLOBAL), 3 runs | 0,0018 – 0,0042 | 21 – 27 · ~19 | 1,5 – 2,5 min |
| **DESIGN, réglage mémétique**, 3 runs | **0,000147 – 0,000215** (médiane 0,000172) | 34 · 25,8–26,8, couches ≥ 5 nm | 7 – 9 min |
| sonde hors fenêtre (sans plancher de 5 nm) | 0,000168 | 32 · 25,6 | ~1 h |

**Réglage** : `run_optim("global", memetic_children=1000, memetic_population=30, memetic_qwot_max=30)` et, sur la
fenêtre, `_pareto_champion_respects_5nm = True` ; départ 34 lignes QWOT, `allow_growth` faux. Tout est inactif par défaut.

**Esquisse RMSE / couches** (10 à 35 couches de départ, un run DESIGN chacune, réglage mémétique) :
[`sweep/best_by_layers.png`](sweep/best_by_layers.png), tableau [`sweep/best_by_layers.csv`](sweep/best_by_layers.csv).
DESIGN passe sous 1e-3 dès 22 couches réelles ; la dispersion d'un run à l'autre est de ±20 % ou plus.

**Défauts de DESIGN trouvés** : bornes globales à 1,2 QWOT par couche ; règle finale des 5 nm sans réoptimisation ;
champion Pareto qui ignore cette règle (option corrigée) ; export qui écrivait un autre design dans le tableau (corrigé,
`76349415`).

**Décisions de 👤** : activer le mémétique et l'option de champion par défaut ; leurs réglages par défaut ; la réoptimisation
après la règle des 5 nm (`_polish_after_5nm_rule`, défaite aujourd'hui par la restauration du champion).

**Validation** (CLAUDE.md §2, `validate_parallel.py`, `34febabe` + ETAT) : ruff, oracle 1149, unit 5608, ui 1324, reste 319,
performance 40 réussis ; un seul échec réel, la taille de la section 0 d'ETAT.md (corrigée, test vert ensuite) ;
`coherence_md` échoue sur une commande morte antérieure (`ETAT_actions.md:67`, script STRAT absent).
