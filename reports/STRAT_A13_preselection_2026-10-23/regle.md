# A13 — présélection des candidats de la recherche locale : règle écrite avant la mesure (2026-10-23)

Choisie par 👤 le 2026-10-23, commitée avant le premier lancement.

**Réglage mesuré** : `strat_local_search_presel_runs` = 75, `strat_local_search_presel_keep` = 3, contre l'étage actuel (sans
présélection), garde active dans les deux bras.

**Protocole** : `stage_ab.py.txt`, hors ligne, sur les huit cas jugés d'A14/A10 (48c premium 42 ; r75x1.5, r75x1.75, r75x2-2nm graine
77 ; 75c 101 et 202 ; r75x0.5 202 ; r75x2 101). Même plan de départ (celui de l'étage du banc), mêmes graines de recherche, de contrôle
et de confirmation dans les deux bras ; plans finaux jugés sur graines neuves (20261101001 + 1000 × rang du cas, 3 × 1 000 tirages,
mêmes tirages pour les deux bras), à ±0,005 et ±0,010.

**Règle.** La présélection est retenue comme candidate au défaut si, et seulement si :
1. sur **chaque** cas, le SEEL de son plan final ne dépasse pas de plus de **2 %** celui du plan final de l'étage actuel, à ±0,005
   **et** à ±0,010 (estimation ponctuelle) ;
2. sur chaque cas, son plan final n'a **pas plus d'arrêts** au jugement que celui de l'étage actuel, aux deux corridors ;
3. la durée totale de l'étage sur les huit cas baisse d'au moins **40 %**.

Sinon elle reste inactive. Le défaut ne change que sur décision de 👤.
