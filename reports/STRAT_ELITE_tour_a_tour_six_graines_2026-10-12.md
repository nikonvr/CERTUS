# ELITE « tour à tour » sur six graines — `r75x2`, `deep`, fente 2 nm, D100 et D103 corrigés (2026-10-12)

Mesuré le 2026-10-12 de 07:27 à 11:42, arbre `2eb52a38` (les artefacts disent `2eb52a38`), six graines à la suite :
`CERTUS_PROBE_OVERRIDES=elite_round_robin=true CERTUS_PROBE_TAG=rr python scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 <graine>`.
Le comparatif est la mesure « nue » du même jour (`reports/STRAT_r75x2_sept_graines_D100_D103_corriges_2026-10-12.md`, code `411e6eb5`
ou `6df9d294` pour la graine 42), graine par graine. Résumé et journaux : `reports/mesure_rr_D103_2026-10-12/`.

## Résultat

| graine | déposables, nue → tour à tour | meilleur SEEL (nm), nue → tour à tour | écart du SEEL |
|---|---|---|---|
| 42 | 147/4244 → **561**/4816 | 0,6354 → **0,5420** | **−14,7 %** |
| 77 | 517/5036 → 457/4980 | 0,5404 → 0,5474 | +1,3 % |
| 101 | 727/5514 → **869**/5658 | 0,5634 → 0,5793 | +2,8 % |
| 303 | 0/4144 → 0/4144 | aucun déposable | — |
| 404 | 741/5157 → 444/4578 | 0,5323 → 0,5318 | −0,1 % |
| 505 | 382/4954 → **424**/4558 | 0,5493 → 0,5530 | +0,7 % |

- **Cinq graines sur six trouvent des déposables, avec ou sans l'option** (la 303 n'en trouve aucun dans les deux cas).
- **Écart du meilleur SEEL : médiane +0,7 %, moyenne −2,0 %** sur les cinq graines qui ont les deux. La moyenne ne tient qu'à la graine 42,
  dont la mesure nue était la pire de la série (147 déposables, 0,6354 nm) ; sans elle, l'option est en moyenne **+1,2 % plus mauvaise**
  (77, 101, 404, 505).
- Le nombre de déposables monte sur trois graines (42, 101, 505) et baisse sur deux (77, 404).
- **L'option arrive bien au calcul** : les surcharges consignées dans chaque artefact sont `{'elite_round_robin': True}`, et les plans
  ELITE diffèrent presque entièrement (0 à 27 plans communs sur 549 à 1 244 ; 435 plans hors ELITE, tous communs, à la graine 303 où
  l'ELITE est vide).

## Ce que cela décide, et ne décide pas

**Pas de gain net démontré.** Sur six graines, l'ELITE « tour à tour » est meilleure une fois (de beaucoup), équivalente une fois,
moins bonne trois fois (de 0,7 à 2,8 %) : un écart du même ordre que la dispersion entre graines d'un même protocole (0,53 à 0,58 nm).
Je ne l'arme pas par défaut ; la décision reste à 👤 (ETAT §5).

Non mesuré : le bruit d'une même graine rejouée (un seul tirage par graine et par mode ici ; un cache Numba à froid décale les derniers
chiffres et la population de plans n'est alors pas identique au bit, mesuré le 2026-10-11) ; l'effet à d'autres protocoles que celui
d'août.

## Hygiène de la mesure

Des calculs de saphir ont tourné en parallèle de 08:47 à 09:17 (un ajustement a pris environ 11 cœurs, la SVD de `least_squares` sans
limite de threads), puis à un thread. Les durées par graine (38,3 ; 46,9 ; 59,3 ; 35,1 ; 40,1 ; 35,0 min, `WAIT_TIMEOUT=0` partout) en
portent la trace. Je n'ai trouvé aucun budget en temps réel dans la recherche de STRAT (`time.time()` ou `monotonic()` borne seulement
INDEX et le Sellmeier de substrat), donc les résultats ne dépendent pas de la charge ; je ne l'ai pas vérifié en rejouant une graine à vide.
