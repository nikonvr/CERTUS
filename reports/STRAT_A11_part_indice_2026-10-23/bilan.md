# A11 — part de l'erreur due à l'indice, sur les trois 75 couches (Claude, 2026-10-23)

Code `07805ceb` : `strat_index_share_top_k` (0 = éteint) calcule, pour les K meilleures stratégies, **part d'indice = 1 − RMSE²(corridor
nul) / RMSE²(corridor configuré)**, même plan, mêmes tirages, bruit nominal, tirages aboutis des deux côtés ; colonne « Index share % »
du tableau et des exports, présente seulement quand elle est calculée. Mesure : `a11_index_share.py.txt` (la fonction de STRAT
sur les dix premières stratégies des bancs de la garde, `reports/STRAT_garde_A10_2026-10-22`, 300 tirages), chiffres dans `a11_index_share.json`.

| composant (graine de banc) | n°1, recherche locale : part d'indice | ELITE n°2 à 10 | part d'indice absolue n°1 / n°2 | reste n°1 / n°2 |
|---|---|---|---|---|
| 75c (202) | 56 % | 59 à 71 % | 0,37 | 0,46 |
| r75x0.5 (202) | 45 % | 40 % | 0,68 | 0,55 |
| r75x2 (101) | 89 % | 94 % | 0,67 | 1,25 |

- Sur l'étalon `r75x2`, **l'erreur d'indice fait environ 90 % de l'erreur** des meilleurs plans (60 couches Rate sur 75 pour l'ELITE) ;
  sur `r75x0.5`, 40 à 45 % ; sur 75c, 56 à 71 %.
- La recherche locale réduit la part due à l'indice **en valeur absolue** sur les trois composants (facteurs 0,37 à 0,68). Sur `r75x2`,
  elle passe 16 couches du Rate à l'optique et l'erreur hors indice augmente un peu (×1,25) : son gain vient de la moindre sensibilité à
  l'indice, ce que la surveillance optique compense et le Rate non.
- Limites : une graine de banc par composant, une graine de tirages (300) ; la part relative dépend aussi du reste de l'erreur, la
  colonne absolue le complète. Le modèle de Rate de STRAT n'a pas de dérive de la source.
