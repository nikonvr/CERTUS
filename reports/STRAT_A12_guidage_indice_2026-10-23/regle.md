# A12 — passe guidée par l'indice : règle écrite avant la mesure (2026-10-23)

Choisie par 👤 le 2026-10-23, commitée avant le premier lancement.

**Réglage mesuré** : `strat_local_search_index_guided_layers` = 8, `strat_local_search_index_guided_group` = 3 (paires et triplets),
contre l'étage actuel, garde active dans les deux bras.

**Protocole** : `stage_ab_a12.py.txt`, hors ligne, trois cas : 75c graine 202, `r75x0.5` graine 202, `r75x2` graine 101. Même plan de
départ, mêmes graines de recherche, de contrôle et de confirmation ; le bras actuel, déterministe, est repris des résultats d'A13
(`reports/STRAT_A13_preselection_2026-10-23/`). Plans finaux jugés sur graines neuves (3 × 1 000 tirages, mêmes tirages pour les deux
bras), à ±0,005 et ±0,010.

**Règle (« gain sans perte »).** La passe guidée est retenue comme candidate au défaut si, et seulement si :
1. sur **chaque** cas, le SEEL de son plan final n'est pas pire de plus de **1 %** que celui de l'étage actuel, à ±0,005 et à ±0,010 ;
2. sur chaque cas, **pas plus d'arrêts** au jugement, aux deux corridors ;
3. elle gagne **au moins 2 %** de SEEL à ±0,005 sur la **majorité** des cas (deux sur trois).

Sinon elle reste inactive. Le défaut ne change que sur décision de 👤.
