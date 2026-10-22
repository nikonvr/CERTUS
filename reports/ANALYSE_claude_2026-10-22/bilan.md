# Réanalyse indépendante de Gemini A14/A10 et de GPT A4 (Claude, 2026-10-22)

Branche `chatgpt/2026-10-22`, code `4a090135` (A4 : `b399b842`). Sources : artefacts versionnés de
[A14](../STRAT_etage_A14_2026-10-21/bilan.md), [A10](../STRAT_etage_A10_2026-10-21/bilan.md),
[A4](../STRAT_A4_parents_optiques_2026-10-22/bilan.md) et de la [relecture GPT](../RELECTURE_gemini_2026-10-22/bilan.md) ;
demande : [relais GPT](../RELAIS_chatgpt_2026-10-22.md).
Aucun banc STRAT relancé : six mesures ciblées sur plans figés (≈ 6 min de calcul), scripts dans `outils/`, chiffres et
tableaux par tirage dans `resultats/`. SEEL = 2·√(P95, pire des trois niveaux de bruit 0,5×/1×/2×) ; arrêts sur 9 000 tirages
(3 graines × 1 000 × 3 niveaux) ; IC95 par rééchantillonnage apparié des tirages.

## En bref

1. L'étage `strat_local_search` livré **ne tient pas** le critère écrit d'avance (« jamais de SEEL dégradé ni d'arrêt
   ajouté ») : `r75x2` graine 101, SEEL +10,7 % à ±0,005 et 0 → 2 arrêts à ±0,010. Les neuf autres cas le tiennent.
2. **Cause établie par contre-épreuve : le défaut ouvert de STRAT**, l'hystérésis de détection des points tournants qui
   suit le bruit. Au niveau 0,5× le seuil tombe à 0,000415 T, sous l'ondulation du biais de fente de L63 surveillée à
   680 nm : faux point tournant, couche arrêtée 3,7 nm trop tôt. Au seuil du niveau nominal (0,00083 T), sept des huit
   plans jugés battent nettement leur ELITE aux deux corridors et le huitième est à égalité à ±0,005
   (`r75x2_s101` : −12,1 %).
3. Le même défaut gonfle le gain du 75c à ±0,010 : −73 % annoncés, −15 % et −25 % sans lui (ELITE non déposables par
   faux arrêts à 0,5×).
4. A4 n'a aucun effet utile : aucun plan optique pur dans les six populations ; tous les parents du quota plantent
   (≥ 42 %) ; il coûte 6 à 23 % des candidats retenus par ELITE ; M=4 dégrade le gagnant `r75x0.5` (+2,7 %, confirmé sur
   plans figés, une graine). Sa prémisse (50 plans optiques purs déposables) valait pour l'ancien modèle d'arrêt.
5. Code A4 : chemin à zéro conservé, C1 tenu, validation 8 441 réussis / 0 échec vérifiée sur pièces. Deux commentaires
   🔴/📏 ont été supprimés pour tenir le plafond de 1 500 lignes : à restaurer.

## 1. Gemini A14/A10 — dix cas recalculés

Provenance : arbres propres, étage actif, recherche à ±0,010, `index_corridor` des composants ±0,005. Critères commités en
`0fa855b9`, avant le code de la campagne (`62020451`). Mes chiffres = `cas.json` (≤ 2,3·10⁻¹⁴ nm, arrêts identiques). Rejeu
GPT = originaux de Gemini au bit sur sept cas ; 48c à ≤ 1,2·10⁻¹⁴ près sur les RMSE, arrêts identiques (§5).

