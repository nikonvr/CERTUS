# Rate : expertise de la régression et essais successifs (2026-10-13)

La répartition uniforme des familles à budget 120 dégrade le meilleur SEEL de **0,396715 à 0,479488 nm (+20,86 %)**
sur `r75x0.5 deep`, graine 101. Les deux runs ont la même source et les mêmes profondeurs de notation
(300 tirages complets, 50 au screening, consensus à 300). Le [rapport A/B](STRAT_Rate_equilibre_AB_2026-10-13.md)
conserve les plans et les artefacts complets. Le second run réutilise le cache : son temps plus court ne prouve pas une accélération due au code.

## Cause établie sur le chemin à 9 blocs

Le premier raffinement complet à 9 blocs reçoit **les mêmes dix parents** dans les deux runs.
Les 229 plans déposables avant ce raffinement sont conservés dans chaque artefact ; ils permettent de reconstruire
le filtre des signatures déjà présentes. Le script `scratch/expertise_rate_selection.py` extrait les fonctions réelles
par AST et appelle le générateur de candidats, sans noyau optique ni simulation. Il lit la grille du composant,
les parents réellement journalisés et leurs blocs/masques Rate dans les artefacts.

Au premier tour, le parent `990950004` porte Rate de L7 à L75. L'ordre actuel ouvre la fenêtre optique **L35–L36** :
le générateur reconstitue le candidat **`900950560` avec son identifiant exact**. Son SEEL enregistré est 0,478838 nm.
Il devient le premier parent au tour suivant. Au troisième tour, le meilleur plan `900951015`, à 0,396715 nm,
comporte aussi la fenêtre L11–L12 et garde L35–L36.

Avec l'équilibrage et le même plafond, l'ouverture L35–L36 n'est **pas générée**. Elle ne figure toujours pas dans
les 240 candidats Rate équilibrés ; elle réapparaît au plafond 360. Le mécanisme de perte est donc établi avant la notation.
Ce constat explique un chemin perdu ; il ne démontre pas qu'il explique seul toute la régression des autres passes.

| ordre / plafond Rate | extrémités | fenêtres de 2 | fenêtres de 4 | insertions Rate | ouverture L35–L36 de ce parent |
|---|---:|---:|---:|---:|---|
| actuel / 120 | 25 | 95 | 0 | 0 | présente |
| équilibré / 120 | 25 | 34 | 29 | 32 | absente |
| actuel / 240 | 25 | 201 | 14 | 0 | présente |
| équilibré / 240 | 25 | 84 | 80 | 51 | absente |
| équilibré / 360 | 25 | 144 | 140 | 51 | présente |

Résultats reproductibles : [reconstruction structurelle](STRAT_Rate_expertise_2026-10-13/selection_structurelle.json).
Les préfixes bruts de ce JSON ne sont pas les candidats effectifs : la reconstruction exacte du premier tour applique aussi
le filtre des 229 plans et les mutations optiques. Pour les tours suivants, le JSON expose seulement l'ordre structurel,
car les plans déjà présents évoluent. Ne pas attribuer aux préfixes bruts les identifiants du générateur complet.

## Hypothèses à tester, une variable par essai

1. **Élargir l'ordre actuel** : `elite_rate_max_candidates=240`, équilibrage désactivé. Les premiers candidats utiles restent
   proposés, et des fenêtres de largeur 4 entrent dans le budget. Le plafond d'évaluation complète reste 36 : générer un candidat
   supplémentaire ne garantit pas qu'il sera noté complètement ni qu'un ancien sera conservé après sélection.
2. **Approfondir le raffinement actuel** : `elite_rounds=6`, budget Rate 120, équilibrage désactivé. Chaque tour peut ajouter une
   fenêtre ou ajuster une frontière ; tester plus de tours peut aider à construire une alternance, sans changer sa physique.
   L'arrêt si aucun gain est trouvé reste actif ; six est un plafond, pas une promesse de six tours exécutés.
3. Selon ces résultats : équilibrage au plafond 360 pour séparer troncature et ordre ; réserve supplémentaire de mouvements
   diversifiés qui garde le voisinage utile ; choix conjoint d'une fenêtre optique et de sa longueur d'onde. Chaque nouvelle
   option reste inactive par défaut et demande ses vérifications de routage, de C1 et d'architecture avant mesure.

Les deux premiers essais emploient des paramètres déjà routés, sans nouveau changement des sources. Même instantané que le A/B,
graines, bruit et profondeur de notation conservés. [Campagne des pistes](STRAT_Rate_pistes_2026-10-13.md),
points de reprise et résultats dans `STRAT_Rate_pistes_2026-10-13/`.

## Travail autorisé pendant la nuit

👤 donne priorité à des essais successifs sur ce cas, y compris d'autres pistes, jusqu'à obtenir une amélioration,
et laisse la machine allumée jusqu'au **14 octobre à 9 h (Paris)**. A2 sauvegarde son calcul courant avant pause ;
son point de reprise est conservé. Une seule mesure à la fois, 16 processeurs logiques, priorité normale, 15 threads de bibliothèque.
Un suivi dans ce chat revient toutes les 30 minutes jusqu'à 9 h pour analyser les résultats et préparer la suite.
Les calculs actifs ne sont pas interrompus ; aucun nouveau calcul n'est lancé après cette échéance.

Une amélioration sur la graine de recherche n'est pas une validation générale. Rejouer les plans comparés sur des graines
indépendantes avec les mêmes perturbations et profondeurs avant de conclure ; garder les essais négatifs et les temps.

### Préparation de la validation indépendante (15 h 30, aucun rejeu lancé)

La référence complète est exportée dans [plans_reference.json](STRAT_Rate_expertise_2026-10-13/plans_reference.json),
avec ses blocs, ses 65 couches Rate, sa fente, son identifiant d'origine et le SHA256 de l'artefact source.
Le [protocole préparé](STRAT_Rate_expertise_2026-10-13/protocole_validation.json) impose d'abord un point fixe :
graine 101 et consensus 41/42/43, comme la mesure initiale. Puis les deux plans fixés doivent être comparés sur
les graines 202 et 303, avec consensus respectifs 202/203/204 et 303/304/305, à profondeur inchangée.
Changer seulement `robustness_seed` en gardant le consensus 41/42/43 ne rendrait pas les scores de consensus indépendants.

**Limite de routage constatée à la lecture du code :** `_resolve_injected_strategies` ne transmet que les blocs,
l'identifiant et l'origine ; il omet `rate_layers`, la fente propre au plan et les changements de témoin.
Cette entrée ne peut donc pas servir telle quelle à un rejeu des plans mixtes. Corriger et tester son routage ou
utiliser l'entrée existante `loaded_strategies` d'`ExternalEvaluationStrategy`, qui transmet les dictionnaires complets.
Dans les deux cas, vérifier d'abord le point fixe de référence, les masques et le score du plan original : le meilleur
plan régénéré d'un nouveau run ne remplace pas une comparaison de plans fixes. Aucun gain validé à ce stade.

### Reprise de 16 h : outil de rejeu préparé, non exécuté

`scratch/rate_fixed_replay.py` utilise `ExternalEvaluationStrategy`, avec les paramètres réels collectés par
l'application et son préalable nominal. Il transmet les dictionnaires complets des plans. Dans ce seul processus
expérimental, il appelle la notation existante avec `expand_variants=False` et neutralise la génération ELITE :
aucun enfant, aucune expansion Rate/fente ni secours Rate. Le calcul physique et le consensus restent ceux de CERTUS.
Le profil d'ablation, diagnostic sans effet sur les scores, est désactivé et consigné.

L'outil contrôle l'identité des blocs, Rate, fente et témoins, le nombre de plans, la profondeur et les graines réellement
résolues, ainsi que les trois échantillons de consensus. Son premier calcul doit reproduire le score de référence
0,039345655797984144, tolérance relative `1e-7`, absolue `1e-10` pour la gigue numérique observée ; ce contrôle
n'est pas une preuve C1 au bit. Les contrôles indépendants refusent de démarrer sans ce point fixe réussi sur les mêmes plans.
Utiliser un nouveau dossier de validation pour chaque paire de plans ; conserver les requêtes, résultats et échecs.

Ruff, analyse syntaxique et aperçu `--plan` passent. **Aucun test ni calcul de rejeu lancé pendant la mesure active.**
Le contrôle numérique reste donc à faire. Instantané du script :
[replay_external_prepared_v2.py](STRAT_Rate_expertise_2026-10-13/replay_external_prepared_v2.py), SHA256
`76a30697e0edea0f866959c015a147ba7dd248d41d9e911e73681aab697b62f4`.
Le premier instantané préparatoire est également conservé. Le script exige l'instantané source du A/B,
applique la limite à 16 processeurs et 15 threads de bibliothèque et refuse les contrôleurs concurrents
ou un nouveau calcul après 9 h. Le calcul `budget_240` continue normalement ; aucune mesure terminée à cette reprise.

### Résultat de budget 240 et validation différée (16 h 30)

L'ordre actuel à budget 240 termine en 39 min 57 s et donne **0,3828099733 nm** contre **0,3967147882 nm**,
soit **−3,50 %** sur la graine 101 ; 4 134 plans déposables contre 4 069. Artefact vérifié par le contrôleur :
mêmes sources et cache clé `caf88a3320c7`, profondeur 300/50/100/300, surcharges effectivement routées, verdict `OK`.
Il s'agit d'un gain apparent sur la recherche ; il reste sous la marge historique de discrimination de 8 % et doit être contrôlé.

Le plan `900851523`, à huit blocs, utilise l'optique L1–L6, L11–L14 à 451 nm, L32–L35 à 706 nm,
puis Rate jusqu'à L75. Il élargit et déplace les fenêtres par rapport au plan de référence à neuf blocs.
La profondeur de notation ne change pas. Sa durée avec cache réutilisé ne mesure pas une accélération de code.
Le [rapport des pistes](STRAT_Rate_pistes_2026-10-13.md) conserve le résultat complet.

La [paire fixée](STRAT_Rate_expertise_2026-10-13/plans_reference_vs_budget240.json) porte les plans complets,
les identifiants, scores attendus et SHA256 des artefacts. L'outil de rejeu contrôle maintenant les points fixes
**des deux plans**. Instantané [v3](STRAT_Rate_expertise_2026-10-13/replay_external_prepared_v3.py), SHA256
`f4a26bf3c82d8b79ae342c5d632a2faf96c4c514abbae8ba39f1c83490a2bcb9` ; versions antérieures conservées.

Le contrôleur `scratch/rate_validation_runner.py`, PID 41088, démarre à 16 h 35 mais ne calcule pas : il attend
la fin sauvegardée des deux essais paramétriques et la libération du contrôleur 38880. Puis il mesure successivement
`control`, `holdout_202`, `holdout_303`, à profondeur identique, et s'arrête si un point fixe ou un rejeu échoue.
Ruff, syntaxe et aperçu des commandes passent ; aucun test ni mesure en parallèle de `raffinement_6`.
Points de reprise et instantanés dans `STRAT_Rate_validation_budget240_2026-10-13/` ; aucun contrôle numérique mesuré à cette reprise.

