# CERTUS — acquis du Rate et corrections qui invalident des mesures

> Ce contenu **fait autorité** ;
> `ETAT.md` n'en garde qu'un renvoi. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus sont les sections de `ETAT.md`. Les travaux actifs sont dans [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md).

**Vocabulaire.**
*Rate* : couche posée pour un temps, à la vitesse estimée sur les couches du même matériau contrôlées optiquement (ce n'est pas un quartz).
*Paquet de Rate* : couches consécutives au Rate. *Fenêtre d'optique* : couches contrôlées optiquement entre deux paquets. *Queue* : le Rate va
d'une coupure à la dernière couche. *Plan mixte* : de l'optique après du Rate. *Plan optique pur* : aucune couche au Rate. *Déposable* :
plantage inférieur à 5 % au pire des trois niveaux de bruit (0,5×, 1×, 2×). *SEEL* = 2·√score, en nm, toujours rapporté avec la graine et le
mode. Les indices de couche des artefacts commencent à 0 ; l'interface et les rapports numérotent à partir de 1 (« L18-L75 » = indices 17 à 74).

**Acquis du Rate (programme R0–R6, clos le 2026-10-16).** [Bilan final et limites](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md),
[synthèse du 2026-10-14](../reports/STRAT_Rate_bilan_2026-10-14.md). Tous ces SEEL sont ceux du modèle de Rate de STRAT, sans dérive de la source.
- Correctif RMSE validé ; intégration Rate R5 validée et **inactive par défaut** (`elite_rate_joint_candidates=0`, `rate_post_refinement=False`).
- `r75x0.5` : gains propres confirmés sur trois graines (1,25 / 1,29 / 1,76 % contre le contrôle complet) ; **aucun gain au 48c**.
- Chaîne de plans sur `r75x0.5 deep`, graine 101 : 0,3967 → 0,3345 nm (−15,7 %, plan 9900008, 13 à 16 % sur neuf groupes frais) ; non confirmés : l'apport
  propre des voisins conjoints, le préfixe fin à 598 nm, les couples de fenêtres ; R3 sans gain. Généralisation à d'autres composants non établie.
- A2 (12 paires avec et sans `elite_rate_moves`, [bilan](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md)) : de −0,6 % (48c, une graine)
  à +11,8 % (`r75x0.5`) ; aucune supériorité établie ni confirmation indépendante homogène.
- `elite_rate_moves` actif depuis `978b8f04` : `r75x0.5` 0,5031 / 0,4981 / 0,5000 → 0,4347 / 0,3967 / 0,3967 nm
  ([rapport](../reports/STRAT_ELITE_couches_Rate_paquets_2026-10-12.md)).

**Corrections qui invalident des mesures plus anciennes.**
- D100 (`2cba90f4`, 2026-10-11) : du 2026-09-08 au 2026-10-11, tout résultat STRAT a tourné sans Rate, sans biais de fente et sans recherche de fente, sauf surcharge explicite
  ([rapport](../reports/STRAT_D100_interrupteurs_non_charges_2026-10-11.md)).
- D103 (`de9a2025`) : en `deep` et `extreme`, des identifiants de groupements en double mélangeaient les scores du consensus ; les résultats `deep` d'avant (campagnes d'août, repères
  du §2 hors `r75x2` sans rampes) ont pu choisir leurs parents ELITE sur des scores mélangés ([rapport](../reports/STRAT_D103_identifiants_en_double_2026-10-11.md)).
- D106 (`6fcdd56a`) : les enfants d'ELITE étaient notés sans biais de fente. À `r75x2` sans rampes (graine 101, ancien modèle d'arrêt, sans secours Rate) : 706 déposables sur 6 042
  stratégies sans la correction, 0 sur 4 821 avec ; sans rampes, `r75x2` n'est pas fabricable en optique pure. Au juge de paix, le meilleur SEEL passe de 0,1776 à 0,1927 nm (+8,5 %) :
  les repères d'avant la correction sont optimistes d'autant.
- C-L4 (`5be9f704`, 2026-11-15) : depuis `c2b10301` (2026-05-27), STRAT calculait le substrat « SiO2 » avec le mélange des feuilles de couches SiO2, n = 1,48625 à 550 nm au lieu de
  1,45991 (silice fondue) ; tout résultat STRAT sur « SiO2 » d'avant est touché ([recensement](../reports/audit_code_2026-11-15/recensement_sio2.md)). Au juge de paix, entre deux
  bancs que seule C-L4 sépare pour STRAT : SEEL 0,1531 → 0,1713 nm (+11,9 %) ; le gagnant passe de 2 blocs [544, 471] à 4 blocs [544, 469, 454, 471] ; la recherche locale finale, qui
  portait le score de 0,007402 à 0,005862, le laisse à 0,007340 (parent 0,007335) ([banc](../reports/audit_code_2026-11-15/bancs/juge_de_paix_apres_C-L4.txt)).
- M-L2 (`23459079`, 2026-11-15) : le consensus ne gardait que les scores finis de ses graines ; une stratégie rejetée par une graine gardait la moyenne des autres. Tout classement
  STRAT par consensus d'avant a pu retenir une telle stratégie. Au juge de paix (C-L4 déjà corrigé) : SEEL 0,1713 → 0,1577 nm (−8,0 %) ; 6 des 29 meilleurs d'étape passent à un
  score infini ; le meilleur ELITE à 4 blocs passe de 0,00733 à 0,00828 et le gagnant redevient un 2 blocs, [544, 497] à 0,007776, que la recherche locale porte à 0,006217
  ([banc](../reports/audit_code_2026-11-15/bancs/juge_de_paix_apres_M-L2.txt)). Journal des graines au code C-L4 seul ([relevé](../reports/audit_code_2026-11-15/bancs/juge_de_paix_C-L4_graines.txt)) : l'ancien gagnant à 4 blocs avait ses trois graines finies, et aucune des 365 stratégies notées n'a de graines mêlées ; M-L2 agit ici par les 150 stratégies rejetées sur leurs trois graines, qui gardaient avant leur score de base.
- ε1 de Tauc-Lorentz pour C ≥ 2·E0 (`758b13e7`, 2026-11-17) : la forme fermée et son gradient bridaient 4·E0² − C² à 1e-12 ; tout ajustement INDEX arrivé à C ≥ 2·E0
  (bornes : C jusqu'à 10 eV, E0 dès ~1,6 eV) avait un ε1 faux, 0,41 de Kramers-Kronig à C = 7, E0 = 3,074. Les ajustements à C < 2·E0 ne bougent pas (au bit).
- Mineurs STRAT de l'audit (2026-11-16, `83f0b7c6`, `cda58825`) : la porte ELITE lit le niveau de bruit du run (L2-m1) et la phase B reçoit k en float64 (L4-m4). Juge de paix : SEEL 0,1577 → 0,1704 nm ; gagnant à 4 blocs [544, 485, 453, 473] ; les deux corrections, mesurées ensemble, ne sont pas séparées ([banc](../reports/audit_code_2026-11-15/bancs/juge_de_paix_apres_mineurs.txt)).