| cas | étage (changements gardés) | ±0,005 : ELITE → final (nm) | Δ SEEL [IC95] | arrêts | ±0,010 : ELITE → final (nm) | Δ SEEL [IC95] | arrêts |
|---|---|---|---|---|---|---|---|
| 48c premium s42 | repli (35/38) | 0,1699 → 0,1569 | −7,7 % [−9,2 ; −6,0] | 0 → 0 | 0,2314 → 0,1722 | −25,6 % [−26,6 ; −24,7] | 0 → 0 |
| 35c s42 | refusé (repli 8/21) | — | — | — | — | — | — |
| r75x1.5 s77 | repli (12/41) | 0,4820 → 0,4507 | −6,5 % [−7,5 ; −5,6] | 0 → 0 | 0,6118 → 0,5019 | −18,0 % [−18,8 ; −17,0] | 0 → 0 |
| r75x1.75 s77 | repli (20/36) | 0,4805 → 0,4099 | −14,7 % [−15,6 ; −13,7] | 4 → 0 | 0,6243 → 0,5522 | −11,5 % [−12,6 ; −10,8] | 5 → 0 |
| r75x2-2nm s77 | accepté (49) | 0,5468 → 0,4726 | −13,6 % [−14,7 ; −12,4] | 0 → 0 | 0,6684 → 0,5624 | −15,9 % [−16,3 ; −15,4] | 3 → 2 |
| 75c s101 | accepté (52) | 0,2429 → 0,2400 | −1,2 % [−3,0 ; +0,2] | 10 → 0 | 1,0080* → 0,2749 | (−72,7 %) | 297 → 2 |
| 75c s202 | accepté (47) | 0,2467 → 0,2081 | −15,7 % [−16,5 ; −14,7] | 0 → 0 | 0,9125* → 0,2480 | (−72,8 %) | 233 → 7 |
| r75x0.5 s202 | repli (8/28) | 0,4007 → 0,3564 | −11,1 % [−12,4 ; −9,6] | 0 → 0 | 0,4450 → 0,3962 | −11,0 % [−12,1 ; −10,2] | 0 → 0 |
| **r75x2 s101** | accepté (34) | 0,5383 → 0,5959 | **+10,7 % [+8,3 ; +12,2]** | 0 → 0 | 0,6854 → 0,6738 | −1,7 % [−3,0 ; −0,7] | **0 → 2** |
| r75x2 s202 | refusé (repli 42/51) | — | — | — | — | — | — |

\* ELITE non déposable à ±0,010 : 9,9 % et 5,6 % d'arrêts au niveau 0,5×. Son « SEEL » tombe dans les tirages arrêtés.

- **Critères.** SEEL dégradé : un cas (`r75x2_s101`, trois graines sur trois). Arrêt ajouté : un cas (même cas, ±0,010 ;
  ailleurs le total ne monte jamais). Gain sur la majorité : significatif à ±0,005 sur 6 cas sur 10 et 6 designs sur 8.
  Tenue à ±0,010 : gain sur les 8 cas jugés. **Verdict : critère non tenu**, sur le composant étalon.
- **Statuts.** L'étage contrôle le plan final à ±0,010 seulement : pas plus d'arrêts, gain apparié au-delà de 2 SE, P95
  non supérieur (`_judge`). *Accepté* : le final passe. *Repli* : le final ajoute 1 à 11 arrêts, un plan intermédiaire
  passe contrôle et confirmation. *Refusé* : l'intermédiaire ajoute encore des arrêts à la confirmation (0 → 3, 0 → 1) ;
  le gagnant ELITE revient inchangé, effet neutre. Les statuts appliquent correctement cette règle.
- **75c.** À ±0,005 : −15,7 % (s202), −1,2 % non significatif (s101). L'étage y ajoute du Rate (4 → 12, 5 → 9 couches),
  à l'inverse des autres designs (−2 à −20 couches).
- **r75x2 sur trois graines** : gain (s77, banc du 21 sur arbre modifié), dégradation (s101), refus (s202). Le bénéfice
  sur l'étalon n'est pas établi.
- Le ΔRMSE² des bilans (moyenne à 1×, tirages arrêtés exclus) et le SEEL (P95 au pire niveau, arrêts inclus) ne mesurent
  pas la même chose : `r75x2_s101` affiche −33,7 % et +10,7 %. Ce n'est pas une erreur de calcul, mais la juxtaposition
  des deux colonnes trompe.

## 2. Le niveau 0,5× : cause de la contradiction `r75x2_s101`

Chemin des 34 changements reconstruit depuis l'artefact, identique à la ligne LOCAL_SEARCH ; témoin rejoué au bit sur les
tableaux versionnés. SEEL par niveau (0,5× / 1× / 2×), deux graines neuves × 1 000 tirages :

| plan | ±0,005 | ±0,010 |
|---|---|---|
| départ (ELITE) | 0,5212 / 0,5219 / 0,5331 | 0,6798 / 0,6738 / 0,6840 |
| après 30 changements | 0,4712 / 0,4719 / 0,4749 | 0,6023 / 0,6084 / 0,6063 |
| après 31 (`L63 optical@680`, Rate → optique) | **0,5562** / 0,4720 / 0,4752 | 0,6555 / 0,6072 / 0,6063 |
| final (34) | **0,5906** / 0,4712 / 0,4742 | 0,6717 / 0,6040 / 0,6036 |

Au final, L63 (146,6 nm) a un biais de −3,66 nm (σ 2,12 ; 79 % des tirages au-delà de 2 nm) à 0,5×, contre −0,12 nm à
1× et −0,26 nm à 2×. Les couches Rate du même matériau (L65, L67, L69, L71) prennent −0,224 % : leur vitesse est
étalonnée sur les couches optiques. Une erreur qui **diminue quand le bruit augmente** n'est pas du bruit.