### Contrôle réussi et suite (17 h)

Les six raffinements terminent en 43 min 47 s, à 0,387351 nm (−2,36 %) et 5 113 déposables. Le masque Rate de leur
meilleur plan est celui de référence ; la fenêtre L35–L36 passe de 706 à 705 nm. Budget 240 reste meilleur à 0,382810 nm.
La [reconstruction structurelle à huit blocs](STRAT_Rate_expertise_2026-10-13/selection_budget240.json) retrouve,
parmi les parents du troisième tour, le mouvement qui ouvre L11–L14 depuis `900850890` et mène à la géométrie du meilleur plan.
Son rang brut 175 ignore le filtre des signatures : il ne prouve pas à lui seul une exclusion au plafond 120.

Premier rejeu : échec strict conservé. `SharedIndicesManager` convertit les indices en `float32` pour le batch ; le
rejeu externe direct utilisait leur précision initiale. En reprenant ce transport **existant**, sans changer la physique
ni la tolérance, le nouveau rejeu reproduit les deux points fixes : nouveau score exact, référence à 5,8·10⁻¹⁶ près.
Puis les deux consensus indépendants confirment un gain de SEEL de **1,98 %** sur 202/203/204 et de **3,63 %** sur 303/304/305.
Le [rapport de validation](STRAT_Rate_validation_budget240_2026-10-13.md) détaille les scores, profondeurs,
masques et limites. Tout est conservé dans `attempt_02`, sans écraser le premier échec. Script v4 :
[instantané](STRAT_Rate_expertise_2026-10-13/replay_external_prepared_v4.py), SHA256
`144c358b4a57a1de23ac8e97ad7cb6e688c5f93ae23a87211ec27f6eafbd0aaf`.

L'essai `budget_360` commence à 17 h 11 min 36 s, contrôleur 32588, calcul 26580, même ordre et même profondeur,
une seule variable modifiée, ressources inchangées. Aucun rejeu concurrent ni changement de défaut scientifique.

Le choix conjoint est préparé **sans simulation** : [958 propositions](STRAT_Rate_expertise_2026-10-13/joint_window_proposals_v1.json),
SHA256 `462f48cacc0579316b1c9f45fef70de9afa623bd3024d55f3368f6e99e3b8409`.
Chaque proposition modifie une seule des deux fenêtres optiques du plan budget 240, reste dans son bloc et conserve
la partition : largeur 2/4/6, décalage −2/−1/0/1/2 si admissible, 40 λ sur la grille de contrôle. Les autres couches
gardent leur mode et leur λ. La recette distingue **22 changements de fenêtre seule, 78 de λ seule, 858 conjoints**,
pour comparer les effets sans introduire une autre physique. Le plan courant et la référence restent les ancres.
Graine de recherche 101 et consensus 41/42/43 ; les graines indépendantes ne servent pas à choisir ces propositions.
Source conservée : [prepare_joint_source_v1.py](STRAT_Rate_expertise_2026-10-13/prepare_joint_source_v1.py).
Ruff et génération structurelle passent. Outil de mesure par petits groupes, notation complète de chaque candidat,
conservation des rejets et contrôle des ancres à préparer avant calcul. Aucune mesure conjointe encore lancée.

### Outil conjoint préparé et attente (17 h 30)

`scratch/rate_fixed_replay.py` ajoute un mode de recherche expérimental, séparé des contrôles stricts. Il exige un contrôle
réussi des mêmes ancres et du même contexte. Chaque groupe garde au plus dix variantes et les deux ancres : toutes les
notations finies restent sous le plafond de consensus de 12. Les ancres doivent reproduire leurs scores dans chaque groupe.
Le nouveau mode observe les appels réels du noyau, sans changer leurs entrées ni leurs sorties, pour conserver les scores,
plantages, paramètres de tirage et statistiques par bruit des candidats rejetés avant le consensus. Chaque candidat reçoit
300 tirages complets ; les candidats finis sont re-notés sur 41/42/43 à 300 tirages. Un consensus incomplet n'est pas éligible.
Une exception de simulation fait échouer le groupe et conserve sa trace ; elle ne devient pas un rejet physique silencieux.

Rejeu préparé [v6](STRAT_Rate_expertise_2026-10-13/replay_search_prepared_v6.py), SHA256
`05376a9240c66a99a1f4f5bf1a7300045d13ed83ca0ed4a4f88300a73688a2c3` ; v5 et les contrôles antérieurs conservés.
Le contrôleur [préparé](STRAT_Rate_expertise_2026-10-13/joint_runner_prepared_v1.py), SHA256
`4d8c0f2d19bec1a17dfce8069ab2cf2a152154fceee9e540f83719266cd22ed3`, prépare 97 étapes :
un contrôle d'ancres, puis 96 groupes. Il garde les étapes terminées, les tentatives et les échecs, et vérifie les
empreintes des scripts, de la recette, des paramètres et du protocole. Aucun nouveau calcul après 9 h.

Ruff, syntaxe et aperçus des commandes passent. Revue manuelle : transport `SharedIndicesManager/Worker` identique au
contrôle validé ; import de la lecture d'artefacts avant la création de l'application pour conserver l'ordre de DLL et
le flux de console ; chaque groupe repasse le contrôle numérique. Aucun test ni mesure de cette extension pendant le
budget 360. Son premier contrôle runtime reste requis avant les nouvelles notes.

Contrôleur lancé à 17 h 40, PID 45024, affinité `0xffff`, priorité normale, 15 threads de bibliothèque au plus :
il **attend** le budget 360 (PID 26580), ne lance encore aucune simulation. État et instantanés dans
`STRAT_Rate_joint_window_2026-10-13/`, [rapport de suivi](STRAT_Rate_joint_window_2026-10-13.md).
Le meilleur résultat affiché pendant l'attente reste celui déjà mesuré à budget 240 ; ce n'est pas un résultat nouveau.

Les variations observées par 👤 sont entre dépôts ; le modèle n'introduit pas de dérive de vitesse intradépôt.
Ne pas ajouter du bruit inventé pour favoriser une méthode. Validation complète et revue restent requises avant commit ; aucun push autorisé.

### Budget 360 et recherche conjointe (18 h)

Le budget 360 termine à 17 h 52 min 57 s en 41 min 21 s, à **0,3828099733 nm** : même score exact et même masque Rate
que le budget 240, malgré 4 191 plans déposables et dix blocs au lieu de huit. Les partitions supplémentaires ne touchent
que des couches Rate. Le supplément de budget ne donne donc pas de gain sur cette graine.

Le contrôleur conjoint démarre après la sauvegarde du budget 360. Contrôle des ancres et notation observée réussis,
verdicts `OK`, aucune mesure concurrente. À 18 h 05 : 730 propositions sauvegardées ; candidat `9600579`,
optique L1–L6, L11–L14 à 451 nm et **L33–L34 à 630 nm**, SEEL **0,365338 nm**, soit −7,91 % contre la référence.
Ce résultat reste provisoire jusqu’à la fin des 958 propositions et au contrôle indépendant.

Le [protocole joint](STRAT_Rate_expertise_2026-10-13/protocole_validation_joint_v1.json), SHA256
`7e8d3bc107d3b51b5fec2cf390a6db652f5106576076a1d46e32d24c7c77f3b9`, ajoute les groupes
404/405/406 et 505/506/507 avant tout rejeu du vainqueur. Les groupes 202/203/204 et 303/304/305 sont conservés.
Ces groupes ne choisissent pas les candidats. Le rejeu indépendant est une copie du rejeu mesuré, avec seulement
les noms de ces deux nouveaux runs autorisés ; SHA256 `9bfe04e96215e11efce9be38a23463661386103e644fbf52af30430a175b9726`.
Le script de recherche en cours reste figé.

### Résultat conjoint et raffinement (18 h 13)

Les 958 propositions sont terminées à 18 h 08 min 43 s. Vainqueur `9600579`, 0,365338 nm : point fixe reproduit,
quatre groupes indépendants confirment un gain de 4,57 % à 7,13 % contre la référence, sans plantage observé.
[Contrôle, comparaison des mouvements isolés et limites](STRAT_Rate_validation_joint_2026-10-13.md).
La même fenêtre à 706 nm donne 0,426482 nm ; la même λ 630 nm sur l’ancienne fenêtre donne 0,902766 nm :
chacune seule dégrade, leur combinaison améliore. Le choix conjoint franchit donc un obstacle de sélection locale.

Le contrôleur 50136 lance une seconde recherche autour de ce plan : **1 753 propositions**, λ fines ±10 nm
et grille large conservée, 177 étapes, mêmes ancres vérifiées à chaque groupe, profondeurs et code inchangés.
Propositions SHA256 `c820393cbaeda4b43a6fd1fd2e976e72120d3e647a37cbabb0864dd9ff1643d9`.
Tout est figé dans `STRAT_Rate_joint_refinement_2026-10-13/`. Les groupes indépendants ne servent pas à classer ses candidats.
L’intégration à une recherche native complète reste à éprouver ; ces recherches locales sont centrées sur un plan connu.

### Reprise du raffinement et préparation native (18 h 30–18 h 45)

Le contrôleur 50136 échoue à 18 h 26 sur un `PermissionError` Windows : remplacement du rapport, puis du point de reprise.
Le calcul lancé du groupe 085 continue et termine avec verdict `OK` à 18 h 26 min 37 s. Pas d’arrêt de calcul scientifique.
Anciens JSON/tmp, rapport/tmp, trace et scripts conservés dans `STRAT_Rate_joint_refinement_2026-10-13/recovery_20261013_1830/`.
Le groupe est validé contre ses empreintes, sources et ancres, puis ajouté au point de reprise ; aucune mesure écrasée.
Les sauvegardes utilisent l’`atomic_open` existant et réessaient 40 fois un refus temporaire d’accès avant de propager un échec permanent.
Ruff et essai runtime simulant deux refus puis succès, ainsi qu’un refus permanent, passent ; aucun calcul actif pendant cet essai.
Reprise au groupe 086 par le contrôleur 24884. La durée récupérée du groupe 085 est une différence horodatage d’artefact/requête,
consignée comme telle ; la durée monotone du contrôleur disparu n’est pas inventée.

Adaptateur natif préparé dans `STRAT_Rate_native_joint_2026-10-13/`, contrôleur 32804 **en attente**. Après la fin sauvegardée
du raffinement, il vérifie le constructeur réel puis lance une recherche complète seulement si les contrôles passent.
Budget séparé de 480 candidats conjoints ; ancien ordre et budget Rate 120 conservés, autres plafonds et profondeurs inchangés.
Le générateur modifie une fenêtre existante et sa λ, widths 2/4/6, shifts ±2 ; λ déjà présentes chez le parent puis grille espacée
d’au moins 10 nm. Fenêtres et parents prennent leurs tours ; aucune λ ou couche gagnante écrite en dur dans le générateur.
Le constructeur original attribue identifiants et métadonnées, valide et déduplique ; ses candidats précédents restent le préfixe.
La profondeur et la sélection restent celles du pipeline réel : ajouter un candidat ne garantit pas son évaluation complète.

