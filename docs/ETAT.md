# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-16.

## 0. Reprise — à lire en premier, à tenir à jour

> Mettre à jour cette section avec le travail : « en cours » dès le début, mesure et commit
> à la fin. Les règles de validation sont dans les sections 2, 4 et 12 de
> [CLAUDE.md](../CLAUDE.md) ; les décisions scientifiques appartiennent à 👤 (§5).

**Reprise courante (2026-10-16).** Après le bilan clos, 👤 demande « continue la suite logique ».
Le terminal est rétabli et le préflight estGO ; aucun calcul scientifique vivant au contrôle de reprise.
Diagnostic R5/h03 enregistré terminé ; préparation contrôlée échouée avant application/claim/mesure
sur accès sandbox refusé au worktree externe. Fenêtre48c `[9,11)` admissible identifiée, correctif non écrit.
👤 demande une passation, « push et commit all », puis un ménage drastique sous1Go et choisit
archives locales/dépôtGit léger.2242JSON volumineux conservés en archivesSHA horsCERTUS ; caches
retirés, ancienne copie.claude préservée horsCERTUS. Dossier certus0310 environ509Mo Git compris
au contrôle avant commit ; sources scientifiques inchangées, publication en préparation.
[Ménage, emplacement des archives et restauration ciblée](../reports/STRAT_Rate_publication_2026-10-16/README.md).
[Diagnostic précis, commandes et limites pour l'IA suivante](STRAT_Rate_reprise_20261016.md).
[Autorisation, périmètre et plafonds distincts](../reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json).
L'ancien programme et ses contextes restent figés, son suiviPAUSED. Aucune nouvelle mesure engagée.

**Programme historique (décision du2026-10-15, terminé).** Corriger le noyau RMSE puis reprendre
le Rate **jusqu’à la fin du programme borné R0–R6**, avec **24 processeurs logiques**, affinité0xffffff,
priorité Normal et23threads de bibliothèque au maximum. A2 est terminée24/24 ; poursuivre selon le
[guide complet de reprise Rate](STRAT_Rate_suite_chantier.md). Il contient les preuves, comparateurs,
contrats, commandes, expériences, critères d’arrêt et procédure après crash. La passation vers une autre IA
n’est plus l’action prévue. Aucune nouvelle activation de défaut ni publication autorisée.
Cette décision remplace l’ancienne limite du15 octobre8 h ; les anciens protocoles/lanceurs et leur
échéance restent conservés comme archives. [Nouvelle autorisation et sources avant correctif](../reports/STRAT_RMSE_uniform_weights_2026-10-15/authorization_and_baseline.json).
Une seule mesure à la fois, aucun test pendant une mesure, aucun arrêt scientifique ni publication.
**Autonomie confirmée le15 octobre jusqu’à demain matin.** Le repère annoncé par l’IA est le
**vendredi16 octobre2026 à8 h Paris, soit06:00UTC** : aucun nouveau test ni mesure après ce repère.
La fin des quotas R0–R6 reste une condition d’arrêt plus précoce. L’IA tranche les choix techniques
courants et réparations sûres sans nouvelle question, à partir des preuves ; elle n’invente ni donnée
machine ni approbation hors périmètre. À8 h, conserver et laisser finir le calcul engagé, sauvegarder
et rendre le bilan, puis mettre le même suivi en pause. Les futurs lanceurs doivent vérifier cette
limite avant chaque lancement, dans de nouvelles copies ; scripts scientifiques vivants inchangés.
[Demande exacte, interprétation horaire et limites](../reports/STRAT_Rate_suite_2026-10-15/autonomie_jusqu_20261016_0800/authorization.json).
**État actuel : programme borné R0–R6 clos par arrêt précoce R6 le16octobre2026. Correctif RMSE validé ; intégration Rate validée et inactive par défaut ; gains frais propres confirmés sur les trois graines r75x0.5 (moyennes1,2541%/1,2888%/1,7562%), mais aucun gain48c (même plan complet,0%). Quatre paires R6 consommées sur six ; x1.5/x2 non lancés selon la règle fixée. Aucun calcul vivant ; sauvegarde finale effectuée, suivi mis en pause (statut PAUSED confirmé). [Bilan final et limites](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md), [audit final et empreintes](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/audit_final.json).** R4 :62groupes/518propositions/2198appels réels300tirages ; meilleur natif raffiné0,3431123800nm, gain de recherche4,7071%. Confirmation :84appels réels,3/3 victoires sur le natif, gain moyen4,4772%/médian4,2638%, minimum2,5777%, aucune perte ni plantage observé pour le gagnant. Il ne bat le meilleur local9900008 que1/3fois ; la lignée issue du seul contrôle natif ne confirme pas son gain. Les contrôleurs de recherche et confirmation sont terminés, à revérifier par les processus avant action. [Confirmation et limites](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/confirmation_01/bilan_confirmation_20261015.md). [Plan concret R3_h03, sources et lanceurs préparés/vérifiés](../reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/reprise_et_plan.md). Le défaut initial d’égalité stricte de pondération RMSE
est reproduit sur le worktree A2 propre, avec un cache neuf : écart d’un ULP, préexistant au Rate.
Correctif séparé validé : une petite fonction JIT sans fastmath dirige les poids constants positifs
valides vers la spécialisation non pondérée ; le corps du noyau historique est conservé à l’AST, seul son nom devient privé.
Comparaison froid/froid de49 cas : **490 tableaux non concernés identiques au bit,392 cas uniformes
alignés sur le non pondéré, contre272 écarts avant correction**. Les4 cas de régression échouent sur
l’ancien noyau et passent après ;59 contrôles ciblés et1143 oracle passent. Suite unité du15 octobre :
**5433 passed,7 skipped,0 failed**,32 min22 s. UI terminée : **1324 passed,12 skipped,2 xfailed**,
aucun échec inattendu,28 min02 s. Première validation : reste **358 passed,1 failed**,11 min14 s ;
contrôleur `FAILED`, test concurrent à ratio2,3237 contre plafond1,82 ; documentation/C1 non exécutés dans cette tentative.
[Observation et sources du test](../reports/STRAT_RMSE_uniform_weights_2026-10-15/performance_failure_01/observation.json).
Identité du test/harnais àHEAD vérifiée à l’AST et après normalisationCRLF/LF :
[preuve](../reports/STRAT_RMSE_uniform_weights_2026-10-15/performance_failure_01/source_identity_02.json).
Diagnostic fini : origine et correctif échouent avec plafondNumba23. Le masque1 du thread principal
ne s’applique pas aux workers, observés à23 ; une limite1 globale ne suffit pas toujours à rendre le test vert.
Harnais corrigé dans `tests/performance/test_performance.py` : initializerNumba1 sur chaque worker,
**aucun seuil ni source physique modifié**. Contrat de threads : rouge avant/vert après avec calcul factice ;
**18 tests de performance réels passent à froid**,20,93 s. [Diagnostic et limites](../reports/STRAT_RMSE_uniform_weights_2026-10-15/performance_failure_01/bilan.md).
**Continuation séquentielle terminéeGO à9 h06 le15 octobre** dans
`reports/STRAT_RMSE_uniform_weights_2026-10-15/full_validation_02/validation.json` : groupe restant **359 passed**,
15 min17 s ; Ruff et trois contrôles documentaires verts, **C1 à froid :8008 tableaux identiques au bit**.
Résultats verts des suites inchangées conservés avec leur provenance ;
première validation échouée intacte. Les gardes préparées R0/R2 lisent cette nouvelle continuation.
R0 terminé et auditéGO : trois plans, douze appels réels à300tirages101/41/42/43, références reproduites.
L’observateur passif est vérifiéGO. **R2 terminé le15 octobre à10 h13 Paris**,47min59s exports inclus,
5353 stratégies ; sources/scripts/copies vérifiés, verrous libérés, réservation conservée. Meilleur consensus
0,032410960467156955, SEEL0,3600608863nm : plan natif historique retrouvé, aucun nouveau gain.
[Audit et diagnostic R2](../reports/STRAT_Rate_suite_2026-10-15/bilan_R2_diagnostic_R3_20261015.md).
**R3_h01 terminé et renoté à12 h34 : aucun gain,0,0000 %.** Les deux voies donnent le même plan complet
à0,3600608863nm. Rejeu homogène : cinq plans uniques dont ablation9900001 et ancres,20 appels300tirages
101/41/42/43, tous points fixes reproduits ; aucun groupe frais consommé. Les largeurs seules ne sont pas
retenues comme amélioration. [Bilan et preuves](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/bilan_R3_h01_20261015.md).
Contrôle terminé à11 h20, variante à12 h18 ; coordinateur33592 terminé, sortie variante0. Contrôle21508 auditéGO :
5412 stratégies,44min20s exports inclus ; meilleur consensus natif0,032410960467156955 inchangé.
[Audit du contrôle](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/audit_control.json).
Le contrôle est adopté, jamais rejoué. [Protocole h01v3](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/protocol_v3.json).
Seul facteur : largeurs conjointes2/4/6 contre1..7 ; budgets480/240, six tours, λ, ordre et notation inchangés.
Garde, générateur/observateur et sauvegarde réelle vérifiésGO ; PythonCPU24 dès démarrage, affinité0xffffff/Normal.
Le premier coordinateur19112 a échoué avant tout enfant sur sa sauvegarde ; état/logs conservés.
Après le contrôle, le coordinateur36608 signale un faux échec : Windows PowerShell5.1 renvoie
un `ExitCode=null` sans handle conservé. Contre-épreuve réelle avant/aprèsGO ; la reprise conserve
le handle. Une tentative41504 échoue avant tout enfant, `Get-FileHash` absent dans ce contexte ;
la nouvelle copie utiliseSHA256.NET, éprouvé sous le même PowerShell5.1. Anciennes sorties intactes,
aucun calcul ni quota rejoué. [Diagnostic et réparation](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/controller_repair_after_control_20261015.json).
Le service IDE pyright n’est pas un calcul ;
seule sa commande installée exacte est exclue de l’inventaire, les autres Python restent bloquants.
**R3_h02 engagé à12 h42 Paris** : contrôle30284 terminé à13 h25 min38 s, sortie0 enregistrée ;
variante28532 terminée à14 h10 min37 s, sortie0 ; coordinateur24768 terminé à14 h10 min48 s. Lire
`R3_h02_wavelengths/pair_controller.json`, les états des voies et les processus avant toute action.
Audits des deux voiesGO :5375/5408 stratégies,43 min34 s/44 min43 s exports inclus. Renotation prête :
six plans complets figés,24 appels réels300tirages attendus,22 vérifications de garde/contrats/ASTGO.
Renotation38144 terminéeOK à14 h38 min55 s :24 appels300tirages effectifs, ancres reproduites ; réservation conservée. La première invocation
a échoué avant réservation, date ISO reformattée par PowerShell ; invocation corrigée sans changer
les sources, première console/sortie conservées dans `replay_launch_failure_01`.
[Protocole, commande et revue](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/replay_command_and_review.json).
Les12 propositions conjointes à fenêtre interne[34,37)/688 prouvent l’accès à ce voisinage, pas un gain.
**Bilan h02 :0,3600987135nm contre0,3600608863nm, aucun gain**, aucun groupe frais consommé.
Deux candidats admissibles au seuil80tirages sont classés58e/59e pour42 conservés, avant le plein36.
[Bilan, renotation et diagnostic des étapes](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/bilan_R3_h02_20261015.md).
R4 terminé et audité :62groupes,518 propositions nouvelles,2198 appels réels300tirages ; budgets, plans, sources, ancres et appels réconciliés. Branche locale195propositions sans gain, arrêt sans passe2. Branche native210 internes puis113 préfixe : gagnant97000497,0,3431123800nm. [Bilan de recherche](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/bilan_R4_recherche_20261015.md), [audit complet](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/complete_audit_01.json).
Confirmation terminée : sept plans figés, trois groupes/84 appels réels300tirages ; principal3/3 gains contre natif (moyenne4,4772%, médiane4,2638%, pire perte0),1/3 contre9900008 ; secondaire issu du seul contrôle1/3, non retenu. [Bilan frais](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/confirmation_01/bilan_confirmation_20261015.md). Les12 graines17410001..04/11..14/21..24 sont consommées, comme202–3535. Pas de confirmation supplémentaire pour rechercher un gain secondaire.
Incidents conservés, aucun calcul rejoué : [adoption046, sortie initiale inconnue](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/controller_repair_01.md), [adoption du checkpoint061, enveloppeIO bornée](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/checkpoint_repair_01/reprise.md), [contrôle des graines fraîches corrigé après groupe01](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/confirmation_01/validator_repair_01.md). Sources numériques/générateurs figés et protocoles historiques inchangés. Générateur839contrats, lanceur26contrôles+6refusGO, callbacksAST identiques et contre-épreuvesIO/ancres/graines conservés.
La découverte native automatique est étayée pour r75x0.5 ; la généralisation à d’autres composants reste non établie. Dernière paireR3_h03 décidée : même politiqueh02 àλ fine dans les deux voies, seul facteurpost-raffinement final ; parents extraits exclusivement de la même sortie native, jamais d’ancres injectées. [Plan détaillé, vérification des lanceursGO avant mesure](../reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/reprise_et_plan.md). R3_h03 : [revue et contrôles avant lancement](../reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/launch_review.md),10contrôlespipeline/AST,7gardes et persistancePowerShell5.1GO ; protocole figé ; contrôle4868/variante51868 terminés sortie0 ; coordinateur41628 terminé à20 h15. AuditGO :36groupes305propositions +renotationparents,1333appels300 ; gagnant98000284 issu automatiquement de900754520,0,3431123800nm. Confirmation30404 terminée :72appels réels, gain propre5,2130% moyen/5,5052% médian,3/3victoires,min4,0078%,0/3contre9900008 ; pas de groupes supplémentaires. [Bilan fraish03](../reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/confirmation_01/bilan_confirmation_20261015.md). Graines17510001..04/11..14/21..24 consommées. Les trois pairesR3 sont épuisées, aucune relance. R5 code écrit inactif par défaut : elite_rate_joint_candidates=0/rate_post_refinement=False ;78tests ciblés verts, Mypy trois nouveaux modulesGO,123contextes/78546candidats équivalents au prototype et37groupes305propositions rejoués sur issues enregistrées sans simulation. [RepriseR5, limites et validation](../reports/STRAT_Rate_suite_2026-10-15/R5_integration/reprise_et_validation.md). Oracle avant/après1143passed ; validation généraleR5 terminéeGO le15octobre22h29Paris :5450unité,1324UI,359reste, Ruff/Mypy/docs/diffverts et C1froid8008tableaux identiques au bit. Nouveau contexte rate-r5-native créé depuis les16snapshotsvalidés,321sources du paquet et24écartsCRLF/LF/ASTégaux documentés. Points fixesR5 terminésOK à22h41Paris :12appels réels300tirages101/41/42/43, ancres reproduites et sources vérifiées. Coordinateur26152/enfantnatif35596 terminés sortie0 à23h31Paris. AuditR5 :305propositions/37groupes,997appels300, gagnant et307plans identiques au prototype ; différences numériques explicites et29parcours de génération natifs distincts, identité globale au bit non établie. R6cas77 terminé : contrôle35160 et variante12900 sorties0, coordinateur55048 clos à01h15Paris. Meilleur consensus propre0,4105379101nm contre variante0,4047476385nm, gain initial de recherche~1,41%. Six plans figés avant les groupes176100xx, trois confirmationsv2 terminées sortie0 à01h41Paris/72appels300. Gain moyen1,2541%/médian1,0523%,3/3contre contrôlecomplet et3/3contre exportofficiel (moyenne1,6198%) ;0/3contre référence et meilleur local. Critère préfixé3/3+médiane≥1% satisfait, effet modeste sans intervalle de confiance. Graines17610001..04/11..14/21..24 consommées. fresh_audit.jsonGO et bilan_20261016.md ; cas202 terminé : contrôle2184/variante21820 sorties0, coordinateur39516 clos à03h14Paris ;306propositions38groupes1028appels post300. Meilleurs consensus0,3766377392nm et0,3647537596nm, gain initial3,1553%. Six plans figés puis72appels frais300 terminés sortie0 à03h32Paris ; gains propres1,4166/1,0253/1,4245%,moyenne1,2888%/médiane1,4166%,3/3victoires,pireperte0. Contre export officiel3/3moyenne3,3405%,contre référence3/3moyenne6,3086%,contre meilleur local0/3moyenne−9,4730%. fresh_audit.jsonGO et critère préfixé satisfait ; graines176200xx consommées, aucun groupe ajouté. Cas404 terminé : contrôle24380/variante7640 sorties0, coordinateur40204 clos à04h57Paris ;325propositions39groupes1068appels post300. Trois groupes frais terminés sortie0 à05h01Paris,72appels300,gains propres0,4330/2,4731/2,3623%,moyenne1,7562%/médiane2,3623%,3/3,pireperte0. Groupes176300xx consommés. Trois cas initiaux favorables/216appels frais ; bilan initial et initial_gate.jsonGO. Autres composants en copies distinctesR6_other_components préparées/vérifiées sans simulation, 48c/premium/77/fente recherchée terminé, deux sorties0 et auditGO : même plan complet,0proposition, huit appels post150 ; puis12appels frais300 sur trois groupes, gain0%, auditGO. Fenêtre interne traversant plusieurs blocs, contexte non applicable ; arrêt sans gain avant passe préfixe. Arrêt de cette extension selon critère fixé avant mesure, x1.5/x2 non lancés et24graines177200xx/177300xx réservées non consommées ; bilan final conservé ; trois nouvelles paires au maximum,sixR6total,arrêt au premier cas conditionnel non confirmé et limite06:00UTC prioritaire. Première préparationLF/CRLF conservée, aucun calcul répété. Lire R6_generalization/launch_review.md et c01_s77/controller.json ;77/202/404 partagent les réglagesλfine480/240/six tours, seul facteur post-finaloff/on. Trois groupes frais propres par cas réservés avant recherche. Lire R5_integration/measurement_launch_review.md, measurement_controller.json, points/measurement/control.json ou native/measurement/etat.json ; ne pas lancer de doublon ni autrePython/test pendant un enfant. Contextes historiques figés. Programme borné clos par arrêt précoceR6 ; trois pairesR3 et quatre pairesR6 mesurées, aucuneh04R3 ni suite conditionnelle après48c. Options inactives, aucun nouveau défaut/commit/push/publication.
Lors deh02, seul facteur : voisinage deλ autour du bloc parent, voisins légaux±1/±2/±3 prioritaires devant le flux
historique. Largeurs1..7 identiques dans les deux voies ; budgets480/240, six tours, sélection et physique inchangés.
Les347 nouvelles fenêtres de trois couches observées enh01 n’avaient jamais688 : tester ce couplage
ne promeut pas le résultat nul des largeurs seules. Si le couple gagne, la troisième paire peut ablater
les largeurs sous la même politique deλ. [Reprise h02, protocole et vérificationsGO](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/reprise_et_protocole.md).
Les deux voiesh02 et leurs renotations sont terminées ; ne pas les relancer. Aucun doublon, test ni modification des sources/scripts actifs.
[Transition et preuves R0/R2](../reports/STRAT_Rate_suite_2026-10-15/bilan_R0_R2_transition_20261015.md),
[état R2](../reports/STRAT_Rate_suite_2026-10-15/R2_native_base/etat.json). Validation générale courante :
[état et commandes](../reports/STRAT_RMSE_uniform_weights_2026-10-15/full_validation_02/validation.json) ;
contrôleur de validation terminé ; aucun nouveau passage des suites n’est nécessaire sans nouvelle modification pertinente.
Suivi existant **ACTIVE**, même chat, arrêt au premier atteint : fin des quotas R0–R6 ou16 octobre8 hParis ; sources historiques figées.
[Diagnostic, tentatives et preuves RMSE](../reports/STRAT_RMSE_uniform_weights_2026-10-15/bilan_et_reprise.md).
[Bilan du blocage initial et reprise concrète](../reports/STRAT_Rate_suite_2026-10-14/validation_after_A2/blocker_20261014/bilan_et_reprise.md).
R1 préparée dans l’arbre principal : la sonde conserve les scores base/consensus, métadonnées de graines/
échantillons et resets des témoins ; aucune modification de score ou de sélection. Test de régression
validé : **3 tests passent avec R1 et échouent sur l’ancien code** pour les champs manquants.
La première validation générale du14 octobre a échoué : suite unité **5428 passed,7 skipped,2 failed**
en31 min04 s. Ré-export manquant de
`_balanced_elite_rate_moves` dans la façade corrigé uniquement dans l’arbre principal ;
test de pondération uniforme : écart strict5,55e-17. Contrôle ciblé après correction avec cache neuf :
**65 passed,1 failed** ; le ré-export et les mouvements Rate passent. Contre-épreuve sur A2 propre
`da1af082`, cache neuf distinct : **4 passed,1 failed**, même écart ; noyau et test identiques.
Diagnostic du15 octobre :les deux branches du corps Python donnent les mêmes bits, les spécialisations
JIT historiques diffèrent ; un simple cache chaud n’explique pas l’écart. Les tests stricts sont renforcés,
aucune tolérance relâchée ; worktrees de mesure historiques inchangés. Relevé précédent
`validation_after_A2/attempt_02/health_20261014_1730_wake.json` conservé dans le dossier de suite.
Le premier montage de comparaison échoue à l’import du snapshot ; échec conservé, chemin logique corrigé.
[État et journaux de validation](../reports/STRAT_Rate_suite_2026-10-14/validation_after_A2/attempt_02/validation.json).
Sources avant/après et état dans `reports/STRAT_Rate_suite_2026-10-14/R1_score_export/`.
R2 : [analyse statique des traces existantes terminée](../reports/STRAT_Rate_suite_2026-10-14/R2_static_trace_v2/analysis.md),
aucun appel physique ni test parallèle. 38410 conjoints dans le natif six tours ; dans le natif préfixe,
36358 conjoints et47615 préfixes. Ni fenêtre L35–L37/688, ni préfixe L1–L5/613 dans ces propositions
supplémentaires ; grille/étapes de sélection non enregistrées, cause précise encore à tracer.
Ce diagnostic ne constitue pas une nouvelle amélioration mesurée ; le R2 complet engagé doit préciser la cause.
Archives de préparation du14 octobre : `scratch/rate_native_pipeline_trace.py`, snapshot et liste de validations
dans `reports/STRAT_Rate_suite_2026-10-14/R2_pipeline_trace_preparation/`. Il doit conserver grille,
parents, appels réels et métadonnées par étape. **Ancien raccordement à échéance expirée, ne pas relancer** :
`scratch/rate_native_pipeline_probe.py`, échéance/tag explicites, fin24/24 et machine libre obligatoires,
record de vérification `GO` aux mêmes SHA256 et contrôle R0 des trois ancres à300 tirages/graines réelles.
`scratch/verify_rate_native_pipeline_trace.py` préparé pour factory/ordre/IDs/curseur, copie NumPy,
délégation et restauration après exception, sans simulation. Ruff/parsing verts ; **aucun test exécuté**.
Snapshots/commandes et état dans `reports/STRAT_Rate_suite_2026-10-14/R2_native_trace_launch_preparation/`.
[Revue statique des lanceurs](../reports/STRAT_Rate_suite_2026-10-14/R2_native_trace_launch_preparation/static_review_20261014.md)
consignée : ID de contrat provisoires et ordre de fin des tâches ne doivent pas servir seuls aux
jointures/classements ; fallback ELITE et profondeurs réelles à respecter. Aucun nouveau résultat physique.
Ancien R0 préparé le14 octobre : `scratch/rate_fixed_replay_R0_suite.py`, contrôle seul, échéance explicite,
A2complète/machine libre obligatoires et sauvegardes atomiques du helper. Plans/protocole/SHA256 et
[commandes](../reports/STRAT_Rate_suite_2026-10-14/R0_replay_preparation/commands.md) conservés ;
AST du corps scientifique identique àv11, Ruff vert. **Aucun aperçu/test/contrôle runtime lancé**.
Contexte de mesure séparé créé : worktree géré `rate-rmse-r0`, HEADda1af082, cinq sources copiées
exactement depuis la validation ; preflightGO. [Descripteur de provenance](../reports/STRAT_Rate_suite_2026-10-15/reference_context.json).
Les24 autres écarts d’octets du paquet sont uniquementCRLF/LF, sources normalisées/AST identiques ;
empreintes et clés de cache réelles conservées, aucun fichier figé supplémentaire modifié.
R0 et observateur terminésGO : [points fixes](../reports/STRAT_Rate_suite_2026-10-15/R0_verified.json),
[contrats de l’observateur](../reports/STRAT_Rate_suite_2026-10-15/observer_verification/verification.json).
R2 audité : grille légale450..750/1nm ; les348 fenêtres internes[34,37) des propositions conjointes sont
héritées, aucune n’est activement reconstruite ni à688nm. R3 teste d’abord les largeurs, sans ajouter de λ.
Après la paire, auditer puis renoter les finalistes à profondeur homogène avec les comparateurs fixes,
avant toute confirmation fraîche conditionnelle. Les scripts historiques restent figés ; aucun doublon.
Copies actuelles préparées dans `scratch/*_bounded.py`, garde commune `rate_suite_bounded_guard.py` :
un emplacement de mesure R0 et un R2, validationGO et machine libre obligatoires. Gardes et aperçusGO ;
**R0/R2, les deux voies et le rejeuR3_h01, et les deux voiesR3_h02 ont leurs réservations permanentes ; renotationh02 terminée, réservation distincte conservée ; aucun calcul scientifique engagé.**
La base101 préfère le plan9900006, le consensus41/42/43 préfère9900008 : inversion observée en R0,
simple hypothèse à confronter à la trace native, pas une cause déjà démontrée ni un nouveau gain.
[Sources et empreintes actuelles](../reports/STRAT_Rate_suite_2026-10-15/launcher_preparation/preparation_current_03.json),
[procédure de lancement aprèsGO](../reports/STRAT_Rate_suite_2026-10-15/launcher_preparation/reprise.md).
Vérificateur des refus/quotaGO : `scratch/verify_rate_suite_bounded_guard.py`,
[fixtures synthétiques isolées et conservées](../reports/STRAT_Rate_suite_2026-10-15/guard_verification/verification.json).

**Terminée (2026-10-14 à16 h35, A2).** Les 24 exécutions demandées par 👤 sont sauvegardées et vérifiées.
[Audit complet et limites](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md) ;
contrôleurs terminés, verrous libérés, machine libre à17 h01. Les exécutions sont relancées le13 octobre à 12 h 01 (Paris), dans l'ordre du tableau,
sur le worktree géré `campagne-a2`, figé à `da1af082`, propre et recontrôlé (`PREFLIGHT=GO`), hors Drive. Le lancement initial
(11 h 23 à 11 h 48, Paris) est interrompu : 👤 signale un PC figé et demande de redémarrer, puis de reprendre avec la moitié
des cœurs. Point de reprise intact, 0/24 mesure terminée, aucun processus résiduel constaté avant relance ; les journaux de
la tentative interrompue sont conservés dans le dossier de campagne (`*_avant_reprise_*.log`). Nouvelle limite vérifiée sur
le contrôleur et son calcul : 16 processeurs logiques sur les 32 du poste, affinité Windows `0xffff`, priorité normale.
Le contrôle d'héritage rend `RESOURCE_CHECK=GO` : CPU déclaré 16, 14 workers, 15 threads Numba au maximum ; une mesure à la fois,
cache Numba réutilisé. À la demande de 👤, A2 a fait une pause de 13 h 18 à 14 h 56 (Paris) pour intercaler le batch ci-dessous :
2/24 exécutions terminées, `r75x1.5 deep 0 0 2 0 42 0`, avec puis sans `elite_rate_moves`, en 39 min 30 s et 38 min 21 s.
Les deux artefacts sont sauvegardés et vérifiés ; aucun calcul A2 interrompu. A2 a repris automatiquement à 14 h 56,
toujours à 16 processeurs logiques, sur `r75x1.5_deep_s101_avec`. À 14 h 59, après demande de 👤 d'expertiser la régression
et de tester d'autres pistes, son calcul est repris par le contrôleur `--adopt-current --stop-after-current`, puis sauvegardé
à 15 h 40 avant pause : **3/24** exécutions terminées. Cette troisième mesure dure 43 min 53 s et donne un SEEL de 0,487613 nm.
Aucun échec A2 constaté. Exploration Rate terminée ; **A2 reprise le 14 octobre à 5 h 35 min 23 s (Paris)**,
contrôleur nocturne **23280**, désormais terminé ; continuation ci-dessous, **24/24 terminées**.
Quatrième mesure `r75x1.5_deep_s101_sans` sauvegardée à **6 h 16 min 46 s**,
**41 min 23 s**, SEEL **0,4881866128 nm**, **4 554 déposables**, verdict/provenance/option effective vérifiés.
Paires `r75x1.5` complètes : gain avec/sans **3,25 %** sur42, **0,12 %** sur101 ; écarts inférieurs au repère de dispersion,
aucune supériorité établie ni conclusion globale. Cinquième mesure `r75x1.75_deep_s042_avec` sauvegardée à **7 h 04 min 19 s**,
**47 min 33 s**, SEEL **0,4788232294 nm**, **3 998 déposables**. Sixième mesure sans sauvegardée à **7 h 50 min 34 s**,
**46 min 15 s**, **0,4967841046 nm**, **4 060 déposables** ; verdict/provenance/options effectives vérifiés pour la paire42.
Écart avec/sans inférieur au repère de dispersion, aucune supériorité établie. Septième mesure avec sur101 sauvegardée à
**8 h 38 min 20 s**, **47 min 46 s**, **0,4717267402 nm**, **3 800 déposables**, verdict/provenance/option effective vérifiés.
Huitième mesure `r75x1.75_deep_s101_sans` sauvegardée à **9 h 25**, **46 min 42 s**,
SEEL **0,4967841046 nm**, **3570 déposables**, verdict/provenance/option effective vérifiés.
Paire101 complète : écart brut avec/sans **5,0439 %**, sans renotation homogène des gagnants fixes,
aucune attribution causale ou conclusion globale. Même worktree figé,16 processeurs / `0xffff` / Normal /15 threads.
**Nouvelle demande explicite de 👤 le14 octobre : terminer les batchs restants**, après l’ancienne limite de9 h.
Le contrôleur nocturne a fini sa huitième mesure et libéré le checkpoint ; continuation **51884**,
`scratch/a2_continue_runner.py`, terminée. Sources/checkpoint/processus vérifiés ; elle a lancé le contrôleur
original **24128** à **9 h 25 min 04 s**, jusqu’à **24/24**. Neuvième mesure `35c_deep_s042_avec`
sauvegardée à **9 h 31**, **5 min 58 s**, **0,4833014938 nm**, **1488 déposables**.
Dixième `35c_deep_s042_sans` sauvegardée à **9 h 37 min 19 s**, **6 min 17 s**,
**0,4886754175 nm**, **1523 déposables**. Paire35c : gain brut **1,0997 %**, verdict/options effectives
et empreintes vérifiés ; aucune confirmation homogène indépendante. Onzième `75c_deep_s042_avec`
sauvegardée à **10 h 28**, **50 min 42 s**, **0,2407378291 nm**, **3683 déposables**,
verdict/option effective/empreinte vérifiés. Douzième `75c_deep_s042_sans` sauvegardée à **11 h 21**,
**53 min 48 s**, **0,2408512734 nm**, **4702 déposables** ; verdict/provenance/option effective/empreinte
vérifiés. Paire75c complète : gain brut **0,0471 %**, aucun progrès établi ni confirmation homogène indépendante.
Treizième `48c_premium_s077_avec` sauvegardée à **11 h 30**, **8 min 46 s**, **0,1922274813 nm**,
**2602 déposables**, verdict/provenance/option effective/empreinte vérifiés. Profondeurs déclarées150/25/40/150,
distinctes de deep300/50/100/300 ; pas de comparaison au cas `r75x0.5`, métadonnées complètes de consensus absentes.
Quatorzième `48c_premium_s077_sans` sauvegardée à **11 h 38**, **8 min 18 s**, **0,1911013642 nm**,
**2472 déposables**, verdict/provenance/option effective/empreinte vérifiés. Paire48c/77 complète :
régression brute avec/sans **0,5893 %**, aucune supériorité établie ni confirmation homogène indépendante.
Quinzième `48c_premium_s101_avec` sauvegardée à **11 h 47**, **8 min 28 s**, **0,1919806063 nm**,
**2621 déposables**. Seizième `48c_premium_s101_sans` sauvegardée à **11 h 55**, **7 min 57 s**,
**0,1922429122 nm**, **2457 déposables** ; verdict/provenance/options effectives/empreintes vérifiés pour la paire.
Gain brut48c/101 **0,1364 %**, aucune supériorité établie ni confirmation homogène indépendante.
Dix-septième `48c_premium_s202_avec` sauvegardée à **12 h 04**, **8 min 47 s**, **0,1873016155 nm**,
**2575 déposables** ; verdict/provenance/option effective/empreinte vérifiés. Dix-huitième `48c_premium_s202_sans`
sauvegardée à **12 h 12**, **8 min 16 s**, **0,1879353657 nm**, **2482 déposables** ; mêmes contrôles vérifiés.
Paire202 complète : gain brut **0,3372 %**, aucune supériorité établie ni confirmation homogène indépendante.
Les trois paires48c/premium77/101/202 sont terminées, sans progrès établi sur ces minima exportés.
Dix-neuvième `r75x0.5_deep_s077_avec` sauvegardée à **12 h 51**, **38 min 39 s**, **0,4362542820 nm**,
**3675 déposables**, verdict/provenance/option effective/empreinte vérifiés. Vingtième `r75x0.5_deep_s077_sans`
sauvegardée à **13 h 28**, **37 min 21 s**, **0,4943430491 nm**, **3594 déposables** ; mêmes contrôles vérifiés.
Paire77 complète : gain brut avec/sans **11,7507 %** des mouvements Rate de production existants,
confirmation homogène indépendante des plans fixes encore à faire ; aucun résultat d’intégration native
du nouveau raffinement local. Aucune comparaison directe à la référence101 ni au meilleur plan local.
Vingt-et-unième `r75x2_deep_s202_avec` sauvegardée à **14 h 16**, **48 min 16 s**, **0,5411587816 nm**,
**4964 déposables**, verdict/provenance/option effective/empreinte vérifiés. Vingt-deuxième `r75x2_deep_s202_sans`
sauvegardée à **15 h 02**, **45 min 29 s**, **0,5678354293 nm**, **4168 déposables** ; mêmes contrôles vérifiés.
Paire202 complète : gain brut **4,6980 %**, aucune supériorité établie ni confirmation homogène indépendante.
Aucune comparaison au cas `r75x0.5`. Vingt-troisième `r75x2_deep_s077_avec` sauvegardée à **15 h 51**,
**49 min 18 s**, **0,5440634380 nm**, **4744 déposables** ; verdict/provenance/option effective/empreinte
vérifiés. Dernière mesure `r75x2_deep_s077_sans` sauvegardée à **16 h35**, **44 min12 s**,
**0,5713569313 nm**, **3754 déposables** ; mêmes contrôles vérifiés. Paire77 complète : gain brut
**4,7770 %**, sans confirmation homogène indépendante ; aucune conclusion générale.
Une seule mesure à la fois ; aucun calcul interrompu et aucun script scientifique actif modifié. Préparation et état dans
`reports/STRAT_A2_continuation_2026-10-14/`. Suivi existant actualisé pour cette poursuite.
Contrôle final à **17 h01** : aucun processus scientifique/contrôleur ni verrou résiduel ;
worktree A2 à `da1af082`, aucun fichier suivi modifié. Ressources16/0xffff/Normal/15threads conservées.
Preuves `transition_verified_0932.json` et `health_continuation_0933.json` dans le dossier de continuation.
Dernière preuve : `final_audit_20261014_1700.json`,24 cellules uniques, options/provenances/SHA256 vérifiées ; preflight terminé `GO`.
Relevés précédents conservés, dont `health_20261014_1100_wake.json`, `health_20261014_1030_wake.json`
et `health_20261014_1018.json`. Aucun test ni mesure Rate lancé pendant A2.
Le relevé `health_transition_0932.json` chevauche la fin normale de35c/avec ; son ancien PID avait déjà
quitté et le dixième l’avait remplacé, aucun échec de contrôleur. Aucun test parallèle. Les anciennes
configurations de suivi et la garde nocturne sont conservées ; relire l’état avant tout lancement manuel.
Le contrôleur `scratch/campagne_a2_runner.py` (non versionné)
enchaîne les runs, vérifie la provenance et la valeur effective de `elite_rate_moves`, copie les artefacts et actualise le
[rapport](../reports/STRAT_ELITE_couches_Rate_autres_composants_2026-10-13.md) et son
[état](../reports/STRAT_ELITE_couches_Rate_autres_composants_2026-10-13/etat.json). Il s'arrête sur un échec ; aucune conclusion globale avant 24/24.
A1 : SHA1 remplacé localement par SHA256 dans le suffixe chirurgical ; Ruff vert, 117 tests ciblés passed,
1 728 combinaisons de suffixes vérifiées (1 536 identiques, 192 changées comme prévu), oracle 1 143 passed en 13,46 s.
Validation générale interrompue pour réserver la machine à A2 : aucun échec de test constaté, suite non terminée,
correction non committée ; elle n'entre pas dans le worktree de mesure. À reprendre après la campagne.

**Analyse terminée (2026-10-13, intégration Rate/optique).** 👤 précise que les variations de vitesse observées
sont surtout un écart entre deux dépôts ; cette réponse ne donne pas une dérive au cours d'un dépôt.
Le [rapport d'analyse](../reports/STRAT_integration_Rate_optique_analyse_2026-10-13.md) lit le noyau et deux artefacts,
et compte les mouvements sans simulation : l'ordre des familles, tronqué au plafond, peut exclure les ouvertures optiques.
Priorités proposées : répartir ce budget, puis chercher ensemble la fenêtre optique et sa longueur d'onde ; vérifier aussi
les diagnostics de fente sur les blocs entièrement Rate. Les mesures autorisées sont consignées ci-dessous. A2 conserve son code figé ;
aucun défaut ni modèle physique modifié.

**En cours (2026-10-13, après accord de 👤).** `elite_rate_balanced_moves`, option expérimentale inactive par défaut,
répartit les mêmes mouvements Rate entre familles, largeurs et positions, au même plafond. Code dans l'arbre principal :
Ruff vert, 72 tests ciblés passed (couverture, routage, ordre éteint, identifiants et architecture) en 11,30 s ; oracle
1 143 passed en 64,77 s. `certus_strat_consensus.py` reste à 1 500 lignes, sa fonction ELITE à 300. Validation complète
non terminée, aucun commit. Aucun noyau physique modifié. Le voisinage conjoint fenêtre/longueur d'onde est mesuré ci-dessous ; l'ablation doit être renotée à profondeur homogène avant attribution.

Le batch A/B sur `r75x0.5 deep 0 0 2 0 101 0` est lancé à 13 h 32 (Paris), d'abord
`elite_rate_balanced_moves=false`, puis `true`, défauts et plafond de 120 identiques. Worktree géré `rate-equilibre` :
base `da1af082` plus les deux sources modifiées, instantané volontairement non committé (`git_dirty=true` attendu).
Le patch exact et les SHA256 des sources identiques entre les deux variantes sont conservés dans
[`reports/STRAT_Rate_equilibre_AB_2026-10-13/`](../reports/STRAT_Rate_equilibre_AB_2026-10-13/) ; les surcharges dans les artefacts,
le routage actif dans le journal (`[balanced families]`). Contrôleur `scratch/rate_equilibre_batch.py` non versionné,
[rapport de suivi](../reports/STRAT_Rate_equilibre_AB_2026-10-13.md) et
[état](../reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json). Une mesure à la fois, affinité `0xffff`, priorité normale,
15 threads de bibliothèque au maximum. Après le batch, reprise automatique A2 ; revue des résultats et validation complète
du code à faire. Le défaut n'est pas activé sur un seul exemple.
Batch terminé à 14 h 56 (Paris), 2/2 artefacts sauvegardés et contrôlés, routage `[balanced families]` constaté.
Référence : SEEL 0,396715 nm, 4 069 plans déposables, 46 min 45 s ; équilibré : 0,479488 nm, 3 777 plans,
37 min 48 s. Régression de SEEL de 20,86 % sur cette graine ; durées non attribuables au seul changement (cache chaud au second run).
**En cours (2026-10-13, expertise après accord de 👤).** Reconstituer les mouvements et parents réellement explorés,
identifier les chemins utiles évincés par le plafond, puis tester d'autres pistes avec paramètres inactifs par défaut.
Une mesure à la fois, 16 processeurs logiques ; préparer pendant la fin du calcul A2 courant, valider et mesurer après sa pause.
👤 autorise une recherche autonome par essais successifs, y compris d'autres pistes, et laisse son PC allumé jusqu'au
14 octobre à 9 h (Paris) : priorité à une amélioration vérifiée sur `r75x0.5`, A2 conservée à son point de reprise.
Cause observée : à mêmes parents et signatures existantes, l'équilibrage au plafond 120 ne génère plus la fenêtre L35–L36
qui menait au meilleur plan. Reconstruction exacte du premier tour à 9 blocs, via les fonctions extraites par AST, sans noyau physique :
[rapport d'expertise](../reports/STRAT_Rate_expertise_2026-10-13.md) et JSON structurel associé. Les durées du A/B incluent des états de cache différents.
Contrôleur des pistes lancé à 15 h 20, PID 38880 ; premier essai `budget_240` démarré automatiquement à 15 h 40 min 56 s,
après la sauvegarde et la pause A2, puis sauvegardé à 16 h 20 : 39 min 57 s, **0,382810 nm**, 4 134 déposables.
Gain apparent de **3,50 %** contre 0,396715 nm ; graine de recherche seule, contrôle indépendant requis.
Deuxième essai `raffinement_6` sauvegardé à 17 h 04 : 43 min 47 s, 0,387351 nm (−2,36 %), 5 113 déposables.
Budget 240 reste meilleur. Troisième essai `budget_360` terminé à 17 h 52 min 57 s : 41 min 21 s,
0,3828099733 nm, score exactement égal au budget 240, 4 191 déposables. Même masque optique/Rate ;
les différences de partition restent dans des couches Rate. Aucun gain supplémentaire au plafond 360.
Trois essais paramétriques, sans nouveau changement des sources : ordre actuel à budget Rate 240, puis ordre actuel à budget 120
et plafond de six raffinements, puis ordre actuel à budget 360. Ruff des scripts, syntaxe, aperçu des commandes et `git diff --check` verts ;
trois résultats sauvegardés et provenance contrôlée.
[Rapport des essais](../reports/STRAT_Rate_pistes_2026-10-13.md), état et plan dans `reports/STRAT_Rate_pistes_2026-10-13/`.
Suivi de ce chat créé et vérifié : `certus-essais-rate-jusqu-au-14-octobre-9-h`, toutes les30 minutes.
La campagne nocturne et son échéance initiale sont terminées ; la dernière demande de 👤 prolonge ce suivi
pour finir A2 puis le programme borné R0–R6 du guide, avec cette IA. Anciennes configurations conservées.
Garder tous les essais et contrôler les gains sur des graines indépendantes ; aucune activation de défaut.
Reprise de 18 h : A2 sauvegardée à 3/24, trois essais paramétriques terminés ; recherche conjointe active. Contrôle indépendant terminé,
sans test ni mesure en parallèle : référence exportée avec ses blocs/Rate/fente et protocole fixé sur graines 202/303,
consensus distincts 202/203/204 et 303/304/305, après reproduction de la référence 101 + consensus 41/42/43.
Limite de routage lue : `_resolve_injected_strategies` perd Rate/fente/témoins ; ne pas l'utiliser telle quelle pour le rejeu mixte.
Le rapport d'expertise détaille les deux voies à vérifier. L'outil `scratch/rate_fixed_replay.py`, conservé dans le dossier
d'expertise, prépare la voie `ExternalEvaluationStrategy` avec plans complets et génération désactivée ; Ruff, syntaxe
et aperçu verts. La paire référence/budget 240 est exportée avec scores attendus et empreintes des artefacts.
Premier contrôleur de validation arrêté sur échec strict du point fixe à 17 h 04 ; artefact et journaux conservés.
Cause éprouvée : le batch transmet les indices optiques par `SharedIndicesManager/Worker` en `float32`, le rejeu direct gardait leur précision
initiale. Rejeu corrigé avec le même transport, sans modifier la tolérance ni les sources de production ; nouvelle tentative `attempt_02`.
À 17 h 08, deux points fixes reproduits (écart de référence 5,8·10⁻¹⁶), holdouts 202/303 terminés avec verdict `OK`,
trois échantillons de consensus par plan, profondeur conservée, masques/blocs/fente/témoins contrôlés.
Budget 240 contre référence : 0,388957 contre 0,396828 nm (−1,98 %) sur 202/203/204 ;
0,385017 contre 0,399513 nm (−3,63 %) sur 303/304/305. Gain observé sur cet exemple, pas une validation générale.
[Rapport du contrôle](../reports/STRAT_Rate_validation_budget240_2026-10-13.md), état complet et snapshots dans
`reports/STRAT_Rate_validation_budget240_2026-10-13/attempt_02/` ; aucun défaut scientifique activé, aucun commit.
Première piste conjointe terminée : 958 propositions autour du plan budget 240, largeurs 2/4/6, décalages jusqu'à deux couches,
40 longueurs d'onde ; partition conservée. 858 mouvements conjoints, 22 fenêtres seules, 78 λ seules. Recette, propositions et source dans
le dossier d'expertise (`joint_window_proposals_v1.json`). Reprise de 17 h 30 : outil de mesure préparé, Ruff, syntaxe et aperçus verts,
revue manuelle du transfert d'indices et de la conservation des rejets ; aucun test pendant `budget_360`.
Premier contrôleur `scratch/rate_joint_runner.py` (PID 45024) **terminé** à 18 h 08, après la fin sauvegardée
du budget 360 à 17 h 52 ; affinité `0xffff`, priorité normale. Il contrôle d'abord les deux ancres, puis 96 groupes de dix variantes au maximum avec les deux ancres dans chaque groupe.
Chaque candidat reçoit 300 tirages complets ; les admissibles reçoivent les trois consensus à 300, un consensus incomplet l'exclut.
Les résultats bruts de notation (y compris les rejets), paramètres, sources et graines sont conservés ; arrêt sur erreur de simulation,
point fixe perdu ou empreinte changée. Reprise par étapes sauvegardées, anciennes tentatives préservées.
État : `reports/STRAT_Rate_joint_window_2026-10-13/etat.json` ; scripts figés et rapport dans le même dossier et son `.md`.
Contrôle runtime réussi : deux ancres reproduites, appels réels à 300 observés, étapes terminées avec verdict `OK`.
Première recherche terminée à 18 h 08 min 43 s : 958/958 propositions sauvegardées, 370 consensus complets,
581 scores de base non finis et 7 consensus incomplets exclus. Meilleur `9600579`, fenêtre L33–L34 à 630 nm,
SEEL 0,365338 nm (−7,91 % contre la référence). Point fixe du nouveau plan reproduit ; quatre groupes indépendants
202/203/204, 303/304/305, 404/405/406 et 505/506/507 rendent `OK`, profondeur inchangée, sans plantage observé :
SEEL respectifs 0,378707 / 0,371040 / 0,371966 / 0,371250 nm, gains de 4,57 / 7,13 / 6,95 / 7,05 % contre leur référence.
[Rapport et limites](../reports/STRAT_Rate_validation_joint_2026-10-13.md), plans, paramètres, graines et sources conservés.
Mouvements isolés depuis le parent budget 240 : même fenêtre L33–L34 à 706 nm → 0,426482 nm ; même λ 630 nm sur
L32–L35 → 0,902766 nm. La combinaison améliore alors que chacun seul dégrade ; la recherche native et son ablation sont consignées ci-dessous.
Deuxième recherche conjointe lancée à 18 h 13, contrôleur 50136 : 1 753 voisins des fenêtres du nouveau plan,
λ fines jusqu’à ±10 nm sur grille de 1 nm et grille large conservée. Même code figé, mêmes profondeurs et ancres ;
177 étapes séquentielles. État et snapshots dans `reports/STRAT_Rate_joint_refinement_2026-10-13/`, aucune mesure concurrente.
Raffinement : contrôleur 50136 arrêté à 18 h 26 sur `PermissionError` Windows lors du remplacement du rapport et de l’état.
Son dernier calcul `batch_085` a continué et terminé avec verdict `OK` ; aucun calcul scientifique arrêté. Anciens états JSON/tmp,
rapport/tmp, journaux et scripts conservés dans `recovery_20261013_1830/`. Groupe réconcilié, 850 propositions conservées ;
reprise au groupe 086 par le contrôleur **24884**, après vérification de provenance, ancres et processus.
Sauvegarde réparée dans les scripts de contrôleur : `atomic_open` existant, 40 tentatives sur refus temporaire d’accès,
échec persistant propagé. Ruff et essai runtime de deux refus temporaires puis succès / refus permanent passent, sans mesure active.
Aucune source physique modifiée. Raffinement terminé à 18 h 47 min 36 s : 1 753/1 753 propositions, 559 consensus complets,
1 187 scores de base non finis et 7 consensus incomplets exclus ; même meilleur plan, aucun gain supplémentaire.
Premier essai natif terminé : contrôleur **32804**, calcul **47776**, lancé à 18 h 47 min 54 s après fin du raffinement.
Vérifications exécutées entre les mesures : `NATIVE_ADAPTER_VERIFY=GO`, cinq chemins inactifs identiques (sortie/ordre/identifiants/curseur),
préfixe historique conservé à l’activation, nouveaux identifiants uniques, masques/fente/témoins et contrats conservés, parents inchangés,
patches temporaires restaurés ; géométrie gagnante proposée génériquement. Ruff, syntaxe et revue manuelle passent.
Mesure complète `r75x0.5 deep`, graine 101, avec budget séparé de 480 voisins conjoints.
Ancien ordre/budget Rate 120, profondeur et plafonds de screening/évaluation complète conservés. Les candidats réutilisent le
constructeur de CERTUS ; adaptateur temporaire du processus, code de production figé, option inactive à zéro.
Largeurs 2/4/6, décalages ±2, λ des parents puis grille large ; fenêtres et parents prennent leurs tours.
Affinité `0xffff`, priorité normale et 15 threads de bibliothèque vérifiés ; une seule mesure, aucun test pendant son exécution.
État : `reports/STRAT_Rate_native_joint_2026-10-13/controller.json` ; scripts, empreintes et préparation dans ce dossier.
Reprise de 19 h : `PREFLIGHT=GO` après conservation à octets identiques de l’ancienne archive du contrôleur
en `01_campagne_a2_runner.py.txt` (copie E731 avant correction), déplacement documenté dans `archive_relocation_1900.json`.
Ruff et configuration inchangés. Routage natif effectif constaté à neuf blocs au tour 2 : 720 candidats,
dont 600 modifient Rate (120 historiques + 480 conjoints), plafond d’évaluation complète toujours 36. Aucun test parallèle.
Résultat natif sauvegardé à 19 h 29 min 25 s : **0,3967147882 nm**, 4 092 déposables, 16 808 voisins conjoints proposés ;
même plan que la référence, aucun gain. Export de la trace des candidats ensuite échoué sur un tableau NumPy ajouté aux objets
partagés : trace en mémoire perdue, artefact scientifique, paramètres, compteurs et journaux conservés. États réconciliés sans
recalcul, preuves et anciennes sources dans `STRAT_Rate_native_joint_2026-10-13/recovery_20261013_1930/`.
Export réparé dans l’adaptateur expérimental par copie indépendante de la trace ; sauvegarde de l’état garantie même sur
échec d’export. Vérification de la mutation tardive et sérialisation passée entre les mesures (`NATIVE_ADAPTER_VERIFY=GO`).
Confirmation indépendante **terminée, 7/7 OK**, tentative `attempt_02` après conservation du contrôleur 21120 arrêté sur
l’échec d’export natif. Point fixe de la référence et du meilleur local, puis six groupes indépendants à profondeur identique.
Le plan natif étant exactement la référence (blocs/Rate/fente et score reproduit), aucun doublon de rejeu n’est ajouté.
202/203/204, 303/304/305, 404/405/406 et 505/506/507 conservés ; nouveaux groupes 606/607/608 et 707/708/709
fixés avant inspection du vainqueur. L’observateur délègue chaque appel physique inchangé et conserve ses plantages par graine/bruit.
Meilleur local : 0,371150 contre 0,392822 nm sur 606/607/608 (−5,52 %), 0,369640 contre 0,397299 nm sur
707/708/709 (−6,96 %). Gain observé sur les six groupes de **4,57 à 7,13 %** ; aucun plantage observé dans les appels
physiques enregistrés de chaque groupe. Un composant et des plans fixes, sans intervalle de confiance ni validation générale.
[Rapport de confirmation](../reports/STRAT_Rate_confirmation_native_2026-10-13.md), état, distributions par bruit et empreintes
dans `reports/STRAT_Rate_confirmation_native_2026-10-13/attempt_02/`.
Deuxième essai natif **terminé** à 20 h 30 min 28 s, lancé à 19 h 47 min 35 s : contrôleur **46404**, calcul **12568**, budget conjoint 480 inchangé,
budget Rate **240**, nombre de raffinements par défaut ; seule différence scientifique avec le premier essai natif.
Surcharges effectives et ressources vérifiées, contrôles structurels passés avant la mesure ; aucun test concurrent.
Sources scientifiques et scripts préparés inchangés, affinité `0xffff` et priorité normale conservées ; aucun arrêt ni autre calcul.
Résultat : **0,3828099733 nm**, 4 129 déposables, 42 min 52 s, même score, blocs, masque Rate et fente que le budget 240 seul.
Gain de 3,50 % contre la référence, **aucun gain supplémentaire des voisins conjoints**. 78 appels, 17 770 propositions ;
trace des candidats sauvegardée. Le plan gagnant n’est jamais parent d’un appel observé, son voisin conjoint local exact
n’est pas proposé. Le journal place ce vainqueur après le troisième et dernier tour à huit blocs ; cause unique non prouvée.
État : `reports/STRAT_Rate_native_joint_rate240_2026-10-13/controller.json`, sources figées et paramètres dans le même dossier.
Troisième essai natif **terminé** à 21 h 23 min 48 s, lancé à 20 h 31 min 41 s : contrôleur **19656**, calcul **37604**, mêmes budgets,
plafond de **six raffinements**, seule différence avec le précédent. Vérification de l’adaptateur passée avant la mesure ;
surcharges effectives constatées. Dossier `STRAT_Rate_native_joint_rate240_round6_2026-10-13/`.
Résultat global : **0,3600608863 nm (−9,24 %)**, 5 412 déposables, environ 52 min, meilleur identifiant **901054165**,
dix blocs. Optique L1–L6 à 632 nm, L11–L12 à 451 nm, L36–L39 à 691 nm ; les autres couches Rate.
124 appels, 38 410 voisins conjoints proposés, artefact et trace sauvegardés. Le meilleur plan global diffère du meilleur local.
À huit blocs, le quatrième tour retrouvait déjà 0,365338 nm ; à dix blocs, un voisin conjoint à préfixe 630 devient parent,
puis le plan final emploie 632. Observations consignées ; contribution causale encore à confirmer après la renotation homogène de l’ablation.
Confirmation **terminée, 9/9 OK** : contrôleur **27636**, point fixe strict des trois plans puis huit groupes indépendants, avec les nouveaux
groupes **808/809/810** et **909/910/911** fixés avant inspection du vainqueur final. Les six groupes antérieurs sont conservés.
Profondeurs et appels physiques inchangés ; seules les listes de runs/graines et le nom affiché sont étendus dans les copies v3.
Protocole, scripts, résultats par bruit, empreintes et résumé dans `reports/STRAT_Rate_confirmation_native_round6_2026-10-13/`.
Gain natif contre référence de **6,33 à 10,49 %** sur les huit groupes, aucun plantage observé dans les appels enregistrés,
profondeur inchangée. Sur les deux groupes nouveaux : 0,363221 contre 0,396132 nm (−8,31 %),
0,362084 contre 0,404538 nm (−10,49 %). Le natif améliore le meilleur local sur sept groupes, mais le dégrade de 0,68 % sur 707.
Limites : un composant, plans fixes, pas d’intervalle de confiance formel ni de validation générale ou machine.
Ablation **terminée** à 22 h 18 min 17 s, lancée à 21 h 32 min 22 s : contrôleur **49780**, calcul **1368**, même Rate 240 et six tours,
budget conjoint **480 → 0**, seule différence. Sources figées, surcharges et ressources vérifiées, contrôles structurels
passés avant la mesure ; aucun test concurrent. Dossier `STRAT_Rate_native_joint_ablation_rate240_round6_2026-10-13/`.
Résultat du batch sans voisins conjoints : **0,3654948110 nm**, 5 240 déposables, environ 45 min 46 s, zéro candidat conjoint.
Écart apparent de 1,49 % avec le natif conjoint ; **comparaison non valide à même profondeur effective**.
Contrôle strict des quatre plans terminé à 22 h 32, verdict `FAILED_REPLAY` pour l’ablation seule : son score original
**0,03339661422533983** reproduit exactement la simulation de base 101, mais les trois consensus complets donnent
**0,03517507293183044**. Référence, local et natif reproduits ; tolérance inchangée, échec conservé dans
`STRAT_Rate_validation_ablation_2026-10-13/`, preuve détaillée `diagnosis.json`. Ne pas attribuer le supplément apparent au code.
Renotation homogène **terminée** le 14 octobre à **0 h 13 min 57 s**, lancée à 22 h 37 min 09 s : contrôleur **51116**, tous les **5 240 plans sauvegardés** de l’ablation,
groupes de dix avec référence et meilleur natif comme ancres ; 525 étapes, 300 tirages puis consensus 41/42/43 à 300,
consensus incomplets exclus, tous les rejets conservés. Aucun nouveau voisin généré. Deux ancres strictes dans chaque groupe.
État : `reports/STRAT_Rate_ablation_consensus_all_2026-10-13/etat.json`, sources/propositions/protocole figés dans ce dossier.
Attention : `state.best` inclut l’ancre native ; pour le meilleur de l’ablation, prendre le minimum des `runs[].results` admissibles.
Identifiants originaux conservés séparément des identifiants de rejeu, mondes C2 indépendants de ces identifiants.
16 processeurs, `0xffff`, Normal, 15 threads ; une seule mesure, aucun test pendant cette renotation. Arrêt des nouveaux groupes à 9 h.
**525/525** étapes, **5 240/5 240** plans renotés, **5 238 consensus complets**, deux incomplets exclus, aucun échec du contrôleur.
Meilleur de l’ablation **900752354**, rejoué **9980047** : **0,3619390295 nm**, score 0,032749965266219656.
Son score exporté antérieur 0,03601493845654845 ne représentait pas cette notation complète ; résumé final `summary.json`.
Nouveaux groupes indépendants **1010/1011/1012** et **1111/1112/1113** fixés
avant choix du meilleur final, protocole `STRAT_Rate_expertise_2026-10-13/protocole_validation_ablation_full_v4.json`.
Validation comparative **terminée, 11/11 OK**, contrôleur **35012** : minimum des propositions à consensus complet
après 525/525 étapes et verrou retiré ; référence, natif conjoint et meilleur de l’ablation reproduits au point fixe strict,
puis dix groupes indépendants. Aucun rejeu concurrent. Copies v4 à appels physiques, profondeur et tolérance inchangés,
AST et revue statique ; scripts/empreintes dans `reports/STRAT_Rate_validation_ablation_full_2026-10-14/`.
Résultat : avantage du natif conjoint contre l’ablation **0,52 % sur la recherche**, mais seulement **4/10** groupes
indépendants favorables, médiane **−0,80 %**, moyenne **−0,67 %**, plage −3,97 à +2,86 %. Les deux groupes nouveaux :
+0,16 % sur 1010/1011/1012, −2,15 % sur 1111/1112/1113. **Apport propre du voisinage conjoint non confirmé.**
Le meilleur de l’ablation garde un gain contre la référence de **6,39 à 11,47 %** sur les dix groupes, aucun plantage observé.
Les réglages de recherche et la notation homogène fournissent une amélioration sur ce composant ; aucun nouveau défaut activé.
Piste du préfixe **terminée** le 14 octobre à **0 h 52 min 59 s**, lancée à **0 h 37 min 53 s**, contrôleur **52556** : longueur du **préfixe optique**
et λ de son premier bloc cherchées ensemble, autres fenêtres et partition conservées. Deux parents à notation complète
(natif conjoint et meilleur ablation), **876 propositions**, 89 étapes, 748 couples / 13 longueurs seules / 115 λ seules.
Les deux premières couches restent optiques ; fente/témoins hérités. `PREFIX_CONTRACT_VERIFY=GO` sur les 876 plans,
Ruff et aperçu passent avant mesure. Rejeu, profondeurs et sources physiques inchangés ; ancres référence/natif strictes par groupe.
État `reports/STRAT_Rate_prefix_joint_2026-10-14/etat.json`, préparateur et sources figés dans ce dossier.
**876/876** propositions, **563 consensus complets**, 292 scores de base non finis et 21 consensus incomplets exclus.
Meilleur **9960194** : préfixe **L1–L5 à 600 nm**, autres fenêtres du parent natif conservées ;
SEEL **0,3539592452 nm**, gain de **10,78 %** contre référence, **1,69 %** contre natif et **2,20 %** contre ablation sur la recherche.
Confirmation **terminée, 14/14 OK**, lancée à **1 h 05 min 07 s**, contrôleur **36380** : quatre points fixes stricts,
puis trois groupes frais et dix groupes antérieurs comme contexte réutilisé. Identifiant du préfixe rejoué **9900002**,
original conservé ; copies v5 limitées aux choix CLI, identité AST des appels physiques v4/v5 vérifiée, Ruff et aperçus passent.
État et plans/sources/empreintes dans `reports/STRAT_Rate_validation_prefix_2026-10-14/` ; une seule mesure à la fois.
Sur les **trois groupes frais**, gain du préfixe contre référence **9,35 à 10,03 %**, contre natif **1,75 à 3,04 %**,
contre meilleur ablation **1,05 à 1,80 %** ; aucun plantage observé dans les appels physiques enregistrés.
Contexte réutilisé : dix gains contre référence/natif, neuf contre ablation (régression de 0,29 % sur un groupe conservée).
Mouvements isolés depuis le natif : cinq couches à 632 nm **0,363479**, six à 600 nm **0,361198**, couple cinq/600 **0,353959 nm**.
Les deux mouvements isolés dégradent le parent ; leur combinaison l'améliore. Limite : un composant et des plans fixes.
Nouveaux groupes **1212/1213/1214**, **1313/1314/1315**, **1414/1415/1416** fixés avant notation des voisins du préfixe,
protocole v5 dans ce dossier. Groupes antérieurs ayant orienté l’exploration à traiter comme contexte comparatif réutilisé.
Le champ `prepared_utc` du protocole v5 est hérité de v4 ; sa création effective avant lancement et son empreinte sont
documentées dans `protocol_preparation_time_note.json`. Protocole figé conservé sans modification pendant la mesure.
Essai natif du préfixe **terminé à 2 h 08 min 06 s**, lancé à **1 h 09 min 34 s**, contrôleur **14820**, calcul **25072** :
ajouter un budget séparé de **720 voisins préfixe/λ** après tous les candidats historiques et les 480 conjoints ;
Rate 240, six raffinements et plafonds de screening/notation conservés. Seule différence avec le natif précédent.
Adaptateur temporaire dans `scratch/`, sources scientifiques figées ; budget préfixe nul par défaut.
Vérification de la vraie fabrique passée entre mesures : cinq chemins inactifs identiques, préfixe de candidats historiques/conjoints
conservé, contrats/identifiants/fente/témoins/parents et trace contrôlés (`PREFIX_NATIVE_ADAPTER_VERIFY=GO`).
Premier Ruff : six PT018 dans les assertions du vérificateur ; source conservée, assertions séparées, Ruff ensuite vert avant mesure.
Préparation, paramètres, sources et état dans `reports/STRAT_Rate_native_prefix_2026-10-14/` ;
groupes frais **1515/1516/1517**, **1616/1617/1618**, **1717/1718/1719** fixés avant cette recherche native, protocole v6.
16 processeurs, `0xffff`, Normal, 15 threads ; une seule mesure, aucun test pendant son exécution.
Résultat natif sauvegardé : **5 119 déposables**, 120 appels, 36 358 voisins conjoints et 47 615 voisins préfixe ;
trace et artefact conservés. Meilleur exporté **901457827**, 14 blocs, **0,3642973891 nm** ; son score est de base seulement.
Confirmation initiale **échouée avant mesure**, contrôleur **21248** : la copie préparatoire des comparateurs `plans.json`
occupait le nom que le contrôleur devait créer. Dossier d’échec conservé ; copie désormais `baseline_plans_snapshot.json`
dans une nouvelle `attempt_02`, relancée à 2 h 31 min 36 s par **14948**, sans écrasement ni recalcul natif.
Confirmation stricte **FAILED_REPLAY pour le natif seul**, quatre comparateurs reproduits :
base 101 **0,03317814691821762** égale l’export, consensus 41/42/43 **0,03336799909407186**, SEEL **0,3653381945 nm**.
Tolérance inchangée ; diagnostic et cinq plans dans `STRAT_Rate_confirmation_native_prefix_2026-10-14/attempt_02/`.
Le gain incrémental du préfixe dans la recherche native n’est pas établi ; renotation homogène du pool ci-dessous.
Copies v6 : choix CLI uniquement pour le moteur (identité AST physique vérifiée), orchestration séquentielle et comparateurs figés ;
Ruff et revue statique passent, aucun test runtime pendant la mesure native. Dossier `STRAT_Rate_confirmation_native_prefix_2026-10-14/`.
Raffinement de λ **terminé, 5/5 étapes**, **36/36 consensus complets** : **36 λ nouvelles** sur grille 1 nm
à ±20 nm de 600, sur le préfixe fixe L1–L5 déjà confirmé. Seule la première λ varie, autres fenêtres et partition conservées ;
λ déjà mesurées exclues. Contrôleur initial **46612** arrêté après l’échec du prérequis natif, sans mesure.
Reprise **24552**, lancée à 2 h 32 min 34 s dans `attempt_02`, sur le préfixe déjà indépendamment confirmé comme prérequis,
après fin du contrôle natif ; propositions/physique/profondeurs inchangées, deux ancres strictes par groupe.
Verrou résiduel du préfixe confirmé (PID 22496 absent, état complet 14/14) préservé sous un autre nom ; réconciliation documentée.
Groupes frais **1818/1819/1820**, **1919/1920/1921**, **2020/2021/2022** fixés avant toute notation fine, protocole v7.
AST et Ruff passent, contrat réel vérifié par le rejeu avant notation de chaque plan ; aucun test pendant le calcul natif.
Meilleur fin **9950016**, préfixe L1–L5 à **598 nm**, **0,3518277850 nm** (−11,31 % contre référence, −0,60 % contre 600 sur la recherche).
Confirmation **30360**, **4/4 OK**, cinq points fixes puis trois groupes frais : supplément contre 600 **−0,796 / −0,251 / +0,704 %**.
Seulement **1/3** favorable, gain fin incrémental **non confirmé** ; **600 nm reste le plan retenu**. Aucun plantage observé.
Sources/paramètres/empreintes dans `reports/STRAT_Rate_prefix_lambda_fine_2026-10-14/`, mesures dans `attempt_02` ;
confirmation/table/résumé dans `STRAT_Rate_validation_prefix_fine_2026-10-14/`. Aucun défaut activé.
Renotation de tous les **5 119 plans natifs sauvegardés terminée à 4 h 12 min 29 s**, contrôleur **42128**, lancé à **2 h 37 min 46 s**
après le contrôle fin complet : **513 étapes**, dix propositions et référence/préfixe 600 comme ancres, moteur v6 réel inchangé.
Chaque candidat reçoit 300 tirages puis trois consensus à 300 ; incomplets exclus, rejets et identifiants originaux conservés.
Dossier `STRAT_Rate_native_prefix_consensus_all_2026-10-14/`, propositions/sources/protocole figés ; groupes frais 1515/1616/1717
fixés avant la recherche native et mesurés après pool complet. `state.best` inclut l’ancre ; meilleur natif extrait hors ancres.
Limites : seuls les déposables sauvegardés sont disponibles ; le pool natif antérieur sans ajout préfixe n’a pas été intégralement renoté.
16 processeurs, `0xffff`, Normal, 15 threads ; une seule mesure, aucun test pendant cette renotation.
**513/513** étapes, **5 119/5 119** plans, **5 118 consensus complets**, un incomplet exclu ; aucun échec.
Meilleur natif **901454694**, rejoué **9940095**, **0,3630828420 nm**, encore derrière l’ancre 600 à 0,3539592452 nm.
Confirmation du pool **terminée à 4 h 13 min 19 s, 4/4 OK**, contrôleur **7984** : minimum des propositions
admissibles après 513/513, puis point fixe strict face aux cinq plans conservés et groupes frais 1515/1616/1717.
Identifiant distinct **9900005**, original conservé ; copies du contrôleur de pool éprouvé, moteur v7 inchangé, Ruff/AST
et revue statique passent, aucun test runtime pendant la renotation. Snapshots des comparateurs nommés
`baseline_plans_snapshot.json`, nom de sortie scientifique préservé. Dossier `STRAT_Rate_validation_native_prefix_pool_2026-10-14/`.
Sur les trois groupes frais, meilleur natif préfixe perd face au 600 de **5,03 / 3,37 / 1,96 %**, et face au natif conjoint
précédent confirmé de **1,74 / 0,65 / 1,52 %** ; aucun plantage observé. Pas de gain par cet ajout dans la recherche ELITE.
Limite causale conservée : pool natif conjoint antérieur non entièrement renoté, comparer seulement aux plans effectivement validés.
Essai des fenêtres internes **terminé à 5 h 03 min 57 s**, contrôleur **42024**, après fin du contrôle natif à 4 h 13 : parent retenu à préfixe 600,
une fenêtre interne à la fois, longueurs **1 à 7** (paires et impaires), décalages **−3 à +3**, λ grille 10 nm et fine ±10 nm.
**3 133 propositions**, 2 977 conjointes / 67 fenêtres seules / 89 λ seules, **315 étapes** ; préfixe, autre fenêtre, partition,
fente et témoins conservés. Référence et préfixe 600 comme ancres ; choix du parent figé avant mesure, sans remplacement silencieux.
Les 3 133 contrats ont passé la vraie fonction du worktree, identifiants/signatures et portée d’une seule fenêtre vérifiés,
**avant** toute notation : `WINDOW_TRIALS_VERIFY=GO`. AST/Ruff/revue statique passent ; aucun test pendant la notation.
Résultat complet : **315/315** étapes, **3 133/3 133** propositions, **1 194 consensus complets admissibles**, 1 939 exclus conservés.
Meilleur **9932265**, fenêtre **L35–L37 à 688 nm**, **0,3409240518 nm**, gain **14,06 %** contre référence et **3,68 %** contre le préfixe 600.
Préfixe L1–L5 à 600 nm et autre fenêtre L11–L12 à 451 nm conservés. Fenêtre seule à 691 nm : 0,3459403805 nm ;
λ688 seule sur l’ancienne fenêtre L36–L39 : 0,3624981294 nm. Le choix conjoint apporte un gain supplémentaire.
Empreintes inchangées, une seule mesure, `0xffff`/Normal/15 threads.
Groupes frais **2121/2122/2123**, **2222/2223/2224**, **2323/2324/2325** fixés avant tout score des nouveaux voisins,
protocole v8 et sources/propositions figés dans `reports/STRAT_Rate_window_widths_2026-10-14/`.
Confirmation des fenêtres **terminée à 5 h 04 min 40 s, 4/4 OK**, contrôleur **21828** : sept points fixes stricts puis groupes frais
2121/2222/2323 face aux six comparateurs conservés. Gains contre référence **13,72 / 14,22 / 14,74 %**, contre préfixe 600
**3,95 / 4,32 / 5,20 %**, aucun plantage observé. Plan retenu **9900006**, original 9932265 conservé.
Copie v8 du moteur : choix CLI seuls, AST physique identique, Ruff passe. Gain de plan fixe sur ce composant, pas de preuve
que l’ajout natif dans ELITE retrouve automatiquement ce plan ; aucune validation machine ou générale.
Dossier `STRAT_Rate_validation_window_widths_2026-10-14/`, snapshots des comparateurs sous un nom distinct.
Piste de couples de fenêtres **terminée à 5 h 12 min 16 s**, contrôleur **35728**, confirmation **38128 terminée à 5 h 13 min 05 s** : après recherche mono-fenêtre complète et son contrôle,
combiner les **12** meilleurs candidats à consensus complet de chaque fenêtre (score 101 puis ID), au plus **144 couples**,
préfixe 600 conservé. Aucun classement à partir des holdouts. Groupes frais **2424/2425/2426**, **2525/2526/2527**,
**2626/2627/2628** et règle de sélection fixés avant notation ; `STRAT_Rate_window_pairs_2026-10-14/`, protocole v9.
**144 propositions**, **16 étapes**, ancre courante 9900006 et référence strictes dans chaque groupe. Contrats réels, composition
exacte des deux sources, produit cartésien complet, préfixe/partition/fente/témoins et signatures/IDs vérifiés **avant** mesure :
`WINDOW_PAIRS_VERIFY=GO`. Premier contrôle refusé par le sandbox au changement de répertoire du worktree, deuxième avec
chemins relatifs devenu introuvable ; relance à chemins absolus passée, causes conservées, sources inchangées. Ruff vert et revue manuelle.
Rejeu v9 : seuls choix CLI étendus aux groupes frais, AST physique identique à v8. **16/16 étapes, 144/144 consensus complets**.
Meilleur 9920025, repris sous 9900007 : L11–L12 à 450 nm et L35–L37 à 689 nm, préfixe 600 conservé ; **0,3360076100 nm**
sur recherche, gain apparent **15,30 %** contre référence et **1,44 %** contre fenêtre 688. Huit points fixes et trois groupes frais,
**4/4 OK**, aucun plantage observé. **Perd contre la fenêtre 688 sur les trois groupes frais de 1,39 / 0,35 / 0,30 %** :
gain incrémental non confirmé, plan **9900006 conservé**, vainqueur de recherche archivé. Aucun défaut activé, aucun commit.
Dernier voisinage local **terminé à 5 h 27 min 56 s**, contrôleur **27312**, confirmation **48928 terminée à 5 h 28 min 38 s** : refaire le choix conjoint
préfixe/λ sur le parent confirmé à fenêtre 688, autres fenêtres et partition conservées. **607 propositions, 62 étapes**,
préfixes de 2 à 9 couches, grille large antérieure et fine ±20 nm ; 525 conjointes / 7 préfixes seuls / 75 λ seules.
Les 607 contrats réels, signatures/IDs et portée exacte passent **avant** mesure (`PREFIX_AFTER_WINDOW_VERIFY=GO`) ;
Ruff et revue statique verts. Groupes frais **2727/2728/2729**, **2828/2829/2830**, **2929/2930/2931** fixés avant tout score.
Rejeu v10 : seuls choix CLI étendus, AST physique identique à v9. Dossiers `STRAT_Rate_prefix_after_window_2026-10-14/`
et `STRAT_Rate_validation_prefix_after_window_2026-10-14/`. **62/62 étapes, 607/607 propositions, 429 consensus complets admissibles**,
178 exclus conservés. Meilleur **9910275**, repris **9900008** : préfixe **L1–L5 à 613 nm**, fenêtres internes **451 / 688 nm**
conservées ; **0,3345159946 nm**, gain **15,68 %** contre référence et **1,88 %** contre le parent sur recherche101.
Confirmation initiale **4/4 OK**, neuf points fixes et groupes frais2727/2828/2929 : gains contre référence **13,68 / 15,87 / 14,35 %**,
contre parent **0,48 / 1,08 / 1,04 %**, aucun plantage observé. Petit gain incrémental : contrôle prolongé avant reprise A2.
Confirmation supplémentaire **terminée, 7/7 OK**, contrôleur **27312** (PID réattribué par Windows, commande distincte du
contrôleur de recherche terminé) : neuf points fixes puis six groupes frais **3030/3131/3232/3333/3434/3535**, trois graines consécutives
par groupe, fixés avant leur notation. Rejeu v11 : seuls choix CLI étendus, AST physique identique à v10 ; Ruff et revue statique passent.
Sur les **neuf groupes frais au total**, le plan613 gagne contre la référence de **13,23 à 15,87 %**, aucun plantage observé.
Face au parent688/préfixe600 : **8 victoires sur 9**, une perte de **2,33 %** sur3434 ; avance moyenne faible, supériorité uniforme non établie.
Meilleur score de recherche conservé avec cette limite, parent9900006 conservé comme comparateur. Un composant et plans fixes,
pas de validation machine/générale ni de preuve que la recherche ELITE native retrouve ce plan. Aucun défaut scientifique activé.
Dossier `STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/` ; exploration terminée, A2 reprise au point sauvegardé.
Préparation de l’intégration en lecture seule dans `STRAT_Rate_expertise_2026-10-13/production_integration_review_2200.md` ;
aucune modification de production. Le gain natif contre la référence reste vérifié sur dix groupes, sa supériorité sur l’ablation n’est pas établie.
A2 **en cours, 7/24 terminées**, huitième exécution engagée ; continuation **51884** en attente pour terminer jusqu’à24/24
sur demande explicite de 👤 après l’ancienne échéance de9 h. La copie nocturne termine son calcul engagé,
puis le nouveau contrôleur reprend le checkpoint, sans arrêt scientifique ni modification de source figée.
Original partagé `campagne_a2_runner.py` inchangé pour les contrôleurs Rate actifs. AST de tous les anciens chemins identique
après retrait de la seule garde et de l’import UTC ; Ruff passe. Garde éprouvée **entre les mesures** : avant l’échéance,
à l’échéance, après, et calcul déjà engagé adopté ; AST réel de la garde, horloge/persistance simulées, points de reprise conservés.
`A2_DEADLINE_GUARD_VERIFY=GO`, aperçu des 24 cellules inchangé ; ce contrôle ne simule pas toute la campagne.
Snapshot/empreintes dans `STRAT_Rate_expertise_2026-10-13/A2_deadline_preparation/`, run courant `r75x1.75_deep_s101_sans`.
Diff suivi du worktree A2 vide, HEAD da1af082 contrôlé ; artefacts scientifiques non suivis attendus conservés.
Aucun nouveau défaut scientifique activé, aucun commit ni publication.

Bilan demandé par 👤 à 8 h 42 : [rapport synthétique](../reports/STRAT_Rate_bilan_2026-10-14.md), meilleurs plans fixes et
neuf groupes indépendants conservés. Gain local vérifié de 15,68 % sur101 ; intégration automatique native encore à valider.
Le shell configuré `pwsh.dll` devient indisponible lors de l’écriture du bilan, sans démarrer la commande ; reprise de l’outil
avec `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, code et calcul scientifique inchangés.

**Contrôle de reprise (2026-10-13, `da1af082`, Python 3.14.8).** `PREFLIGHT=GO`, Ruff sans erreur ; oracle : 1 143 passed en 83,44 s ; les trois contrôles documentaires : 0 point à instruire. Premier lancement de pytest arrêté avant les tests par un refus d'écriture du sandbox dans son dossier temporaire ; relance réussie avec `TEMP`, `TMP` et `NUMBA_CACHE_DIR` dans `.pytest_cache/certus_review/`. Code inchangé, suite complète non relancée, aucun commit créé. CI de la PR #9 : contrôle A1 ci-dessous.

**Point de départ.** `certus0310`, branche `claude/ecstatic-newton-3grmls` : `master` (`80dd7d3c`), plus
`parite-zenodo` (PR [#8](https://github.com/nikonvr/CERTUS/pull/8)) et l'audit de l'arrêt de STRAT face à un OMS
(`reports/STRAT_audit_declenchement_OMS_2026-10-10.md`) ; PR [#9](https://github.com/nikonvr/CERTUS/pull/9) en
brouillon vers `master`. Les entrées `.git/worktrees/certus0310`, `profwt`, `buildwt`, `valwt`, `ratewt` et `ratewt2`, incomplètes (Drive en
refuse la suppression), déclenchent un avertissement à chaque commit sans l'empêcher.

**Dernière validation complète** (2026-10-13, Windows 11, Python 3.14.8, Ryzen 7 5700G, `631c4830` ; depuis, ont changé des rapports, ce document, le texte de mesure d'un levier du registre,
trois passages de la vitrine et deux lignes d'un rapport HTML (le mot « quartz » en est parti), et un script de lecture d'artefact
(`scripts/resumer_artefact_sonde.py`) avec son test ; ces ajouts n'ont passé que seuls : ruff, les 11 tests du script, les tests des scripts, les contrôles
documentaires et `scripts\verifier_html.py`) : Ruff 0 ;
oracle 1 143 passed en 54 s ; unit 5 406 passed, 7 skipped en 24 min 35 ; UI 1 324 passed, 12 skipped, 2 xfailed en
22 min 24 ; autres tests 348 passed, 2 skipped en 10 min 20 ; trois contrôles documentaires : 0. Un premier passage de l'unit, à
`978b8f04`, avait rendu deux rouges (`test_the_architecture_debt_only_shrinks` : `certus_strat_consensus.py` à 1 529 lignes et
`_apply_elite_refinement_if_enabled` à 307) ; `631c4830` les ramène sous les plafonds, avec les mêmes candidats. C1 : aucun fichier de
noyau n'a changé depuis `dbf8025f`, mesuré contre `master` (196 s) : 299 tableaux sur 8 008 diffèrent (`strat.growth` 295,
`strat.states` 4), tous sur la grille machine (pas > 0 ou lissage > 1), que la branche corrige (D93 à D95) ; les 171 cas de
croissance sans grille machine sont identiques au bit. Contre `212126d4`, où ces 299 écarts avaient été mesurés : les 8 008
tableaux sont identiques au bit.

**Un seul indice de saphir** (2026-10-12, `reports/SAPHIR_indice_unique_2026-10-12.md`). La référence est le Sellmeier d'id 3
(rayon ordinaire, Malitson et Dodge) ; les mesures absolues de la séance 24-03 en donnent le niveau à +0,0003 ± 0,0028, donc on ne
la corrige pas. « Sapphire Fresnel » (un second Sellmeier, n plus bas de 0,0077 ; dans METAL, un substrat N-BK7 sans un mot) est un
alias de l'id 3 (`b9223b43`) ; les tables mortes `sapphire fresnel.xlsx` et `sapphire_index.txt` sont supprimées (`925b3788`) ;
`tests/unit/test_one_sapphire_index.py` garde l'unicité. Reste : C1 et C3 diffèrent entre le JSON et le code (n : 4,6·10⁻⁷ au plus),
non alignés pour ne pas changer le hash verrouillé du JSON. Validé en entier avec le reste à `631c4830` (validation ci-dessus).

**D103, trouvé le 2026-10-11, corrigé par `de9a2025`** (`reports/STRAT_D103_identifiants_en_double_2026-10-11.md`). En
`deep` et `extreme`, la DP rend jusqu'à 2 × `top_k` groupements par carte de coût, numérotés dans des plages de cent :
les rangs 100 à 199 d'une carte prenaient les numéros de la suivante, et le consensus, qui range ses scores par
identifiant, donnait aux deux homonymes le score d'un seul. Présent depuis le premier commit ; `fast` et `premium` (au
plus 40 et 80 groupements par carte) n'en sont pas touchés. Les cent premiers groupements de chaque carte gardent leur
numéro, les suivants ont leur propre plage. Mesuré le 2026-10-12 sur `r75x2` : les graines 42, 404 et 505, que le
garde-fou d'unicité retenait, vont au bout ; les graines 101 et 202 sont identiques champ par champ, et les graines 77
et 303 portent les mêmes plans, scores, plantages et marges (18 et 41 plans renumérotés). Les résultats `deep`
antérieurs à la correction (campagnes d'août, repères de la section 2 hors `r75x2` sans rampes) ont pu choisir leurs
parents ELITE sur des scores mélangés.

**D100 corrigé le 2026-10-11** (`2cba90f4`) : les interrupteurs de STRAT reçoivent de nouveau le fichier chargé. Du
2026-09-08 au 2026-10-11, tout résultat STRAT a tourné sans Rate, sans biais de fente et sans recherche de fente, sauf
surcharge explicite (`reports/STRAT_D100_interrupteurs_non_charges_2026-10-11.md`).

**L'optique reprend après le Rate** (2026-10-12 ; `reports/STRAT_ELITE_couches_Rate_paquets_2026-10-12.md`). 👤 observe en salle de bonnes
stratégies qui alternent des paquets d'optique à une λ et des paquets de Rate (« purement empirique »). Le noyau le permettait ; la recherche ne le
proposait pas. ELITE déplace maintenant les couches Rate de ses parents (`elite_rate_moves`, actif par défaut depuis `978b8f04` ; `allow_rate`
faux l'éteint) : `r75x0.5` (graines 42 / 101 / 202) 0,5031 / 0,4981 / 0,5000 → **0,4347 / 0,3967 / 0,3967 nm** (le meilleur plan des graines 101 et 202 : trois
paquets de Rate et deux fenêtres d'optique de deux couches, la première à 451 nm), juge de paix 0,1849 → **0,1721 nm**, `r75x2` (graines 101 / 42) 0,5406 / 0,5678
→ 0,5358 / 0,5477 nm ; le meilleur SEEL baisse dans les six exécutions, toutes les listes sont déposables, au modèle de Rate de STRAT (sans dérive de la source).

**Modèle d'arrêt de production et Rate dans tous les scénarios** (2026-10-12 ;
`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, `reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`). D96, D97 et D98 sont le
modèle d'arrêt par défaut (`8d9ced13`, décision de 👤, §3) : l'attente sans fin retire 95 % des plans que l'ancien modèle jugeait
fabricables (6 sur 120 au rejeu) et la recherche du juge de paix n'en garde que 2 sur 1 112. Le Rate entre dans chaque design : le
secours Rate (`0fc7c5f2`, `40642146`) pose au temps la queue des plans dont le contrôle optique cède, et les enfants d'ELITE gardent
les couches Rate de leur parent (`4a4e1f0d`). Avec eux, `r75x0.5` et un seul verre témoin, que la recherche ne savait pas fabriquer
(0 déposable sur 8 687 plans), rend 3 383, 3 701 et 3 279 plans déposables aux graines 42, 101 et 202 (meilleur SEEL 0,5031 / 0,4981 /
0,5000 nm) ; le juge de paix, 0,1849 nm. Ces SEEL sont ceux du modèle de Rate de STRAT (§7), dont la stabilité de la vitesse n'est pas
mesurée. D106 (les enfants d'ELITE étaient notés sans biais de fente) est corrigé par `6fcdd56a`, et son effet est mesuré par un A/B :
à `r75x2` sans rampes (graine 101, ancien modèle d'arrêt, sans secours Rate, même code), **706 déposables sur 6 042** stratégies sans la
correction, **0 sur 4 821** avec elle ; la graine 42 : 0 sur 4 561. Les déposables optiques de `r75x2` d'avant la correction (« six
graines sur sept » ci-dessous) étaient des enfants d'ELITE sans biais de fente : **sans rampes, `r75x2` n'est pas fabricable en optique
pure**. Avec les défauts de production, tous les plans de la liste le sont (4 175 et 4 307 plans aux graines 101 et 42, meilleur SEEL
0,5406 et 0,5678 nm), avec du Rate (`reports/STRAT_r75x2_D106_secours_Rate_2026-10-12.md`). Au juge de paix (ancien modèle d'arrêt, sans
secours, graine 42), D106 fait passer le meilleur SEEL de 0,1776 à 0,1927 nm (+8,5 %) : les repères du juge de paix d'avant la correction
sont optimistes d'autant.

**Mesure d'avant D106 (2026-10-12), D100 et D103 corrigés**
(`reports/STRAT_r75x2_sept_graines_D100_D103_corriges_2026-10-12.md`, code `411e6eb5`). `r75x2` en `deep`, sans
rampes, protocole d'août, sept graines : **six trouvent des déposables** (42, 77, 101, 202, 404, 505 ; août : trois),
la 303 n'en trouve aucun ; meilleurs SEEL de 0,5323 à 0,6354 nm, médiane 0,5563 nm. Tous les déposables sont des plans
ELITE. L'ELITE « tour à tour » sur les six graines (`reports/STRAT_ELITE_tour_a_tour_six_graines_2026-10-12.md`) :
meilleur SEEL médian +0,7 % (mieux une fois, de 14,7 %), pas de gain net démontré. Les déposables de `r75x2` de cette mesure sont des
enfants d'ELITE sans biais de fente : D106 les invalide (ci-dessus). Mesures du
2026-10-11 (`reports/STRAT_remesure_D100_2026-10-11.md`, `782972bf`) : juge de paix **0,178 nm** (`premium`, ancien modèle d'arrêt, même
`RESULT` au bit après D103) ; le passe-bande de 99 couches en une campagne reste non fabricable (0 déposable sur
2 139, plantage minimal 82,7 %) ; `r75x0.5` avec un seul verre témoin : aucun déposable aux graines 42, 101 et 202
avant le secours Rate, plantage minimal 8,3 % à la graine 101 (§7).

**Prochaines actions — à lancer avec une autre IA.** Lire dans l'ordre : [`CLAUDE.md`](../CLAUDE.md) (les règles et les onze interdits),
ce §0, puis l'action choisie. Chaque action est **autonome** : pourquoi, quoi lancer (commandes exactes), quand elle est finie, ce qu'il ne
faut pas faire. Faire A1 d'abord ; les autres sont indépendantes les unes des autres, par priorité décroissante. Une action peut donner
plusieurs commits, chacun d'une seule chose (C3). **Jamais de `git push`, jamais de fusion de la PR #9 : l'un et l'autre sont à 👤.** La
branche a été poussée à `bee0d3c5` le 2026-10-13, sur l'ordre de 👤 ; les commits locaux qui suivent restent à pousser sur son ordre.

**Vocabulaire.**
*Rate* : couche posée pour un temps, à la vitesse estimée sur les couches du même matériau contrôlées optiquement (ce n'est pas un quartz).
*Paquet de Rate* : couches consécutives au Rate. *Fenêtre d'optique* : couches contrôlées optiquement entre deux paquets. *Queue* : le Rate va
d'une coupure à la dernière couche. *Plan mixte* : de l'optique après du Rate. *Plan optique pur* : aucune couche au Rate. *Déposable* :
plantage inférieur à 5 % au pire des trois niveaux de bruit (0,5×, 1×, 2×). *SEEL* = 2·√score, en nm, toujours rapporté avec la graine et le
mode. Les indices de couche des artefacts commencent à 0 ; l'interface et les rapports numérotent à partir de 1 (« L18-L75 » = indices 17 à 74).

**En vigueur au 2026-10-13** (ne pas le remettre en cause sans mesure) : D96, D97 et D98 (attente sans fin) ; le secours Rate (`rate_rescue`) ;
`rate_by_swing` ; ELITE déplace les couches Rate de ses parents (`elite_rate_moves`) ; les enfants d'ELITE portent le biais de fente (D106) et
gardent les couches Rate de leur parent. Dernière validation complète : `631c4830` (ci-dessus). Les preuves sont dans `reports/STRAT_*_2026-10-12*`.

**Avant toute action.**
1. `python scripts\preflight.py` doit finir par `PREFLIGHT=GO` (l'arbre où l'on édite est celui qu'`import certus` résout).
2. `git status -sb` propre ; noter `git log -1` : c'est le point de départ de l'action.
3. Lancer la validation de CLAUDE.md §2 **en entier** avant de committer du code : un sous-ensemble de tests a déjà laissé passer une régression
   (le garde-fou `tests/unit/test_the_architecture_debt_only_shrinks.py` ne tourne pas avec les tests voisins).

**Mesurer, une fois pour toutes** (toutes les actions de mesure suivent ce protocole ; il a produit tous les rapports du 2026-10-12).
```bat
rem depuis la racine du dépôt ; l'arbre jetable pèse plusieurs Go : le supprimer en fin de mesure
git worktree add --detach "%TEMP%\mesure_wt" HEAD
cd /d "%TEMP%\mesure_wt"
set CERTUS_BENCH_TIMEOUT_S=21600
python scripts\probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 101 0
python scripts\resumer_artefact_sonde.py reports\blocs_vs_plantage_r75x0.5_deep_s101.json
```
- Les 8 arguments : composant (`48c` juge de paix, `35c`, `75c`, `99c`, `r75x0.5`, `r75x1.5`, `r75x1.75`, `r75x2`, `r75x2-2nm`), mode (`fast`,
  `premium`, `deep`), recherche de fente (1 pour le juge de paix, 0 ailleurs), `require_turning_point` (0), résolution du monochromateur en nm (2),
  élargissement (0), graine, réglages de production (0 = rien n'est forcé). Les rapports du 2026-10-12 utilisent `48c premium 1 0 2 0 <graine> 0`,
  `r75x0.5 deep 0 0 2 0 <graine> 0` et `r75x2 deep 0 0 2 0 <graine> 0`.
- Pour changer un réglage sans toucher au code : `set CERTUS_PROBE_OVERRIDES=cle=valeur,cle2=valeur2` **et** `set CERTUS_PROBE_TAG=etiquette`
  (l'étiquette est obligatoire avec une surcharge ; elle entre dans le nom de l'artefact). Les valeurs `true` et `false`, les entiers et les flottants
  sont reconnus. Vider les deux variables après l'essai.
- L'artefact est écrit dans `reports\` **de l'arbre jetable** : `blocs_vs_plantage_<composant>_<mode>_s<graine sur trois chiffres>[_<etiquette>][_fente].json`.
  Si le nom existe déjà, un horodatage s'ajoute : prendre le plus récent par date de modification. Il porte le commit, `git_dirty` (doit être faux, sauf
  A/B voulu), les surcharges et les réglages Rate effectifs (`config`).
- **Une seule mesure à la fois sur la machine** (sinon `RESULT=None` ou dépassement du délai) ; pas de test lancé pendant une mesure. Ordres de grandeur,
  machine seule (Ryzen 7 5700G, 16 threads) : juge de paix `premium` 9 min ; `r75x0.5 deep` 44 min ; `r75x2 deep` 44 à 52 min.
- **Lire un écart avec prudence** : à 150 tirages la dispersion d'un meilleur SEEL est de l'ordre de 6 % (§2) ; deux exécutions à moins de 8 % ne se
  distinguent pas. Le SEEL d'un gagnant est le minimum de plusieurs milliers de plans. Un résultat meilleur que prévu se vérifie avant de le croire
  (rejeu de la graine de base, `rmse_par_bruit` dans l'artefact).
- **Vérifier qu'un réglage arrive au calcul** avant de lui attribuer un effet : sa valeur dans `config` de l'artefact et sa ligne de journal
  (`[ELITE-RATE]`, `[RATE-RESCUE]`, `[RATE]`).
- Fin : copier les artefacts utiles dans un dossier de `reports\` (pour une exécution sans déposable, retirer `margin_by_layer`, `lambdas` et
  `rmse_par_bruit` de chaque stratégie : voir `reports/STRAT_r75x2_D106_secours_Rate_2026-10-12/`), écrire un rapport en français dans `reports\` (protocole,
  tableau, ce qui n'est pas mesuré), mettre à jour ce document, `git worktree remove --force "%TEMP%\mesure_wt"`. Aucun chemin personnel dans un
  fichier versionné. Les entrées `.git/worktrees/*` que Drive refuse de supprimer sont normales.

**A1 — Vérifier la CI de la PR #9** (30 min, d'abord). *Pourquoi* : 105 commits ont été poussés le 2026-10-13 ; la CI calcule sous Linux et teste
l'interface et le gel sous Windows. *Faire* : `gh pr checks 9` ; pour un job rouge, `gh run view <identifiant> --log-failed`, corriger la cause (un
commit par cause), rejouer la validation locale. *Fini quand* : `lint`, `security`, `tests` et `release-windows` sont verts sur le dernier commit
poussé, ou chaque rouge est expliqué dans ce §0 avec sa cause. *Ne pas* : pousser, fusionner la PR, supprimer ou assouplir un test, agrandir
`extend-ignore`.

*Contrôlé le 2026-10-13 par l'API publique GitHub, tête de PR `bee0d3c5`.* `ruff (py3.14.5)`, `pytest (ubuntu, py3.14)`, `interface (windows, py3.14)`,
`pip-audit + gitleaks`, `validate-and-build (3.14.5)` et l'exécution CodeQL sont verts. Le [contrôle des alertes CodeQL](https://github.com/nikonvr/CERTUS/runs/115106912883)
est rouge : une alerte de sévérité haute « Use of a broken or weak cryptographic hashing algorithm on sensitive data » dans
`scripts/probe_blocs_vs_plantage.py`, construction de `suffixe`. Le SHA1 tronqué y nomme un artefact à partir de `CERTUS_RATE_SETS`,
une liste de numéros de couches interprétés comme des entiers ; l'analyse la qualifie de « certificate ». À la lecture du flux, faux positif probable :
ce hash n'authentifie ni certificat ni donnée sensible. Correction locale : SHA256 remplace SHA1 dans ce suffixe (validation et statut au début de ce §0).
L'alerte distante reste ouverte : aucun push, aucune action sur GitHub, pas de réexécution CodeQL sur la correction locale.

**A2 — Confirmer `elite_rate_moves` sur les composants et les graines non mesurés** (≈ 8 à 15 h de machine, par cellules indépendantes).
*Pourquoi* : l'option est active par défaut depuis `978b8f04` sur six exécutions (`r75x0.5` aux graines 42, 101, 202, le juge de paix à la graine 42,
`r75x2` aux graines 101 et 42) : le meilleur SEEL baisse dans les six (de 0,9 à 20,7 %). *Faire* : pour chaque cellule du tableau, deux exécutions au même
commit, la première aux défauts, la seconde avec `set CERTUS_PROBE_OVERRIDES=elite_rate_moves=false` et `set CERTUS_PROBE_TAG=sans_mouvements`.

| composant (arguments 1 à 3) | graines | durée d'une exécution |
|---|---|---|
| `r75x1.5 deep 0`, `r75x1.75 deep 0` | 42 et 101 | non mesurée (compter 45 min) |
| `35c deep 0`, `75c deep 0` | 42 | non mesurée (la mesurer à la première) |
| `48c premium 1` (juge de paix) | 77, 101, 202 | 9 min |
| `r75x0.5 deep 0`, `r75x2 deep 0` | 77 ; 202 et 77 | 44 min ; 45 à 52 min |

(Les arguments 4 à 8 sont toujours `0 2 0 <graine> 0`.) *Fini quand* : un rapport « STRAT_ELITE_couches_Rate_autres_composants » (date du jour) donne, par
cellule, le meilleur SEEL sans et avec, l'écart, les nombres de plans déposables, la classe et la forme du meilleur plan (`resumer_artefact_sonde.py`), et
conclut en une phrase : « le défaut reste » (le meilleur SEEL baisse ou reste dans la dispersion partout, aucune liste ne perd ses déposables) ou « à
signaler à 👤 » (une dégradation de plus de 8 % ou une liste qui perd ses déposables). *Ne pas* : changer le défaut ; `elite_rate_moves=false` n'est
qu'une surcharge de mesure.

**A3 — Refaire les repères d'avant D106 et d'avant D96-D98** (§2 ; ≈ 6 h). *Pourquoi* : ces nombres datent d'avant D106 (qui coûte 8 % au juge de paix et retire tous les déposables optiques de `r75x2`)
et d'avant le secours Rate : leur population n'est plus celle de la production. *Faire* : le juge de paix au banc officiel, aux défauts : `python scripts\bench_examples.py strat
--auto-yes --out reports\STRAT_bench_juge_de_paix_<commit>_defauts_<date>.txt` (33 min ; `RESULT` et `STRAT_RANK00..09` sont les chiffres à reporter) ;
puis, avec la variable `CERTUS_DESIGN_JSON` pointant le fichier de `example/example_strat/` (`set CERTUS_DESIGN_JSON=example\example_strat\JSON-strat-bandpass-3cav-deep.json`,
à changer à chaque composant) la même commande pour le passe-bande de 35 couches (`JSON-strat-bandpass-3cav-deep.json`), l'aléatoire de 75 couches (`JSON-strat-random75.json`),
`r75x2` à fente native (`JSON-strat-random75-x2-fabricable.json`) et la configuration livrée avec rampes (`JSON-strat-random75-x2-fabricable-2nm.json`) ;
le passe-bande de 99 couches à verres témoins multiples se refait par intervalles (`python scripts\campagne_intervalles.py --etat` puis ses vagues : lire sa
docstring, c'est long). *Fini quand* : chaque ligne concernée de la table du §2 porte le nombre refait, sa condition (commit, mode, graine) et son
rapport ; les anciens nombres sont retirés (un fait, un seul endroit). *Ne pas* : modifier `example/example_strat/JSON-strat-example.json` (interdit 4).

**A4 — Le Rate évince-t-il l'optique pure ?** (conception 2 h, mesure 2 h). *Pourquoi* : au juge de paix, les plans optiques purs déposables sont passés de
487 à 50 (ancien modèle d'arrêt), le meilleur plan optique pur de 0,178 à 0,193 nm ; l'hypothèse, non mesurée, est qu'ELITE, dont les parents sont
maintenant en majorité des plans Rate, raffine moins la lignée optique pure (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, mesure 4). *Faire* : un
levier `elite_optical_parents` (entier, `0` = le chemin d'avant, **bit pour bit** : le prouver comme `tests/unit/test_strat_elite_rate_moves.py` le fait
pour `rate_moves=False`) qui garantit, parmi les parents d'ELITE, au moins M plans sans aucune couche Rate quand la liste en contient ; le mesurer au
juge de paix (graine 42) avec M = 0, 2, 4, puis à `r75x0.5` (graine 101). *Fini quand* : pour chaque M, le meilleur SEEL optique pur, le meilleur SEEL
global et le nombre de plans optiques purs déposables, dans un rapport. **Le contrat de taille** : `certus/core/certus_strat_consensus.py` est à 1 498
lignes (plafond 1 500) et `_apply_elite_refinement_if_enabled` à 299 (plafond 300) : ne rien y ajouter qui ne soit pas compensé, mettre la logique dans
`certus/core/certus_strat_robustness_rate.py` comme `_elite_rate_candidates`. *Ne pas* : l'armer par défaut (c'est à 👤).

**A5 — ELITE : plus de tours, autre budget pour les mouvements sur les couches Rate** (≈ 4 h). *Pourquoi* : ELITE fait 3 tours en `deep` et s'arrête
quand rien ne progresse ; la recherche des paquets est une escalade qui n'a peut-être pas fini. *Faire* (`r75x0.5`, graine 101, référence : 0,3967 nm) :
`elite_rounds=6,elite_stop_on_no_gain=false`, puis `elite_rounds=10,elite_stop_on_no_gain=false` ; puis, à 3 tours, `elite_rate_max_candidates=40` et
`elite_rate_max_candidates=360`. Une surcharge à la fois, avec son étiquette. *Fini quand* : un tableau tours et budget → meilleur SEEL, durée, nombre de
paquets de Rate du meilleur plan. Si les largeurs de fenêtre (`ELITE_RATE_WINDOWS`) ou le pas (`ELITE_RATE_STEP`) méritent un balayage, en faire des
paramètres **inactifs par défaut** (chemin d'avant identique) avant de les mesurer. *Ne pas* : changer un défaut sans 👤.

**A6 — Le modèle de Rate sans dérive de la source** (le sujet scientifique central ; **ne pas commencer sans la valeur de 👤**). *Pourquoi* : tous les SEEL
des plans Rate supposent une vitesse constante pendant le dépôt (`certus/physics/certus_strat_growth.py`, « RATE MODE ») ; 👤 observe en salle ±1 à 2 %
(§6, A25) et de bons plans en paquets alternés. Le modèle ne peut ni confirmer ni infirmer ce qui vient de la salle. *Faire* : (1) **demander à 👤** la
dérive ou l'instabilité de la vitesse pendant un dépôt (relative, par couche ou par run, et comment elle a été observée) ; ne pas l'inventer ; (2) ajouter un
paramètre **inactif par défaut** qui perturbe l'épaisseur des couches Rate (tirage fonction pure de la graine, du tirage et de l'indice physique,
`_seeded_noise_sample` de `certus/physics/certus_strat_math.py`, jamais de la stratégie : C2), sur le modèle de `stop_model_flags`
(`certus/physics/certus_strat_readings.py`) et de `tests/unit/test_strat_stop_model_is_the_decided_one.py` ; `python scripts\c1_diff.py HEAD` doit rendre « C1 TENU »
avant de committer ; (3) refaire `r75x0.5` (graine 101), le juge de paix et `r75x2` (graine 101) avec la dérive de 👤 divisée par 3, telle quelle et multipliée par 3,
et comparer la forme du meilleur plan (queue, paquets alternés, optique pur). *Fini quand* : le tableau, le rapport, le §6 mis à jour. *Ne pas* : activer par
défaut ; conclure sur une seule graine.

**A7 — Proposer les corrections de la vitrine `pages/CERTUS_STRAT.html`, sans l'éditer** (2 h). *Pourquoi* : la vitrine suit un régime strict (CLAUDE.md §10) : 👤
la relit avant qu'on la touche. Ses §10.18 et §10.19 citent les chiffres d'août ; ses déposables de `r75x2` sans rampes sont invalidés par D106 ; elle dit que le Rate
est « offert mais jamais choisi » à ×1,5, ×1,75 et ×2 (« zero out of 1510 »), ce qui n'est plus vrai à `r75x2` aux défauts de production (tous les plans
déposables portent du Rate ; ×1,5 et ×1,75 ne sont pas mesurés aux défauts). *Faire* : écrire un fichier
« STRAT_vitrine_passages_a_relire » (date du jour) dans `reports\` : pour chaque passage, la ligne, le texte actuel, ce qui est faux, le texte proposé (en anglais,
chaque nombre sourcé dans un rapport, la limite montrée : le modèle de Rate n'a pas de dérive). *Fini quand* : le fichier est écrit ; **la page n'est pas modifiée**.
Après accord explicite de 👤, une action séparée l'édite puis lance `python scripts\verifier_html.py pages\CERTUS_STRAT.html` (0 point à instruire).

**A8 — Dette technique** (§4 et §6) : un défaut par tâche, un commit par changement, jamais `ruff check --fix`, jamais agrandir `extend-ignore`.
- *D25, lint* : mesure officielle `python -m ruff check . --isolated --select "E,F,I,B,UP,RUF,PT,PERF" --ignore E501 --line-length 120 --target-version py314 --statistics`
  (1 416 violations le 2026-10-12 : F401 659, E402 555, RUF001 77, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2). Une règle ne quitte `extend-ignore`
  qu'à zéro violation, dans le commit qui met à jour la liste de `tests/oracle/test_lint_debt_ratchet.py`. Commencer par E402, module par module, avec les trois
  photos avant/après du §6 (`scripts/lint_ns_snapshot.py`). RUF001 touche des chaînes dont des libellés vus de l'utilisateur : ne pas les réécrire sans 👤.
- *D26, imports montants* : 20 arêtes (§4) ; commencer par celles qui ne demandent qu'un symbole à descendre dans `certus/domain/` ou `certus/core/` ; après chaque
  dette payée, `python scripts\metrics.py --dette tests\architecture_debt.json` réécrit le registre depuis les sources (il ne fait que rétrécir) ; **ne jamais le lancer
  pour faire passer `tests/unit/test_the_architecture_debt_only_shrinks.py`** : il y inscrirait la régression au lieu de la signaler.
- *D23 puis D11, D50, D72* : reproduire D23 avant tout (`scripts/sonde_retenants_fenetre.py`) ; ne pas toucher `WA_DeleteOnClose` avant (§4). D72 (taille du gel) après la
  fiabilité du gel.
- *D82* (logo du thème sombre) demande des yeux ; *D84* (écart au dernier bit au premier passage après un changement de clé du cache Numba) : relancer une fois avant de
  conclure à une régression ; *D68* (silicium lu à l'import) est optionnel.

**Décisions qui n'appartiennent qu'à 👤 — une IA ne les tranche pas, elle rapporte les mesures.**
1. D98 : l'attente sans fin (défaut) ou l'arrêt tardif (`oms_arming=1`) — chiffres au §3 et dans `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.
2. `elite_rate_moves` : garder actif (défaut actuel) ou le désarmer (`False`, ou `git revert 978b8f04`) — A2 apporte les mesures.
3. `rate_rescue_hard` : inactif, mesuré sans gain (35 plans déposables sur 410) — le garder ou le retirer.
4. Le Rate et l'optique pure (§5, A4) ; la valeur de la dérive du Rate (A6) ; D71 (2) ; l'information D69 (changement de définition d'un indicateur).
5. Toute poussée (`git push`), toute fusion de la PR #9, toute modification de la vitrine.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Sans rampes, aucun plan optique pur n'est déposable une fois D106 corrigé (graines 101 et 42, 2026-10-12) ; avec les défauts de production (secours Rate), tous les plans de la liste le sont, au modèle de Rate de STRAT (§2). La voie à rampes de la configuration livrée (mesurée avant D106) est à refaire | A2 à A6 (§0) |
| **RE** | indices tabulés lus en n − ik depuis R148 (2026-10-05) : tout RE antérieur fait sur des indices absorbants en incidence oblique est à refaire ; un indice demandé hors de sa table est prolongé par une constante, avec un avertissement (ex-D86, `dec73219`, 2026-10-05) | — |
| **Base de dépôts** | 140 monocouches mesurées au Photon RT (`example/database_depots/`, importées le 2026-10-11 par `scripts\importer_base_depots.py`) ; la voie (T ou R) se lit dans la géométrie du détecteur, le mode manuel déclarant « Transmittance » quoi qu'il mesure. INDEX les charge par « Deposit database… ». Onze ajustements certifiés de l'application autonome, dont le spectre est un dépôt de la base, servent de références (`references_index.json`) ; `scripts\bench_base_depots.py` y confronte INDEX. Banc du 2026-10-12 (11 références × 3 exécutions, `reports/BASE_DEPOTS_banc_INDEX_2026-10-12.md`) : neuf références sur onze à moins de 2,0 % d'épaisseur de la référence, deux non retrouvées (`mesures-c1b-sio2`, −49 %, et `sb2s3-silice`, −3,85 %), cause non cherchée. RE ne la lit pas : il lui faut un classeur complet | instruire les deux échecs ; choix de 👤 (§5) |
| **Exécutable gelé** | sur la couche OpenMP depuis `31745571` (D87), sans les outils de développement depuis `5ccaa210` (411 Mo) ; construit à `dbec2fc1` le 2026-10-06, hub et modules contrôlés au démarrage, et 👤 y a calculé : « l'exécutable fonctionne ». Les licences de ce qu'il embarque le suivent (`licenses/`) | A8 (D72, §0) |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | A8 (§0) et choix de 👤 (§5) |
| **Qualité** | CI : calcul sous Linux, interface sous Windows, gel construit et démarré sous Windows, audit de sécurité (`pip-audit`, `gitleaks`) ; tests isolés des préférences de 👤 ; l'audit du code mort couvre tout `certus/`. Indicateurs du plan le 2026-10-06 (`scripts\metrics.py`) : tous dans leur cible, sauf la couverture et la taille du gel, non remesurées ce jour | rangs 5 et 6 |
| **Documentation** | règles dans `CLAUDE.md`, état ici ; 15 rapports HTML, 34 schémas Mermaid et 2 SVG validés le 2026-10-03 ; anciens dossiers lisibles dans Git | tenir « un fait, un seul endroit » |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même, et c'est assumé (décision de 👤 du 2026-10-06 : les deux dépôts réels du dichroïque ne sont plus prévus) | — |

## 2. Repères mesurés — fente 2 nm, modèle courant

| composant | SEEL | plantage | condition |
|---|---|---|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,173 nm** | 0 % | 6 blocs, une campagne |
| le même, D100 corrigé (`782972bf`) | **0,178 nm** | 0 % | 5 blocs (λ 544, 471, 466, 467, 462 nm), 823 stratégies dont 154 éliminées, `RESULT` 0,007917103726810235 ; `scripts\bench_examples.py strat` (`premium`), caches de l'arbre, 2026-10-11 (`reports/STRAT_bench_juge_de_paix_782972bf_D100_2026-10-11.txt`). Sous D100 (`b60d80e2`) : 0,175 nm |
| le même, défauts du 2026-10-13 (D96 à D98, secours Rate, ELITE déplace les couches Rate) | **0,1721 nm** | 0 % | 2 blocs, 2 652 stratégies, toutes déposables, toutes avec du Rate ; `scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`, `cea0db66`, 2026-10-12. Sans les mouvements sur les couches Rate : **0,1849 nm** (1 bloc, 2 260 stratégies dont aucune éliminée, `RESULT` 0,00854267382381426 ; `scripts\bench_examples.py strat` (`premium`), caches de l'arbre, `03990e9a` ; `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`). Les cinq combinaisons du modèle d'arrêt au code final, sans ces mouvements : de 0,1759 à 0,1854 nm (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`). Sans le secours (`8d9ced13`) : 0,2000 nm, 2 plans déposables sur 1 112 |
| passe-bande 3 cavités, 35 couches | **0,482 nm** | 0 % | 6 blocs, mode `deep` |
| aléatoire `JSON-strat-random75`, 75 couches | **0,272 nm** | 0 % | une campagne, 241 déposables sur 662 |
| passe-bande 5 cavités, 99 couches | **0,81 nm** | 0 % par campagne | 4 verres témoins, partition 0-22 / 22-42 / 42-76 / 76-99 |
| le même en une seule campagne | aucun score valide | 100 % | 487 stratégies, toutes plantent : non fabricable |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,6248 nm** | 0 % | `deep`, pur optique, 277 déposables ; mesuré avant D106 : à refaire |
| `r75x2` à 2 nm, configuration livrée | **0,5676 nm** | 1,67 % | avec `example/example_strat/rampes_r75x2-2nm.json` ; étendue 0,55 % sur 3 graines ; mesuré avant D106 : à refaire |
| `r75x2` à 2 nm, sans rampes, défauts de production du 2026-10-12 | **0,5406 nm** (graine 101), 0,5678 nm (graine 42) | 0 % | `deep`, `dbf8025f` : tous les plans de la liste déposables (4 175 et 4 307), aucun optique pur, du Rate (61 et 23 couches) ; l'optique pur sans secours Rate : 0 déposable aux deux graines (D106 corrigé). Avec ELITE qui déplace les couches Rate (`cea0db66`, graine 101) : 0,5358 nm ; graine 42 (`5da02db9`) : 0,5477 nm. `reports/STRAT_r75x2_D106_secours_Rate_2026-10-12.md` |

Le passe-bande de 99 couches est chiffré en moyenne de trois graines, jamais par la meilleure.

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** : ils sont notés sur des
  domaines de largeur différente (section 7). Toute comparaison **à composant fixé** est valide.
- 🔴 **Un score seul ne départage rien.** À N = 150 tirages, la dispersion Monte-Carlo vaut
  σ ≈ 6 % ; deux runs à moins de ~8 % sont indiscernables. On compare des **classes
  d'équivalence SEEL**. Sur `r75x2`, σ ≈ 1,8 % mesuré en changeant le triplet de graines de
  consensus : un bruit emprunté à un autre composant ne vaut rien.
- Ces repères comprennent le **biais de fente** ; une mesure sans ce biais ne leur est pas comparable.
- 🔴 Les repères où des enfants d'ELITE comptent, mesurés avant la correction de D106 (2026-10-12), les notent sans biais de fente : `r75x2` sans rampes perd tous ses déposables optiques à la correction (§0). Les repères du juge de paix en sont aussi touchés.
- 🔴 Les repères mesurés en `deep` avant la correction de D103 (passe-bande de 35 couches, `r75x2` à fente native de
  1 nm, `r75x2` avec rampes) ont pu choisir leurs parents ELITE sur des scores de consensus mélangés entre homonymes
  (§0).
- Le banc `scripts\bench_examples.py strat` lit sa configuration dans `CERTUS_DESIGN_JSON` ; par défaut le juge de
  paix standard (`JSON-strat-example.json`). Les mesures `fast` de D5, D73, D20, D70 et D17 prenaient
  `JSON-strat-example-fast.json` (194 stratégies), celles de D14 et D15 le standard (370) : les deux ne se comparent pas.
- Les repères du tableau, sauf les deux lignes du juge de paix au modèle de `782972bf` et de `03990e9a`, sont antérieurs à R130 et
  à D96 à D98 par défaut (2026-10-12) : à refaire. Depuis R130, la gagnante est prise dans la classe du meilleur SEEL
  (à un pas de 0,01 nm près) par rendement puis marge ; son SEEL dépasse le meilleur d'au plus un pas.
- La longueur seule ne met pas le monitoring optique en échec, la **structure** si :
  75 couches aléatoires passent, 99 couches à cavités et miroirs non. Sur un empilement
  structuré, la longueur pèse ensuite : sur 270 sous-intervalles du passe-bande de 99 couches,
  la part de déposables s'effondre avec elle (r = −0,869).
- Un taux de 100 % obtenu en `fast` ne conclut rien (la recherche peut n'avoir rien proposé) ;
  un 100 % qui tient jusqu'à `deep` est un constat sur le composant et sa fente.
- Au banc : `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée attendue)`. Au-delà du plafond le
  banc rend `RESULT=None` avec une poignée de stratégies : cherche `WAIT_TIMEOUT=` dans le journal.

## 3. Ce que 👤 a décidé — ne pas rouvrir sans mesure qui le contredise

### Réglages

| réglage | valeur |
|---|---|
| cadence machine | 4 Hz, une lecture témoin par tour |
| pas d'échantillonnage machine | un point tous les 0,125 nm à 0,5 nm/s |
| bruit de lecture | ±0,05 point, soit `A = 5e-4` en unités T |
| `reading_smoothing_window` | 1 (inactif) en exploitation ; 8 lectures dans le modèle figé |
| `tp_hysteresis_factor` | 1,66 en usage. Cible 1,00, mesurée à k = 8 et N = 800 : à remesurer avant de l'appliquer, les configurations tournant à k = 1. |
| `phase_a_level_margin_factor` | 1,66 ; 3,33 à évaluer |
| `index_corridor` | 0,005 en indice absolu, actif |
| `photometric_curvature_amp` | **0,00375**, actif |
| `affine_scale_amp`, `affine_offset_amp` | 0,05 et 0,02 |
| `allow_rate` | vrai — « le cas général » |
| `rate_by_swing` | vrai, dans l'application comme dans le noyau (2026-10-12) : des variantes Rate aux couches dont la dynamique est sous 0,025 |
| `rate_rescue`, `rate_rescue_few` | vrai, 10 (2026-10-12) : le secours Rate pose en Rate la queue des plans qui plantent ; 30 plans × 8 coupures quand aucun plan ne se termine, 3 × 2 à partir de 10 plans déposables, linéaire entre les deux |
| `elite_rate_moves`, `elite_rate_max_candidates` | vrai, 120 (2026-10-13) : ELITE déplace les couches Rate de ses parents (optique, paquet de Rate, optique à une autre λ) ; `allow_rate` faux l'éteint |
| `slit_bias_enabled` | vrai, fente nominale 2 nm |
| choix de fente de l'opérateur | 5, 1 ou 0,5 nm en plus du nominal ; facteurs de bruit ÷1,5, ×2, ×5 |
| `robustness_num_runs` | 300, décidé le 2026-08-13 : il commande la sensibilité du filtre de plantage, donc **quelles stratégies existent**. 🔴 Le mode d'exécution l'emporte sur le fichier (150 en `premium`), et la ligne `[MODE]` du journal le dit |
| `n_screen_runs` | 25 ; à 10, un seul plantage tue une stratégie **et** la perd comme parent |
| profondeurs par mode | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 pour fast / premium / deep ; `extreme` = `deep` avec une génération élargie |
| graine de référence | 42, avec `scan_wl_step` à 1,0 |
| grille des λ de contrôle | figée à 1 nm |
| `machine_sampling_dd` | 0, figé dans le noyau (ce n'est plus un réglage depuis le 2026-09-27) : pas grossier (~21 points par couche au lieu de 800), par choix de vitesse. Le modèle est donc optimiste sur les faux points tournants |
| cible spectrale | non pondérée jusqu'à nouvel ordre |
| mode par défaut | `premium` |

### Le modèle de la chaîne de lecture (OMS 5100) — figé le 2026-08-08

1. Une lecture témoin par tour à 4 Hz, soit un échantillon tous les 0,125 nm.
2. Bruit additif borné à ±0,05 point, σ = A/3, tirages indépendants d'une lecture à l'autre.
3. Moyenne glissante de k = 8 lectures (2 s) dans le modèle, inactive en exploitation.
4. Seuil de point tournant : la borne **mesurée** vaut 1,00 A à k = 8 et N = 800 ; la loi en
   1/√k est réfutée (elle laisse 100 % de points tournants fabriqués). Une mesure, pas une loi.
5. Aucun retard de déclenchement.
6. Marge de sélection des λ : 5 σ du bruit brut (1,66 A) ; 10 σ (3,33 A) à évaluer.
7. Quantification de l'arrêt `U(0 ; 0,125 nm)` — non implantée (§3, STRAT, D13).

Hors du modèle, et à y laisser : σ dépendant de T ou de λ, grenaille, bruit multiplicatif,
bruit corrélé d'un tour à l'autre, tout filtre autre que la moyenne glissante. Seul un run réel
du dichroïque dont le plantage s'écarterait nettement du prédit rouvrirait ce modèle.

### Logiciel — décidé le 2026-09-27 et le 2026-10-03

- **CERTUS tourne toujours sur un poste à jour** : les bornes minimales de `pyproject.toml` ne comptent pas ; la CI ré-résout vers les dernières versions stables à chaque run (`uv sync --upgrade`), `uv.lock` n'est qu'un point de départ (`uv lock --upgrade`). Pas de pré-version.
- **La non-reproductibilité est acceptée** : INDEX, RE et METAL_BILAYER ne rendent pas deux fois la même RMSE — leurs générateurs ne sont pas amorcés, et on ne les amorce pas. Mesuré le 2026-09-27 : INDEX de 0,002546 à 0,002691 sur dix exécutions, et 0,0067 (2,6 fois la référence) environ une fois sur huit ; RE 0,05 % ; METAL_BILAYER 1 %. La garde de convergence retient pour eux la meilleure de quatre exécutions au plus (`tests/regression/test_convergence_guard.py`).
- **Fastmath conservé dans tous les noyaux JIT — décidé le 2026-10-03** : 👤 arbitre « on garde fastmath » (D52/D67). Les gains de vitesse (7 à 19 %) sont conservés ; la non-reproductibilité froide vs chaude (jusqu'à 424 ulp sur les gradients, 1e-13 en relatif) est acceptée. Le harnais C1 maintient ses comparaisons froid à froid.

### Licence et comportement par défaut — décidé le 2026-09-29

- **Le projet est publié sous GPL-3.0** : c'est ce que PyQt6 exige de l'exécutable gelé (R36).
- **Quatre changements du comportement par défaut de DESIGN, acceptés** (R29) : la porte de stagnation et les seuils de gain prédit du Needle sont ceux réglés sur la fenêtre ; la phase globale est plafonnée quand la croissance topologique est cochée ; les graphiques prennent le fond du thème compact ; le substrat complexe est lu en oblique.
- **La sauvegarde des commits locaux** est un bundle Git hors dépôt (`../CERTUS_certus0310_<date>_<commit>.bundle`), à actualiser après chaque lot non poussé ; pousser requiert ton ordre.

### Publication — décidé le 2026-09-30

- **Rien à cacher côté public** (« je n'ai aucune crainte de tout mettre en espace public, c'est mon choix ») : l'historique n'est pas purgé — ni le nom porté par les métadonnées de 44 classeurs anciens, ni l'adresse personnelle de quatre commits — et `git filter-repo` n'est pas au programme.
- **Les œuvres de tiers restent à leurs auteurs** : la GPL-3.0 ne les couvre pas (le texte de thèse de l'historique, les PDF d'articles). Elles vont dans les avis de tiers, pas dans une purge.

### Interface — décidé le 2026-09-28

- **INDEX : les réglages d'absorption du substrat ne s'affichent que pour le silicium**, le seul
  substrat dont le calcul lit l'absorption ; pour tous les autres, le worker force k = 0 (D43).

### Indice du saphir — décidé le 2026-10-12

- **Un seul indice de saphir dans CERTUS** : le Sellmeier d'id 3, partout (noyaux, INDEX, INDEX SPLINE, STRAT, FIELD, METAL).
  Aucune table de saphir, aucun second Sellmeier. Les libellés « Sapphire Fresnel » et « Sapphire (FR) » restent des alias pour
  qu'un composant enregistré se charge encore.

### Règles gravées

- **Une λ de contrôle est interdite** si, signal bruité, elle risque de mal compter les points
  tournants ou de ne pas s'arrêter au niveau voulu — en Phase A comme en Phase B. La marge se
  compte **en transmission, jamais en nanomètres**.
- Les λ se choisissent sur la **grille de balayage** (`_resolve_monitoring_wavelength_grid`),
  jamais d'après les clés de `clues_at_wl`, qui mêlent grille de balayage et d'affichage.
- Les heuristiques de la littérature (15-85 %, amplitude de départ, swing) sont des
  **colonnes explicatives**, jamais des couperets.
- **Rate interdit sur les couches 0 et 1, autorisé partout ailleurs, dernière comprise**
  (`RATE_MIN_LAYER = 2`) : avant la couche 2, aucune couche de même nature n'a été déposée
  dont tirer un rate. Le rate ne se calcule **que sur les couches déposées optiquement**.
  Son mécanisme est la **position terminale** : une couche Rate lègue son erreur en boucle
  ouverte à tout ce qui la suit, la dernière n'a rien en aval.
- **SEEL** est la seule grandeur à rapporter : `SEEL = 2 × √score` (`_apply_strategy_ranking`),
  en nanomètres d'erreur d'épaisseur par couche. Tri : SEEL quantifié au pas de 0,01 nm, puis
  rendement, puis marge de la couche critique. Un écart d'un pas est une égalité (classement final, R130).
- **`fast` crible, il ne publie pas** : il est quantifié à 10 % sur le plantage, et un SEEL
  retenu en `fast` se rejoue en `premium`. **`extreme` n'a aucune justification mesurée** —
  zéro amélioration sur cinq configurations, `deep` seul fait aussi bien pour un cinquième du coût.
- **La profondeur Monte-Carlo sert à noter, jamais à choisir** : une candidate écartée parce
  que N était petit est perdue pour toujours.
- **Le multi-témoins est un outil de faisabilité**, pas d'optimisation : il rend le passe-bande
  de 99 couches fabricable et dégrade tout composant qui s'en passait (contrôle négatif 3 sur 3).
  Il se règle dans la fenêtre STRAT depuis le 2026-10-11, sur demande de 👤 : champ « New test glass at layers: »
  de la carte « Machine model — error sources » (`witness_reset_layers`), vide par défaut, donc un seul verre témoin.

### STRAT — arbitrages délégués par 👤 le 2026-10-04

🔴 Les mesures de cette sous-section (2026-10-04 et 2026-10-05) ont tourné sous D100 : sans biais de fente, sans Rate,
sans recherche de fente. Leurs décisions tiennent jusqu'à leur remesure sous le modèle voulu : le juge de paix et `r75x2` l'ont été les 2026-10-11 et
2026-10-12 (§0), pas ces mesures-là.

- **D73, point tournant sous l'arrêt : corrigé.** La marge se mesure en
  transmission au sommet interpolé, même si la pente change de signe sur
  l'échantillon d'arrêt. Sur 20 000 empilements aléatoires, 1 617 marges
  ont baissé ; le juge de paix `fast` a gardé ses 194 stratégies et son
  `RESULT` au bit.
- **D20, classement final : corrigé.** Dans la classe à 0,01 nm du meilleur
  SEEL, trier par rendement, marge critique, puis score brut. Le juge
  `fast` conserve 194 stratégies mais change 147 positions ; la
  recherche interne garde son tri propre.
- **D70, critère en épaisseur : retiré.** Son réglage était inerte ; la
  marge valable est en transmission. L'ancienne clé est ignorée au
  chargement avec journal. C1 : 8 008/8 008 tableaux identiques au bit.
- **D17, gain négatif : conservé.** Il détecte une fragilité que la porte
  de plantage peut manquer. Sur le juge `fast`, 159 candidates ont un
  gain négatif, dont 13 sont écartées par ce seul critère ; le journal
  les compte toutes.
- **D15, historique POEM : quatre couches conservées.** Douze couches
  rendent les mêmes 370 stratégies, leur ordre et leurs taux de
  plantage sur le juge standard ; 303 scores ne diffèrent que dans
  les derniers bits (≤ 6,7·10⁻¹¹ en relatif).
- **D14, densité de l'historique : 16 points conservés ; la densité relève de la cadence machine (12.4, §6).**
  Sur le balayage grossier, l'historique rejoue 16 points par couche contre 21 par épaisseur nominale pour la couche
  courante ; sur la grille de la machine, `_machine_grid_signal` lit les deux à la même cadence. Porter l'historique
  à 21 points changerait tous les résultats pour une densité aussi arbitraire que 16 (juge standard, 2026-10-04 :
  8 plans sur 370 survivent, plantage moyen au bruit ×2 de 0,0012 à 0,0069).
- **Hystérésis : le seuil suit le niveau de bruit, comme aujourd'hui** (1,66 × le bruit du niveau simulé : 0,5×, 1×,
  2×). Un seul seuil réglé sur le bruit nominal, mesuré sur `r75x2` en `deep` (graine 42, `306559d3`, caches vierges,
  2026-10-05) : aucun des 300 plans communs aux deux runs ne gagne ni ne perd le statut de déposable ; meilleur SEEL
  déposable 0,5566 contre 0,5560 nm, sous le σ ≈ 1,8 % de ce composant. Aucun gain mesuré, donc pas de changement de
  toutes les populations. Le plantage y croît avec le bruit pour 684 stratégies et décroît pour 33 (en août : 61 contre
  532) ; `scripts\probe_plantage_vs_sigma.py` rouvrira la question s'il recommence à décroître. Sorties : `reports/STRAT_bench_r75x2_deep_hysteresis_{noise_level,nominal}_306559d3_2026-10-05.json`.
- **D6, réglages du consensus : vérifiés, aucun écart à corriger.** Chaque mode d'exécution fixe ensemble
  `robustness_num_runs` et `consensus_num_runs` (50, 150, 300, 300 ; mode inconnu → `premium`), et la ligne `[MODE]`
  nomme toute valeur du fichier qu'il remplace. Les graines du consensus viennent de `consensus_seed_list` quand elle
  est renseignée, de `robustness_seed` sinon (`_resolve_consensus_seeds`), et chaque journal les imprime. Pour mesurer
  la dispersion d'un run à l'autre, changer le triplet, pas `robustness_seed` ; le consensus ne réécrit que le score,
  jamais le taux de plantage.
- **D7, ce que `RESULT` agrège : établi dans le code.** `RESULT` est le `robustness_score` de la première stratégie
  classée (`extract_best_rmse`) : le P95 du RMSE des tirages, au pire des trois niveaux de bruit
  (`_test_strategy_robustness_task`), remplacé pour les `consensus_top_k` par la moyenne plus `consensus_std_weight`
  écarts-types de ce même score sur les graines du consensus. **Les tirages plantés comptent dans ce P95** : au-delà
  de 5 % de plantés, il est celui d'un tirage planté (r75x0.5, graine 101, niveau 2×, 25 plantés sur 300 : SEEL
  0,960 nm sur tous les tirages, 0,644 nm sur ceux qui aboutissent,
  `reports/STRAT_r75x0.5_graine101_plan_de_repli_par_bruit_2026-10-12.md`). **La moyenne du consensus ne garde que les
  scores finis** (`_store_and_consume_consensus_score`) : un plan rejeté par la porte de plantage à une graine n'y
  compte pas. Il ne dit rien du reste de la population : comparer deux runs se fait sur le classement
  (`dump_strat_ranking`) ou sur les vidages par stratégie, comme les rapports `STRAT_bench_*` de `reports/`.
- **D9, la plage de blocs ne vide pas la DP : un seuil de faisabilité, dit dans le journal** (R147). Sous un nombre
  minimal de blocs contigus (7 sur le juge de paix standard, entre 9 et 10 sur `r75x2`, 2026-10-05), aucune λ n'est
  admissible dans toutes les couches de chaque bloc : le mineur ne rend que les graines structurées et l'écrit
  (`[MINING] n_blocks=…: the DP found no grouping; the fewest contiguous blocks … is N`). L'héritage depuis le nombre
  de blocs supérieur y ajoute ses stratégies dérivées, et elles comptent (sur `r75x2`, de 5 à 9 blocs, 188 stratégies
  déposables ; la gagnante du juge de paix standard a 4 blocs) : sauter ces nombres de blocs les perdrait. Sorties :
  `reports/STRAT_bench_juge_de_paix_ca99bc8c_D9_*_2026-10-05.*`.
- **D8, intervalles du 99c avec recherche de fente : les verdicts tiennent.** Les quatre intervalles de la
  partition retenue ([0,22), [22,42), [42,76), [76,99)), remesurés comme le fait `scripts\campagne_intervalles.py`
  (`fast`, graine 42, `ca99bc8c`, 2026-10-05), sont déposables avec et sans recherche de fente (plantage minimal 0 %,
  meilleur score déposable à −2,6 %, −0,8 %, 0 % et +1,8 %). Le SEEL assemblé (§2, 0,81 nm sur trois graines) n'est
  pas remesuré. Sorties : `reports/STRAT_99c_intervalles_retenus_fente_{off,on}_ca99bc8c_2026-10-05.json`.
- **Sans changement de code :** D16 (THICKNESS² conserve l'ordre DP),
  D18 (seuils 0,025 et 0,04 appliqués à deux grandeurs), D19 (le
  comptage des points tournants est déjà dans le noyau Phase A), D22
  (effet borné à une couche et Rate simulé en Phase B), D12 (lissage
  causal inactif à `k=1`), D13 (quantification temporelle à reporter
  jusqu'à une mesure réelle). Une mesure contradictoire les rouvrira.

### DESIGN — tranchés par Claude sur l'ordre de 👤, 2026-10-04

Chaque correctif est un commit (R136 `c738a130`, R137 `83661fd4`) qu'un `git revert` annule seul.

- **D45, gradient avec pile arrière : corrigé.** Le coût et son gradient
  utilisent désormais la même somme des poids. C1 : 93 des 8 008
  tableaux changent, tous dans ce gradient ; la différence finie
  confirme le nouveau gradient à 10⁻⁵.
- **D46, opacité : bornes d'épaisseur limitées.** Les modes global,
  local et healing restent à 1 % sous l'épaisseur où `|Im φ|=700`.
  Une couche non absorbante garde ses bornes au bit ; un métal
  infrarouge n'envoie plus l'optimiseur dans la zone où le noyau
  répond (R, T) = (0, 0). Les noyaux restent inchangés.

### Arbitrages de 👤 du 2026-10-05 (soir)

- **Polarisation « Avg » de DESIGN (ex-D47) : retirée officiellement.** Le tableau des cibles n'offre que s et p ; une configuration ancienne « Avg » se charge en s avec un avertissement. Rien à calculer.
- **Threads Numba d'une tâche de robustesse STRAT : adaptatif** (`task_numba_threads`) : 4 sur une machine de 16 cœurs logiques ou plus, 2 sinon, jamais au-dessus de la limite de Numba. Sur le juge de paix standard (mode `premium`, caches froids, Ryzen 7 5700G, 16 threads, 2026-10-05), 4 threads prennent 11 à 13 % de moins que 2, populations identiques au bit (chaque tirage des noyaux parallèles écrit sa propre case). Les machines de moins de 16 cœurs gardent 2 faute de mesure.
- **D86 : garder l'avertissement**, ne pas refuser l'extrapolation.

### Arbitrages de 👤 du 2026-10-06

- **Un matériau absent de la base refuse le calcul** (D88), plutôt que de seulement prévenir.
- **Le gel passe sur la couche OpenMP** (D87).
- **D48 : le substrat reste non absorbant**, sans champ d'épaisseur. DESIGN construit ses matériaux, substrat
  compris, par un modèle de Cauchy réel à deux indices (n à 400 et 700 nm, `Material`) et STRAT ne lit que la
  partie réelle de l'indice du substrat : l'épaisseur du substrat n'entre dans aucun de leurs calculs. La lame
  absorbante reste dans la physique (`certus_substrate_absorption`), avec son épaisseur par défaut de 1 mm.
- **Tolérance de C1 pour retirer du code mort d'un noyau : 10⁻¹⁰ en relatif** (D54).

### Réponses de 👤 du 2026-10-06

- **Données Nb2O5 « Syrus » : laissées telles quelles.** Dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de
  `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm,
  quand les feuilles H400 et H800 restent entre 2,07 et 2,13 ; un creux de cette taille avec k ≤ 0,018 n'est pas
  physique. Un résultat fondé sur ces feuilles au-delà de 4 µm en hérite.
- **Stop pendant l'étage IR d'INDEX : le résultat raffiné est gardé**, comme aujourd'hui ; rien à changer.
- **Le dépôt reste dans Google Drive.** Les fichiers hors git sont archivés à côté des bundles ; l'archive est à
  refaire si ces fichiers changent.
- **Toute fusion dans `master` se redemande à 👤**, sauf la PR de la parité (`parite-zenodo`), qui se fusionne dès que
  sa CI est verte. La protection de `master` est un réglage de sécurité de GitHub, appliqué par 👤 : rien à ajouter
  aux contrôles exigés (ruff, pytest, interface), pas d'épinglage SHA obligatoire (les actions sont épinglées de
  toute façon).
- **Le gel embarque toutes les licences** : `LICENSE`, `THIRD_PARTY_NOTICES.md` et les fichiers de licence de chaque
  distribution embarquée, dans `licenses/`.
- **Un gel local se construit dans un environnement jetable installé depuis `requirements.lock`**, comme celui de la
  CI, et supprimé ensuite : l'exécutable local n'embarque pas ce que porte le Python du poste.
- **Données et logo de 👤** : `BSCNES_*` et le reste de `example/` et `samples/`, la table du silicium sous 1200 nm,
  les préréglages de Cauchy, le logo. `certus_re` (Zenodo) est publié sous CC BY 4.0. Les quatre
  termes de B270i autres que B1 et C1 sont d'origine inconnue.
- **Le RE garde sa pénalité QWOT** : l'a priori MAP de `certus_re` n'est pas porté.

### Arbitrages de 👤 du 2026-10-12

- **D99 n'est pas un défaut** : la lecture d'arrêt est **une lecture brute** (un tirage par couche), pas une moyenne sur 8
  lectures. Le modèle figé reste tel quel ; `fige_arret_lisse` de `scripts/probe_modele_lecture.py` documente l'hypothèse écartée
  (notes plus basses de 8 à 21 %, classement à 0,92).
- **D96 et D97 : activer par défaut** l'ancre exacte et l'inversion exacte de l'arrêt POEM (l'arrêt sans bruit retombe sur POEM
  exact). Les scores STRAT changent : les références mesurées sont à refaire. Actifs par défaut depuis `8d9ced13`.
- **D98 : l'OMS attend sans fin** quand le niveau d'arrêt est plus proche de l'extremum que le seuil d'hystérésis : la couche est
  plantée (pas d'arrêt tardif). Actif par défaut depuis `8d9ced13` (`oms_arming` = 2). Effet mesuré à ce commit sur le juge de paix
  (`premium`, graine 42, `scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`, une recherche complète par ligne, avant le
  secours Rate et D106) : ancien modèle 669 plans déposables sur 823 (487 optiques purs, meilleur 0,1780 nm) ; D96 et D97 seuls 550
  sur 632, 0,1787 nm ; D98 seul 323 sur 489, 0,1689 nm ; les trois avec l'arrêt tardif 381 sur 1 034, 0,1904 nm ; les trois avec
  l'attente sans fin (la production) 2 sur 1 112, 0,2000 nm. Sur les 120 premiers plans du banc du 2026-10-04
  (`reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`), notés de nouveau avec 300 tirages (sans biais de fente ni
  Rate, `scripts/probe_modele_lecture.py`) : 120 déposables à l'ancien modèle, 6 à l'attente sans fin, avec ou sans D96 et D97.
  L'attente sans fin retire donc 95 % des plans que l'ancien modèle jugeait fabricables. Au code final (secours Rate, `rate_by_swing`,
  D106 ; mêmes lignes, une exécution chacune), toutes les listes sont déposables et le meilleur SEEL est le même à la dispersion près
  sous les cinq combinaisons (de 0,1759 à 0,1854 nm) ; ce qui change est le nombre de plans optiques purs déposables, 50 à l'ancien
  modèle, 107 avec D96 et D97, 101 avec l'arrêt tardif, 4 avec D98 seul et **0 à l'attente sans fin complète**, et le meilleur plan
  est un plan Rate sous chacune (de 1 à 28 couches au Rate). Rapport : `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.
- **D68 (1) : le hub ne lance pas l'échauffement JIT** ; chaque module garde le sien.
- **Rate dans tous les scénarios.** Le Rate est une couche posée **au temps, à la vitesse estimée** sur les couches du même
  matériau contrôlées optiquement (`_rate_layer_thickness`), pas un quartz ni un chrono. 👤 : il doit être intégré à chaque
  design, quel que soit le filtre ; favorisé sur les couches difficiles à contrôler optiquement ; renforcé quand peu de plans
  se terminent ; `r75x0.5` avec un seul verre témoin est le test, et il doit finir par trouver des plans, « quitte à tout
  finir au rate ». Traduit en trois changements : `rate_by_swing` actif par défaut **dans l'application** (elle lisait Faux
  depuis le 2026-08-22, le noyau et le registre disaient Vrai), le **secours Rate** (`rate_rescue`, `rate_rescue_few`, actifs par
  défaut) qui pose en Rate la queue des plans qui plantent, et des enfants d'ELITE et de la recherche locale qui **gardent les
  couches Rate**, la fente et les échanges de verre de leur parent (ils les perdaient : ELITE ne pouvait jamais affiner un plan
  Rate). Mesuré à `r75x0.5` : §7. Le secours sait aussi poser le Rate là où les tirages plantent d'abord, quelques couches de plus
  à chaque tour (`rate_rescue_hard`) : inactif par défaut ; à `r75x0.5` (graine 101) il ajoute 35 plans déposables sur 410 et ne change
  pas le meilleur SEEL (§7). **L'optique reprend après du Rate** : le noyau le permet (une couche optique est arrêtée sur son propre
  signal, quelle que soit la façon dont les précédentes ont été posées ; `tests/unit/test_strat_optics_after_rate.py`) et 👤 observe en
  salle de bonnes stratégies en paquets (optique à un λ, Rate, optique à un autre λ), ce qui reste empirique. La recherche ne le
  proposait presque pas : les plans déposables du 2026-10-12 avec de l'optique après du Rate ont exactement deux paquets de Rate, une
  couche puis la queue, et ELITE rendait à ses enfants les couches Rate du parent sans les changer. ELITE sait maintenant les déplacer
  (`elite_rate_moves`, `elite_rate_max_candidates`) : étendre ou raccourcir un paquet, fermer un trou, ouvrir une fenêtre d'optique
  dans une queue, poser un paquet de Rate dans l'optique. Actif par défaut depuis `978b8f04`, après mesure (§7).

### RE — décidé par 👤 le 2026-10-05

- **Divergence du faisceau : deux ou trois rayons suffisent.** 👤 : « définitivement, la prise en compte de
  la divergence faisceau se fait avec 2 ou 3 rayons, c'est suffisant ». Le RE en emploie deux (θ ± h,
  `_re_p4_effective_half_width_deg`) ; la quadrature de Gauss-Legendre à neuf nœuds du paquet Zenodo n'est pas
  portée (dans ses propres sorties, elle ajustait moins bien : RMSE jointe 0,4166 % contre 0,1481 % à deux
  rayons, ouverture imposée de 2°, `results/insitu_model_refinement.json`).

## 4. Défauts ouverts

Numérotés ici ; un défaut corrigé sort de la liste et son numéro n'est pas réattribué. Les
numéros de l'ancien registre sont entre parenthèses
(`git show 7b08dc8:docs/archives/DEFAUTS_OUVERTS.md`). Tous revérifiés contre le code le 2026-10-06.

**Ils faussent un résultat, trompent l'utilisateur ou empêchent de calculer, et le modèle physique — connus, non corrigés**

Aucun. D96 à D98 (le modèle d'arrêt) sont décidés et actifs depuis le 2026-10-12 : §3.

**Le code, les tests et la documentation**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | À instruire : six `gc.collect()` exécutés dans les threads de calcul STRAT (deux dans `_parallel_block_worker`, un dans `_run_segment`, un dans `_execute_nucleation_and_cost_mapping`, deux dans l'exécuteur du pipeline) peuvent libérer des objets Qt hors du thread GUI, sans arrêt observé ; les tests n'isolent pas `sys.modules`. L'arrêt pendant l'étage IR d'INDEX garde le résultat raffiné, décidé par 👤 (§3). Reproduire avant de changer le cycle de vie ; traiter avec D11 |
| D25 | Dette de lint masquée par `extend-ignore` : **8 règles**, E501 compris, et 1 416 violations à la mesure du plan (`scripts\metrics.py`, 2026-10-12, E501 exclue : F401 659, E402 555, RUF001 77, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2, ce dernier écarté des tests par `per-file-ignores`) ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 (trier `__all__`) reste ignorée à dessein |
| D26 | Imports montants entre couches, mesurés le 2026-10-06 (`scripts\metrics.py`) : 20 arêtes, `certus.spline → certus.ui` (8), `certus.metal → certus.ui` (6), `certus.utils → certus.ui` (3), `certus.utils → certus.spline` (3) ; un cycle d'imports à l'exécution (le cœur de STRAT) ; `certus.physics.gradient_analytic` ne s'importe pas seul (cycle avec `gradient_utils`) |
| D50 | Gelé, `loky` ne marche pas (repli sur des fils) et le multigraine reste refusé, le message le dit. La couche Numba du gel est D87, sa taille D72. Le job `release-windows` l'a construit et démarré sur un poste neuf le 2026-09-30 (R42) |
| D68 | **La physique lit le silicium (`SI_*`, feuille `Si-substrate` de `indices.xlsx`) À L'IMPORT**, par pandas et openpyxl (mesuré sur la fenêtre DESIGN, machine chargée : 0,53 s pour `materials_data`, dont 0,42 s d'import d'openpyxl) ; les rendre paresseux demande que les tableaux existent avant la première compilation de `get_nk_si` (numba les fige), donc toucher le chargement de la physique. (L'échauffement JIT du hub est tranché : il ne le lance pas, §3.) |
| D69 | Une définition d'indicateur a changé en route, et 👤 doit le savoir. « Couverture des noyaux, compilation coupée » : le plan la mesurait par `oracle` + `core` (base 45,9 %, cible ≥ 70 %) ; elle se mesure maintenant par ces deux répertoires, `property` et les tests de `unit` marqués `kernels` (R78 : 74,0 %). La base de l'audit reste celle de l'ancienne définition ; avec l'ancienne, l'indicateur serait à 46,0 % le 2026-10-01 (non atteint). Je tiens la nouvelle pour la bonne (les tests des noyaux de STRAT ont été écrits pour cela), mais c'est un changement de critère. |
| D71 | **Tauc-Lorentz-Urbach n'est pas continu en E = Eg** (`certus_optical_models.py`, `gradient_analytic.py`). ε₂ saute là : la queue d'Urbach, utilisée pour E ≤ Eg, vaut 1,9e-4 pour l'oxyde de l'exemple, l'absorption de bande (E > Eg) vaut 0 et monte jusqu'à l'ancre de la queue, posée à Eg + 0,01 eV ; le saut est de 2e-5 du maximum, sans effet sur un empilement, mais le modèle n'est pas continu là pour un ajustement qui passerait au bord du gap. Le raccorder change le modèle des références certifiées (leurs paramètres ont été ajustés sur lui) : à trancher avant de le toucher. (La première observation, k par différence qui s'annule sous ε₂ ≈ 1e-7, est corrigée : `extinction_from_epsilon`, k = ε₂/(2n).) |
| D72 | **Taille du gel (S7.2) : objectif ≤ 300 Mo non atteint.** 411 Mo le 2026-10-06 (442 avant `5ccaa210`, qui laisse dehors les outils de développement). Le reste : llvmlite 115 Mo (Numba, indispensable), Qt 77 Mo (dont le rendu OpenGL logiciel), scipy 68 Mo avec ses bibliothèques, numpy 28, matplotlib 15, Pillow 13, pandas 13, lxml 7, OpenSSL 8. Étape suivante : mesurer ce que l'application charge vraiment (sous-modules de scipy, plugins Qt, ssl, lxml) avant d'autres exclusions. Un gel local embarque ce que porte l'interpréteur qui le construit : celui du 2026-10-06 contient aussi lxml, psutil, pywin32, PyYAML, certifi, charset_normalizer, MarkupSafe et cffi, absents de `requirements.lock`, d'où part le gel de la CI. Le spec embarque tout `example/`, base de dépôts comprise (11 Mo sur disque, 2026-10-11) |
| D82 | **Thème sombre : logo et mesure de contraste à terminer.** Les textes et états vides suivent désormais le thème (R102). Le logo foncé reste peu visible en thème sombre, constat visuel sans mesure ; le harnais ne résout pas encore une encre de palette sur fond hérité. |
| D84 | **Validation locale intermittente.** Des écarts au dernier bit sur des tests STRAT apparaissent au premier passage après un changement de clé du cache Numba, puis disparaissent à la relance (deux fois le 2026-10-03 ; le 2026-10-06, `test_neutral_parameters_are_bit_identical_to_the_legacy_call` dans la validation de `29240ee7`, après la modification de `certus_colorimetry.py` : rouge à froid, vert à la relance, 0 ulp mesuré entre les deux appels du noyau). Signature compatible avec D52 : compilation sur place contre lecture du cache, cause non prouvée. Si l'écart persiste à la relance, comparer les noyaux froids et chauds avant de modifier le calcul. |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Les choix déjà faits figurent en section 3.

| sujet | ce qui est en jeu |
|---|---|
| **avis de tiers** | une ligne reste « à confirmer par toi » dans `THIRD_PARTY_NOTICES.md` : les DLL du runtime Visual C++ (`VCRUNTIME140*.dll`, `VCOMP140.DLL`) se redistribuent avec un programme, mais Microsoft réserve ce droit aux utilisateurs de Visual Studio sous licence |
| **paquet `certus_re`** | la correction de la citation du saphir (Malitson et Dodge, 1972) attend d'être commitée par 👤 dans ce dépôt-là, qui contient ses modifications en cours, puis publiée avec la prochaine version Zenodo |
| **interface** | Revoir visuellement les onze fenêtres et choisir les teintes de marque, la bande des fichiers récents et les bornes des champs numériques. |
| **base de dépôts** | RE : remplacer la seule mesure d'un classeur RE déjà chargé par celle d'un dépôt (il faudrait découper `load_reverse_engineering_from_path`) ? Apparier dans la base la T et la R d'un même échantillon que l'opérateur a nommées différemment (`NbT3` et `NbR3`) ? INDEX : en phase 2, la fenêtre λ de l'utilisateur est remplacée par toute l'étendue des données (`_on_tlu_constrained_finished`), est-ce voulu ? |
| **ELITE « tour à tour »** | `elite_round_robin`, six graines, D100 et D103 corrigés, avant D106 (2026-10-12) : mieux à la graine 42 (0,5420 contre 0,6354 nm), équivalent à la 404, moins bien aux 77, 101 et 505 (de +0,7 à +2,8 %), la 303 sans déposable des deux côtés ; médiane +0,7 %. L'option est inactive et le reste tant que 👤 ne dit pas de l'armer ; ce qui manque pour trancher est le bruit d'une même graine rejouée |
| **arrêt de STRAT** | D96 à D98 sont le modèle par défaut (§3). L'attente sans fin de D98 retire 95 % des plans que l'ancien modèle jugeait fabricables (§3) ; ce que l'OMS fait à un niveau franchi avant que son contrôleur soit armé n'est pas connu. À secours Rate égal (juge de paix, code final), l'arrêt tardif rend un meilleur SEEL du même ordre (0,1792 contre 0,1849 nm) et garde 101 plans optiques purs déposables, que l'attente sans fin ne garde pas : avec elle le Rate est une nécessité pour ce composant, avec l'arrêt tardif une option. À confirmer, ou à remplacer. Reste aussi : noter ou non au modèle figé, au moins pour départager la tête du classement (rapport du 2026-10-10, sections 4 et 6) |
| **le Rate et l'optique pure** | Au juge de paix (code final), le meilleur plan porte du Rate sous les cinq modèles d'arrêt (de 1 à 28 couches) et le meilleur plan optique pur est de 4 à 37 % moins bon ; les plans optiques purs déposables sont 50 à l'ancien modèle, contre 487 avant le secours Rate (mesure d'avant D106). Le modèle de Rate de STRAT n'a ni dérive de la source ni bruit propre de la vitesse (§7), ce qui le favorise, et ELITE refine maintenant des parents Rate (et déplace leurs couches Rate : §3) : l'hypothèse, non mesurée, est que la lignée optique pure y perd des tours. Faut-il réserver à ELITE des parents optiques purs, ou ne laisser le Rate que là où l'optique ne suffit pas ? La réponse dépend de la stabilité réelle de la vitesse (A25, §6) |

## 6. Chantiers spécifiés, en attente

**Saphir** — INDEX traite le saphir comme transparent (k = 0) : son absorption au-delà de 3,9 µm (α de 0,05 cm⁻¹ à 4 µm à 1,1 cm⁻¹ à
5,2 µm, lue sur le saphir nu de la séance 24-03) n'est pas modélisée, ce qui biaise les films mesurés au MWIR ; à brancher comme
nouveau paramètre inactif par défaut (C1) · mesurer la polarisation du faisceau du spectrophotomètre : elle domine l'incertitude
du niveau (0,025 d'indice par unité de fraction p).

**Calcul** (détail : `git show 7b08dc8:docs/archives/REPRENDRE_ICI.md`) —
dimensionner K, le nombre de graines à lancer : à refaire au code final (`r75x2`, avec D106 corrigé : deux graines sur deux trouvent des
déposables avec le secours Rate, aucune sans ; avant D106, 6/7 puis 3/7 en août) · balayer `tp_hysteresis_factor` à bruit fixé sur la grille machine : sur la grille
grossière, il est presque inerte (juge de paix, 370 plans, 2026-10-11 : de 1,0 à 2,0 A, 358 à 362 notes identiques au
bit à celles de 1,66 A, même meilleur plan ; rapport de l'audit du 2026-10-10, section 4) · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre · accélérer à résultat identique au bit : aucune piste ouverte
(les 17 % d'« attente du consommateur de statistiques » d'un profil par échantillonnage sont un artefact de
l'échantillonneur de `scripts/bench_examples.py`, `scripts/probe_sampler_idle_thread.py`, 2026-10-11 ; mémoriser
`build_M_before_cache` ne fait rien gagner, populations identiques au bit, 2026-10-06) · mesurer `elite_rate_moves` (actif) sur
d'autres composants (×1,5, ×1,75, 35 et 99 couches), d'autres graines (une seule au juge de paix, deux à `r75x2`) et avec plus de tours d'ELITE.

**Modèle physique** (détail : `git show 7b08dc8:docs/archives/TRAVAUX_A_VENIR.md`) :

| | sujet | état |
|---|---|---|
| 12.2 | modéliser le lissage de lecture | fait sur la grille machine : lecture du T exact à chaque pas, lissage sur 8 lectures au seuil de 1,00 A ; D54, D55, D93, D94 et D95 sont corrigés et ce chemin reproduit une machine indépendante rejouée lecture par lecture (rapport du 2026-10-10, section 2) — surtout ne pas remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié : corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | fait : voir 12.2 ; inactive par défaut (§3) |
| 12.5 | quantification temporelle du déclenchement | ouvert |
| 12.6 | facteur de face arrière | en dernier, ou jamais |
| 12.7 | résolution du monochromateur | spécifié |

**Réserve** (détail : `git show 7b08dc8:docs/archives/RESERVE_A25_A27.md`) —
**A25** `sigma_rate` comme prédiction : la seule grandeur vérifiable de l'extérieur, contre les
±1 à 2 % que 👤 observe en salle · **A26** un bloc de santé de run (A27, le harnais C1, est fait : R45).

**Architecture** (détail : `git show 7b08dc8:docs/archives/PLAN_AMELIORATION.md`) —
reste un cycle à l'exécution (le cœur de STRAT), 20 arêtes montantes et les points chauds
de taille (32 fonctions de plus de 300 lignes, 12 de complexité supérieure à 60, 18 fichiers de plus
de 1 500 lignes le 2026-10-06), nommés dans `tests/architecture_debt.json` ; l'hygiène des imports (D25).

**Lint à effet possible (D25).** F401 est traité pour les imports sans rôle ; restent
E402 et les petites règles (RUF001 à RUF003, RUF022, RUF100), un cas à la fois.

| règle | ce qui peut changer un comportement | démarche proposée |
|---|---|---|
| F401 | un import « inutilisé » peut être un ré-export (y compris dans un import sur plusieurs lignes, ou un nom déclaré par `__all__.extend`), un effet de bord (enregistrement, sous-module `import a.b`, configuration numba avant un `@njit`), ou servi par une façade `CertusFacadeModule` | **fait** par lots (R9) : un nom ne part que si l'import est au niveau du module, hors `try`, sans accès dynamique du module à ses globales, et si aucun fichier suivi, aucune façade, aucun test qui charge le fichier par son chemin ni aucun code lancé depuis une chaîne ne le prend ; le reste est listé, pas retiré |
| E402 | l'ordre des imports compte : cycle `physics ↔ core`, `configure_numba_env()` avant tout `@njit`, `QT_QPA_PLATFORM` avant la première `QApplication` | réordonner seulement les fichiers sans import à effet, jamais les façades ni `certus_core` ; E402 cas par cas |

**Contrôles du chantier lint** : ruff ; oracle ; unit ; `tests/ui/` ; le reste de `tests/` ; trois
photos avant/après — l'espace de noms final de chaque module touché (`scripts/lint_ns_snapshot.py`),
les modules que charge chaque script d'entrée une fois son fil de préchauffage fini, et les noms
que sert chaque façade `CertusFacadeModule`. Un nom qui disparaît ne doit être ni utilisé ni
demandé par personne.
**Ordre** : E402, puis les petites règles.

**Prédictibilité** (détail : `git show 7b08dc8:docs/archives/CHANTIER_PREDICTIBILITE.md`) —
prédire sans tout calculer si un design passe avec un seul verre témoin ; quatre routes déjà
fermées par la mesure.

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`, sauf mention) | couches | notation | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400-700 nm | le juge de paix : passe-court, front vers 545 nm |
| passe-bande 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600-660 nm | une résonance, une bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550-750 nm | ni cavité, ni miroir, ni périodicité : teste si une règle est **générale** |
| passe-bande 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610-655 nm | le cas dur |
| aléatoire ×0,5 | `reports/serie_echelle_r75/cfg_x0.5.json` (`r75x0.5` des sondes) | 75 | 550-750 nm | le côté mince de la série d'échelle ; fabricable avec un seul verre témoin grâce au secours Rate (ci-dessous) |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` (fente 1 nm) ; `JSON-strat-random75-x2-fabricable-2nm.json` (fente 2 nm, rampes injectées de `rampes_r75x2-2nm.json`) | 75 | 550-750 nm | l'étalon depuis le 2026-08-20 : épaisseurs doublées |

Une règle n'est acquise que si elle survit sur un empilement **sans structure**.

**La série d'échelle de l'aléatoire** (`reports/serie_echelle_r75/`, 2026-08-15) : même empilement, mêmes matériaux
(H800-Nb2O5 sur H800-SiO2, substrat SiO2, λ₀ 633 nm), seule l'épaisseur est multipliée ; c'est la seule expérience
contrôlée du projet. Somme des QWOT (QWOT par couche ; couches sous 1 QWOT) : ×0,5 57,4 (0,25-1,24 ; 59) · ×1 114,9
(0,50-2,48 ; 11) · ×1,5 172,3 (0,76-3,72 ; 3) · ×1,75 201,1 (0,88-4,34 ; 2) · ×2 229,8 (1,01-4,96 ; 0). Optique et
mécanique y sont proportionnelles : une conclusion en micromètres ne se généraliserait pas à d'autres matériaux.

**×0,5 avec un seul verre témoin, avant le secours Rate** (2026-10-11, `782972bf`, D100 corrigé, `deep`, fente 2 nm,
`reports/blocs_vs_plantage_r75x0.5_deep_s{042,101,202}.json`) : aucun déposable aux graines 42, 101 et 202 (0 sur
2 895, 2 897 et 2 895 stratégies), plantage minimal 69,0 %, 8,3 % et 62,3 % (août : 68,7 % pour la graine 42 avec le
profil élargi, 70,0 % et 67,0 %), et la cause de plantage dominante est « niveau d'arrêt hors d'atteinte » pour toutes
les stratégies des trois graines. D103 ne la touche pas (aucun identifiant en double dans les trois journaux). Quand
rien ne passe, le repli garde le plan au plantage le plus bas : celui de la graine 101, qui plante dans
1,7 / 1,7 / 8,3 % des tirages aux bruits 0,5× / 1× / 2×, seul le 2× dépassant 5 % ; 5 blocs aux λ de contrôle 636,
686, 737, 747 et 734 nm, variante `RATE_L31`. Son SEEL affiché est 0,673 nm (score de consensus, D7). Rejoué niveau
par niveau (`reports/STRAT_r75x0.5_graine101_plan_de_repli_par_bruit_2026-10-12.md`) : 0,655 / 0,660 / 0,960 nm sur
tous les tirages, **0,633 / 0,636 / 0,644 nm sur les tirages qui aboutissent**.

**×0,5 avec un seul verre témoin, avec le secours Rate** (2026-10-12, `40642146`, `deep`, fente 2 nm,
`reports/STRAT_secours_rate_2026-10-12/`, `reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`) : tous les plans de la liste finale
sont déposables aux trois graines (3 383, 3 701 et 3 279 plans), aucun n'est un plan optique pur, plantage maximal de 2,67 %,
4,67 % et 2,00 %. Meilleur SEEL 0,5031 / 0,4981 / 0,5000 nm (graines 42 / 101 / 202), 12 blocs, 0 % de plantage aux trois bruits,
Rate des couches 18 à 75 (indices 17 à 74). Les queues Rate seules (`21d1b1c3`, graine 101, avant l'héritage d'ELITE) donnaient
0,555 nm (coupure à l'indice 16 : 522 plans sur 547 se terminent) et 0,563 nm (coupure 14 : 2 272 plans sur 2 272) ; des
ensembles fixes de couches critiques (indices 22, 25, 28, puis 46, 51, 62, 69, 72) n'en rendent aucun (0 sur 4 614, plantage
minimal de 52 % pour les ensembles) : les couches qui cèdent se déplacent quand les précédentes passent au Rate. **Le modèle de
Rate de STRAT** (`certus_strat_growth.py`, « RATE MODE ») fige l'estimation de la vitesse à l'entrée de la queue : toutes ses
couches héritent de la même erreur relative, corrélée, et la source ne dérive pas pendant le dépôt (non modélisé, non mesuré) :
ces SEEL sont ceux de ce modèle. Le Rate posé aux seules couches où les tirages plantent d'abord (`rate_rescue_hard`, inactif par
défaut) ajoute 35 plans déposables sur 410 essayés et laisse le meilleur SEEL à 0,4981 nm (graine 101, `dbf8025f`). **Avec ELITE qui déplace
les couches Rate** (`reports/STRAT_ELITE_couches_Rate_2026-10-12/`) : **0,4347 / 0,3967 / 0,3967 nm** aux graines 42 / 101 / 202 (`5da02db9`, `cea0db66`,
`5da02db9`), toutes les listes déposables ; le meilleur plan des graines 101 et 202, le même, alterne optique (couches 1 à 6), Rate 7 à 10, optique 11 et 12
(λ 451 nm), Rate 13 à 34, optique 35 et 36, Rate 37 à 75. Le cas à plusieurs
verres témoins n'est pas mesuré.