Contre-épreuves sur le plan final, ±0,005, niveau 0,5× :

| réglage | SEEL 0,5× | biais de L63 |
|---|---|---|
| défaut (`tp_hysteresis_floor` 0,000415) | 0,5906 nm | −3,656 nm |
| plancher 0,00083 T (seuil du niveau 1× : 1,66 × 0,05 %) | 0,4707 nm | −0,045 nm |
| biais de fente coupé (`slit_bias_enabled=False`) | 0,4729 nm | −0,031 nm |

Avec le plancher, les niveaux 1× et 2× et le plan de départ restent identiques au bit. Pourquoi l'étage ne l'a pas vu :
chaque changement est retenu sur la moyenne RMSE² **à 1×** et le total des arrêts ; le contrôle se fait **à ±0,010**, où
l'erreur d'indice masque le niveau 0,5× (0,6717 sous le 0,6840 du départ). Rien ne regarde ±0,005, et `refined_first`
classe le plan premier alors que le banc lui-même lui donnait 0,5940 nm contre 0,5358 (339 autres lignes meilleures).

Les huit jugements refaits au plancher 0,00083 (mêmes plans, mêmes tirages) :

| cas | ±0,005 : défaut → plancher | ±0,010 : défaut → plancher |
|---|---|---|
| r75x2 s101 | +10,7 % → **−12,1 %** [−13,5 ; −11,0] | −1,7 % → −11,5 % [−12,0 ; −11,0] ; arrêts du final 2 → 1 (niveau 2×) |
| 75c s101 | −1,2 % → −1,2 % (ELITE : 10 → 0 arrêt) | −72,7 % → **−14,8 %** [−16,2 ; −13,8] (ELITE : 297 → 0 arrêt) |
| 75c s202 | −15,7 % → −15,7 % | −72,8 % → **−24,8 %** [−26,7 ; −23,7] (ELITE : 233 → 109 arrêts) |
| cinq autres | inchangés | inchangés (r75x2-2nm : un arrêt ELITE de plus à 0,5×) |

Au plancher, le seul écart restant au critère est un arrêt sur 9 000 (`r75x2_s101`, ±0,010, niveau 2×).

Les deux refus, rejoués sur les graines de contrôle et de confirmation de l'étage, redonnent exactement ses arrêts (0 → 4,
0 → 3 ; 0 → 7, 0 → 1) et ne changent pas au plancher : arrêts surtout à 2×, **refus authentiques**. 35c renonce ainsi à
−42 % de RMSE² pour 3 arrêts sur 6 000 (2 graines × 1 000 × 3 niveaux).

## 3. Défauts de l'étage relevés dans le code

1. `_judge` (`certus_strat_local_search.py`) ne juge qu'au corridor de recherche (`search_params`) ; aucune garde au
   corridor configuré, celui qu'on rapporte.
2. `refined_first` (`certus_strat_workers_local_search.py`) met le plan affiné en tête quel que soit son score au corridor
   configuré.
3. La ligne LOCAL_SEARCH garde le `strategy_id` de son parent (8 cas acceptés sur 8) et échappe à
   `validate_unique_strategy_ids`, qui retient table et export en cas de doublon : le classeur la place hors de
   `rank_final_results`.
4. Le docstring du module worker dit « off by default » ; l'étage est actif par défaut.

## 4. GPT A4 — six bancs, chacun contre son M0

Configuration lue dans `config` (M = 0/2/4, étage actif), commit `b399b842`, arbres propres ; traces du quota présentes.

| banc | M | tours servis à 4/2/1 parents | SEEL du premier (nm) | meilleur ELITE (nm) | plans retournés | optiques purs | retenus par ELITE | parents du quota : plantage min. ; à 100 % |
|---|---|---|---|---|---|---|---|---|
| 48c s42 | 0 | — | 0,153126 | 0,172075 | 2 653 | 0 | 532 | — |
| 48c s42 | 2 | –/36/2 | 0,153126 (même plan) | 0,172075 | 2 602 | 0 | 481 | 68 % ; 55 sur 74 |
| 48c s42 | 4 | 27/9/2 | 0,153126 (même plan) | 0,172075 | 2 602 | 0 | 481 | 48 % ; 103 sur 128 |
| r75x0.5 s101 | 0 | — | 0,360142 | 0,396715 | 4 144 | 0 | 1 403 | — |
| r75x0.5 s101 | 2 | –/64/14 | 0,360142 (même plan physique) | 0,396715 | 4 058 | 0 | 1 317 | 42 % ; 114 sur 142 |
| r75x0.5 s101 | 4 | 56/8/14 | 0,371505 (+3,2 %) | 0,457808 (+15,4 %) | 3 822 | 0 | 1 081 | 42 % ; 222 sur 254 |

