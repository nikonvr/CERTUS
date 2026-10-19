# CERTUS — acquis du Rate, corrections qui invalident des mesures, reprises antérieures

> Extrait de la section 0 de [`ETAT.md`](ETAT.md) le 2026-10-18, pour que la reprise tienne en peu de lignes. Ce contenu **fait autorité** ;
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

**Reprise du 2026-10-17.** 👤 valide les trois statuts du registre des leviers Rate (`rate_layer_sets` RESERVE, `rate_tail_keep_optical`
NON_MESURE, `rate_rescue_hard` RESERVE ; `0c7c1e2e`, liste d'attente vide), puis demande d'essayer le 99c avec les dernières évolutions du Rate sur
un seul verre témoin. Quatre mesures exploratoires (`premium`, consensus 41/42/43, graines de recherche 42 et 101, hors protocole de campagne) :
chiffres au §2, bilan dans [`bilan.md`](../reports/STRAT_99c_rate_elargi_2026-10-16/bilan.md). Le gain du profil élargi vient surtout de l'élargissement
de la recherche, pas du raffinement final (−0,89 % à la graine 42, aucun à la 101) ; il n'est confirmé sur aucun groupe frais et suppose un Rate sans
dérive de vitesse (A6). Isolation des leviers (budget 240 seul, puis budget 240 et six tours), graines 42 et 101 : protocoles et bilan dans
`reports/STRAT_99c_isolation_leviers_2026-10-17/` et `reports/STRAT_99c_isolation_leviers_graine101_2026-10-17/`. À la graine 42, sur le score de
consensus, le budget 240 seul porte 62 % de l'écart entre les défauts et le profil élargi avant raffinement, les six tours 7 % (sous le bruit de 4,2 %),
les 480 voisins conjoints 31 % : une graine, un chemin de décomposition, C2 en partie sous charge étrangère. La chaîne de la graine 101 s'est terminée
ou a été interrompue le 2026-10-17 à 05:38 UTC (`MESURES_TERMINEES.txt`) ; son dossier n'a pas de `bilan.md` : lire `chain.log` avant d'en tirer un chiffre.
Contre-audit de `designargon.md` et `UXargon.md` ([rapport](../reports/ARGON_contre_audit_Claude_2026-10-17.md)) : cinq défauts d'intégrité confirmés par
un test rouge puis corrigés, un commit chacun (`868db8c9`, `8c6d951b`, `bdcae9ed`, `c25937b3`, `7f3edea8`) ; ALG-02, non corrigé, est D107 (§4).
Branche publiée à `7f3edea8` le 2026-10-17 sur l'accord de 👤.

**Reprise du 2026-10-16.** Après le bilan clos, 👤 demande une passation, « push et commit all », puis un ménage drastique sous 1 Go : archives
locales et dépôt Git léger, 2 242 JSON volumineux conservés en archives avec empreintes SHA hors CERTUS, caches retirés. Publication faite après
confirmation explicite de 👤 vers `https://github.com/nikonvr/CERTUS.git`, branche `claude/ecstatic-newton-3grmls` (`be3af69e` vérifié sur le distant),
sans réécriture d'historique. [Ménage, emplacement des archives et restauration ciblée](../reports/STRAT_Rate_publication_2026-10-16/README.md) ;
[diagnostic précis, commandes et limites](../reports/STRAT_Rate_reprise_20261016.md) ; [autorisation, périmètre et plafonds](../reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json).
Le programme borné R0–R6 est clos et son ancien suivi est PAUSED. **TODO de 👤 :** tenter le 99c en une seule campagne avec injection de Rate et les
derniers raffinements (A9, dans `ETAT_actions.md`).

**Revue de HEAD du 2026-10-16.** Le groupe « reste » de CLAUDE.md §2 exige `pytest-benchmark` (11 benchmarks de noyaux) ; le projet ne le déclare
nulle part (D110). Dette : les trois interrupteurs Rate lus par la recherche sont au registre des leviers (liste d'attente de
`tests/unit/test_strat_leviers.py` vide) ; les textes `mesure` de `elite_rate_joint_candidates` et `rate_post_refinement` datent d'avant R5/R6 et
attendent la décision de 👤.

**Contre-audits ARGON** (`UXargon.md`, `designargon.md`, preuves dans `reports/ARGON_contre_audit_2026-10-16/`). Le premier contre-audit a corrigé et
qualifié les deux audits par niveau de preuve : 22 démarrages GUI hors écran, 0 cas fautif selon le harnais ; 20 observations ciblées vérifiées,
0 erreur de sonde ; corps extraits et décorateurs Numba retirés, donc aucune validation complète/JIT ni performance démontrée ([preuves, limites et
empreintes](../reports/ARGON_contre_audit_2026-10-16/evidence.json), [reproduction](../reports/ARGON_contre_audit_2026-10-16/probe.py.txt)). Le second,
interrompu le 2026-10-17 quand 👤 a ouvert le sujet « bonne mere », a conservé [cinq observations supplémentaires](../reports/ARGON_contre_audit_2026-10-16/pass02.json)
(grille oblique non densifiée, bornes et arrêt ignorés au raffinement final), pas encore reportées dans les audits. Défauts prioritaires des audits :
snapshot DESIGN et filtre final 5 nm supprimant des couches fixes (corrigé, `bdcae9ed`), précision lambda SMOOTHER, coûts Needle et évaluateur d'élagage
(celui-ci : D107) ; progression RE incompatible, puis grille oblique à valider en worker. Descriptions fautives retirées : métrique de tri prise pour des états
vides, accès JSON SPLINE absent, aide/F1 absents, solveur maison, `jac` absent et paramètres/formule PGLOBAL inexacts. Trois contrôles documentaires à 0 ;
[contrôles complémentaires](../reports/ARGON_contre_audit_2026-10-16/documentation_checks.json).