Le code de production ne change pas. L’adaptateur expérimental du processus, son générateur et le contrôleur sont empreints
dans les snapshots et la provenance de l’artefact. Les candidats offerts sont conservés dans un JSON séparé.
Option inactive à budget zéro. Ruff, syntaxe, aperçu et revue manuelle passent ; tests de routage **non encore exécutés**,
reportés après la mesure active. Aucun gain natif mesuré.

### Raffinement terminé, mesure native lancée (18 h 48)

Raffinement terminé à 18 h 47 min 36 s, 1 753 propositions : 559 consensus complets, 1 187 scores de base non finis,
7 consensus incomplets exclus. Aucun gain au-delà du plan `9600579` déjà contrôlé.

La vérification du constructeur réel s’exécute ensuite et rend `NATIVE_ADAPTER_VERIFY=GO` :
cinq contextes à option inactive rendent mêmes sorties, ordre, identifiants et curseur ;
préfixe historique inchangé à l’activation, contrats et métadonnées conservés, parents non modifiés,
patches restaurés ; la géométrie conjointe mesurée figure dans le budget sans condition sur son identifiant.
Preuve conservée dans `STRAT_Rate_native_joint_2026-10-13/adapter_verification.json`.
Ces contrôles portent le constructeur et son routage ; ils ne remplacent pas une validation numérique générale.

Mesure native lancée à 18 h 47 min 54 s, calcul 47776, contrôleur 32804 ; ressources 16/15, Normal, `0xffff` vérifiées.
Sources de production identiques aux mesures précédentes ; adaptateur SHA256
`861f8ac0406617b8e090ce26220b23e1a55b8ad7ef294962b35c5c4b4fe96d89`, générateur SHA256
`70211dc4fad1c1adabc673ffe95c35b8996459db4f75ecc8831454ff0e48c2af`.
Ce run part du pipeline complet et de ses parents, sans injecter un plan gagnant. Résultat encore inconnu.

### Reprise de 19 h et contrôle natif prévu

Le premier préflight relève E731 dans une archive du contrôleur **avant** sa correction ; le script actif est déjà corrigé.
L’archive devient `01_campagne_a2_runner.py.txt`, octets et SHA256 conservés, sans toucher les sources actives ni la configuration Ruff.
Déplacement décrit dans `recovery_20261013_1830/archive_relocation_1900.json`. Nouveau `PREFLIGHT=GO`.
Le calcul natif continue, ressources inchangées ; au deuxième tour à neuf blocs, 720 candidats dont 600 Rate
(120 précédents et 480 conjoints), évaluation complète plafonnée à 36. Le paramètre atteint bien cette étape du pipeline.

Le [protocole de confirmation](STRAT_Rate_expertise_2026-10-13/protocole_validation_native_v1.json), SHA256
`33974126d23f49d96e7393249c500f0d27aa882159b23be551cb23684c36c68c`, fixe aussi les groupes indépendants
606/607/608 et 707/708/709 avant inspection du vainqueur natif. Les quatre groupes antérieurs sont conservés.
Le rejeu [confirmation v2](STRAT_Rate_expertise_2026-10-13/replay_confirmation_prepared_v2.py), SHA256
`ff7945ef100234936381d84012310f1a73328a6ba9e15f53fa5ec092a2b2e6dd`, autorise ces noms de runs et observe
les appels physiques de chaque graine, sans changer les arguments ni le résultat. Les scores et plantages par bruit sont conservés.
Point fixe strict toujours requis avant les contrôles indépendants, tolérance inchangée.

Le contrôleur 21120 attend la fin sauvegardée de la mesure native. Puis il fige référence, meilleur local et vainqueur natif,
contrôle leur point fixe, puis les six groupes indépendants. Aucune mesure ni test pendant l’attente.
L’identifiant de rejeu natif est distinct pour éviter une collision avec les ancres ; l’original est conservé et le score
d’origine doit être reproduit (C2 impose des mondes indépendants de cet identifiant).
Scripts, paramètres, graines et empreintes préparés dans `STRAT_Rate_confirmation_native_2026-10-13/`.
Ruff, syntaxe et revue manuelle passent. Aucun nouveau rejeu encore effectué ; aucune conclusion native à ce stade.


## 19 h 30–19 h 48 — essai natif sans gain, reprise et six groupes indépendants

Le premier essai natif (480 voisins conjoints, Rate 120, trois tours par défaut) retrouve le plan de référence :
SEEL 0,3967147882 nm, score 0,03934565579798472, 4 092 déposables. 78 appels au générateur et 16 808
voisins conjoints proposés. Le budget de notation complète reste 36 ; offrir un voisin ne prouve pas qu’il est noté entièrement.

L’artefact scientifique est intact et identique dans le worktree et la copie, SHA256
`d8fcf45f8f9fbfcc8d237862f7af8ecfc51616d71dc27f9c0cfc3258138e60ae`.
Échec d’export ensuite : la trace conservait des références aux dictionnaires que le pipeline enrichit par un tableau NumPy
`slit_profile`. La trace de candidats en mémoire est perdue. Les scores, journaux, paramètres, compteurs et empreintes sont conservés.
Les anciens états, sources et journaux sont préservés dans `STRAT_Rate_native_joint_2026-10-13/recovery_20261013_1930/`.
La preuve de réconciliation constate l’absence de recalcul et la perte de trace ; les états sont complets après examen de l’artefact.
Les empreintes originales de cette mesure restent celles de son adaptateur v1, sans les remplacer par celles de la correction.

Correction de l’export expérimental : copie profonde des seuls candidats supplémentaires destinés à la trace, avant mutation
par le pipeline ; sauvegarde de l’état dans un `finally` même si l’export de trace échoue. Vérification hors mesure : cinq chemins
inactifs, préfixe historique, contrats, identifiants et routage inchangés ; mutation tardive des candidats sans pollution de trace,
sérialisation JSON possible. Preuve `adapter_verification_v2.json` dans le dossier de récupération.

Le contrôleur de confirmation initial, arrêté sur l’échec d’export, est préservé. `attempt_02` finit 7/7 OK.
La géométrie native égale exactement la référence ; son point fixe concorde, aucun doublon n’est ajouté au rejeu.
Les deux plans fixes sont référence/meilleur conjoint local. Profondeur 300 conservée et appels physiques observés pour chaque
run, chaque graine et chaque bruit. Aucun plantage observé. Les six groupes de consensus sont distincts de 41/42/43 qui a servi à la recherche.

| Groupe | Référence (nm) | Conjoint local (nm) | Gain |
|---|---:|---:|---:|
| 202/203/204 | 0,3968275691 | 0,3787066495 | 4,566 % |
| 303/304/305 | 0,3995131221 | 0,3710397323 | 7,127 % |
| 404/405/406 | 0,3997442250 | 0,3719660540 | 6,949 % |
| 505/506/507 | 0,3993888246 | 0,3712496806 | 7,046 % |
| 606/607/608 | 0,3928222059 | 0,3711503087 | 5,517 % |
| 707/708/709 | 0,3972990867 | 0,3696404409 | 6,962 % |

Deux derniers groupes fixés avant inspection du vainqueur natif. Protocole inchangé ; résumé avec empreinte de l’état dans
`STRAT_Rate_confirmation_native_2026-10-13/attempt_02/summary.json`. Limites : un composant, plans fixes, pas d’intervalle
de confiance formel, pas de validation globale ou machine. Le gain local ne prouve pas un gain de la recherche automatique.

Deux profils successifs préparés avec sources copiées et empreintes :
- `STRAT_Rate_native_joint_rate240_2026-10-13/` : seule variation, budget Rate 120 → 240, conjoint 480 et tours par défaut conservés.
- `STRAT_Rate_native_joint_rate240_round6_2026-10-13/` : seule variation suivante, plafond de raffinements par défaut → 6.

Premier profil lancé à 19 h 47 min 35 s, contrôleur 46404, calcul 12568 ; le second n’est pas lancé et dépendra de l’analyse.
Surcharges effectives constatées ; 16 processeurs, affinité 0xffff, Normal, 15 threads de bibliothèque. Vérifications de l’adaptateur
passées avant le calcul ; aucune mesure ni test en parallèle. Ordre des candidats historiques et plafonds de screening/complets conservés.
Hypothèse : un budget plus large peut fournir le parent utile, puis un tour supplémentaire peut explorer le voisin conjoint.
Cette explication n’est pas prouvée avant les mesures et la lecture de la nouvelle trace. A2 reste sauvegardée à 3/24.
Aucun noyau ni défaut scientifique de production modifié, aucun commit ni publication.


## 20 h 30 — budget Rate 240, puis six raffinements

Deuxième essai natif complet à 20 h 30 min 28 s : 42 min 52 s, 4 129 déposables,
SEEL 0,38280997329991634 nm, score 0,03663586891447066, id 900852003.
Les blocs, masque Rate, fente et score égalent exactement le budget 240 seul (id 900851523).
Gain contre la référence de 3,50499 %, aucun gain supplémentaire par les mouvements conjoints.
La comparaison est enregistrée dans `STRAT_Rate_native_joint_rate240_2026-10-13/budget240_comparison.json`.
Le plan fixe correspondant avait passé les groupes indépendants 202/203/204 et 303/304/305 ; pas de nouveau gain à confirmer ici.

Artefact SHA256 `f91d16af4e54d4f8874c7753596ea5610153191d92a5ad8a30c3db0292fe444b`.
Trace SHA256 `1bc10bfc108dbc8cd5fb6a596ebbc410508ffbb99f5afea38f84a2fc051057ee` :
78 appels, 17 770 candidats conjoints. Export corrigé réussi ; aucune perte de trace dans cette tentative.
La trace constate que le vainqueur n’est jamais parent d’un appel observé, son voisin local exact n’est jamais offert.
Le journal situe sa sélection après le troisième et dernier tour à huit blocs. Cela soutient l’hypothèse d’une étape supplémentaire,
sans prouver que cette limite est l’unique obstacle ni que le candidat aurait passé le screening.

Troisième essai natif lancé à 20 h 31 min 41 s, contrôleur 19656, calcul 37604, après fin des deux processus précédents.
Même budget Rate 240 et conjoint 480 ; seule variation : plafond des raffinements porté à six. Vérification de l’adaptateur
passée avant le calcul, surcharges effectives constatées. Dossier `STRAT_Rate_native_joint_rate240_round6_2026-10-13/`.
16 processeurs, affinité 0xffff, priorité normale, 15 threads de bibliothèque. Aucun test pendant cette mesure.
Tous les scripts actifs restent figés ; aucun défaut de production ni noyau modifié, aucun commit.
A2 reste à 3/24 et devra recevoir la limite de nouveaux lancements à 9 h avant reprise.


