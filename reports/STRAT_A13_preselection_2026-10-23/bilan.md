# A13 — présélection 75 tirages / 3 candidats : refusée par la règle écrite d'avance (2026-10-23)

Règle : [`regle.md`](regle.md). Banc : `stage_ab.py.txt`. Arrêté après le premier cas, qui suffit à trancher : la règle exige
au plus +2 % de SEEL **sur chaque cas**.

| 75c graine 202 | étage actuel | présélection 75/3 |
|---|---|---|
| durée de l'étage | 1 161 s | 576 s (−50 %) |
| évaluations (300 tirages + présélection) | 2 166 | 443 + 2 314 à 75 tirages |
| SEEL à ±0,005 (départ 0,2448) | 0,2091 nm | 0,2183 nm (+4,4 %) |
| SEEL à ±0,010 (départ 0,8956) | 0,2497 nm | 0,2682 nm (+7,4 %) |
| arrêts au jugement (±0,005 / ±0,010) | 1 / 6 | 0 / 1 |

La présélection divise la durée par deux et améliore encore nettement le plan de départ, mais elle perd 4 à 7 % de SEEL sur le plan
de l'étage actuel : à 75 tirages, le tri écarte parfois le meilleur candidat. **Elle reste inactive.** Chiffres complets :
`75c_deep_s202.json`. Pistes, à mesurer sous la même règle : garder plus de candidats (5 ou plus) ou trier sur plus de tirages
(150), au prix d'un gain de durée plus faible.
