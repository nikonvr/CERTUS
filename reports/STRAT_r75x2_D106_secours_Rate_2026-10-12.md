# r75x2 : ce que D106 cachait, et ce que rend le secours Rate (2026-10-12)

`r75x2` est le composant étalon (75 couches aléatoires, épaisseurs doublées, fente 2 nm, un seul verre témoin). Jusqu'ici ETAT
écrivait que, sans rampes, six graines sur sept y trouvent des déposables (meilleur SEEL de 0,5323 à 0,6354 nm). Ce rapport refait la
mesure au code final et isole D106 (les enfants d'ELITE étaient notés sans le biais de fente).

## Réponse

- **Sans rampes, `r75x2` n'est pas fabricable en optique pure** une fois les enfants d'ELITE notés avec le biais de fente comme tous les
  autres plans : 0 déposable sur 4 821 stratégies (graine 101) et sur 4 561 (graine 42), ancien modèle d'arrêt, sans secours Rate,
  plantage minimal de 100 % aux deux graines.
- **D106 est la cause, mesurée par un A/B** (graine 101, même code, même ancien modèle, sans secours) : avec D106 remis dans l'état d'avant
  la correction, **706 déposables sur 6 042** stratégies, meilleur SEEL 0,5624 nm ; avec la correction, **0 sur 4 821**. Les « six graines
  sur sept » d'ETAT (727 déposables à la graine 101 au commit `411e6eb5`, 0,5634 nm) étaient des plans d'ELITE qui n'avaient pas le biais
  de fente.
- **Avec les défauts de production** (D96 à D98, secours Rate, `rate_by_swing`, D106 corrigé) : **tous les plans de la liste sont déposables**
  aux deux graines, 4 175 (graine 101) et 4 307 (graine 42), plantage nul pour le meilleur, meilleur SEEL **0,5406** et **0,5678 nm**. Aucun
  n'est un plan optique pur.

## Protocole

`python scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 <graine> 0` (`deep`, fente 2 nm, un seul verre témoin, graine de robustesse =
graine), au commit `dbf8025f`, un arbre propre (`git worktree`), `CERTUS_BENCH_TIMEOUT_S=21600`. « Ancien » :
`CERTUS_PROBE_OVERRIDES="exact_inversion=false,exact_anchors=false,oms_arming=0,rate_rescue=false"` (l'ancien modèle d'arrêt, sans secours
Rate). L'A/B ajoute à l'ancien un arbre modifié : dans `certus/core/certus_strat_consensus.py`, `_attach_slit_profiles` ne fait rien
(`git_dirty` vrai dans l'artefact), c'est-à-dire que les enfants d'ELITE et de la recherche locale n'ont pas de profil de fente, comme avant `6fcdd56a`.

## Résultats

| exécution | stratégies | déposables | plantage minimal | meilleur SEEL | classes des déposables |
|---|---|---|---|---|---|
| production, graine 101 | 4 175 | **4 175** | 0 % | **0,5406 nm** | 623 mixtes (de l'optique après du Rate), 3 552 queues, 0 optique pur |
| production, graine 42 | 4 307 | **4 307** | 0 % | **0,5678 nm** | 821 mixtes, 3 486 queues, 0 optique pur |
| ancien, graine 101 | 4 821 | **0** | 100 % | — | |
| ancien, graine 42 | 4 561 | **0** | 100 % | — | |
| ancien, D106 remis comme avant, graine 101 | 6 042 | **706** | 2,67 % | 0,5624 nm | 627 mixtes (une couche Rate), 13 optique pur, 66 queues (une couche Rate) |

Pour mémoire, avant D106 (`reports/STRAT_r75x2_sept_graines_D100_D103_corriges_2026-10-12.md`, `411e6eb5`, ancien modèle, sans secours) :
graine 101, 727 déposables sur 5 514, 0,5634 nm ; graine 42, 147 sur 4 244, 0,6354 nm. Le rejeu de la graine 101 avec D106 remis (706 sur
6 042, 0,5624 nm) retrouve ces ordres de grandeur.

Les plans gagnants :

- **graine 101** : un plan mixte à 10 blocs (ELITE), le Rate de la couche 5 (indice 4) seule, de l'optique de la couche 6 à la 15, puis le
  Rate de la couche 16 (indice 15) à la fin : 61 couches au Rate. La meilleure queue pure vaut 0,5532 nm (Rate dès l'indice 15).
- **graine 42** : une queue (ELITE) à 75 blocs, une λ par couche, le Rate des 23 dernières couches (indices 52 à 74) ; le meilleur plan
  mixte vaut 0,6215 nm.

## Lecture

- **D106 retire à `r75x2` ses déposables optiques.** Une fois les enfants d'ELITE notés comme les autres plans, la lignée optique pure ne
  tient plus : ELITE ne retient aucun candidat (« no candidate beat nominal threshold » dans les 46 passes du journal de la graine 101), les
  parents plantent tous dans 100 % des tirages.
- **Tout repère `r75x2` sans rampes d'avant D106 est à refaire** : les nombres de graines qui trouvent des déposables (six sur sept ; trois en
  août), les meilleurs SEEL (0,5323 à 0,6354 nm) et la phrase « tous les déposables sont des plans ELITE » parlent de plans sans le biais de
  fente. Le même doute pèse sur l'ELITE « tour à tour » des six graines (`reports/STRAT_ELITE_tour_a_tour_six_graines_2026-10-12.md`), mesuré
  avant D106.
- **Le secours Rate rend le composant fabricable au modèle de Rate de STRAT**, qui n'a ni dérive de la source ni bruit propre de la vitesse
  (`reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`). Ces SEEL sont ceux de ce modèle ; je n'ai pas mesuré ce que vaut un plan à 61 couches
  au Rate sur une machine dont la vitesse dérive.
- **Les deux graines ne donnent pas le même type de plan** (un mixte et une queue tardive), ce qui va dans le sens d'une recherche qui
  trouve plusieurs formes ; avec deux graines, je n'ai pas de dispersion.

## Ce que ce rapport ne mesure pas

- Les graines 77, 202, 303, 404 et 505 (ETAT en comptait sept) : seules 101 et 42 sont refaites. L'A/B de D106 n'est fait qu'à la graine 101
  (la graine 42 « ancien » donne 0 déposable avec D106, sans l'A/B).
- La configuration livrée avec rampes (`example/example_strat/JSON-strat-random75-x2-fabricable-2nm.json` et `rampes_r75x2-2nm.json`), dite
  fabricable (SEEL 0,5676 nm, plantage 1,67 %) : mesurée avant D106, à refaire.
- Une exécution par graine et par configuration ; les plans sont des meilleurs de plusieurs milliers (effet de sélection).

## Artefacts

`reports/STRAT_r75x2_D106_secours_Rate_2026-10-12/` : `blocs_vs_plantage_r75x2_deep_s{101,042}_production_dbf8025f.json` ;
`..._ancien_dbf8025f_reduit.json` (graines 101 et 042) ; `..._s101_ancien_sans_d106_dbf8025f_modifie_reduit.json` (arbre modifié). Les trois
« réduits » n'ont plus, par stratégie, `margin_by_layer`, `lambdas` ni `rmse_par_bruit` (pour garder le dépôt léger) ; le reste est l'artefact
tel que la sonde l'a écrit. Chaque artefact porte le commit, l'état de l'arbre et les surcharges qui l'ont produit.
