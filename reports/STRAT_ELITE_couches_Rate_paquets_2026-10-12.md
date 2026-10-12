# ELITE déplace les couches Rate : de l'optique, un paquet de Rate, de l'optique à une autre longueur d'onde (2026-10-12)

Question de 👤 (2026-10-12) : *« est-ce que tu autorises après le Rate à reprendre en optique ? C'est important ! »* ; *« l'expérience
empirique montre qu'il y a des fois de bonnes stratégies avec des paquets d'optique à une longueur d'onde, puis un paquet de Rate, puis
un paquet d'optique à une autre longueur d'onde, etc. Mais c'est purement empirique ! »*

## Réponse

- **Le noyau l'autorise** : `rate_layers` est un ensemble quelconque de couches, et une couche optique est arrêtée sur son propre signal quelle
  que soit la façon dont les précédentes ont été posées (`tests/unit/test_strat_optics_after_rate.py`). Elle perd seulement les extrema qu'elle
  empruntait à la couche d'avant.
- **La recherche ne le proposait pas** : les plans déposables des mesures du 2026-10-12 avec de l'optique après du Rate avaient tous exactement
  deux paquets de Rate (une couche isolée, puis la queue) ; les secours ne posent que des queues, et ELITE rendait à ses enfants les couches Rate
  du parent sans les changer.
- **ELITE sait maintenant les déplacer** (`elite_rate_moves`) : une couche de plus ou de moins au bout d'un paquet de Rate, un trou d'optique
  refermé, une fenêtre d'optique ouverte dans un paquet, un paquet de Rate posé dans l'optique. Les blocs ne changent pas : les couches
  d'optique gardent la λ de leur bloc, qu'ELITE affine comme avant.
- **Mesuré, il donne un meilleur SEEL partout où le Rate domine, et ne coûte rien ailleurs** (une graine par composant) :

| composant | sans (production du matin) | avec | écart | le meilleur plan |
|---|---|---|---|---|
| `r75x0.5`, graine 101 | 0,4981 nm | **0,3967 nm** | **−20,4 %** | optique 1 à 6, **Rate 7 à 10**, optique 11 et 12 (λ 451 nm), **Rate 13 à 34**, optique 35 et 36, **Rate 37 à 75** ; 9 blocs ; plantage nul aux trois bruits |
| juge de paix (48 couches, `premium`, graine 42) | 0,1849 nm | **0,1721 nm** | **−6,9 %** | 2 blocs ; optique 1 à 26, Rate 27 à 39, optique 40 et 41, Rate 42 à 48 |
| `r75x2`, graine 101 | 0,5406 nm | 0,5358 nm | −0,9 % | Rate de la couche 5 seule, optique 6 à 15, Rate 16 à 74, la dernière couche en optique |

Toutes les listes restent entièrement déposables (4 074 plans à `r75x0.5`, 2 652 au juge de paix, 4 678 à `r75x2`).

## Ce que la mesure établit, et ce qu'elle laisse ouvert

- **Plus de forme** : à `r75x0.5`, des 4 074 plans de la liste, 2 819 ont un seul paquet de Rate, 933 deux, 309 trois, 13 quatre (sans l'option : au plus
  deux). Les cinquante meilleurs plans se répartissent en cinq jeux de couches Rate, dont trois en portent 48 ; le meilleur est à trois paquets de Rate.
- **Une vérification indépendante du score** : le rejeu de la graine de base par la sonde (300 tirages, hors consensus) donne, pour le meilleur plan
  de chaque liste, un centile 95 de RMSE (pire niveau de bruit) de 0,0399 avec l'option contre 0,0661 sans (`r75x0.5`). Le gain n'est pas un effet
  du score de consensus.
- **Les fenêtres d'optique que l'option ouvre sont courtes** : deux couches (une de chaque matériau) à `r75x0.5` (deux fenêtres) et au juge de paix (une) ; à
  `r75x2`, elle remet seulement la dernière couche en optique. Ce que je ne sais pas : pourquoi elles aident. Mon hypothèse, que je n'ai pas isolée : une couche d'optique est arrêtée sur le niveau que donne le
  signal réel à sa λ, donc elle compense à cette λ l'erreur que le paquet de Rate d'avant a laissée ; et la vitesse estimée des paquets suivants repose sur
  plus de couches de référence.
- **Le gain dépend du composant** : fort là où presque tout est au Rate (`r75x0.5`, des couches fines), faible à `r75x2`. Les graines 42 et 202 de `r75x0.5`,
  les composants ×1,5 et ×1,75, le passe-bande de 35 couches et celui de 99 couches ne sont pas mesurés avec l'option.
- **Le modèle de Rate de STRAT n'a ni dérive de la source ni bruit propre de la vitesse** (`reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`) : ces
  SEEL sont ceux du modèle. Que des paquets alternés tiennent mieux en salle est ce que 👤 observe ; le modèle n'en est pas la preuve.
- **Le meilleur de plusieurs milliers** : l'effet de sélection existe (le score de consensus en corrige une partie, le rejeu le confirme).
- **Coût en calcul** : jusqu'à 120 candidats de plus par tour d'ELITE ; les durées mesurées (44, 9 et 44 minutes, sur une machine seule) sont du
  même ordre que celles de la production du matin, qui avaient d'autres charges : je n'ai pas de comparaison propre.

## Protocole

`CERTUS_PROBE_OVERRIDES="elite_rate_moves=true" CERTUS_PROBE_TAG=ratemoves python scripts/probe_blocs_vs_plantage.py <composant> <mode> … <graine> 0`, au
commit `cea0db66` (arbre propre), `r75x0.5 deep 0 0 2 0 101 0`, `48c premium 1 0 2 0 42 0`, `r75x2 deep 0 0 2 0 101 0` ; les défauts de production du
matin (D96 à D98, secours Rate, `rate_by_swing`, D106 corrigé) pour tout le reste. « Sans » : `40642146` (`r75x0.5`), `03990e9a`/`dbf8025f` (juge de paix,
`r75x2`), mêmes commandes. L'option est active par défaut depuis `978b8f04`.

## Artefacts

`reports/STRAT_ELITE_couches_Rate_2026-10-12/` : `blocs_vs_plantage_r75x0.5_deep_s101_ratemoves_cea0db66.json`,
`blocs_vs_plantage_48c_premium_s042_ratemoves_cea0db66.json`, `blocs_vs_plantage_r75x2_deep_s101_ratemoves_cea0db66.json`. Chacun porte le commit, l'état de
l'arbre et les surcharges qui l'ont produit.