## 21 h — observation provisoire et confirmation préparée

Le journal à huit blocs montre le meilleur budget 240 (900852003) parmi les parents du quatrième tour, puis
900852938 à SEEL 0,3653 nm après ce tour, avec λ 630 sur le bloc de la deuxième fenêtre. Le calcul complet poursuit les blocs restants.
Ce n’est pas encore un résultat global sauvegardé. Preuve datée `health_20261013_2100.json` dans le dossier round6.

Confirmation v3 préparée et contrôleur 27636 en attente de la fin sauvegardée ; aucun rejeu ni test concurrent.
Point fixe strict puis huit groupes indépendants, dont deux nouveaux 808/809/810 et 909/910/911 prédeclared à 21 h 02.
Seules les listes de choix/runs et le nom affiché du vainqueur changent dans les copies v3 ; AST et revue statique,
aucun appel de physique modifié ni tolérance ajustée. Scripts, paramètres et protocole figés dans
`STRAT_Rate_confirmation_native_round6_2026-10-13/`.
Rejeu SHA256 `1ab91c3fc245e85887e511b4acdc18e7d0dbce27b99746f29b9eaba8920f2639` ;
protocole `7d864ee1416b251257743d718a45c178bb77176b8560678faadcaa199fe94d15`.
La confirmation attend l’état natif `complete` et l’absence du verrou de mesure ; elle ne commence aucune mesure après 9 h.
Les gains observés précédemment sur plans fixes ne sont pas confondus avec le résultat natif provisoire.


## 21 h 30 — gain natif confirmé, ablation en cours

Le profil 480 conjoints / Rate 240 / six tours termine vers 21 h 23, environ 52 min, 5 412 déposables.
Le résultat global dépasse le plan local observé à huit blocs : **SEEL 0,36006088633539163 nm**, score
0,032410960467156955, id 901054165, dix blocs. Optique L1–L6 à 632 nm, L11–L12 à 451 nm, L36–L39 à 691 nm,
reste Rate, fente 2 nm. Gain de 9,23936 % contre la référence, 1,44450 % contre le meilleur local sur le groupe de recherche.

Artefact SHA256 `944774e4d9ce471d2b2b561f1c6143f5c7be40207187d8ec280c338448cca6d9` ;
trace `78eacaa6451b5d7fac7a78070e82acf10dd02622339e312b8af0140a798227ec`.
124 appels, 38 410 voisins conjoints. Final lui-même absent des offres supplémentaires ; une même géométrie à préfixe 630,
id 901053250, est offerte et devient parent au tour 5. Le final emploie 632, mais une ressemblance ne suffit pas à prouver
sa filiation complète ni la contribution causale du générateur. Observations dans `lineage_observations.json`.
Une synthèse hors calcul a supposé à tort un vainqueur équivalent au local (`KeyError: native_same_plan_as`) ; l’état de
confirmation contenait correctement trois plans. Erreur et correction préservées dans `analysis_failure_2130.txt`, sans
altération d’une mesure ou d’un résultat. La synthèse corrigée traite explicitement le natif distinct.

Confirmation v3 terminée 9/9 OK : les trois points fixes passent, le natif conserve son score malgré l’identifiant de rejeu
9900000 (original retenu). Sur huit groupes indépendants, gain contre référence de **6,331 à 10,494 %**, aucun plantage
observé dans les appels enregistrés, profondeurs 300/50/100/300 inchangées.
Nouveaux groupes prédeclared : 808/809/810, 0,3632205049 contre 0,3961320607 nm (−8,308 %) ;
909/910/911, 0,3620838320 contre 0,4045376306 nm (−10,494 %).
Le natif améliore le meilleur local sur sept groupes, mais le dégrade de 0,677 % sur 707 ; ce dernier fait est conservé.
Un composant et des plans fixes, aucun intervalle de confiance formel ni validation générale ou machine.
Rapport et résultats complets dans `STRAT_Rate_confirmation_native_round6_2026-10-13/` et son `.md`.

Ablation préparée et lancée à 21 h 32 min 22 s, contrôleur 49780, calcul 1368 : **budget conjoint 480 → 0 seulement**,
Rate 240 et six tours conservés, code physique, ordre historique, profondeurs et plafonds inchangés.
Elle doit isoler le nouveau voisinage des deux paramètres existants combinés. Profil figé et sources dans
`STRAT_Rate_native_joint_ablation_rate240_round6_2026-10-13/`. Vérification de l’adaptateur avant calcul,
surcharges et ressources constatées : 16 processeurs, 0xffff, Normal, 15 threads de bibliothèque.
Aucun test ni autre mesure pendant cette ablation, aucun défaut scientifique activé, aucun commit.
A2 reste sauvegardée à 3/24 ; garde de l’échéance encore à ajouter avant sa reprise.


## 22 h 30 — ablation sauvegardée, comparaison de profondeur rejetée

Le profil sans voisins conjoints termine à 22 h 18 : SEEL exporté 0,3654948110 nm, 5 240 déposables,
45 min 46 s, zéro voisin conjoint. Artefact `d601d1e118e31773347586161c325a0c754e9ee41c43a1e6b09685f705dbfa5a`.
Le supplément brut apparent du conjoint est 1,48673 %, mais le contrôle strict l’invalide comme comparaison à profondeur homogène.

Point fixe à quatre plans, 22 h 32 : référence, local et natif conjoint passent ; ablation seule échoue.
Score de base 101 exactement reproduit : 0,03339661422533983, égal au score exporté. Consensus complet 41/42/43 :
0,03517507293183044 (moyenne 0,03500030484770064, écart type 0,0004993373832279904, trois échantillons).
Même paramètres 300/50/100/300 ne suffisent donc pas à prouver que chaque vainqueur a reçu la même notation effective.
Tolérance inchangée ; l’échec, les simulations brutes et les quatre plans sont dans `STRAT_Rate_validation_ablation_2026-10-13/`.
La synthèse brute avant audit est préservée, et la synthèse actuelle marque explicitement la comparaison causale invalide.
Le gain du natif contre la référence reste confirmé sur huit groupes ; la contribution incrémentale du nouveau code n’est pas établie.

Renotation de tous les 5 240 plans sauvegardés de l’ablation préparée, puis lancée à 22 h 37 min 09 s, contrôleur 51116.
Groupes de dix propositions avec deux ancres (référence et meilleur natif), 525 étapes ; aucune nouvelle stratégie générée.
Chaque proposition reçoit 300 tirages complets puis les trois consensus à 300 ; incomplets exclus, rejets conservés.
Les identifiants d’origine sont préservés, identifiants de rejeu distincts ; C2 et ancres reproduites dans chaque groupe.
`state.best` inclut l’ancre native : le meilleur de l’ablation doit être extrait séparément des résultats admissibles des propositions.
Limite : seuls les plans déposables sauvegardés sont disponibles ; les candidats non finis rejetés par le batch ne sont pas dans ce pool.

Contrôleur et moteur de rejeu existants réutilisés, seuls titre et libellé d’attente adaptés dans la copie du contrôleur.
Ruff, AST et aperçu des 525 étapes passent hors mesure ; aucune formule ni profondeur changée.
Propositions SHA256 `d0e1a708b5d71e54b29df2c102cfca02674f9c7e6b78337c78660a9024df48f1` ;
rejeu v6 `05376a9240c66a99a1f4f5bf1a7300045d13ed83ca0ed4a4f88300a73688a2c3` ; protocole v3 inchangé.
Dossier `STRAT_Rate_ablation_consensus_all_2026-10-13/`, scripts et sources figés, 16 processeurs, 0xffff, Normal, 15 threads.
Aucun test pendant cette mesure, aucun défaut activé ni intégration de production avant la comparaison, aucun commit.
A2 reste sauvegardée à 3/24 ; échéance des nouveaux lancements à ajouter avant sa reprise.


## 23 h — renotation normale et graines futures fixées

Contrôle 23 h 02 : 136/525 étapes sauvegardées, 1 350/5 240 plans renotés avec consensus complets, aucun échec.
Meilleur de l’ablation provisoire 0,3619390295 nm, originaire de 900752354 ; natif 0,3600608863 nm.
Ces valeurs ne constituent pas une attribution finale : le pool reste incomplet. Ancres reproduites, ressources et empreintes conservées.
Preuve `STRAT_Rate_ablation_consensus_all_2026-10-13/health_20261013_2300.json`.

Groupes futurs 1010/1011/1012 et 1111/1112/1113 fixés avant choix du vainqueur final de l’ablation.
Protocole v4 `protocole_validation_ablation_full_v4.json`, SHA256
`1a0ec42d04903427a97e2c8e719d19ad24c96a8450c073d32c451a8278984ec6`.
Il conserve les huit groupes précédents ; profondeur inchangée. Aucun rejeu indépendant encore lancé pour ce nouveau pool.
Aucun test ni autre calcul parallèle, aucun arrêt du calcul actif, aucun changement de production.


## 23 h 30 — progression et contrôleur de comparaison en attente

À 23 h 35, 311/525 étapes sauvegardées, 3 100/5 240 plans renotés, 3 099 consensus complets, un incomplet exclu.
Aucun échec du contrôleur, meilleur de l’ablation provisoire toujours 0,3619390295 nm. Ancres et ressources conservées.
Preuve `health_20261013_2330.json` ; aucun résultat nouveau justifiant un message utilisateur.

Validation comparative préparée, contrôleur 35012 en attente : fin complète du pool et absence du verrou requises.
Le minimum est choisi parmi les propositions admissibles, hors ancres ; son score et ses métadonnées sont contrôlés dans
l’artefact complet, puis référence/natif/meilleur ablation passent un point fixe strict et dix groupes indépendants.
Le protocole v4 conserve les huit groupes précédents et les deux groupes nouveaux fixés à 23 h 02.
Rejeu v4 : seule extension des noms de runs 1010 et 1111, appels physiques et tolérance inchangés.
AST et revue statique ; aucun test runtime pendant la renotation active.

Scripts figés et empreintes dans `STRAT_Rate_validation_ablation_full_2026-10-14/` :
rejeu `ab6ff3efffd465761f571be5021418e9c98d5e110d2370956eba1da4da0f5afa`,
contrôleur `024835cfaaaf3193001346cc52cf18b2ceb8cb36eea38c85527dc642ebc67f2f`.
État `waiting_for_pool`, aucun calcul indépendant encore engagé. Si une géométrie égale une ancre, elle n’est pas dupliquée
et l’état porte `ablation_same_plan_as`. 16 processeurs, 0xffff, Normal, 15 threads, une seule mesure à la fois ; échéance maintenue.
A2 conservée à 3/24, aucun défaut activé, aucun changement de production ni commit.


## 14 octobre, 0 h — renotation presque achevée

