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

**Acquis du Rate (programme R0–R6, clos le 2026-10-16 par arrêt précoce R6).** Bilan final et limites :
[`bilan_final.md`](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md), audit [`audit_final.json`](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/audit_final.json) ;
synthèse du 2026-10-14 : [`STRAT_Rate_bilan_2026-10-14.md`](../reports/STRAT_Rate_bilan_2026-10-14.md) ; guide : [`STRAT_Rate_suite_chantier.md`](../reports/STRAT_Rate_suite_chantier.md).
- Correctif RMSE validé (les poids constants positifs vont à la spécialisation non pondérée ; 490 tableaux non concernés identiques au bit) ; intégration Rate
  (R5) validée et **inactive par défaut** (`elite_rate_joint_candidates=0`, `rate_post_refinement=False`).
- `r75x0.5` : gains propres confirmés sur les trois graines (moyennes 1,2541 % / 1,2888 % / 1,7562 % contre le contrôle complet, 3/3 victoires chacune) ;
  **aucun gain au 48c** (même plan complet, 0 %) ; quatre paires R6 consommées sur six, `x1.5` et `x2` non lancés selon la règle fixée avant la mesure.
- Chaîne de plans sur `r75x0.5 deep`, graine 101 (SEEL de recherche) : référence 0,3967 nm → natif conjoint (budget Rate 240, six tours, 480 voisins conjoints)
  0,3600608863 nm (−9,24 %) → préfixe L1–L5 à 600 nm 0,3539592452 nm (−10,78 %) → fenêtre L35–L37 à 688 nm 0,3409240518 nm (−14,06 %, plan 9900006) → préfixe 613 nm
  0,3345159946 nm (−15,68 %, plan 9900008, gagnant local : 13,23 à 15,87 % contre la référence sur neuf groupes frais, 8 victoires sur 9 contre son parent).
  **Non confirmés sur groupes frais** : l'apport propre des voisins conjoints (4 groupes sur 10 favorables contre l'ablation), le préfixe fin à 598 nm, les couples de
  fenêtres, les 720 voisins de préfixe ajoutés à la recherche native. R3 (largeurs seules, puis λ) : aucun gain. Le raffinement local alterné retrouve de lui-même
  0,3431123800 nm (R4 : 3/3 contre le natif, moyenne 4,4772 %, 1/3 contre le meilleur local 9900008 ; R3_h03 : moyenne 5,2130 %, 0/3). La découverte native automatique
  est étayée pour `r75x0.5` ; sa généralisation à d'autres composants reste non établie.
- A2 (24 exécutions, 12 paires avec/sans `elite_rate_moves`, terminée le 2026-10-14 : [bilan](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md)). Gains bruts avec/sans :
  `r75x0.5` s77 11,7507 % ; `r75x2` s202 4,6980 %, s77 4,7770 % ; `r75x1.5` s42 3,25 %, s101 0,12 % ; `r75x1.75` s42 sous le repère de dispersion, s101 5,0439 % ; `35c` 1,0997 % ;
  `75c` 0,0471 % ; 48c premium s77 −0,5893 % (régression), s101 0,1364 %, s202 0,3372 %. Aucune supériorité établie ni confirmation homogène indépendante.
- Avant R0, le 2026-10-12 : `elite_rate_moves` actif par défaut depuis `978b8f04` ([rapport](../reports/STRAT_ELITE_couches_Rate_paquets_2026-10-12.md)) : `r75x0.5` (graines 42 / 101 / 202)
  0,5031 / 0,4981 / 0,5000 → 0,4347 / 0,3967 / 0,3967 nm (le meilleur plan des graines 101 et 202 : trois paquets de Rate et deux fenêtres d'optique de deux couches, la première
  à 451 nm) ; `r75x0.5` avec un seul verre témoin, que la recherche ne savait pas fabriquer (0 déposable sur 8 687 plans), rend 3 383, 3 701 et 3 279 plans déposables aux graines
  42, 101 et 202. D96 à D98 sont le modèle d'arrêt par défaut (`8d9ced13`, §3) : l'attente sans fin retire 95 % des plans que l'ancien modèle jugeait fabricables ; le secours Rate
  (`0fc7c5f2`, `40642146`) pose au temps la queue des plans dont le contrôle optique cède ; les enfants d'ELITE gardent les couches Rate de leur parent (`4a4e1f0d`)
  ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)). ELITE « tour à tour », six graines : médiane +0,7 %, pas de gain net démontré (§5,
  [rapport](../reports/STRAT_ELITE_tour_a_tour_six_graines_2026-10-12.md)). Tous ces SEEL sont ceux du modèle de Rate de STRAT, sans dérive de la source (§7).

**Corrections qui invalident des mesures plus anciennes.**
- D100 (`2cba90f4`, 2026-10-11) : du 2026-09-08 au 2026-10-11, tout résultat STRAT a tourné sans Rate, sans biais de fente et sans recherche de fente, sauf surcharge explicite
  ([rapport](../reports/STRAT_D100_interrupteurs_non_charges_2026-10-11.md)).
- D103 (`de9a2025`) : en `deep` et `extreme`, des identifiants de groupements en double mélangeaient les scores du consensus ; les résultats `deep` d'avant (campagnes d'août, repères
  du §2 hors `r75x2` sans rampes) ont pu choisir leurs parents ELITE sur des scores mélangés ([rapport](../reports/STRAT_D103_identifiants_en_double_2026-10-11.md)).
- D106 (`6fcdd56a`) : les enfants d'ELITE étaient notés sans biais de fente. À `r75x2` sans rampes (graine 101, ancien modèle d'arrêt, sans secours Rate) : 706 déposables sur 6 042
  stratégies sans la correction, 0 sur 4 821 avec ; sans rampes, `r75x2` n'est pas fabricable en optique pure. Au juge de paix, le meilleur SEEL passe de 0,1776 à 0,1927 nm (+8,5 %) :
  les repères d'avant la correction sont optimistes d'autant.

**En vigueur au 2026-10-13** (ne pas le remettre en cause sans mesure) : D96, D97 et D98 (attente sans fin) ; `rate_rescue` ;
`rate_by_swing` ; ELITE déplace les couches Rate de ses parents (`elite_rate_moves`) ; ses enfants portent le biais de fente
(D106) et gardent les couches Rate du parent. Preuves : `reports/STRAT_*_2026-10-12*`.
