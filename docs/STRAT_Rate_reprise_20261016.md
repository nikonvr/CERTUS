# CERTUS — diagnostic et passation du 16 octobre 2026

Ce document est le point d'entrée pour l'IA suivante. L'état courant est dans
[ETAT, section0](ETAT.md) ; les règles dans [CLAUDE.md](../CLAUDE.md). Le
[guide historique](STRAT_Rate_suite_chantier.md) contient les protocoles précédents,
pas une autorisation de les relancer.

## 0. Reprendre sans ambiguïté

Le chantier scientifique en est au **diagnostic, avant correctif 48c**. Le programme
R0–R6 précédent est clos ; son automation reste en pause. L'action immédiate demandée
est la passation et le nettoyage : conserver les preuves brutes en archives locales,
garder Git léger et conserver `certus0310` sous **1 000 000 000 octets, `.git` compris**.
Le contrôle après push donne490935336octets (~491Mo), Git compris ; le relevé daté
est conservé dans le dossier de publication.
Après deux refus de la revue automatique, l'utilisateur confirme explicitement :
« force le push public c'est un ordre ». La publication publique du code, des bilans,
plans, indexSHA et journaux de validation est donc autorisée vers
`https://github.com/nikonvr/CERTUS.git`, branche `claude/ecstatic-newton-3grmls`.
Les archives brutes restent locales. Le push a réussi (sortie0), puis le distant a été
vérifié au commit `be3af69ed0271d64b8c98d1f065674ffe6d31b49` ; le présent récépissé
complète cette livraison. Aucun historique Git n'est réécrit.

Pour reprendre la science après cette livraison :

1. Lire [ETAT, section 0](ETAT.md), puis les règles de [CLAUDE.md](../CLAUDE.md).
   Inspecter d'abord les processus et les verrous ; si la machine est libre, exécuter
   `python scripts\preflight.py` et exiger `PREFLIGHT=GO` avant tout autre travail Python.
