# A3 — Repère 99 couches, domaine d'indice = grille spectrale (option (a), 2026-10-24)

**SEEL 0,575 / 0,597 / 0,670 nm (graines 101 / 42 / 202), médiane 0,597 nm, 0 % de plantage.** Code `339e9cb3`,
`index_corridor_fixed_domain` armé : l'erreur d'indice est normalisée sur la grille spectrale seule, la même pour la croissance
et pour l'assemblage (C2), sans l'adoucissement de la plage de balayage
([preuve](../STRAT_domaine_fixe_6bancs_2026-10-24/bilan.md)). Partition 0-22 / 22-42 / 42-76 / 76-99, mode `fast`, fente 2 nm,
cache `reports/intervalles_99c_c2a/`. Toutes les tranches sont déposables, toutes leurs stratégies aussi. Cible 0,300 nm non atteinte.

Contre le domaine de balayage ([repère précédent](../STRAT_A3_C2_99c_2026-10-23/bilan.md), médiane 0,549 nm), la médiane monte de 9 %,
ce qui va dans le sens d'un bruit plus dur. Les deux campagnes ne partagent pas les plans, donc cet écart n'isole pas le seul effet du domaine.
Une seule partition est mesurée. [Pilote](run_a3_c2a.py.txt), [sortie](sortie.txt).