- Le quota agit, mais aucun parent qu'il place n'est viable. Les places prises aux parents productifs se paient : le
  budget de candidats est plein dans tous les cas, mais les retenus baissent, et les écarts de population (−51, −86,
  −322) égalent exactement ceux des retenus.
- La colonne SEEL est un **minimum de recherche** (meilleur de milliers de plans sur les tirages du banc), sur une
  graine. Jugement indépendant des deux gagnants figés de `r75x0.5` (graines neuves 902210301-303, 3 × 1 000) :
  M0 0,3617 → M4 0,3714 nm à ±0,005 (+2,7 % [+1,4 ; +4,2], arrêts 0 → 5) ; 0,3752 → 0,3971 nm à ±0,010
  (+5,8 % [+4,3 ; +7,2], 0 → 19). Le plan M4 est donc moins bon, mais une seule graine de banc ne dit pas que M4 dégrade
  en général. Ces chiffres ne se comparent pas aux jugements Gemini (final contre ELITE d'un même banc).
- Prémisse : les « 50 déposables » de `ETAT.md` §5 valaient pour l'ancien modèle d'arrêt. Au modèle par défaut
  (D96-D98), la mesure 4 du 2026-10-12 en trouvait déjà 0 ; l'arrêt tardif (`oms_arming=1`) en gardait 101.

## 5. Code A4 et ses preuves

- Diff conforme à la déclaration. À zéro, `_evaluate_with_optical_parent_pool` refait l'appel historique et
  `_select_elite_optical_parents` rend `strategies_results[:parent_count]`.
- Tests : les trois tests du correctif v2 échouent sur v1 (`3 failed, 8 passed`), 100 passent après. Le test absent/zéro
  compare octet par octet la sortie du vrai générateur de candidats.
- Validation en série (`validation_serie_v2/resultats.json`) : 1 148 + 5 610 + 1 324 + 359 = 8 441 réussis, 19 ignorés,
  3 `xfailed`, 0 échec, codes de retour nuls. Les SHA-256 des six fichiers validés sont ceux de `b399b842` (aux fins de
  ligne près) ; aucun code ne change ensuite. Non rejouée : rien ne le justifiait.
- C1 : 9 092 tableaux identiques au bit (`c1_v2.log`). De bout en bout, le banc 48c A14 (`62020451`) et A4-M0 donnent les
  mêmes 2 653 plans, `id`, ordre et étage, avec trois scores à ≤ 2·10⁻¹⁶ près. Deux exécutions d'un jugement 48c à
  `4a090135` sont identiques entre elles et aux tableaux de Gemini ; le rejeu GPT s'en écarte de ≤ 1,2·10⁻¹⁴. Ces écarts
  d'un ulp viennent donc des exécutions GPT (cause non identifiée), pas d'A4.
- Pour tenir `certus_strat_consensus.py` à 1 500 lignes, GPT a supprimé le 🔴 « AFTER the ranking, never before » de
  l'ablation (`run_final_simulation_block`) et le paragraphe 📏 mesuré sur l'épuisement du budget par parent
  (`_apply_elite_refinement_if_enabled`) ; ce paragraphe décrivait le mécanisme même du coût d'A4. Le registre marque
  encore le levier `NON_MESURE`.

## 6. Interprétation physique

- Le niveau 0,5× porte un défaut de modèle déjà ouvert : le seuil du détecteur suit le bruit du scénario (1,66 × bruit),
  alors que `detect_turning_points` pose qu'un seuil d'au moins 2 × `trigger_tolerance` (0,001 T) empêche le bruit seul de
  fabriquer un point tournant. Un contrôleur réglé pour le bruit nominal ne baisse pas son seuil quand la machine est plus
  calme. Je tiens donc la dégradation de `r75x2_s101` et la plus grande part des −73 % du 75c pour des artefacts du modèle,
  pas pour de la physique du dépôt. C'est à 👤 de trancher.
- L'étage optimise à 1× et contrôle à ±0,010 : son effet à 0,5× est un hasard, favorable sur 75c (passer en Rate des
  couches fragiles supprime de faux arrêts), défavorable sur `r75x2_s101` (passer L63 en optique crée un faux point
  tournant). Hors de ce défaut, il gagne sur sept paires sur huit à ±0,005 (la huitième à égalité) et sur les huit à
  ±0,010.
