# r75x2 sans rampes, protocole d'août, sept graines — D100 et D103 corrigés (2026-10-12)

Suite de `reports/STRAT_remesure_D100_2026-10-11.md` : la même campagne, après la correction de D103
(`reports/STRAT_D103_identifiants_en_double_2026-10-11.md`). Commande de chaque graine :
`python scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 <graine>`, sans surcharge, `CERTUS_BENCH_TIMEOUT_S=38400`,
une graine à la fois ; lanceur, durées et artefacts dans `reports/mesure_D103_2026-10-12/resume.txt`.

## Conditions

- **Code.** `6df9d294` pour le juge de paix et la graine 42 ; `411e6eb5` pour les six autres (commit de documentation
  seulement : aucun fichier de code ne change entre les deux). Aucun fichier suivi modifié pendant la campagne
  (`git_dirty` faux dans les sept artefacts). Les artefacts de la graine 42 portent `6df9d294` parce qu'ils
  enregistrent le commit du lancement.
- **Les interrupteurs atteignent le calcul** : 16 lignes `[RATE]` et 46 lignes `slit bias active` dans chacun des
  sept journaux. Aucun `WAIT_TIMEOUT`.
- **Juge de paix, avant les sept graines** (`reports/STRAT_bench_juge_de_paix_6df9d294_D103_2026-10-12.txt`) :
  `RESULT` 0.007917103726810235, 823 stratégies dont 154 éliminées, dix premiers rangs : identiques à ceux de
  `782972bf` (`reports/STRAT_bench_juge_de_paix_782972bf_D100_2026-10-11.txt`).
- **D103 n'agit plus** : dans aucun des sept journaux un identifiant ne désigne deux plans, et le garde-fou
  d'unicité ne se déclenche pas.

## Résultats par graine

| graine | août | matin du 2026-10-11 (D100 et D103 présents) | soir du 2026-10-11 (D103 présent) | **D100 et D103 corrigés** |
|---|---|---|---|---|
| 42 | 0 sur 1 617 | 674 sur 768, 0,5566 nm | retenue par le garde-fou | **147 sur 4 244, 0,6354 nm** (13 blocs) |
| 77 | 547 sur 2 231, 0,5692 nm | 814 sur 910, 0,5355 nm | 517 sur 5 036, 0,5404 nm | **517 sur 5 036, 0,5404 nm** (8 blocs) |
| 101 | 0 sur 1 630 | 1 124 sur 1 216, 0,5603 nm | 727 sur 5 514, 0,5634 nm | **727 sur 5 514, 0,5634 nm** (11 blocs) |
| 202 | 0 sur 1 646 | 661 sur 754, 0,5547 nm | 403 sur 5 192, 0,5837 nm | **403 sur 5 192, 0,5837 nm** (6 blocs) |
| 303 | 0 sur 1 680 | 671 sur 763, 0,5622 nm | 0 sur 4 144 | **0 sur 4 144**, plantage minimal 100 % |
| 404 | 372 sur 2 016, 0,5599 nm | 1 041 sur 1 107, 0,5426 nm | retenue par le garde-fou | **741 sur 5 157, 0,5323 nm** (11 blocs) |
| 505 | 311 sur 1 995, 0,6112 nm | 947 sur 1 038, 0,5629 nm | retenue par le garde-fou | **382 sur 4 954, 0,5493 nm** (10 blocs) |

« Déposables » : plantage ≤ 5 % au pire des trois niveaux de bruit (0,5×, 1×, 2× le bruit de lecture) ; SEEL du
meilleur d'entre eux, tel que le logiciel l'affiche.

- **Six graines sur sept trouvent des déposables** (42, 77, 101, 202, 404, 505) ; la 303 n'en trouve aucun (4 144
  stratégies, plantage minimal 100 %, dont 3 709 variantes Rate). Août : trois sur sept (77, 404, 505).
- **Meilleur SEEL par graine** : de 0,5323 nm (graine 404) à 0,6354 nm (graine 42), médiane 0,5563 nm, moyenne 0,5674 nm ;
  quatre graines sur six à 0,57 nm ou moins (77, 101, 404, 505 ; août : 77 et 404). Deux runs à moins de ~8 % l'un de
  l'autre sont indiscernables (ETAT, section 2), et la dispersion d'une graine à l'autre dépasse ce seuil.
