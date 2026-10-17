# Base de dépôts — CERTUS INDEX retrouve-t-il les ajustements certifiés de l'application autonome ? (2026-10-12)

`python scripts\bench_base_depots.py --runs 3`, code `411e6eb5` (aucun fichier suivi modifié :
`git_dirty` false), 11 références × 3 exécutions, 33 exécutions de 3 à 53 s.
Artefact : `reports/bench_base_depots_411e6eb5_2026-10-12.json`.

## Ce que le banc compare

Les références sont les ajustements certifiés de l'application CERTUS INDEX autonome (`CERTIFIED_FRESNEL_CONFIGS`) dont
le spectre embarqué est un dépôt de la base, rapproché sur les données (onze sur vingt-sept ; `example/database_depots/
references_index.json`). **Ce sont des sorties d'ajustement, pas des mesures indépendantes** : le banc dit si INDEX
retrouve le même optimum sur les mêmes données, non s'il retrouve la vérité.

Chaque mesure est chargée dans la fenêtre INDEX comme un utilisateur le fait (`load_file`), avec le substrat, la
normalisation et la bande de la référence ; INDEX choisit lui-même son épaisseur de départ et ses bornes. Les boîtes de
dialogue répondent OUI, donc l'extension IR tourne quand la bande dépasse 2 500 nm et commence sous 2 200 nm : INDEX
ajuste alors le modèle jusqu'à 2 200 nm, puis fige l'épaisseur et l'indice sous 2 500 nm (colonne « étages » = 2).
Épaisseur et indice sont ceux de ce premier étage ; la RMSE est celle du résultat final.

## Résultats

Écart à la référence, trois exécutions séparées par « ; ». L'indice est comparé **au milieu de la bande ajustée**
(plafonnée à 2 200 nm pour un ajustement en deux étages) ; l'écart à 633 nm suit, avec † quand 633 nm est hors de la
bande ajustée.

| référence | étages | bande (nm) | d réf. (nm) | écart d (%) | écart n(milieu) | écart n(633) | RMSE INDEX |
|---|---|---|---|---|---|---|---|
| `h400` | 2 | 1150-5200 | 2953,7 | +0,73 ; +0,74 ; +1,98 | −0,016 ; −0,016 ; −0,041 | +0,081 ; +0,084 ; +0,069 † | 0,0033 ; 0,0034 ; 0,0073 |
| `h800` | 1 | 1000-2400 | 2959,3 | +0,34 ; +0,33 ; +0,33 | −0,012 ; −0,012 ; −0,012 | +0,044 ; +0,045 ; +0,044 † | 0,0043 ; 0,0043 ; 0,0043 |
| `mesures-nb1200` | 2 | 1200-2620 | 1717,8 | −0,35 ; −0,35 ; −0,29 | +0,007 ; +0,007 ; +0,006 | +0,205 ; +0,130 ; +0,181 † | 0,0011 ; 0,0019 ; 0,0021 |
| `mesures-ta1200` | 2 | 1200-5200 | 1705,0 | −0,14 ; −0,14 ; −0,14 | +0,005 ; +0,005 ; +0,005 | +0,148 ; +0,110 ; +0,047 † | 0,0019 ; 0,0037 ; 0,0037 |
| `h400-sio2` | 2 | 1150-5200 | 3326,5 | −1,74 ; −1,66 ; −1,78 | +0,027 ; +0,027 ; +0,028 | +0,073 ; +0,082 ; +0,093 † | 0,0028 ; 0,0028 ; 0,0029 |
| `mesures-fab18-sio2` | 2 | 400-5200 | 3323,7 | −0,64 ; −0,64 ; −0,63 | +0,012 ; +0,012 ; +0,012 | +0,011 ; +0,011 ; +0,011 | 0,0025 ; 0,0025 ; 0,0025 |
| `mesures-c1b-sio2` | 1 | 186-800 | 224,7 | −49,23 ; −49,23 ; −49,23 | +0,349 ; +0,349 ; +0,349 | +0,317 ; +0,317 ; +0,317 | 0,2029 ; 0,2029 ; 0,2029 |
| `sb2s3-silice` | 1 | 550-2400 | 317,4 | −3,85 ; −3,85 ; −3,85 | +0,110 ; +0,110 ; +0,110 | +0,108 ; +0,108 ; +0,108 | 0,0562 ; 0,0561 ; 0,0562 |
| `mesures-yf3vis` | 1 | 600-2400 | 2159,9 | −0,24 ; −0,23 ; −0,24 | +0,004 ; +0,004 ; +0,004 | +0,003 ; +0,003 ; +0,003 | 0,0020 ; 0,0020 ; 0,0020 |
| `pe-nb2` | 2 | 1000-2630 | 3019,7 | −1,19 ; −1,19 ; −0,97 | +0,022 ; +0,022 ; +0,017 | +0,061 ; +0,085 ; +0,058 † | 0,0035 ; 0,0033 ; 0,0035 |
| `pe-ta2` | 2 | 1000-2860 | 3008,4 | −0,07 ; −0,01 ; −0,05 | +0,004 ; +0,003 ; +0,004 | −0,032 ; −0,027 ; −0,033 † | 0,0021 ; 0,0021 ; 0,0021 |

† 633 nm est hors de la bande : l'indice y est extrapolé par le modèle, de la référence comme d'INDEX.

## Lecture

- **Neuf références sur onze : épaisseur à moins de 2,0 % de la référence aux trois exécutions**, dont 6 à moins de
  1 % (`h800`, `mesures-nb1200`, `mesures-ta1200`, `mesures-fab18-sio2`, `mesures-yf3vis`, `pe-ta2`). L'écart d'indice
  au milieu de la bande est de 0,042 au plus pour ces neuf.
- **Deux références ne sont pas retrouvées**, et leurs trois exécutions rendent le même résultat (un échec
  systématique, non une fluctuation) : `mesures-c1b-sio2` (épaisseur −49,2 %, indice au milieu de la bande +0,349,
  RMSE 0,203 contre 0,0011 à 0,0073 pour les neuf autres) et `sb2s3-silice` (épaisseur −3,85 %, indice +0,110, RMSE
  0,056). Toutes deux sont sur substrat de silice, en un étage ; la première est un film de SiO2 sur SiO2 en mode
  normalisé. **Je n'ai pas cherché la cause** : le banc, l'importation (substrat, normalisation) ou INDEX peuvent
  chacun en être responsables.
- **L'indice à 633 nm ne se compare pas** quand la bande commence à 1 000 ou 1 200 nm : les écarts atteignent 0,205 et
  varient d'une exécution à l'autre pour la même référence. Au milieu de la bande ils sont stables.
- **INDEX n'est pas reproductible** (ETAT, section 3) : l'épaisseur varie de moins de 0,5 point entre exécutions, sauf
  `h400` (1,25 point).

## Ce que ce rapport ne dit pas

- Laquelle des deux, la référence ou INDEX, est la plus proche du dépôt réel : les deux ajustent les mêmes données.
- Si le substrat de saphir d'INDEX (Sellmeier) et celui de l'application autonome sont le même modèle.
- Rien sur les seize références de l'application dont le spectre n'est pas dans la base.
