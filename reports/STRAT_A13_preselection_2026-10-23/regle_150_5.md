# A13 — présélection 150 tirages / 5 candidats : règle écrite avant la mesure (2026-10-23)

Choisie par 👤 le 2026-10-23 après le refus de 75/3 ([bilan](bilan.md)), commitée avant le premier lancement. Même protocole et
mêmes huit cas que [`regle.md`](regle.md) (`stage_ab.py.txt REPO CASE OUT 150 5 [PRÉCÉDENT]` ; le bras « actuel », déterministe, est
repris d'un résultat précédent du même cas quand il existe). Arrêt dès qu'un cas viole la règle.

**Règle.** 150/5 est retenu comme candidat au défaut si, et seulement si : (1) sur chaque cas, le SEEL de son plan final ne dépasse
pas de plus de **2 %** celui de l'étage actuel, à ±0,005 et à ±0,010 ; (2) sur chaque cas, pas plus d'arrêts au jugement ; (3) la
durée totale de l'étage sur les huit cas baisse d'au moins **25 %**. Sinon il reste inactif. Le défaut ne change que sur décision de 👤.