À 0 h 01, 455/525 étapes sauvegardées, 4 540/5 240 plans renotés, 4 538 consensus complets, deux incomplets exclus.
Aucun échec du contrôleur ; meilleur de l’ablation provisoire inchangé à 0,3619390295 nm, pool encore incomplet.
Les deux contrôleurs gardent 0xffff et Normal ; un seul enfant scientifique actif, validation 35012 toujours en attente.
Preuve `health_20261014_0000.json`, rejeu figé inchangé. Aucun test, autre mesure ou changement de production.
La validation comparative commencera après 525/525 et retrait du verrou ; aucune attribution nouvelle avant ses résultats.


## 14 octobre, 0 h 30 — contribution propre non confirmée, piste du préfixe

Renotation de l’ablation terminée à 0 h 13 min 57 s : 525/525 étapes, 5 240/5 240 plans, 5 238 consensus complets,
deux incomplets exclus. Meilleur originaire de 900752354, rejoué 9980047 : score 0,032749965266219656,
SEEL 0,3619390295 nm. Natif conjoint 0,3600608863 nm, avantage sur la recherche 0,519 %.

Validation 35012 terminée 11/11 OK : point fixe puis dix groupes indépendants. Le nouveau voisinage ne gagne que sur
4/10 groupes, médiane −0,800 %, moyenne −0,671 %, plage −3,973 à +2,856 %. Groupes frais : +0,162 % sur 1010,
−2,148 % sur 1111. Supériorité propre non confirmée ; pas d’intégration de production motivée par ce supplément.
Les deux plans gardent un gain contre la référence ; ablation 6,39 à 11,47 %, natif 6,33 à 10,49 %, sans plantage observé.
Un composant et des plans fixes ; anciens groupes désormais réutilisés pour orienter l’exploration, aucune validation générale.
Résumé et comparaison détaillée dans `STRAT_Rate_validation_ablation_full_2026-10-14/` et son rapport.

Nouvelle piste : coupler longueur du préfixe optique et λ de son premier bloc, sur les deux meilleurs plans à notation complète.
Les autres fenêtres, partition, fente et témoins restent inchangés. Préfixe de deux couches au minimum jusqu’à la fin du premier bloc,
λ des voisins préparés et grille fine ±10 nm autour du préfixe parent. Une seule fenêtre optique varie par proposition.
876 propositions : 748 couplées, 13 longueurs seules, 115 λ seules ; 89 étapes avec référence/natif comme ancres.
Validation hors mesure : contrat réel de tous les plans, première paire toujours optique, identifiants/géométries uniques,
seules couches du préfixe et première λ modifiées, parents préservés, fente/témoins conservés. `PREFIX_CONTRACT_VERIFY=GO`, Ruff et aperçu passent.

Graines fraîches 1212/1213/1214, 1313/1314/1315 et 1414/1415/1416 fixées avant notation des voisins.
Protocole v5 SHA256 `c8c480c032b2fb4578bbb01c2759b69974518a1f9e82c160a91b2a7a4b8d2d37` ;
propositions `e5e8da27bf02d7a70e520332a06274d26e1a2e42f969f09b146492532aef40bb`.
Contrôleur 52556 lancé à 0 h 37 min 53 s, `STRAT_Rate_prefix_joint_2026-10-14/`, sources figées, moteur de rejeu v6 inchangé.
16 processeurs, 0xffff, Normal, 15 threads ; aucun test pendant la mesure, aucun défaut activé, aucun noyau modifié ni commit.
A2 reste sauvegardée à 3/24 ; limite des nouveaux lancements à 9 h à ajouter avant sa reprise.


Note de provenance v5 : `prepared_utc` est hérité de v4 et ne date pas la création v5. La date effective du fichier et son
SHA256, enregistrés avant le lancement de 0 h 37 min 53 s, sont dans `protocol_preparation_time_note.json`.
Le protocole n’est pas modifié pendant la mesure. Contrôle en cours normal, aucun résultat nouveau ; ressources héritées vérifiées.


## 14 octobre, 1 h — préfixe amélioré, contrôle indépendant

Recherche terminée à 0 h 52 min 59 s, 89/89 étapes et 876/876 propositions. 563 consensus complets,
292 bases non finies et 21 consensus incomplets exclus ; tous les rejets sont conservés. Meilleur 9960194 :
L1–L5 optiques à 600 nm, autres fenêtres et partition du parent natif conservées. Score 0,031321786810495536,
SEEL 0,35395924517094074 nm ; gains de recherche 10,777 % contre référence, 1,695 % contre natif, 2,205 % contre ablation.
Artefact SHA256 `e9167e8f79c40906a1c5a6755f060922e8bbaaefe362b506d39766d16de54b3f`.

Confirmation lancée à 1 h 05 min 07 s, contrôleur 36380, dossier `STRAT_Rate_validation_prefix_2026-10-14/`.
Quatre plans fixes : référence, natif, meilleur ablation renoté et préfixe rejoué 9900002 (original retenu).
Point fixe strict puis groupes frais 1212, 1313, 1414 ; dix anciens groupes mesurés comme contexte réutilisé seulement.
Copie du moteur v4 vers v5 : seuls choix CLI étendus, identité AST hors ces choix vérifiée. Même physique, mondes C2,
transport float32, profondeurs et tolérance. Contrôleur séquentiel existant copié, contrôles des empreintes et appels
physiques renforcés. Ruff et aperçus passent hors mesure ; aucun test pendant le rejeu.
Rejeu SHA256 `1e1a932875863fb96161106dcd6a1a2ea4b9bd345afc6522a832fb0c7249c357`,
contrôleur `d450383fcea4976a852074d016167953e0d8a7409ee9ddaa3e9c2ab1621b9ad2`.
16 processeurs, 0xffff, Normal, 15 threads ; aucun défaut activé ni noyau modifié, aucun commit.
A2 conservée à 3/24 ; garde de nouveaux lancements à 9 h toujours à ajouter avant reprise.


## 14 octobre, 1 h 10 — préfixe confirmé sur groupes frais, recherche native

Confirmation complète 14/14 OK : quatre points fixes et treize groupes, dont trois frais.
Préfixe cinq couches/600 nm : sur les trois groupes frais, gain de 9,347 à 10,034 % contre référence,
1,754 à 3,041 % contre natif et 1,052 à 1,799 % contre meilleur ablation renoté. Aucun plantage observé.
Dix groupes réutilisés : dix gains contre référence/natif, neuf contre ablation ; une dégradation de 0,286 % est conservée.
Ces anciens groupes ont orienté l'exploration et ne constituent pas une nouvelle confirmation indépendante.
Rapport/table et résumé dans `STRAT_Rate_validation_prefix_2026-10-14/` et son `.md`.
Un composant et des plans fixes ; aucun intervalle de confiance formel ni validation générale/machine.

Comparaison isolée à même profondeur, parent natif 0,3600608863 nm : longueur seule cinq couches à 632 nm
→ 0,3634785466 nm ; λ seule 600 nm sur six couches → 0,3611984091 nm ; couple cinq/600 → 0,3539592452 nm.
Les deux mutations isolées dégradent le parent ; le couple améliore. Preuve `isolated_moves_comparison.json` du dossier préfixe.

Recherche STRAT complète lancée à 1 h 09 min 34 s, contrôleur 14820 et calcul 25072. Une différence avec le natif
480 conjoints / Rate240 / six tours : budget séparé 720 de voisins préfixe/λ, après tous les candidats antérieurs.
Fabrique originale utilisée pour validation/déduplication/identifiants/héritage. Grille régulière 10 nm projetée sur les λ
légales du contrôle ; ordre proche de la λ/longueur parent, parents entrelacés, aucune λ gagnante écrite en dur.
Budget préfixe expérimental nul par défaut ; aucun code de production modifié. Sources et plafonds de notation figés.

Vérification hors mesure `PREFIX_NATIVE_ADAPTER_VERIFY=GO` : cinq chemins inactifs identiques en candidats/ordre/IDs/curseur ;
préfixe historique/conjoint conservé à l'activation, contrats/Rate/λ/fente/témoins, parents immuables, trace indépendante
et sérialisable. Ruff passe après six PT018 d'assertions du nouveau vérificateur (source avant correction conservée).
Paramètres/sources/échec de lint et mesures dans `STRAT_Rate_native_prefix_2026-10-14/`.
Adaptateur SHA256 `f9601b7c564ca7386ed0ef88fc2a52fd02795781fa4df401667a6c8ad6fd4d41`,
générateur préfixe `bb3e6c85e868b9805712ecfc091f3fd005f425d133a83f0adcfaa7dc1c35e230`,
contrôleur `213a70208b6d48dc50ef9a2922c425dfae61bf6aa05afee7b0b4c842eb3b9309`.
Groupes frais 1515/1516/1517, 1616/1617/1618 et 1717/1718/1719 fixés avant cette recherche native.
Protocole v6 SHA256 `09b7f40d016b9c516c23e5e30c968ae4a5a3d6b9cbd2b0d8dfe5415ed688dccf`.
16 processeurs, 0xffff, Normal, 15 threads ; une mesure, aucun test pendant le calcul. A2 reste à 3/24.
Aucun défaut activé, aucun noyau modifié, aucun commit ni publication.


## 14 octobre, 1 h 30 — calcul natif normal, confirmation en attente

Contrôleur 14820 et calcul 25072 actifs, 0xffff/Normal ; progression jusqu'à dix blocs, aucun résultat global terminé.
PREFLIGHT=GO, empreintes des scripts natifs inchangées ; A2 toujours sauvegardée à 3/24. Aucun test ni autre mesure.
Preuve `STRAT_Rate_native_prefix_2026-10-14/health_20261014_0130.json`.

Contrôleur 21248 mis en attente à 1 h 32 min 05 s. Il attend le contrôleur natif complet, l'artefact sauvegardé et le verrou retiré.
Point fixe strict du nouveau vainqueur et des quatre comparateurs, puis groupes frais 1515/1616/1717 et treize anciens
groupes comme contexte réutilisé. Un score natif exporté seulement de base doit faire échouer ce point fixe, sans
relâcher la tolérance ; aucune affirmation de gain incrémental avant ce contrôle.
Moteur v5 → v6 : seuls choix CLI étendus, AST des appels physiques identique. Copie du contrôleur séquentiel existant,
comparateurs et lecteur d'artefact figés ; Ruff et revue statique passent, aucun test runtime pendant le calcul natif.
Scripts/protocole/empreintes dans `STRAT_Rate_confirmation_native_prefix_2026-10-14/`.
Rejeu SHA256 `dbcdd6e24103675db50d0f8e6948cb419d471c3a5cbaacbee0921e7e5aee0778`,
contrôleur `9a8da6f704029da399eedc2c68946cadf4518bc103f1105c37115c50cc17c224`.
16 processeurs, 15 threads, limite des nouveaux lancements à 9 h. Aucun défaut activé ni noyau modifié, aucun commit.


## 14 octobre, 2 h — calcul natif normal, grille fine en attente

