# 99c, Rate élargi et raffinement final, un seul témoin (2026-10-16)

Mesure exploratoire à une graine, **pas le protocole A9**. Protocole figé : `protocol.json` ; journal : `run.log`.
`python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 42` avec `elite_rate_max_candidates=240`, `elite_rounds=6`,
`elite_rate_joint_candidates=480`, `rate_post_refinement=true`. HEAD `0c7c1e2e`, code suivi propre (l'artefact dit « arbre modifié » : documents seulement).
Durée 37 min 49 s (17:28:56Z à 18:06:45Z), `exit=0`. Artefact `reports/blocs_vs_plantage_99c_premium_s042_rate_elargi_refinement_240_6_480.json` (26,5 Mo, non suivi).
Un premier run sans raffinement a été arrêté à 4 min 43 s (preuves : `arret_run01.txt`, `run_01_sans_raffinement_arretee.log`).

## Résultat mesuré
- 6 338 stratégies évaluées, **6 302 déposables** (plantage < 5 % au pire des trois niveaux de bruit), plantage minimal 0,00 % à chaque nombre de blocs ; zone 4–7 blocs : 1 410 sur 1 410.
- **Meilleur plan** `999950111` (origine `RATE_POST`) : 13 blocs, **89 couches au Rate** (L10–L12, L14–L99), optique L1–L9 et L13, **SEEL 0,6084 nm**, plantage 0 % aux trois bruits, consensus 41/42/43 complet (moyenne 0,092418, écart-type 0,000337, pire 0,092751 ; score 0,092536).
- Familles : mixte 2 159 plans (meilleur 0,6084 nm), queue 4 143 plans (meilleur 0,6161 nm) ; paquets de Rate par plan déposable : 1 pour 4 151, 2 pour 1 855, 3 pour 296.
- **Raffinement final** : statut `complete`, 2 passes, 283 propositions acceptées, 35 groupes. Passe 1 : score de consensus 0,093363 → 0,092536 (−0,89 %), passe 2 sans gain. Le meilleur plan natif (`901353897`, ELITE, 13 blocs, 86 couches Rate) est à 0,093363 ; les 15 meilleurs plans sont tous `RATE_POST`.
- Repère : le 2026-10-11 le 99c donnait 0 déposable sur 2 139, plantage minimal 82,7 % (mêmes arguments, code antérieur au secours Rate du 2026-10-12).

## Lecture prudente
1. Le gain du raffinement (−0,89 %) est un gain de **recherche** sur les graines 41–43 qui ont servi à chercher ; il est inférieur à la dispersion connue (σ ≈ 1,8 % à `r75x2`) : non confirmé.
2. **Aucun bras aux défauts de production** : le passage de « non fabricable » à « presque tout déposable » ne se sépare pas du secours Rate (actif par défaut depuis le 2026-10-12), des mouvements ELITE, de D96–D98, de l'élargissement et du raffinement. Même constat qu'à `r75x0.5` où des queues seules suffisaient à rendre les listes déposables.
3. Le meilleur plan pose 89 couches sur 99 au Rate : un modèle sans dérive de vitesse (point A6) et sans compensation d'erreur ; son SEEL est celui de ce modèle.
4. Profondeur `premium` (150 tirages, consensus 150) : à ne pas comparer à `deep` (300). Une graine de recherche (42), aucune confirmation indépendante.
5. Le repère historique du 99c, 0,81 nm (assemblage à quatre intervalles, trois graines, ETAT §2/D8), est un autre protocole : non comparable directement.

## Bras aux défauts de production (même graine 42, sans surcharges), terminé à 18:35:25Z, 24 min 41 s
Dossier `reports/STRAT_99c_defauts_production_2026-10-16/` ; artefact `reports/blocs_vs_plantage_99c_premium_s042_20261016_203515.json` (17,4 Mo, non suivi).
| | défauts de production | élargi + raffinement |
|---|---|---|
| stratégies / déposables | 4 761 / 4 761 | 6 338 / 6 302 |
| meilleur SEEL (outil du projet) | 0,7026 nm (queue : Rate L11–L99, optique L1–L10, 7 blocs) | **0,6084 nm** (−13,4 %) |
| meilleur score de consensus | 0,125451 (`991650062`, `RATE_RESCUE6`, 16 blocs, 93 couches Rate, plantage 0 %) | **0,092536** (−26,2 %) |
| durée | 24 min 41 s | 37 min 49 s |
**Attribution dans le run élargi** : le meilleur plan natif avant raffinement est déjà à 0,093363 (−25,6 % contre les défauts) ; le raffinement final n'ajoute que −0,89 %. L'essentiel du gain vient donc de l'élargissement de la recherche ELITE (budget Rate 240, six tours, 480 conjoints), pas du raffinement. Les queues seules progressent aussi (meilleure queue 0,6161 contre 0,7026 nm). Même graine 42 et mêmes graines de consensus 41/42/43 dans les deux bras : gain de recherche, une graine, un run par bras, non confirmé.

## Paire à la graine 101 (même commit, même consensus 41/42/43), terminée à 20:27:06Z
Dossier `reports/STRAT_99c_paire_graine101_2026-10-16/` (`chain.sh`, `chain.log`, deux journaux) ; artefacts `blocs_vs_plantage_99c_premium_s101.json` (16,6 Mo) et `..._s101_rate_elargi_refinement_240_6_480.json` (23,3 Mo), non suivis. Les deux bras sortent `exit=0`.
| | défauts de production | élargi + raffinement |
|---|---|---|
| stratégies / déposables | 4 470 / 4 470 | 5 989 / 5 989 |
| meilleur SEEL | 0,6559 nm (queue : Rate L10–L99, 6 blocs) | **0,6067 nm** (−7,5 %) (mixte : Rate L10–L61 et L64–L99, optique L1–L9 et L62–L63, 15 blocs) |
| meilleur score de consensus | 0,125451 (ELITE, 18 blocs, 93 couches Rate) | **0,096388** (−23,2 %) (ELITE `900355182`, 3 blocs, 83 couches Rate) |
| durée | 24 min 11 s | 31 min 56 s |
**Lecture.** L'effet de l'élargissement se **répète** sur la deuxième graine : score de consensus −26,2 % (graine 42) puis −23,2 % (graine 101), SEEL −13,4 % puis −7,5 %. Le raffinement final ne change rien à la graine 101 : la ligne `RATE_POST` `999950008` renote le même plan que le meilleur natif (même score 0,096388), alors qu'il avait donné −0,89 % à la graine 42 : son apport est au mieux marginal. Le meilleur score de consensus des défauts est **identique** aux deux graines (0,125451, mêmes moyenne, écart-type et pire valeur) : c'est le même protocole effectif (queue de secours), indépendant de la graine de recherche, car le consensus ne dépend que des graines 41/42/43. Les durées ne se comparent pas : un autre agent a exécuté du Python dans le dossier pendant le bras A. Toujours deux graines, un run par bras, mêmes graines de consensus pour la recherche et la notation, aucune confirmation sur groupes frais.

## Pour conclure (reste à faire)
Fait depuis : les deux bras à la graine 101 (ci-dessus) et l'isolation des leviers aux graines 42 et 101 (dossiers `reports/STRAT_99c_isolation_leviers_2026-10-17` et `reports/STRAT_99c_isolation_leviers_graine101_2026-10-17`, protocoles figés avant la lecture des résultats). Reste : les deux bras à la graine 202 ; renotation de plans figés sur des groupes frais prédéclarés (hors 41–43, 202…3537 et les groupes 1741xxxx à 1763xxxx, 177100xx déjà consommés) ; bras optique pur ; vérifier que le résultat n'est pas dû aux seules queues du secours.
