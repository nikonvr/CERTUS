# A12 — passe guidée par l'indice : refusée par la règle écrite d'avance (2026-10-23)

Règle : [`regle.md`](regle.md) (« gain sans perte » : au moins 2 % de SEEL à ±0,005 sur deux cas sur trois). Banc : `stage_ab_a12.py.txt`,
8 couches les plus sensibles, groupes de 2 et 3. Arrêté après deux cas, qui suffisent à trancher.

| cas | durée de l'étage actuel → guidé | mouvements de groupe retenus | SEEL ±0,005 | SEEL ±0,010 | arrêts |
|---|---|---|---|---|---|
| 75c graine 202 | 1 161 → 1 330 s | 0 | 0,2091 → 0,2091 (+0,0 %) | 0,2497 → 0,2497 (+0,0 %) | identiques |
| r75x0.5 graine 202 | 1 057 → 4 050 s* | 0 | 0,3553 → 0,3553 (+0,0 %) | 0,3979 → 0,3979 (+0,0 %) | identiques |

\* machine partagée avec un autre calcul pendant ce cas.

Sur les deux cas, aucun déplacement de deux ou trois couches voisines n'abaisse l'erreur moyenne au bruit nominal sans ajouter
d'arrêt, une fois les deux passes d'une couche faites : le plan final est celui de l'étage actuel. La condition 3 ne peut plus être
remplie : **la passe guidée reste inactive.** Chiffres : `75c_deep_s202.json`, `r75x0.5_deep_s202.json`. Lecture : l'étage actuel
est déjà à un optimum local pour ces mouvements groupés ; la sensibilité par couche (A11) reste un diagnostic, pas un guide de recherche.