PREFLIGHT=GO. Calcul natif 25072 jusqu'à deux blocs, contrôleur 14820 actif ; confirmation 21248 toujours en attente.
Une seule mesure, 0xffff/Normal, 16 processeurs et 15 threads ; empreintes des scripts inchangées. Aucun test ni résultat
global nouveau. Preuve `STRAT_Rate_native_prefix_2026-10-14/health_20261014_0200.json`.

Raffinement de la λ du préfixe fixe L1–L5 déjà confirmé préparé : ±20 nm autour de 600 sur grille 1 nm,
36 λ nouvelles après exclusion des candidats exactement déjà mesurés. Seule la première λ varie ; autres fenêtres,
Rate, partition, fente et témoins conservés. Deux ancres strictes : référence et meilleur préfixe. Cinq étapes séquentielles.
Contrôleur 46612 en attente depuis 2 h 02 min 18 s : confirmation native complète et verrou retiré requis ; un échec
du point fixe natif empêchera ce raffinement, jusqu'à audit explicite. Code du contrôleur de recherche précédent copié,
seuls titre et prérequis changés, moteur de rejeu v6 inchangé. AST et Ruff passent, contrat réel contrôlé par le rejeu
avant chaque notation ; aucune vérification runtime concurrente à la mesure native.

Groupes frais 1818/1819/1820, 1919/1920/1921 et 2020/2021/2022 fixés avant toute notation fine ; les groupes précédents
sont désormais du contexte réutilisé. Dossier `STRAT_Rate_prefix_lambda_fine_2026-10-14/`, sources et paramètres figés.
Propositions SHA256 `cd0baa2c7a62d3838034a9d0c8d36ae7ff53415836819861d05aa500379bf4b3`,
protocole v7 `8b572e6c0955338d1464c7f01cbd9d51df6d48d9ebfc2e00c951ae5c79c0e9b2`,
contrôleur `7fca73e4b02b6ce17891caa17d75da273aeafcb854b19a7c8d9aacd4bc209fce`.
A2 reste à 3/24, aucun défaut scientifique activé, aucun noyau modifié, aucun commit ni publication.


## 14 octobre, 2 h 30 — reprise des contrôleurs, audit natif, gain fin non confirmé

Recherche native préfixe terminée à 2 h 08 min 06 s, environ 58 min 32 s, 5 119 déposables.
120 appels, 36 358 voisins conjoints et 47 615 voisins préfixe ; trace conservée. Meilleur exporté 901457827, 14 blocs,
SEEL 0,36429738905579667 nm, score 0,03317814691821762.
Artefact SHA256 `85f5c3f221214d459460b57975c998ec34366eda5e644ecd1f52730666cb8472`,
trace `1dd162a35eee96e850cdfac4cc9cdc9f86339ace2d9ed99009a848639fb23baf`.

Le contrôleur de confirmation a échoué avant toute mesure : le snapshot préparatoire des comparateurs a été nommé
`plans.json`, nom réservé à son futur export scientifique exclusif. Erreur évitable de préparation ; tous les fichiers
initiaux conservés. Nouvelle tentative `attempt_02`, snapshot renommé `baseline_plans_snapshot.json`, contrôleur 14948
lancé à 2 h 31 min 36 s. Aucun natif recalculé, aucune ancienne donnée écrasée.
Point fixe strict : les quatre comparateurs passent, natif seul FAILED_REPLAY. Base 101 exactement égale à l'export,
consensus 41/42/43 0,03336799909407186, SEEL 0,36533819452157945 nm. Tolérance inchangée.
Erreur, résultats par bruit et diagnostic dans `STRAT_Rate_confirmation_native_prefix_2026-10-14/attempt_02/`.
Il s'agit encore d'un score de base mêlé à des consensus dans le classement exporté ; pas d'attribution causale avant renotation.

Grille fine initialement arrêtée après l'échec du prérequis, sans mesure ; nouvelle tentative 24552 à 2 h 32 min 34 s.
Le prérequis devient le préfixe déjà confirmé à profondeur complète (14/14), après fin de l'audit natif. Aucune modification
des 36 propositions, physique, profondeur ou tolérance. Verrou résiduel PID 22496 de cette ancienne campagne, absent du système,
conservé sous un autre nom après vérification de l'état complet et de ses 14 runs ; preuve `stale_lock_reconciliation_0235.json`.
Grille fine complète 5/5, 36/36 consensus complets : meilleur 9950016, L1–L5 à 598 nm, score 0,030945697580483572,
SEEL 0,35182778503400536 nm (gain de recherche 11,315 % contre référence et 0,602 % contre 600).
Artefact SHA256 `145e4f2392f3cc0d449399a6a55a0a0b2d5e9df40a886b829feb420ca0f12325`.

Confirmation fine 30360, lancée à 2 h 36 min 56 s, terminée 4/4 OK : cinq points fixes puis groupes frais
1818/1819/1820, 1919/1920/1921, 2020/2021/2022. Gain fin contre 600 respectivement −0,7963 / −0,2510 / +0,7043 %,
1/3 favorable, moyenne −0,1143 %, médiane −0,2510 %. Supplément non confirmé, 600 reste le plan retenu.
598 garde un gain contre référence de 8,135 à 11,054 %, aucun plantage observé. Rapport/table et résumé dans
`STRAT_Rate_validation_prefix_fine_2026-10-14/` et son `.md`. Moteur v7 : seuls choix CLI étendus, AST physique identique,
Ruff passé avant la mesure. Un composant, plans fixes, trois groupes frais, pas de validation générale/machine.

Renotation intégrale du pool natif préfixe préparée puis lancée à 2 h 37 min 46 s, contrôleur 42128, après confirmation fine
complète : 5 119 plans, 513 étapes, aucun nouveau plan généré. Deux ancres strictes référence/préfixe 600 et dix propositions
par groupe, base300 + trois consensus300 ; incomplets exclus, tous rejets et IDs originaux conservés. Moteur v6 inchangé.
Dossier `STRAT_Rate_native_prefix_consensus_all_2026-10-14/`, propositions SHA256
`d4901cc4b2a71206c2bfd62ff10a7804c3060a0b3e0363bf0a4623aa22b85f75`,
contrôleur `13c5d76114bb05ef90e6af95e9066288b1c93ac57938e36bb14f5c0e6d25392a`.
Groupes 1515/1616/1717 prédeclared avant natif toujours non mesurés ; ils serviront au meilleur après pool complet.
`state.best` inclut l'ancre 600 ; meilleur natif à extraire parmi les propositions admissibles seulement.
Limites : uniquement les déposables sauvegardés ; pool natif antérieur sans préfixe supplémentaire non intégralement renoté,
pas d'attribution complète depuis le seul meilleur connu. 16 processeurs, 0xffff, Normal, 15 threads, une seule mesure.
Aucun test pendant la renotation, aucun défaut activé, aucun noyau modifié, aucun commit. A2 reste sauvegardée à 3/24.


## 14 octobre, 3 h — renotation normale, confirmation du pool en attente

PREFLIGHT=GO ; contrôleur 42128 et un seul enfant de rejeu actifs, 0xffff/Normal, 16 processeurs et 15 threads.
Point de reprise à 3 h : 123/513 étapes, 1 220/5 119 plans renotés, 1 220 consensus complets. Meilleur natif provisoire
0,3630828420 nm, originaire de 901454694 ; ancre 600 à 0,3539592452 nm. Pool incomplet, aucun nouveau gain ni conclusion finale.
Empreintes inchangées ; preuve datée `STRAT_Rate_native_prefix_consensus_all_2026-10-14/health_20261014_0300.json`.

Confirmation du meilleur natif de pool complet préparée et mise en attente à 3 h 01 min 50 s, contrôleur 7984.
Minimum des propositions à consensus complet hors ancres après 513/513 ; score/métadonnées/artefact vérifiés. Point fixe
strict puis trois groupes frais 1515/1616/1717, face à référence, natif conjoint, ablation renotée, préfixe600 et fine598.
Identifiant de rejeu 9900005, originaux retenus ; équivalences exactes sans doublon. Même moteur physique v7 et tolérance.
Contrôleur du pool précédent copié avec comparateurs/nom/ID/sequence adaptés. Ruff et AST passent, revue statique,
aucune vérification runtime pendant le calcul. Snapshots de comparateurs nommés `baseline_plans_snapshot.json` pour
laisser libre le nom de l'export scientifique. Dossier `STRAT_Rate_validation_native_prefix_pool_2026-10-14/`.
Contrôleur SHA256 `6efbc17a4578316727f086617591bbb3e7c52d893d025fca0346fa93738b6829`,
rejeu v7 `210b9ab4de1c72dccd545e3019bdcec8e6960b9a41235b8d9ddc7543920b4130`.
Aucune attribution complète par comparaison au seul meilleur du natif antérieur dont le pool n'a pas été entièrement renoté.
A2 reste à 3/24 ; aucun défaut activé, aucun noyau modifié, aucun commit ni publication.


## 14 octobre, 3 h 30 — renotation normale, fenêtres internes préparées

PREFLIGHT=GO. À 3 h 35, 308/513 étapes, 3 070/5 119 plans renotés, 3 070 consensus complets, aucun échec.
Meilleur natif provisoire inchangé 0,3630828420 nm ; ancre600 0,3539592452 nm, pool incomplet.
Contrôleur 42128 et un seul enfant scientifique, 0xffff/Normal, 16 processeurs et 15 threads ; confirmation7984 en attente.
Empreintes inchangées, preuve `STRAT_Rate_native_prefix_consensus_all_2026-10-14/health_20261014_0330.json`.

Piste suivante préparée autour du parent préfixe600 déjà confirmé, sans modifier ce préfixe : une fenêtre interne
(position et longueur) avec sa λ à la fois. Longueurs1..7, donc impaires incluses, shifts−3..+3 bornés au bloc courant ;
grille450..750 par10nm et ±10nm à1nm autour de la λ du bloc. Autre fenêtre, partition, fente et témoins conservés.
3 133 propositions : 2 977 conjointes, 67 fenêtres seules, 89 λ seules ; 315 étapes avec référence/préfixe600 comme ancres.
Parent figé, ne sera pas remplacé silencieusement par un résultat du pool natif futur.

Contrôleur42024 en attente depuis3 h35 min27 s de la confirmation native complète. Il exécutera ensuite, hors mesure,
la vérification des 3 133 plans par la vraie fonction du worktree : contrats, signatures/IDs uniques, modification exacte
d'une seule fenêtre/λ, première paire optique, préfixe et métadonnées conservés. Puis seulement commencera la notation.
Ruff, AST et revue statique passent ; aucun test runtime pendant la renotation active. Même moteur de rejeu v6,
physique/profondeur/mondes/tolérance inchangés. Dossier `STRAT_Rate_window_widths_2026-10-14/`, paramètres et sources figés.
Propositions SHA256 `0aaa42e64093bd3403cfbc333305f80ade3c1eb8def6c4421f29e2a89856e1ba`,
contrôleur `42adf21927c38ecf757caccd091ca21102aef8a8d4e3866003178dd6a99f154a`,
vérificateur `83656e032d0cfc2f09a535a9c1380ef94afeb3167c53158d87cfa559463c8a87`.
Groupes frais2121/2122/2123,2222/2223/2224 et2323/2324/2325 fixés avant le premier score de ce voisinage.
Protocolev8 `49f10d3eae437251b7e6dddfdbddf700ef02689d5496c0bf2149f5b9c0cc37a2`.
Une seule mesure, aucun arrêt, aucun défaut activé, aucun noyau modifié ni commit. A2 reste sauvegardée3/24.