2. Lire [l'autorisation distincte de la suite](../reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json),
   [le diagnostic enregistré](../reports/STRAT_Rate_followup_2026-10-16/diagnostic_01/recorded_audit.json)
   et [l'échec de préparation](../reports/STRAT_Rate_followup_2026-10-16/handoff_01/preparation_failure.json).
3. Réparer et vérifier une **nouvelle copie** de la préparation contrôlée, dans un
   nouveau dossier. Le prototype existant n'est pas validé pour mesurer. Restaurer
   seulement les preuves brutes nécessaires depuis les archives locales vérifiées.
4. Auditer les entrées numériques complètes avant une mesure bornée ; ensuite seulement
   isoler le choix de fenêtre admissible 48c. Le correctif n'est pas écrit et aucune
   nouvelle simulation n'a été exécutée depuis la clôture.

Les commandes, empreintes, limites et critères détaillés sont ci-dessous. Un prompt
court prêt à copier à une autre IA figure en section 11.

**TODO supplémentaire demandé par 👤 le16octobre :** tenter le99c en une seule campagne en injectant
du Rate et en appliquant les derniers raffinements Rate intégrés. La tâche A9 de
[ETAT_actions.md](ETAT_actions.md) précise les comparaisons, limites et preuves attendues ; aucun essai99c
n'est lancé par cet ajout documentaire.

## 1. Situation exacte à la passation

Le programme borné R0–R6 est **terminé par arrêt précoce**, après48c sans gain.
Son suivi `certus-essais-rate-jusqu-au-14-octobre-9-h` est **PAUSED**, statut relu
le16octobre. Quatre pairesR6 sur six possibles ont été utilisées ; les deux autres
ne sont pas un budget reportable. Aucune mesure scientifique ne tourne à la reprise
du16octobre10h25Paris. Le préflight exécuté ensuite finit par `PREFLIGHT=GO`.

Après le bilan clos, l'utilisateur a demandé « continue la suite logique » : diagnostic
contrôlé R5/h03, puis examen du choix de fenêtre48c. Il a ensuite demandé une passation
précise et « push et commit all », puis un ménage drastique et un dossier de moins
d'un giga. Il a explicitement choisi « Archives locales, dépôt Git léger ». La demande
de commit/push autorise la publication du code, des bilans, plans et index conservés ;
les archives brutes restent locales. Elle n'active aucun défaut scientifique ni option Rate.
[Périmètre séparé de la suite](../reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json).

**Depuis la clôture : aucune source scientifique modifiée, aucun nouvel appel physique
Monte-Carlo exécuté.** Un diagnostic sur traces enregistrées est terminé. Une nouvelle
préparation de contre-épreuve a échoué avant chargement de l'application, avant claim
et avant calcul. Son script est un **prototype non vérifié**, à ne pas lancer en mesure.

La panne précédente du moteur Codex (`codex-code-mode-host.exe` introuvable) ne se
reproduit plus : terminal PowerShell et commandes Python fonctionnent. L'échec actuel
est différent : accès sandbox refusé au worktree externe lors de `os.chdir(ROOT)`
dans `bench_examples.py`. Il faut un accès réel à ce contexte, pas modifier la physique.

## 2. Arbres, provenance et gel

Racine de travail sur cette machine :

```text
D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310
```

Branche de reprise lors du diagnostic : `claude/ecstatic-newton-3grmls`. Repère source
avant publication : `da1af0825d5e09e8d0a5ff4f1cf42b802e0e30e7`, avec six commits locaux
préexistants. Vérifier le HEAD et la branche présents à la reprise ; ce repère n'est
pas une affirmation sur le commit livré. Le résultat effectif du commit/push relève
du bilan de publication, sans empreinte anticipée dans ce document.

Contextes historiques **figés** sous `C:\Users\Lemarchand\.codex\worktrees\` :
`campagne-a2`, `rate-equilibre`, `rate-rmse-r0`, `rate-r5-native`, chacun contenant
`certus0310`. Ne pas les modifier ni les recréer sous le même nom pour une nouvelle mesure.

Le contexteR5/R6 est `rate-r5-native\certus0310`, même HEADda1af082, avec16snapshots
validés copiés exactement et321sources du paquet vérifiées. Trois modules de production
et deux tests étaient nouveaux/non suivis ; `git diff` seul ne les inventoriait pas.
24autres différences entre arbres sont seulementCRLF/LF, avec texte normalisé/AST égaux,
et leurs empreintes réelles sont conservées. Le manifeste est
[reference_context.json](../reports/STRAT_Rate_suite_2026-10-15/R5_integration/reference_context.json).
Sur une autre machine, les chemins absolus des anciens JSON sont de la provenance,
pas des chemins à substituer silencieusement. Créer un **nouveau** contexte et un
nouveau manifeste après inventaire des sources, si ces anciens arbres n'existent pas.

Noyau RMSE validé :
`44bc530a2ef1f91eb1e3b6ddd59e1d8cc9e069e30d92ac52b0eae0c1e7960e91`.
Les16empreintes de référence figurent dans
[audit_final.json](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/audit_final.json).
Le diagnostic du16octobre les a toutes revérifiées dans la racine avant analyse.

## 3. Ce qui est validé dans le code

Le correctif RMSE envoie les poids constants positifs valides vers la spécialisation
non pondérée. L'ancien corps du noyau est conservé à l'AST sous un nom privé.
Quatre régressions échouent avant et passent après ;49cas froid/froid donnent490tableaux
non concernés identiques au bit et392cas uniformes alignés, contre272écarts avant.

L'intégrationR5 ajoute trois modules :

- `certus/core/certus_strat_rate_moves.py` : génération générique des mouvements ;
- `certus/core/certus_strat_rate_post.py` : sélection des parents propres et recherche bornée ;
- `certus/workers/certus_strat_workers_rate.py` : raccordement à la notation native.

Les raccordements dans consensus, robustness, workers, pipeline et sonde sont conservés.
Les textes de mesure des deux leviers dans `certus_strat_leviers.py` parlent encore d'une
intégration « à mesurer » : cette description est en retard sur les preuvesR5/R6 ci-dessous.
La laisser identifiée comme dette éditoriale ; ne pas la prendre comme un échec de validation
ni réécrire les snapshots scientifiques pour la corriger dans cette passation.
`elite_rate_joint_candidates=0` et `rate_post_refinement=False` restent **inactifs par
défaut** ; `allow_rate=0` désactive les deux. Le post utilise seulement les parents
complets issus de son propre bras, sans ancien gagnant injecté : faisceau2, au plus
deux passes,300propositions par passe/600au total,73groupes incluant la renotation des
parents, arrêt après une passe sans gain. Le classement actif conserve les bases et
incomplets mais privilégie les consensus complets ; le classement inactif reste historique.

L'API `run_final_simulation_block(refine=False, expand_variants=False)` note des plans
fixés sans générationELITE. Le transport d'indices natif `SharedIndicesWorker` est en
float32 ; le remplacer par des indices directs avait déjà déplacé des points fixes.

Validation généraleR5 terminéeGO le15octobre22h29Paris, onze commandes sortie0 :
Ruff, Mypy des trois nouveaux modules, oracle1143, unité5450(7skipped), UI1324
(12skipped/2xfail), reste359, trois contrôles documentaires, C1froid8008tableaux
identiques au bit, `git diff --check`. Source et sorties dans
[full_validation_01](../reports/STRAT_Rate_suite_2026-10-15/R5_integration/full_validation_01/validation.json).
Ces résultats sont réutilisables pour leurs sources exactes, pas pour un futur correctif.

Le test de performance a reçu un initializer `numba.set_num_threads(1)` pour chaque
worker : le masque du thread principal ne s'hérite pas. Aucun seuil de performance
ni modèle physique n'a été changé pour rendre le test vert ; incident et contre-épreuve
restent dans `STRAT_RMSE_uniform_weights_2026-10-15/performance_failure_01`.

## 4. Résultats scientifiques retenus

SEEL = `2*sqrt(score)` en nm ; `n_samples` compte des scores/graines, pas les tirages.
Comparer des consensus homogènes, jamais un minimum mêlant base et consensus.

| Cas | Preuve retenue |
|---|---|
| Référence historique900951015, r75x0.5 |0,396714788219nm |
| Meilleur local historique9900008 |0,334515994638nm, neuf groupes historiques ; toujours meilleur |
| R3h01/h02 |Sans gain ; les trois pairesR3 sont épuisées, aucuneh04 |
| h03 automatique, graine101 |0,343112379987nm ; confirmation propre3/3, gain moyen5,2130%, pire perte0 |
| R5 intégré, graine101 |Même plan gagnant complet997550337, score0,02943152632503351 ; gain propre de recherche4,7171% |
| R6 r75x0.5/77 |Gains frais2,108274/1,052324/0,601626%, moyenne1,254075%, médiane1,052324%,3/3 |
| R6 r75x0.5/202 |1,416610/1,025283/1,424549%, moyenne1,288814%, médiane1,416610%,3/3 |
| R6 r75x0.5/404 |0,433049/2,473140/2,362340%, moyenne1,756176%, médiane2,362340%,3/3 |
| R6 48c/premium/77, recherche de fente1 |Même plan complet des deux bras,0nouvelle proposition, gains frais0/0/0% |

Le critère préfixéR6 était3/3victoires contre le propre meilleur consensus complet et
médiane≥1%. Les trois cas initiaux passent, avec des effets modestes. Les trois groupes
par cas ne donnent ni intervalle de confiance ni garantie de plantage nul. Aucun nouveau
meilleur global r75x0.5 ; les scores entre composants différents ne sont pas comparables.

CoûtsR6 :216appels frais à300tirages pour les trois cas initiaux ;12pour48c, donc228.
Les huit appels post natifs48c sont à150tirages, distincts des renotations fixes à300.
Les natifs contiennent plusieurs profondeurs : lire les tâches réelles, pas le seul champ
de configuration. Bilan complet dans
[bilan_final.md](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md).

## 5. Écarts R5/h03 : ce que les preuves permettent

Les mêmes parents900754638/900754520,37groupes,307entrées de plans complets et305propositions
du post sont retrouvés. Sur889tâches post comparables,239scores bruts diffèrent dans les
tolérances du protocole ; vecteurs de plantage identiques, écart maximal des consensus
agrégés2,5535e-15. R5 exécute997appels post :108de plus correspondent à36plans de quatre
groupes entièrement rejetés. Sans ancre finie de campagne, le repli historique les conserve
jusqu'au consensus ; tous restent inéligibles. Coût explicite, aucune accélération revendiquée.

L'identité globale native active **n'est pas prouvée** :29/123appels de génération diffèrent,
78461candidats contre78425dans la traceh03 et5463lignes finalesR5. La jointure exploratoire
large retrouvait15vecteurs de plantage différents/maxrel0,3081%, mais ne capturait pas tous
les paramètres locaux. Ce n'est ni une contre-épreuve physique contrôlée ni une cause de
cache établie. Lire
[post_numeric_audit_02.json](../reports/STRAT_Rate_suite_2026-10-15/R5_integration/post_numeric_audit_02.json).

Le nouveau diagnostic enregistré ajoute contexteELITE/tour, profondeur réelle, niveaux de
bruit et `compute_layer_profile`, et exclut les clés répétées au lieu de prendre leur
premier résultat. Il trouve87252paires uniques sous ces clés, dont8vecteurs de plantage
différents. **Cela ne résout pas la causalité** : les anciens observateurs n'enregistrent
toujours pas le dictionnaire complet des paramètres ni toutes les entrées optiques des tâches.
Ces comptes ont une autre jointure que l'audit01 ; leur différence ne mesure pas une correction.
[Résultat et SHA des deux traces](../reports/STRAT_Rate_followup_2026-10-16/diagnostic_01/recorded_audit.json).

Prochaine contre-épreuve utile : figer les arguments effectifs complets de quelques tâches
(plans, paramètres, épaisseurs, indices, grilles, matrices, cibles, graine, profondeur, bruit,
profils), puis noter **les mêmes entrées** dans deux interpréteurs et caches froids séparés,
avec les deux sources figées. Rapporter bits/écarts/vecteurs de plantage ; ne pas en déduire
une identité de toutes les branches natives ni une vitesse liée aux caches.

## 6. Cause du blocage48c et correctif à isoler

`window_context(plan, num_layers, "internal")` dans `certus_strat_rate_moves.py` prend
**la dernière fenêtre optique interne**, puis vérifie son bloc. Dans le finaliste48c :

- `[36,38)` traverse la limite37 entre deux blocs : rejet justifié de ce mouvement ;
- `[9,11)` est contenue dans le bloc `[5,11)` et satisfait aussi l'absence d'une autre
  fenêtre optique affectée par la même modification de longueur d'onde.

Le générateur actuel rejette le parent sur la première fenêtre ; il n'essaie pas l'autre.
`_stage_proposals` conserve quatre rejets `not_applicable` pour les deux parents et deux
étapes. La passe interne ne gagne rien et l'arrêt existant intervient avant la passe préfixe.
Il s'agit d'une limite du voisinage exploré, pas d'une preuve d'absence de meilleur plan48c.

Piste minimale : choisir la fenêtre interne admissible la plus profonde en examinant les
autres fenêtres avant d'abandonner. **À ce jour, ce correctif n'est pas écrit.** Garder les
contrats optique/Rate, les partitions complètes, fente, témoins et facteur de bruit ; ne rien
coder pour48c,75c,688nm ou une couche particulière. Ne pas confondre des plans à mêmes
fenêtres mais partitions différentes. Le repli vers la passe préfixe est un **autre facteur**,
à ne pas changer dans la même expérience.

## 7. Préparation actuelle : échec exact et reprise sûre

Scripts nouveaux dans `scratch/` :
`audit_rate_followup_recorded_20261016.py` (exécuté, RuffGO, zéroévaluation physique) et
`rate_followup_controlled_20261016.py` (RuffGO, préparation échouée, non vérifié).
Le second prévoit3plans × profondeurs25/50/300 × deuxcontextes =18tâches, graine101,
dans un plafond initial24tâches ; ce sont des diagnostics, pas des holdouts frais.

Commande tentée :

```powershell
python -X utf8 -X cpu_count=24 scratch\rate_followup_controlled_20261016.py prepare
```

Résultat : sortie1, `PermissionError: [WinError 5] Accès refusé` sur
`C:\Users\Lemarchand\.codex\worktrees\rate-r5-native\certus0310`, depuis
`scripts/bench_examples.py` lors de `os.chdir(ROOT)`. La préparation s'arrête à l'import,
avant `CertusStratApp`, avant claim, avant appel physique. `controlled_01` existe, sans
`manifest.json`. **Relancer le même `prepare` refusera ce dossier existant** : c'est voulu.

Conserver cet essai. Préparer une **copie nouvelle** du script et un dossier `controlled_02`
distinct ; vérifier l'accès Git/lecture/changement de répertoire au contexte externe via
les permissions normales de l'outil avant son exécution. Ne jamais corriger ce refus en
supprimant une réservation, en réécrivant un protocole ancien ou en substituant un arbre.
Le prototype doit encore être revu : intégralité/sérialisation des paramètres, conservation
des entrées, garde des appels et des ressources, refus réel de concurrence/rejeu, caches
froids et sauvegarde de tous les échecs. Un Ruff vert ne prouve pas son fonctionnement.

Les copies nécessaires et les empreintes sont regroupées dans
[le dossier de passation](../reports/STRAT_Rate_followup_2026-10-16/handoff_01/README.md).
`scratch/` est ignoré parGit : restaurer les scripts depuis ces copies contrôlées au besoin.

## 8. Ordre de reprise et critères de fin

1. Inspecter processus/verrous/claims avant toute action. Si parent ou enfant scientifique
   vit, ne lancer aucun Python d'analyse/test/préflight ; lire les fichiers vivants avec
   PowerShell `FileShare.ReadWrite|Delete` puis fermer aussitôt. Laisser finir le calcul.
2. Machine libre : `python scripts\preflight.py`, exiger `PREFLIGHT=GO`, puis lire
   CLAUDE/ETAT et ce diagnostic. Vérifier les SHA et les chemins de contexte, y compris
   les nouveaux fichiers non suivis. Ne pas relancer les anciennes campagnes.
3. Réparer et vérifier la préparation contrôlée dans une copie distincte, avant toute
   mesure. Figer manifeste/source/paramètres et réserver des slots réellement nouveaux.
   Une seule mesure ; Python `-X cpu_count=24` dès démarrage, affinité0xffffff, Normal,
   bibliothèques≤23. Aucun Python parent scientifique exempté ; seuls les services IDE
   installés exactement `pyright-langserver.exe --stdio` peuvent être traités comme tels.
4. Auditer les tâches contrôlées, puis corriger **seulement** le choix de fenêtre si les
   résultats permettent de continuer. Ajouter une régression qui échoue sur l'ancien
   code48c ; couvrir aussi le maintien du choix existant quand il est admissible et le
   rejet quand aucune fenêtre n'est admissible. Vérifier contrats et route inactive.
5. Faire la validation adaptée complète des nouvelles sources, oracle avant/après si
   calcul optique changé, C1 dans sa portée, diagnostics de typage, revue du diff. Les
   preuvesR5 précédentes ne valident pas automatiquement un nouveau générateur.
6. Une paire48c nouvelle au plus, facteur unique, mêmes sources et paramètres des bras
   sauf la sélection étudiée ; plans finalistes complets figés avant confirmation.
   Trois groupes frais nouveaux au plus,≤8plans par groupe, graines réservées avant
   inspection. Aucun ancien slot ou ancien contrôle détourné. Rapporter coût réel,
   moyenne/médiane/victoires/pire perte, rejets, nonfinis et consensus incomplets.
7. x1.5/x2 restent conditionnels à un bilan48c favorable et un protocole nouveau explicite.
   Aucun nouveau défaut scientifique activé. R7 attend des données machine quantitatives.

Pas d'autonomie nocturne ou de nouvelle échéance créée par la demande de reprise. L'ancien
suivi reste en pause. La limite historique du16octobre06:00UTC n'est pas déplacée dans
ses anciens lanceurs ; ceux-ci restent des archives interdites au rejeu.

## 9. Graines, quotas et incidents à préserver

Consommés : groupes historiques202–3535 ;17410001..04/11..14/21..24 ;175100mêmes suffixes ;
176100/176200/176300mêmes suffixes ;177100mêmes suffixes. Les graines77/202/404 servent
aux recherches natives, pas à une confirmation fraîche. Les24graines177200xx/177300xx
restent **réservées et non consommées** dans l'ancien programme clos : ne pas les présenter
comme un nouveau groupe indépendant déjà mesuré.

Après le ménage, un balayage des seuls JSON présents dans le checkout n'est plus exhaustif.
Consulter les manifestes de graines conservés et examiner aussi les archives pour justifier
qu'un futur groupe est réellement nouveau ; une absence dans `rg reports` seul ne suffit plus.

Incidents anciens conservés : sorties PowerShell manquantes adoptées après audit sans
inventer d'ExitCode ; handles conservés avant `WaitForExit` ; persistance atomique bornée
20×100ms/backup ; datesCLI ISO littérales ; SHA256.NET si nécessaire. Première préparation
fraîcheR6 échouée surLF/CRLF avant mesure, puis copiesv2 avec hashes des bytes réellement
écrits. Aucun de ces incidents ne justifie de répéter un slot consommé.

## 10. Nettoyage, publication et récupération des preuves

L'inventaire initial avant publication comptait 9 824 fichiers nouveaux, environ
51,13 Go. Ce volume venait surtout des JSON de campagne, pas du code de l'application.
L'utilisateur a choisi de conserver les archives brutes **localement, hors du dossier
CERTUS**, et de versionner le code, les bilans, les plans et les index SHA256.

À la préparation de cette passation, les suppressions déjà vérifiées sont :

| Éléments retirés | Volume brut en octets | Conservation |
|---|---:|---|
| 25 gros JSON | 7 638 513 848 | Archives gzip vérifiées |
| 2 074 autres JSON | 43 295 203 571 | Archives gzip dédupliquées vérifiées |
| 143 anciens JSON de simulation suivis | 1 454 648 386 | Archives gzip vérifiées, historiqueGit conservé |
| 17 988 fichiers de cache compilé / `.pyc` | 495 944 673 | Régénérables ; aucune source ni mesure |
| 40 répertoires de caches/HTML de couverture | 167 988 949 | Régénérables ; aucun code source |

Chaque JSON a été retiré seulement après vérification du SHA256 du brut, de l'archive
et de sa décompression. Les archives gzip vérifiées représentent environ8,053Go ;
elles sont horsCERTUS, avec l'ancienne copie.claude et les journaux runtime préservés.
Les mesuresINDEX/METAL/SINGLE et `studies/` restent en place.
**Il n'y a donc plus de copie brute décompressée garantie dans l'arbre.**
L'absence d'un JSON attendu par un ancien script signifie d'abord qu'il faut vérifier
les manifestes et le restaurer, pas relancer la mesure.

Les preuves du retrait et la correspondance des chemins figurent dans
[cleanup_large_01.json](../reports/STRAT_Rate_publication_2026-10-16/cleanup_large_01.json),
[cleanup_compact_01.json](../reports/STRAT_Rate_publication_2026-10-16/cleanup_compact_01.json),
[manifest.json](../reports/STRAT_Rate_publication_2026-10-16/manifest.json) et
[compact_manifest.json](../reports/STRAT_Rate_publication_2026-10-16/compact_manifest.json).

Le [dossier de publication](../reports/STRAT_Rate_publication_2026-10-16/README.md)
fait foi pour les lots de nettoyage supplémentaires, l'emplacement externe final des
archives, les commandes exactes de `scripts/restore_rate_evidence.py`, la taille finale
`.git` compris et l'état réel du commit/push. Ces opérations étaient encore en cours
lors de la rédaction de cette section : ne pas les considérer accomplies sur la seule
foi de ce texte. Ne pas restaurer tous les bruts dans CERTUS : les deux lots ci-dessus
réintroduiraient environ 50,934 Go. Vérifier les SHA et restaurer uniquement les fichiers
nécessaires à l'audit engagé, avec le sélecteur `--path` du restaurateur.

Les quatre scripts utiles ignorés par Git dans `scratch/` ont des copies contrôlées
dans [handoff_01/sources](../reports/STRAT_Rate_followup_2026-10-16/handoff_01/README.md).
Leur présence ne valide pas le prototype contrôlé. Une préparation, une vérification
du harnais et une mesure effectivement terminée sont trois états distincts.

## 11. Texte prêt à transmettre à l'IA suivante

```text
Reprends CERTUS à partir de docs/STRAT_Rate_reprise_20261016.md et de docs/ETAT.md §0.
Respecte CLAUDE.md. L'ancien programme R0–R6 est clos par arrêt précoce après 48c sans
gain ; quatre paires R6 ont été consommées sur six. Son automation reste PAUSED.
Ne relance aucun ancien contrôleur, slot, groupe ou protocole ; ne modifie aucun
contexte historique. Ne crée pas d'autonomie nocturne ou de nouvelle échéance.

La demande « continue la suite logique » autorise un diagnostic contrôlé R5/h03 puis
un seul correctif de sélection de fenêtre 48c et son évaluation conditionnelle, selon
reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json. Aucun correctif
scientifique n'est encore écrit et aucune nouvelle simulation n'a été faite depuis
la clôture. L'analyse enregistrée trouve 87 252 paires et 8 vecteurs de plantage
différents, sans établir une cause : les paramètres historiques complets manquent.
Le prototype controlled_01 a échoué à l'import sur PermissionError sandbox lors du
changement de répertoire vers le worktree R5, avant application, claim ou mesure.
Il n'est pas validé. Conserve cet échec et prépare une nouvelle copie contrôlée.

Inspecte les processus et verrous avant toute action. Machine libre : première
commande de travail Python, python scripts\preflight.py, avec PREFLIGHT=GO requis.
Une seule mesure scientifique à la fois, Python -X cpu_count=24 dès démarrage,
affinité 0xffffff, priorité Normal, bibliothèques au plus 23 threads. Aucun autre
Python d'analyse ou de test pendant une mesure, aucune source engagée modifiée,
aucun arrêt scientifique. Fige toutes les entrées effectives, sources et SHA,
plans complets, paramètres, graines et profondeurs ; utilise de nouveaux slots.
Le diagnostic initial est plafonné à 24 tâches physiques, 3 plans, 2 contextes.

Pour 48c, la fenêtre choisie [36,38) traverse une frontière de bloc ; [9,11) est
admissible. La piste minimale est d'essayer les autres fenêtres internes avant de
rejeter le parent, sans codage propre à un composant. Le repli vers le préfixe est
un autre facteur à ne pas ajouter. Régression rouge sur l'ancien code, validation
adaptée des nouvelles sources et revue avant mesure. Au plus une nouvelle paire
48c, puis trois groupes frais de huit plans uniques au maximum, réservés avant
inspection. x1.5/x2 restent conditionnels à un bilan 48c favorable ; R7 attend de
vraies données machine. Les options Rate restent inactives par défaut.

L'utilisateur a aussi demandé commit/push, nettoyage drastique et certus0310 sous
1 000 000 000 octets, .git compris. Il a choisi archives locales et dépôt Git léger.
Lis le bilan de reports/STRAT_Rate_publication_2026-10-16/ pour l'état réellement
livré, la taille finale et l'emplacement externe des archives. Les JSON retirés ont
été conservés sans perte et vérifiés par SHA ; restaure uniquement les preuves
nécessaires avec scripts/restore_rate_evidence.py et son sélecteur --path. Ne
remesure pas une preuve parce que son brut a été archivé. Ne présume ni le commit/push
ni l'objectif de taille terminés avant d'avoir lu leurs preuves finales. Tiens ETAT
§0 à jour et distingue préparation, harnais vérifié, mesure et conclusion scientifique.
```