- Le Rate de STRAT n'a ni dérive de la source ni bruit de vitesse (§7 d'`ETAT.md`). Les gains obtenus en ajoutant du Rate
  (75c) sont donc optimistes ; ceux obtenus en le retirant (48c, famille r75) ne le sont pas.
- A4 : au modèle d'arrêt par défaut, l'optique pure n'est pas déposable sur ces composants. Réserver des parents optiques
  nourrit ELITE de lignées non viables et prend la place de parents productifs.

## 7. Limites

Une graine de banc par design, sauf 75c, `r75x0.5` et `r75x2` (trois graines, dont la 77 tirée des bancs du 21, lancés sur
des arbres modifiés). Les IC couvrent les tirages, pas le hasard de la recherche. Les contre-épreuves au plancher jugent
des plans cherchés sous l'ancien seuil : elles ne disent pas ce que l'étage trouverait sous le nouveau. Le mécanisme
(faux point tournant) est déduit de deux contre-épreuves, pas tracé tirage par tirage. A4 : deux designs, une graine
chacun, modèle d'arrêt par défaut seulement. STRAT n'est validé que contre lui-même.

## 8. Recommandation

**Conserver** : l'étage actif, car ses gains sont réels hors défaut ; sa validation au critère écrit n'est en revanche pas
acquise. A4 inactif (0), C1 tenu : ne pas l'armer. Les relectures et le correctif documentaire `d0d0acf1`.

**Corriger**, sur accord de 👤, un commit chacun (C3) :
1. décider le seuil des points tournants à bas bruit, c'est-à-dire le défaut ouvert. Option mesurée ici : plancher au
   seuil nominal, 0,00083 T. C'est un changement de modèle pour toute évaluation au niveau 0,5×, donc un défaut à changer ;
2. ajouter une garde de l'étage au corridor configuré dans `_judge`, et ne plus forcer le premier rang d'un plan moins bon
   à ce corridor. Paramètre inactif, puis armé après mesure ;
3. donner un `strategy_id` neuf à la ligne affinée (`next_refinement_strategy_id`) et contrôler l'unicité sur la liste
   entière ;
4. restaurer les deux commentaires supprimés (le 📏 à côté de `_select_elite_optical_parents`, hors du module plafonné),
   corriger le docstring et passer le registre d'A4 de `NON_MESURE` à « mesuré sans effet ».

**Confirmer** : après 1 ou 2, rejouer A14/A10 sur arbre propre avec les mêmes critères ; au moins trois graines pour
`r75x2`. A4 ne se rejoue qu'avec `oms_arming=1` (arrêt tardif), et seulement si 👤 poursuit « le Rate et l'optique
pure » ; sinon, le retirer. La branche peut être fusionnée après le point 4, sur décision de 👤 : aucun défaut n'y change.

**Suite proposée** :
1. 👤 décide des points 1 et 2 ;
2. ChatGPT code les points 2 à 4 : tests qui échouent sur le code d'avant, `c1_diff`, validation complète ;
3. Gemini confirme, avec un lanceur prêt (arbre jetable) ;
4. en parallèle de l'étape 3, sur sa propre branche, ChatGPT mène **A8b** : un commit par arête, sans toucher
   `certus_strat_local_search.py`, `certus_strat_workers_local_search.py` ni `certus_strat_ranking.py` avant la fusion
   de l'étape 2 ;
5. Claude interprète, puis 👤 fixe les défauts ;
6. **A9** vient seulement ensuite, avec `GO_OWNER.txt` (absent le 2026-10-22). Plus tôt, la campagne de 99 couches
   mesurerait un défaut sur le point de changer.

## Reproduire

Depuis la racine, `W` étant un dossier de travail vide (le scanner change de répertoire : chemins absolus) :

```bat
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/analyse_gemini.py.txt . gemini.json
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/analyse_a4.py.txt . a4.json
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/diag_path.py.txt . W\diag_r75x2_s101
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/analyse_path.py.txt . W\diag_r75x2_s101 path.json
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/diag_mechanism.py.txt . W\diag_mecanisme
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/diag_floor_panel.py.txt . W\diag_plancher_panel
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/diag_refus.py.txt . W\diag_refus
python -X utf8 reports/ANALYSE_claude_2026-10-22/outils/judge_a4.py.txt . W\judge_a4_r75x0.5_s101
```

`diag_path` utilise `r75_scan_nominal.py.txt` (le scanner archivé plus une ligne qui écrit les épaisseurs nominales) ;
les autres utilisent le scanner archivé tel quel. `resultats/brut/rejeu_48c` contient les deux exécutions identiques du
jugement 48c.