## 14 octobre, 4 h — fin de renotation proche, garde A2 préparée

PREFLIGHT=GO. À 4 h 03 : 460/513 étapes, 4 590/5 119 plans renotés, 4 589 consensus complets et un incomplet exclu.
Aucun échec du contrôleur ; meilleur natif provisoire toujours 0,3630828420 nm, ancre600 0,3539592452 nm.
Pool incomplet, aucune conclusion finale. Empreintes inchangées, 16 processeurs, 0xffff, Normal et 15 threads ;
un seul enfant scientifique, confirmation7984 et fenêtres42024 en attente. Preuve `health_20261014_0400.json`.

Copie A2 nocturne préparée sans lancement, `scratch/campagne_a2_deadline_runner.py`. Une garde ajoutée à la seule
frontière de création du prochain calcul : plus de lancement à partir du14 octobre7 hUTC /9 hParis. Une mesure
adoptée déjà engagée reste attendue jusqu'à son terme. Original partagé inchangé, SHA256
`77e26f57341c198830e5ed8b19e072b94285eb24f5ed2cdd2e78dadf378f7e51` ; aucun contrôleur Rate actif modifié.
Après retrait de la garde/importUTC, AST de chaque instruction ancienne identique ; Ruff passe. Validation runtime
différée à la première période sans mesure, avant reprise A2. Snapshot/protocole dans `A2_deadline_preparation/`,
copie SHA256 `52aee00f5ff49e0c93dd5fcacab418354cb4774952c92d428334e1f17e6c40e6`.
A2 reste à3/24, prochain `r75x1.5_deep_s101_sans`, point de reprise intact. Aucun test pendant la renotation,
aucun défaut activé ni noyau modifié, aucun commit ni publication.


## 14 octobre, 4 h 30 — pool natif terminé, fenêtres en cours

PREFLIGHT=GO. Pool natif préfixe terminé à 4 h 12 min 29 s : 513/513 étapes, 5 119/5 119 plans,
5 118 consensus complets, un incomplet exclu. Meilleur original901454694, rejoué9940095, score0,03295728754388596,
SEEL0,36308284202857044 nm. Artefact SHA256 `8910dc02338f24370829bd8e461e3051f2e22f192377f75f9cf6df3c5b73d3cd`.
Ancre600 reste meilleure sur la recherche. Résumé final du pool conservé.

Confirmation7984 terminée à 4 h 13 min 19 s, 4/4 OK : six points fixes puis groupes frais1515/1616/1717.
Natif préfixe contre600 : −5,026 / −3,368 / −1,962 % ; contre natif joint connu : −1,737 / −0,649 / −1,521 %.
Aucun plantage observé. Cet ajout de voisins pendant ELITE n'améliore pas le meilleur plan connu ; aucun défaut activé.
Limite : ancien pool joint non entièrement renoté, donc pas d'attribution causale exhaustive, comparaison des plans fixes
effectivement contrôlés seulement. Table et résumé dans `STRAT_Rate_validation_native_prefix_pool_2026-10-14/`.

Fenêtres internes42024 démarrées après ce contrôle complet. Les 3 133 plans passent la vraie validation du worktree,
signatures/IDs et portée exacte d'une fenêtre contrôlés avant notation (`WINDOW_TRIALS_VERIFY=GO`).
À 4 h 43 : 186/315 étapes, 1 850/3 133 propositions, 735 consensus complets ; ancre600 toujours meilleure.
Pool incomplet, aucune conclusion nouvelle sur ce voisinage. Un seul enfant scientifique, 0xffff/Normal,
16 processeurs et15 threads, empreintes inchangées ; preuve `STRAT_Rate_window_widths_2026-10-14/health_20261014_0430.json`.
Aucun test pendant la mesure.

Confirmation21828 en attente depuis4 h41 : minimum complet après315 étapes. Si aucun voisin ne bat600, termine
sans mesure indépendante inutile (ancres déjà reproduites chaque groupe). Si gain, nouveau point fixe et groupes
frais2121/2222/2323 contre les six comparateurs. Rejeu v8 : seuls choix CLI étendus, AST physique identique v7/v8,
Ruff et revue statique passent. Dossier `STRAT_Rate_validation_window_widths_2026-10-14/`.
Contrôleur SHA256 `c772250a68c1477ae02776522a74c9aa030888664eca1b4505f48e779cae205f`,
rejeu `8a7adefe3e87823be76d2e70c6f8da3762a5f8386da0bb2c2b5e6c846a6bb901`.

Piste suivante seulement prédeclared, pas de code lancé : combiner les douze meilleurs candidats complets de chaque
fenêtre interne après recherche mono-fenêtre et contrôle, classement par score101 puisID, au plus144 combinaisons.
Préfixe600 et autres métadonnées conservés ; aucun rang issu des holdouts. Groupes frais2424/2525/2626 fixés avant
notation de ces couples, avec graines de consensus consécutives. Politique et protocolev9 dans
`STRAT_Rate_window_pairs_2026-10-14/`, SHA256 `672ad408e2652a30c4cc8446d596b04707ad6972783cc13e9678801612a0a2bf`.
Code/contrats encore à préparer et vérifier avant mesure. A2 conserve3/24 et sa garde9 h préparée, non lancée.
Aucun défaut scientifique activé, aucun noyau modifié, aucun commit ni publication.


## 14 octobre, 5 h — fenêtres confirmées, couples rejetés, dernier voisinage

PREFLIGHT=GO. Fenêtres internes terminées à 5 h 03 min 57 s : 315/315 étapes, 3 133/3 133 propositions,
1 194 consensus complets admissibles et 1 939 exclus conservés. Meilleur9932265, repris9900006 :
L35–L37 à688 nm, préfixe L1–L5 à600 nm et fenêtre L11–L12 à451 nm conservés. SEEL0,3409240518 nm,
gain14,0632 % contre référence et3,6827 % contre préfixe600 sur recherche101. Artefact SHA256
`3d8fb6f61a2f2f76be24f139cf5c0f66c51f4e65c8230b946186c8a1809d3261`.
Confirmation21828 complète à5 h04 min40 s : 4/4 OK, sept points fixes stricts puis groupes frais2121/2222/2323.
Gains contre référence13,7182 /14,2192 /14,7364 %, contre600 3,9453 /4,3233 /5,1984 %, aucun plantage observé.
Mouvements isolés : fenêtre L35–L37 à691 →0,3459403805 nm ; λ688 seule sur L36–L39 →0,3624981294 nm.
La fenêtre seule améliore, λ seule dégrade ; leur combinaison apporte un gain supplémentaire. Résumé/table conservés.
Gain de plan fixe sur un composant : aucune preuve que l’ajout natif ELITE retrouve automatiquement ce plan,
pas de validation machine ni d’intervalle de confiance formel. Aucun défaut activé.

Couples préparés selon la règle fixée à4 h41 avant leur notation : top12 uniques complets de chaque fenêtre,
rang sur101 puisID, produit cartésien144, préfixe600 figé. Les24 sources ont un consensus vérifié dans leurs
artefacts. Tous144 contrats réels, signatures/IDs, composition exacte et métadonnées passent avant mesure
WINDOW_PAIRS_VERIFY=GO. Premier essai de contrat refusé par sandbox sur chdir du worktree, second avec
chemins relatifs après ce chdir introuvables, troisième à chemins absolus passe ; sources inchangées, causes
conservées. Aucun Monte Carlo avant validation. Ruff/revue manuelle passent ; seuls choix CLI du rejeu v9
étendus, AST physique identique àv8. Propositions SHA256
`9a3162a3b9c954da51b4061eeca7777ed14e43e7d060357c6a040f4536c701bf`, protocolev9 déjà figé.
Contrôleur35728 terminé5 h12 min16 s, 16/16 étapes et144/144 consensus complets.
Meilleur9920025 repris9900007, L11–L12 à450 etL35–L37 à689 nm, SEEL0,3360076100 nm,
gain apparent15,3025 % contre référence et1,4421 % contre fenêtre688. Confirmation38128 complète
5 h13 min05 s, 4/4 OK : huit points fixes puis groupes frais2424/2525/2626, aucun plantage observé.
Le couple perd face à688 sur les trois groupes frais de1,3879 /0,3543 /0,3014 %.
Gain incrémental non confirmé, conserver9900006 ; candidat de recherche et toutes ses mesures archivé.

Dernier voisinage local lancé, contrôleur27312 ; confirmation48928 en attente : parent9900006 seulement,
fenêtres internes à451/688 fixes, faire varier préfixe2..9 et premièreλ ; grille large antérieure plus±20 nm
sur1 nm autour600. 607 propositions :525 conjointes,7 préfixes seuls,75λ seules,62 étapes avec deux ancres.
Les607 contrats réels et changements exacts de préfixe/λ passent avant notation PREFIX_AFTER_WINDOW_VERIFY=GO.
Rejeu physique v6 inchangé pour recherche ; v10 pour confirmation, seuls choix CLI étendus, AST physique
identique àv9. Groupes frais2727/2728/2729,2828/2829/2830,2929/2930/2931 fixés avant le premier score.
Propositions SHA256 `9d5b462394b8baaee51cb06a8ae1fa7848251aa5a2543f0d4ef7a010a881de37`,
protocolev10 `be6b866075ce6378dc0495df8359914d05dc4392b8f60e306557c2b2de6c1dae`,
contrôleur `bf1f83ca16d5b0c1c91420bb89d1e3fb784bef26d603bcafc2178bb8ecd96703`,
rejeu v10 `0249da490dd9d59c4ae483fcaa9dbaf662eb4adb5c122fde86fb47bb53e9c7a6`.
Sources/préparation/contrats dans STRAT_Rate_prefix_after_window_2026-10-14 et confirmation associée.
Une seule mesure,16 processeurs/0xffff/Normal/15 threads, aucun test pendant les calculs, aucune vitesse
attribuée au code plutôt qu’au cache. Reprendre A2 après la confirmation de ce dernier voisinage.

Garde A2 éprouvée entre les mesures : AST réel du seul if ajouté, horloge/persistance simulées,
quatre cas avant/à/après échéance et adoption d’un calcul engagé. A2_DEADLINE_GUARD_VERIFY=GO ; aperçu
24 cellules inchangé, git diff --check vert. Premier Ruff du vérificateur : quatre B023, liaisons explicites
ajoutées, ancienne source archivée à octets identiques en .py.txt, Ruff ensuite vert. Ce contrôle ne simule
pas toute A2. Copie nocturne encore non lancée, A2 préservée3/24 et prochain101sans.
Aucun noyau, défaut de production ou worktree scientifique changé, aucun commit/push/publication.


