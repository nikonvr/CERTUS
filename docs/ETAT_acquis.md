# CERTUS — acquis du Rate et corrections qui invalident des mesures

> Ce contenu **fait autorité** ;
> `ETAT.md` n'en garde qu'un renvoi. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus sont les sections de `ETAT.md`. Les actions A3 à A9 et le protocole de mesure sont dans [`ETAT_actions.md`](ETAT_actions.md).

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