- **Tous les déposables sont des plans ELITE** (147, 517, 727, 403, 741 et 382 plans) ; les 3 671 à 4 313 variantes Rate
  de chaque graine n'en donnent aucun.
- **Le meilleur plan de la graine 42 est au bord** : plantage 0 / 0,7 / 4,0 % aux bruits 0,5× / 1× / 2×, la classe de
  son SEEL (+0,01 nm) compte 7 plans, le plantage minimal de la graine est 2,7 %. Ceux des graines 101 et 202 sont à
  3,0 % et 4,7 % au bruit 2×.

## D103 : ce qu'il a changé, comparé au soir du 2026-10-11

Comparaison stratégie par stratégie des artefacts du soir et de ce matin, aux graines qui avaient terminé :

- **graines 101 et 202 : contenu identique** — mêmes identifiants dans le même ordre, mêmes scores, plantages par
  bruit, marges, λ, blocs et couches Rate, pour 5 514 et 5 192 stratégies ;
- **graines 77 et 303 : mêmes plans, mêmes scores, mêmes plantages et mêmes marges** (multiensembles égaux), mais
  18 et 41 stratégies ont changé de numéro — de `13349` à `801300349`, par exemple — et les libellés d'origine de leurs
  variantes Rate citent le nouveau numéro (267 et 516 lignes). Ce sont les groupements minés de rang 100 à 199 de leur
  carte ;
- **graines 42, 404 et 505** : le soir, le garde-fou retenait le classement final ; elles vont maintenant au bout.

La correction ne change donc aucun score là où aucune collision n'avait mordu, et elle débloque les runs qui
s'arrêtaient. Elle ne permet pas de comparer les graines 42, 404 et 505 à l'ancien code : il n'a jamais fini ces runs.

## Ce qui n'est pas conclu

- **Août contre aujourd'hui** (trois graines sur sept contre six) : le code a beaucoup changé entre les deux
  (grille de la machine, classement R130, correctifs D5 à D103). La mesure ne dit pas lequel y est pour quelque chose.
- **Matin contre aujourd'hui** : les SEEL montent de 0,9 % (graine 77), 0,6 % (101), 5,2 % (202) et 14 % (42) quand le
  biais de fente et le Rate sont rétablis, et baissent de 1,9 % (404) et 2,4 % (505). Sous le σ ≈ 1,8 % que l'ETAT mesure
  en changeant le triplet de graines de consensus, seules les hausses des graines 202 et 42 le dépassent nettement. Je
  n'ai pas mesuré la part du biais de fente.
- **La graine 303**, qui trouvait 671 déposables sans biais de fente, n'en trouve aucun avec. Une graine ne fait pas
  une tendance : sept graines, une exception.
- **L'ELITE « tour à tour »** : une seule graine (202), et son effet change de signe d'un modèle à l'autre (section suivante).

## ELITE « tour à tour » (graine 202)

Lancé après les sept graines, même commit (`411e6eb5`), même graine, avec `CERTUS_PROBE_OVERRIDES=elite_round_robin=true`
(la surcharge est consignée dans l'artefact `reports/blocs_vs_plantage_r75x2_deep_s202_rr_20261012_062518.json`) :

| graine 202 | nue | tour à tour |
|---|---|---|
| stratégies | 5 192 | 5 155 |
| déposables | 403 | 368 (−9 %) |
| meilleur SEEL | 0,5837 nm (6 blocs) | 0,5602 nm (12 blocs), 4,0 % plus bas |
| plantage minimal | 4,0 % | 2,0 % |
| plans ELITE | 753 | 739, dont 3 communs avec la nue |
| plans déposables communs aux deux | — | 0 |

- **L'option atteint le calcul** : les populations ELITE sont presque disjointes (3 plans communs sur 739 et 753).
- **Son effet n'est pas stable d'un modèle à l'autre.** Sous D100 (le matin du 2026-10-11, sans Rate ni biais de fente), la même graine
  rendait 33 % de déposables en plus et un SEEL du meilleur plan dans le bruit (0,5662 contre 0,5547 nm ;
  `reports/STRAT_r75x2_sept_graines_protocole_aout_2026-10-11.md`). Avec D100 et D103 corrigés, elle rend 9 % de déposables
  en moins et un SEEL du meilleur plan plus bas de 4,0 %, au-delà du σ ≈ 1,8 % de l'ETAT mais sur une seule paire de runs.
- **Rien n'autorise à l'armer par défaut** : une graine, deux modèles, deux signes. Ce choix est à 👤.