## 14 octobre, 5 h 30 — préfixe613 contrôlé, exploration terminée, A2 reprise

PREFLIGHT=GO. Dernier voisinage terminé5 h27 min56 s : 62/62 étapes,607/607 propositions,
429 consensus complets admissibles,178 exclus conservés. Meilleur9910275 repris9900008 :
préfixe L1–L5 à613 nm, fenêtres L11–L12 à451 etL35–L37 à688 nm conservées, partition/fente/témoins fixes.
Score0,02797523766720083, SEEL0,3345159946382285 nm ; gain15,6785 % contre référence sur101,
1,8796 % contre parent9900006. Artefact SHA256
`4bd54122f4517c3a123e2321684b355513fc7b5f766b466293ed8f976dc7ce9e`.
Confirmation48928 complète5 h28 min38 s,4/4 OK : neuf points fixes puis groupes frais2727/2828/2929.
Gains contre référence13,6821 /15,8693 /14,3511 %, contre parent0,4792 /1,0796 /1,0429 %.
Aucun plantage observé. Gain incrémental petit : contrôle prolongé avant reprise A2.

Six groupes supplémentaires3030/3031/3032,3131/3132/3133,3232/3233/3234,3333/3334/3335,
3434/3435/3436 et3535/3536/3537 figés après sélection613 et avant leur notation. Plans fixes seulement,
aucun classement de candidats sur ces groupes. Rejeu v11 : seule extension CLI, AST physique identique
àv10, Ruff et revue statique passent. Comparateurs figés sousbaseline_plans_snapshot ; neuf plans,
vainqueur équivalent dédupliqué et point fixe strict conservé. Contrôleur27312 (PID réattribué, ancienne
recherche terminée et machine vérifiée libre) complète7/7 OK ; neuf points fixes puis six groupes,
aucun plantage observé. Protocolev11 SHA256
`2d95977d620377938534e12f45bd0a77e62ce0a24bd64aaad8d6ba9bdbae7314`,
rejeu `e134846ad489a6af1950504ff7539ca3917ab6bc9dd3493c4e34d76512c8989d`.
Bilan des neuf groupes frais :9/9 gains contre référence,13,2343 à15,8693 %.
Face au parent àpréfixe600 :8/9 gains, moyenne0,3074 %, médiane0,4792 % ; perte2,3282 % sur3434.
Le meilleur score de recherche reste613 ; sa petite avance est hétérogène, aucune supériorité uniforme
ou intervalle de confiance formel. Les deux plans complets sont conservés. Un composant et plans fixes,
pas de validation machine/générale ni preuve que la recherche native ELITE retrouve automatiquement ce plan.
Tous artefacts/propositions/rejets/sources/graines conservés, aucun défaut activé, aucun noyau modifié.

Exploration Rate terminée. A2 reprise5 h35 min23 s : contrôleur23280, quatrième calcul41632,
r75x1.5_deep_s101_sans ;3/24 terminées au lancement. Worktree campagne-a2,HEADda1af082, diff suivi vide,
trois artefacts scientifiques non suivis attendus préservés. Ancien checkpoint copié avant reprise,
arguments/empreintes et garde fournie dansA2_deadline_preparation. Contrôleur nocturne52aee00f
exactement celui éprouvé entre mesures ; original77e26f57 inchangé. Pas de nouveau départ àpartir9 hParis,
calcul déjà engagé laissé finir. Machine vérifiée libre avant lancement, aucune mesure interrompue.
Affinité65535/0xffff etNormal observés sur contrôleur et calcul,16CPU/15threads déclarés, preuve
health_20261014_0530.json. À5 h38 CPU et journal progressent, consensus300/graines41/42/43 observés,
un seul enfant scientifique, aucun échec. Aucun test pendant A2. git diff --check vert.
Aucun commit/push/publication ; validation générale de code toujours àterminer après la campagne.


## 14 octobre, 6 h — A2 progresse, aucune mesure Rate relancée

PREFLIGHT=GO. A2 :3/24 terminées, quatrième r75x1.5_deep_s101_sans active depuis5 h35,
contrôleur23280 et calcul41632. Journal à6 h : notation à8 blocs,300 tirages,8 workers effectifs
observés dans cette phase ; CPU et journal avancent, un seul enfant scientifique, aucun échec.
Affinité0xffff etNormal vérifiés sur les deux processus ; plafond16CPU/15threads conservé.
Garde52aee00f inchangée, aucun nouveau départ après9 hParis ; calcul engagé laissé finir.
Preuve health_20261014_0600.json. Points de reprise/artefacts conservés, aucun test pendant A2,
aucun arrêt ni nouveau calcul Rate. Meilleur plan et limites de sa confirmation inchangés.
Aucun défaut activé, aucun commit/push/publication.


## 14 octobre, 6 h 30 — quatrième A2 sauvegardée, cinquième active

PREFLIGHT=GO. A2 :4/24 sauvegardées ; r75x1.5_deep_s101_sans terminée6 h16 min46 s,
41 min23 s, SEEL0,4881866128 nm,4554 déposables. Artefact verdictOK, HEADda1af082,
git_dirty=false, cacheclé caf88a3320c7, elite_rate_moves=false effectivement transmis.
SHA256 `cd057594b75590e695605f93c926bc4eb066e38ee47873fb3cd0b452c11f7c80`.
Sur les deux paires r75x1.5 exportées : gain avec/sans3,2514 % sur42 et0,1176 % sur101,
inférieurs au repère de dispersion ; aucune supériorité ni conclusion globale établie.
Les lignes de stratégies exportées ne gardent pas le statut de consensus : ces paires de recherches
ne remplacent pas une renotation homogène de plans fixes, non faite sur ces gagnants A2.
Contrôleur23280 a enchaîné r75x1.75_deep_s042_avec, calcul25072, depuis6 h16 min46 s.
À6 h30 :12 blocs en screening,8 workers observés,300 tirages complets/consensus dans le journal.
CPU/journal progressent, un seul enfant scientifique, aucune erreur ;0xffff/Normal/16CPU/15threads
conservés et garde52aee00f inchangée. Health_20261014_0630.json et contrôle d’artefact conservés.
Aucune nouvelle mesure Rate, aucun arrêt ou test pendant A2, aucun défaut activé/commit/push.


## 14 octobre, 7 h — cinquième A2 progresse normalement

PREFLIGHT=GO. A2 :4/24 sauvegardées, r75x1.75_deep_s042_avec toujours active,
contrôleur23280 et calcul25072. À7 h : notation à2 blocs,300 tirages,8 workers effectifs
observés ; CPU et journal avancent, un seul enfant scientifique, aucune erreur.
0xffff/Normal vérifiés,16CPU/15threads déclarés, garde52aee00f inchangée.
Health_20261014_0700.json conservé. Aucun test ou nouvelle mesure Rate, aucun arrêt,
aucun défaut activé, aucun commit/push. Conclusions Rate et limites inchangées.


## 14 octobre, 7 h 30 — cinquième A2 sauvegardée, sixième active

PREFLIGHT=GO. A2 :5/24 sauvegardées. r75x1.75_deep_s042_avec terminée7 h04 min19 s,
47 min33 s, SEEL0,4788232294 nm,3998 déposables. Verdict/HEADda1af082/git_dirty=false,
elite_rate_moves=true et copie d’artefact vérifiés. SHA256 `7686b76d5009ab7ee5cad1394c9739bd1acffddcd24042d48ecedfd486f8a769`.
La variante sans mouvements reste en cours : aucune comparaison avec/sans pour cette cellule.
Contrôleur23280, calcul35744, r75x1.75_deep_s042_sans depuis7 h04 min19 s.
Journal à7 h30 : screening à9 blocs, CPU/journal progressent, un seul enfant scientifique,
aucune erreur,0xffff/Normal vérifiés et16CPU/15threads conservés. Garde52aee00f inchangée.
Preuve health_20261014_0730.json et contrôle d’artefact conservés. Aucun nouveau calcul Rate,
aucun test ou arrêt pendant A2, aucun défaut activé/commit/push. Meilleur plan Rate et limites inchangés.


## 14 octobre, 8 h — sixième A2 sauvegardée, septième active

PREFLIGHT=GO. A2 :6/24 sauvegardées. r75x1.75_deep_s042_sans terminée7 h50 min34 s,
46 min15 s, SEEL0,4967841046 nm,4060 déposables. Verdict/HEADda1af082/git_dirty=false,
elite_rate_moves=false et copie d’artefact vérifiés. SHA256 `b0ac41a3335d32b8dbaedee40efd9e3ad9d16d6ab91e7f51417a1e212c050fbd`.
Paire42 de r75x1.75 : gain exporté avec/sans3.6154 %, inférieur au repère de dispersion ;
pas de supériorité ni conclusion globale, pas de renotation homogène des plans fixes A2.
Contrôleur23280, calcul51800, r75x1.75_deep_s101_avec depuis7 h50 min34 s.
À8 h : bloc13, les601 candidats de screening ont des scores non finis et100 % de plantages ;
rejet scientifique explicitement journalisé, calcul poursuivi via classement de secours/consensus,
aucun arrêt ou échec du contrôleur. Ceci ne conclut pas sur les autres blocs ou sur le composant.
CPU et journal avancent, un seul enfant scientifique,0xffff/Normal vérifiés et16CPU/15threads
conservés, garde52aee00f inchangée. Health_20261014_0800.json et contrôle d’artefact conservés.
Aucun nouveau calcul Rate, aucun test ni arrêt pendant A2, aucun défaut activé/commit/push.


## 14 octobre, 8 h 30 — progression et réveil final sécurisés

PREFLIGHT=GO. A2 :6/24 sauvegardées, r75x1.75_deep_s101_avec active depuis7 h50,
contrôleur23280/calcul51800. Journal à8 h30 :4 blocs,300 tirages et8 workers dans cette phase.
À8 h34 CPU/journal progressent, un seul enfant scientifique,0xffff/Normal vérifiés,
16CPU/15threads conservés, aucun échec du contrôleur ni interruption. Health_20261014_0830.json.
Garde52aee00f inchangée : aucun nouveau départ scientifique après9 hParis/7 hUTC.
Le suivi avait une expiration à7 hUTC pile ; le réveil final pourrait être décalé de quelques secondes.
Configuration antérieure préservée, outil natif utilisé pour une minute de grâce du réveil de bilan seulement,
prompt/fréquence/thread/préférences conservés. Mise àjour confirmée et configuration relue ; aucune mesure
supplémentaire autorisée après9 h. final_wake_20261014_0830.json et snapshot antérieur conservés.
Aucun test pendant A2, aucune nouvelle mesure Rate, aucun défaut activé/commit/push/publication.
Meilleur plan et limites de la confirmation inchangés ; bilan à9 h.
