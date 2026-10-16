# STRAT — passation et plan de chantier pour améliorer le Rate

Document de travail préparé le 14 octobre 2026 à la demande de 👤, pour une reprise complète du chantier.

**Programme borné clos le16octobre2026 par arrêt précoce R6 après48c sans gain.** [Bilan final, résultats, limites et cas non exécutés](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md). Aucun nouveau défaut activé ; toute nouvelle campagne nécessite une décision distincte. Les étapes ci-dessous conservent le protocole et les preuves du programme terminé.
**Suite demandée le16octobre :** diagnostic R5/h03 puis choix de fenêtre admissible48c, avec
[périmètre et plafonds séparés](../reports/STRAT_Rate_followup_2026-10-16/authorization_and_plan.json).
Diagnostic enregistré terminé ; préparation contrôlée échouée avant mesure, ancien suiviPAUSED.
La [passation précise du16octobre](STRAT_Rate_reprise_20261016.md) décrit l'état réel,
le diagnostic48c, les écartsR5/h03 non résolus et la reprise sûre. Publication et ménage demandés.
👤 a ensuite choisi de poursuivre avec cette IA en totale autonomie : le guide s’applique à la continuation
actuelle et reste utilisable pour une passation ultérieure.
**Dernière autorisation, le15 octobre2026 : corriger RMSE puis reprendre jusqu’à la fin du programme borné R0–R6.**
24processeurs logiques, affinité0xffffff, priorité Normal,23threads de bibliothèque au maximum ;
une seule mesure et aucun test pendant celle-ci. Les anciennes limites temporelles et ressources16/15
restent l’historique des mesures et ne définissent plus la continuation. Les nouveaux lanceurs seront
des copies distinctes, bornées par les quotas du programme ; aucun script de mesure historique modifié.
[Autorisation et sources avant correctif RMSE](../reports/STRAT_RMSE_uniform_weights_2026-10-15/authorization_and_baseline.json).
Les règles restent dans [CLAUDE.md](../CLAUDE.md), l’état courant dans [ETAT.md, section 0](ETAT.md),
les mesures datées dans [le bilan](../reports/STRAT_Rate_bilan_2026-10-14.md) et
[l’expertise](../reports/STRAT_Rate_expertise_2026-10-13.md). Ce guide décrit les actions suivantes ;
une piste proposée ici n’est ni implémentée ni validée par sa seule présence dans ce document.

## 1. Objectif, résultat disponible et limite principale

L’objectif suivant est de faire trouver **automatiquement par STRAT** de bons plans alternant couches
contrôlées optiquement et couches au Rate, avec un gain confirmé à notation homogène et un coût de calcul maîtrisé.
La recherche locale a déjà trouvé un meilleur plan sur `r75x0.5 deep`, graine 101 : le gain de 15,68 %
contre la référence est confirmé sur neuf groupes indépendants. Les chiffres, les essais moins bons
et les limites de cette confirmation sont consignés dans le bilan, qui fait foi pour ces mesures.

Le prochain chantier doit relier ce succès à une recherche native reproductible. L’ajout de nombreux
candidats pendant ELITE n’a pas encore démontré cette capacité. **Ne pas annoncer que l’intégration
automatique est achevée, ne pas transformer le meilleur plan de ce cas en constante du programme.**

Le contexte machine donné par 👤 est une variation de vitesse **entre deux dépôts**. Une dérive au cours
d’un dépôt et une amplitude quantitative n’ont pas été fournies pour cette campagne. Ne pas les inventer.
Les résultats actuels restent ceux du modèle simulé et de plans fixes, pas une validation sur la machine.

## 2. Ordre de lecture et premier démarrage

Depuis la racine `certus0310`, la première commande doit être :

```powershell
python scripts\preflight.py
```

Attendre sa fin et `PREFLIGHT=GO`. Lire ensuite, dans cet ordre :

1. [ETAT.md, section 0](ETAT.md), pour les calculs et décisions encore en cours.
2. [CLAUDE.md](../CLAUDE.md), particulièrement validation, C1/C2/C3 et architecture.
3. [Bilan du 14 octobre](../reports/STRAT_Rate_bilan_2026-10-14.md), pour les résultats et pistes écartées.
4. [Expertise du Rate](../reports/STRAT_Rate_expertise_2026-10-13.md), pour les causes et échecs conservés.
5. [Préparation de l’intégration](../reports/STRAT_Rate_expertise_2026-10-13/production_integration_review_2200.md),
   en tenant compte de sa date : elle précède les dernières confirmations et ne remplace pas le bilan.
6. Ce guide, puis les scripts de la phase effectivement choisie.

Le shell par défaut a échoué sur un chemin `pwsh.dll` indisponible lors de la rédaction du bilan.
Si cela persiste, utiliser explicitement Windows PowerShell, sans réparer l’environnement au hasard :

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile
```

Pour les outils d’exécution qui permettent de choisir le shell, sélectionner cet exécutable et désactiver
le chargement du profil. Python est 3.14.8 ; garder la syntaxe PEP 758 du projet.

### 2.1 Inventaire avant toute action

```powershell
git status -sb
git log -1 --format="%H %s"
git config --get core.hooksPath
Get-Content reports/STRAT_ELITE_couches_Rate_autres_composants_2026-10-13/etat.json -Raw
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match '^python' -and
        $_.CommandLine -match 'probe_blocs|campagne_a2|a2_continue|rate_pistes|rate_fixed|rate_validation|rate_joint|rate_native|rate_ablation|rate_prefix|rate_window|rate_pair'
    } |
    Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
```

Vérifier les journaux du calcul identifié et les `.running` des dossiers de campagne. Un contrôleur
en attente n’est pas une deuxième mesure ; compter les enfants qui exécutent réellement un calcul.
Un PID peut être réattribué : comparer **PID, commande, date de création et état de campagne**.
Ne pas conclure qu’un ancien calcul vit encore à partir du seul numéro du PID.

### 2.2 Situation de l’arbre à préserver

Le point de départ des mesures est `da1af0825d5e09e8d0a5ff4f1cf42b802e0e30e7`.
Au moment de cette passation, cinq fichiers suivis sont modifiés dans l’arbre principal :

- `scripts/probe_blocs_vs_plantage.py` : correction locale du suffixe SHA1 vers SHA256 pour A1.
- `certus/core/certus_strat_robustness_rate.py` : équilibrage expérimental des familles.
- `certus/core/certus_strat_consensus.py` : routage de cette option, inactive par défaut.
- `tests/unit/test_strat_elite_rate_moves.py` : vérifications de l’option précédente.
- `docs/ETAT.md` : état du chantier.

Les rapports et `scratch/` ne constituent pas une validation complète ni un commit. Il y a déjà six
commits locaux non poussés : ne pas les attribuer à ces derniers essais et ne pas les publier.
Ne pas reset, ne pas effacer les changements ou artefacts existants pour obtenir un arbre « propre ».
La validation complète d’A1 et de l’équilibrage reste à terminer ; l’équilibrage a régressé scientifiquement.

### 2.3 Worktrees et durée de vie des anciens scripts

Les worktrees gérés existants sont `campagne-a2` et `rate-equilibre`, sous le répertoire des worktrees Codex.
Retrouver leurs chemins avec l’outil de liste des artefacts si disponible ; sinon `git worktree list --porcelain`.
Utiliser les chemins retournés, sans en inventer un. Ne pas modifier une source dans un worktree qui mesure.

`campagne-a2` conserve le code de la campagne A2. `rate-equilibre` conserve le snapshot mesuré :
HEAD `da1af082` et les deux modifications de cœur attendues, avec l’équilibrage désactivé dans ces essais.
Il contient des artefacts non suivis attendus. Le snapshot de référence est décrit par
[`STRAT_Rate_equilibre_AB_2026-10-13/etat.json`](../reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json).

Les anciens contrôleurs, probes et moteurs de rejeu contiennent une garde fixée au **14 octobre 2026,
7 h UTC / 9 h Paris**. Ils ne sont pas des lanceurs réutilisables sans préparation après cette date.
Pour la nouvelle campagne demandée par 👤 : faire une **nouvelle copie**, avec sa propre échéance documentée,
son dossier de résultats et ses empreintes. Garder les anciennes sources à octets identiques.
Ne pas contourner la garde d’un calcul actif ni modifier en place les scripts dont il vérifie les empreintes.

## 3. Ce qu’il faut conserver comme preuves

### 3.1 Repères et plans fixes

Le fichier de départ le plus compact est
[selected_fixed_plans.json](../reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/selected_fixed_plans.json).
Il contient les plans complets de la référence, du parent confirmé et du meilleur plan local.
Le fichier [plans.json](../reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/plans.json)
contient les neuf comparateurs. Ne pas perdre les champs `blocks`, `rate_layers`,
`monochromator_resolution_nm`, `witness_reset_layers` lorsqu’ils sont présents, ni la provenance.

| Identité de rejeu | Rôle | Origine à conserver |
|---:|---|---|
| 900951015 | Référence historique | Artefact A/B de référence |
| 9900000 | Meilleur natif conjoint, Rate240, six raffinements | Original 901054165 |
| 9900001 | Meilleur de l’ablation après renotation complète | Original 900752354 |
| 9900002 | Préfixe L1–L5 à600 nm | Recherche locale 9960194 |
| 9900004 | Préfixe fin598 nm, avantage incrémental non confirmé | Recherche 9950016 |
| 9900005 | Meilleur pool natif préfixe renoté | Original 901454694, rejeu de pool 9940095 |
| 9900006 | Fenêtre L35–L37 à688 nm, préfixe600 | Recherche 9932265 |
| 9900007 | Meilleur couple de fenêtres sur101, non retenu | Recherche 9920025 |
| 9900008 | Préfixe613 avec fenêtre688 | Recherche 9910275 |

Les identités servent à la traçabilité, pas à la génération des perturbations ni à favoriser un candidat.
Ne pas réutiliser un identifiant existant pour un autre plan. Le numéro 9900003 correspond à une tentative
de contrôle échouée et n’est pas un nouveau comparateur valide. Vérifier l’ensemble des IDs avant les prochaines allocations.

### 3.2 Résultats confirmés et limites à garder visibles

- La répartition équilibrée au plafond120 a évincé une fenêtre utile ; la reconstruction exacte est dans l’expertise.
- Le budget240 aide ;360 ne gagne pas davantage. Un budget plus grand n’est pas une preuve de meilleure sélection.
- Le préfixe et la λ, puis la fenêtre interne et sa λ, ont produit des gains par recherche conjointe.
- Les fenêtres de longueur impaire ont été utiles ; le générateur natif conjoint étudié ne proposait que2/4/6.
- Le raffinement598 et les couples de fenêtres n’ont pas confirmé leur avantage incrémental sur des groupes frais.
- L’ajout natif de720 voisins de préfixe a échoué à battre le parent confirmé, même après renotation de tout son pool.
- Le plan613 gagne contre la référence sur neuf groupes frais, mais son petit avantage sur le parent600 est hétérogène.
- Le gain du natif conjoint contre la référence ne prouve pas son avantage propre sur l’ablation à profondeur homogène.
- Un contrôle de point fixe perdu annule la comparaison concernée ; aucune tolérance n’a été relâchée pour le faire passer.
- Les temps incluent des états de cache différents ; aucune accélération de code n’est démontrée par ces seuls chronométrages.

### 3.3 Carte des artefacts et scripts à relire

| Besoin | Dossier ou source |
|---|---|
| Référence, snapshot et équilibrage raté | `reports/STRAT_Rate_equilibre_AB_2026-10-13/` |
| Essais de budgets et raffinements | `reports/STRAT_Rate_pistes_2026-10-13/` |
| Ablation complète et renotation homogène | `reports/STRAT_Rate_ablation_consensus_all_2026-10-13/` |
| Première recherche du préfixe | `reports/STRAT_Rate_prefix_joint_2026-10-14/` |
| Recherche native du préfixe et renotation de ses5119 plans | `reports/STRAT_Rate_native_prefix_2026-10-14/`, `reports/STRAT_Rate_native_prefix_consensus_all_2026-10-14/` |
| Fenêtres1..7, déplacements et λ | `reports/STRAT_Rate_window_widths_2026-10-14/` |
| Couples de fenêtres et résultat non retenu | `reports/STRAT_Rate_window_pairs_2026-10-14/` |
| Dernier choix préfixe/λ sur fenêtre688 | `reports/STRAT_Rate_prefix_after_window_2026-10-14/` |
| Confirmation des neuf groupes frais du meilleur plan | `reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/` |
| Rejeu physique strict et observateur | `scratch/rate_fixed_replay_confirmation_v11.py` |
| Prototypes de générateurs purs | `scratch/rate_joint_native_candidates.py`, `scratch/rate_prefix_native_candidates.py` |
| Adapter natif et vérifications structurelles | `scratch/rate_native_joint_probe.py`, `scratch/rate_native_prefix_probe.py`, `scratch/verify_rate_native_prefix_adapter.py` |
| Contrats des fenêtres et du préfixe | `scratch/verify_rate_window_trials.py`, `scratch/verify_rate_prefix_after_window.py` |
| Contrôleur A2 d’origine et copie nocturne | `scratch/campagne_a2_runner.py`, `scratch/campagne_a2_deadline_runner.py` |

Les copies figées de ces scripts, leurs paramètres et SHA256 sont dans les dossiers `reports/`.
Ne pas supposer que `scratch/` est encore identique : comparer son empreinte au snapshot avant réemploi.

### 3.4 Empreintes vérifiées et pièges du contexte de rejeu

Empreintes SHA256 relues le14 octobre2026 ; elles identifient **les sources historiques**, pas
automatiquement les prochaines sources de développement. La préparation R1 dans l’arbre principal
est un changement d’export distinct ; elle ne doit pas remplacer le snapshot historique de référence.

| Source historique | SHA256 |
|---|---|
| `certus/core/certus_strat_consensus.py` du snapshot Rate | `ebaf566725a56e401e87823924ad34e6c3ae30cea8b683b9064679176f62d156` |
| `certus/core/certus_strat_robustness_rate.py` du snapshot Rate | `f08d255e79166a8ed24ad6026c31382c8dff5da858268b47275d64f6458a4127` |
| Moteur `scratch/rate_fixed_replay_confirmation_v11.py` | `e134846ad489a6af1950504ff7539ca3917ab6bc9dd3493c4e34d76512c8989d` |
| Protocole `protocole_validation_prefix_extended_v11.json` | `2d95977d620377938534e12f45bd0a77e62ce0a24bd64aaad8d6ba9bdbae7314` |
| Helper `scratch/campagne_a2_runner.py` | `77e26f57341c198830e5ed8b19e072b94285eb24f5ed2cdd2e78dadf378f7e51` |

Le snapshot source est décrit dans l’état A/B ; le moteur vérifie HEAD, liste des fichiers modifiés
et leurs empreintes avant/après. Une nouvelle copie du moteur ne suffit pas à autoriser un autre
snapshot. Préparer sa provenance séparément et établir le point fixe, sans réécrire l’état A/B.

Le rejeu utilise `ExternalEvaluationStrategy` avec `expand_variants=False`, générationELITE,
RateRescue et expansion de fente désactivées. `_resolve_injected_strategies` du Worker historique
perd des champs Rate/fente/témoins : **ne pas utiliser cette route inchangée pour un plan mixte**.
Les indices passent par `SharedIndicesManager` et le Worker enfloat32 ; un transfert directfloat64
avait fait perdre le point fixe. La création Qt et les chemins absolus suivent les précautions de§5.
Les observateurs délèguent au simulateur physique du projet : aucune formule optique réimplémentée.

## 4. Reprise d’A2 et coexistence des chantiers

**Instruction la plus récente :** 👤 a demandé de terminer les batchs A2 restants, puis de continuer le
chantier Rate avec cette IA en totale autonomie. L’ancienne limite de9 h n’arrête plus cette nouvelle
poursuite d’A2. `scratch/a2_continue_runner.py`, contrôleur51884 au lancement, a attendu la fin du
nocturne23280 sur son handle Windows ; checkpoint, empreintes, HEAD et processus vérifiés,
il a lancé le contrôleur A2 original24128 à9 h25, jusqu’à24/24. Le snapshot, les logs et son état sont
dans `reports/STRAT_A2_continuation_2026-10-14/`. **Ne pas lancer un second contrôleur A2.**

Lire l’état A2 courant ; le nombre terminé dans un rapport daté peut déjà être dépassé.
Le champ ancien `next_key` peut rester au checkpoint de reprise : décider avec `runs`, `current`,
`current_pid`, la commande et le journal actuels, jamais en réimposant ce seul champ résiduel.
Le 14 octobre à8 h47, la huitième mesure était active et sept étaient sauvegardées ; **ce n’est pas un état à réimposer**.
Ne pas arrêter une mesure A2 pour lancer un essai Rate ou un test.

Pendant une mesure, limiter le travail à la lecture, l’analyse des artefacts, la préparation documentaire et
la revue statique. Les tests, vérifications de contrats qui importent le runtime et autres mesures attendent une période libre.
La copie nocturne reste inchangée : elle laisse finir sa mesure puis bloque son propre prochain départ.
La continuation nouvellement autorisée démarre ensuite au checkpoint libéré ; les nouveaux essais Rate
attendent une période libre, après les batchs A2 programmés. Ne pas modifier la copie nocturne active.

Pour une reprise ultérieure explicitement lancée par 👤, inspecter et reprendre le checkpoint existant avec un
contrôleur adapté à la nouvelle plage de travail. L’aperçu suivant ne lance aucune mesure :

```powershell
$a2wt = Join-Path $env:USERPROFILE '.codex\worktrees\campagne-a2\certus0310'
$a2out = (Resolve-Path 'reports/STRAT_ELITE_couches_Rate_autres_composants_2026-10-13').Path
python scratch/campagne_a2_runner.py --worktree $a2wt --output $a2out --logical-cpus 16 --plan
```

Utiliser le chemin réellement inventorié si différent. Le contrôleur d’origine n’a pas la garde nocturne :
ne pas utiliser sa commande de lancement sans avoir prévu la nouvelle limite de temps.
`--adopt-current` sert à reprendre l’attente d’un calcul réel encore vivant, après vérification de son identité ;
`--stop-after-current` sert à terminer puis sauvegarder avant pause. Ne jamais faire adopter un même calcul par deux contrôleurs vivants.

Pour un verrou orphelin : vérifier l’absence du PID **et** de la commande, le statut, les fichiers de résultat,
la provenance et le journal. Préserver l’état/verrou/journal dans un nouveau dossier `recovery_...`, puis renommer
le verrou au lieu de le supprimer sans preuve. Réconcilier un résultat déjà terminé plutôt que le recalculer.
Un enfant scientifique peut continuer après l’échec de son contrôleur : attendre sa fin, ne pas le tuer.

Le remplacement atomique des rapports a rencontré des `PermissionError` temporaires sur Drive ; le helper
existant utilise `atomic_open` et40 tentatives espacées de0,25 s, puis propage l’échec. Garder cette propriété.
Les gagnants A2 exportés ne portent pas leur statut de consensus : leur comparaison ne remplace pas une
renotation homogène des plans fixes. La campagne24/24 et l’audit de ces scores restent des travaux distincts.

## 5. Contrat d’une nouvelle expérience

Préparer un dossier neuf `reports/STRAT_Rate_suite_<date>/<experience>/`, sans réutiliser un répertoire
qui contient déjà une tentative. Chaque expérience doit comporter :

- `protocol.json` : hypothèse, seul facteur changé, comparateurs, mode, profondeurs, graines de recherche,
  groupes de confirmation, bruit, fente, budgets, critères de décision et échéance.
- `prepared.json` : commande et huit arguments du probe, surcharges effectives attendues, worktree, HEAD,
  patch éventuel, SHA256 des sources scientifiques, de l’adaptateur et des propositions.
- `plans.json` ou `proposals.json` : plans complets, identités uniques et origine de chaque proposition.
- `etat.json` : contrôleur/mesure courante, étapes terminées, ressources, chemins des résultats et erreurs.
- Journaux, résultats bruts, simulations observées, rejets et snapshots des sources. Garder aussi les tentatives échouées.
- `summary.json` et un `.md` : SEEL, plantages, profondeur **réellement reçue**, scores de base/consensus distingués,
  écart à la référence et aux comparateurs proches, durée, limites et décision.

Créer les comparateurs préparatoires sous `baseline_plans_snapshot.json`. Ne pas occuper `plans.json` si
le contrôleur doit le créer avec ouverture exclusive : cela a déjà causé un échec avant mesure.
Si `bench_examples` change le répertoire courant, seuls des chemins **résolus absolument avant import** sont sûrs.
Créer `QApplication` par `bench_examples.qapp()` avant les imports qui en ont besoin, comme les replayers existants.

### 5.1 Conditions de notation à conserver

| Élément | Condition |
|---|---|
| Cas de développement | `r75x0.5 deep 0 0 2 0 101 0` |
| Point fixe | Graine101, consensus41/42/43 |
| Profondeur pleine | 300 tirages |
| Profondeur de chaque graine de consensus | 300 tirages, trois graines, consensus complet requis |
| Screening | 50 pour le protocole de rejeu actuel ; enregistrer aussi les étapes ELITE réellement utilisées |
| `dp_top_k` | 100 dans les rejeux de référence |
| Fente | 2 nm, profil et facteur de bruit hérités, pas de changement dans les premiers essais |
| Bruit | Niveaux historiques0,5×/1×/2×, même perturbation physique pour tous les plans comparés |
| SEEL | `2 * sqrt(score)`, objectif et poids de consensus inchangés |
| Ressources | Continuation du15 octobre :24 processeurs logiques,0xffffff,Normal,23 threads maximum ; mesures historiques16/15 conservées |

Un consensus marqué complet doit avoir trois scores finis et les bonnes graines ; ne pas se contenter
de paramètres déclarés dans un JSON. Conserver les paramètres et nombres de tirages des appels réels.
Dans les replays de recherche, deux ancres plus dix propositions tiennent dans le plafond actuel de
douze candidats de consensus. **Trois ancres nécessitent au plus neuf propositions** ; ne pas ajouter une
ancre en oubliant cette contrainte. Un candidat non complètement noté est exclu de la sélection finale.

La tolérance existante du point fixe est `rel_tol=1e-7`, `abs_tol=1e-10`. Si elle échoue : préserver les
artefacts, chercher la cause et corriger le contexte. Ne pas élargir la tolérance. Les premiers échecs
venaient notamment d’un transfert direct d’indices enfloat64 au lieu du transportfloat32 du Worker.

### 5.2 Recherche et confirmation ne jouent pas le même rôle

Choisir les candidats avec la graine de développement seulement, puis figer le plan, les sources,
la profondeur et le protocole avant toute confirmation fraîche. Les groupes déjà utilisés pour orienter
une décision deviennent des données de contexte, même si leur comparaison est intéressante.
Les groupes202 à3535 déjà présents dans les protocoles ne sont plus un nouveau jeu de validation.

Pour une prochaine expérience, réserver par exemple les groupes consécutifs
`3636/3637/3638`, `3737/3738/3739`, `3838/3839/3840` **après avoir vérifié qu’ils sont encore inutilisés**.
Les inscrire dans le nouveau protocole avant le premier score de l’expérience. Ce sont des propositions
de graines pour la tâche future, aucune de ces mesures n’a été lancée par cette passation.
Pour une autre expérience sélectionnée après ces résultats, réserver d’autres groupes frais.

Rapporter chaque groupe séparément, le nombre de gains, moyenne, médiane et pire perte ; ne pas masquer
une graine défavorable. Un gain minuscule appelle plus de groupes ou une analyse d’incertitude appariée,
pas un changement silencieux du nombre de tirages. Si la profondeur est augmentée, rejouer tous les
comparateurs à cette même profondeur dans une expérience séparée.

## 6. Ordre concret du chantier

| Phase | Travail | Livrable permettant de passer à la suivante |
|---|---|---|
| R0 | Inventaire, reprise sûre, reproduction des références | État/processus/sources vérifiés et points fixes valides |
| R1 | Rendre les exports et traces de scores interprétables | Chaque candidat distingué en base/consensus/rejet, sans effet numérique |
| R2 | Localiser où les candidats utiles disparaissent | Tableau génération→contrat→screening→plein→consensus→parent |
| R3 | Corriger une cause observée dans la recherche native | A/B à budget/profondeur identiques et gain indépendant |
| R4 | Tester un petit raffinement local alterné ou un faisceau | Gain supplémentaire confirmé, coût et candidats bornés |
| R5 | Intégrer proprement le prototype retenu | C1, architecture, tests complets et équivalence prototype/intégration |
| R6 | Vérifier la généralisation | Recherche native sur nouvelles graines et autres composants |
| R7 | Étudier le modèle machine à partir de données réelles | Calibration par matériau et scénario de variation justifié |

R1 et R2 sont prioritaires. R3 dépend de leur diagnostic ; ne pas lancer tous les leviers en même temps.
R4 peut être préparée en lecture seule pendant une mesure R3. Les calculs restent séquentiels.
R7 est distinct du travail d’optimisation et ne doit pas modifier la physique au milieu de R1–R6.

### R0 — reproduire et sécuriser la base

1. Réaliser l’inventaire de§2. La décision actuelle est de terminer A2 jusqu’à24/24, puis de mesurer
   le Rate ; les préparations documentaires et statiques peuvent avancer pendant A2.
2. Archiver le diff suivi, les versions dePython/NumPy/SciPy/Numba, la clé de cache et les empreintes.
3. Préserver les worktrees de référence. Si un nouvel arbre de développement est nécessaire, réutiliser
   un worktree géré adapté ou en créer un sur le ref explicitement choisi. HEAD seul ne copie pas les deux
   sources modifiées du snapshot `rate-equilibre` : vérifier cette différence avant toute mesure.
4. Préparer une nouvelle copie du replayer v11, avec la nouvelle échéance et, si nécessaire, les nouveaux
   choix CLI de graines. Comparer son AST hors garde/CLI à l’ancien : aucun changement de physique.
5. Rejouer ensemble la référence900951015, le parent9900006 et le meilleur plan9900008 avec le transport
   Workerfloat32. Conserver les scores attendus existants et les plans complets, sans regénérer des enfants.
6. Si le snapshot change, créer une **nouvelle description de provenance** à côté de l’ancienne et établir
   son point fixe ; ne jamais modifier le JSON historique pour faire accepter de nouvelles sources.

Commande d’aperçu du moteur existant, sans simulation, à exécuter hors mesure :

```powershell
$ratewt = Join-Path $env:USERPROFILE '.codex\worktrees\rate-equilibre\certus0310'
$plans = (Resolve-Path 'reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/selected_fixed_plans.json').Path
$protocol = (Resolve-Path 'reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/protocole_validation_prefix_extended_v11.json').Path
$reference = (Resolve-Path 'reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json').Path
$previewOut = Join-Path (Get-Location).Path 'scratch/rate_suite_preview'
python scratch/rate_fixed_replay_confirmation_v11.py --worktree $ratewt --plans $plans --protocol $protocol --reference-state $reference --output $previewOut --run control --plan
```

Pour la mesure future, remplacer le moteur et le protocole par les **nouvelles copies préparées** ;
le moteur v11 d’origine refusera un nouveau départ après l’ancienne échéance. Utiliser un dossier de
sortie neuf. `--run control` doit donner `OK` avant tout `holdout_*`, et ces holdouts exigent le
`control.json` des **mêmes plans** dans le même dossier. Aucun contrôle n’est réputé passé sur la seule commande d’aperçu.

**Fin de R0 :** les trois points fixes sont reproduits, aucune mesure concurrente, provenance vérifiée,
nouvelle fenêtre temporelle documentée. Sinon résoudre le défaut avant toute expérimentation.

### R1 — provenance et profondeur de chaque score

**Problème observé :** dans `scripts/probe_blocs_vs_plantage.py`, la construction des lignes de
`strategies` conserve un scalaire `score` mais omet `robustness_consensus_meta`. Des scores de base
et de consensus peuvent donc être comparés sans que l’export les distingue. Deux gagnants exportés
ont déjà échoué au point fixe de consensus, puis leurs pools ont été renotés complètement.

**Changement ciblé :** rendre ces métadonnées disponibles dans la sonde/trace, en conservant les champs
actuels. Exporter les métadonnées réellement présentes, les graines, le nombre d’échantillons, les
profondeurs observées et l’étape d’évaluation. Si une donnée n’existe pas, écrire « inconnue »/null,
pas une profondeur déduite du seul nom `deep`. Conserver aussi le plan complet et les métadonnées héritées.

**Ne pas changer à cette étape :** ordre de génération, liste de parents, ID, score, filtrage, budgets,
physique, valeurs de bruit ou mode de consensus. Les métadonnées d’export ne nécessitent pas une
nouvelle option scientifique. Les éventuelles modifications de classement constitueront R3.

**Sources :** `scripts/probe_blocs_vs_plantage.py`,
`certus/core/certus_strat_consensus.py::_build_item_consensus_meta`, `_select_consensus_candidates`,
`certus/core/certus_strat_robustness.py`, et les observateurs déjà utilisés dans les replayers.

**Vérifications hors mesure :** export d’un vrai consensus complet, d’un consensus incomplet et d’un
score de base ; fidélité des champs présents ; conservation du scalar score, de l’ordre, des plans
et des graines. Ajouter une régression qui échoue sur l’export précédent muet. Ne pas modifier
les anciens artefacts pour leur ajouter des métadonnées non mesurées.

**Livrable :** export enrichi, test ciblé, exemple de rapport distinguant les trois catégories,
compteurs « consensus complets/admissibles » vérifiables. Un export lisible ne résout pas à lui seul le mélange dans la sélection.

Attention au sens de `robustness_score_base` : `_apply_item_consensus_scores` y recopie le score
présent **avant ce passage de consensus**. Si la même ligne est renotée, il peut donc contenir un
consensus antérieur, pas le premier score de101. L’export R1 conserve le champ existant sans changer
ce mécanisme ; la trace des appels/étapes R2 doit retrouver la provenance initiale quand elle est requise.

### R2 — tracer le parcours des candidats utiles

**Hypothèse à vérifier :** les bonnes géométries sont parfois absentes, rejetées par le screening,
privées d’une évaluation pleine, non retenues au consensus ou découvertes trop tard pour devenir parents.
Ces causes demandent des remèdes différents ; ne pas les attribuer toutes au plafond de génération.

Pour chaque appel d’ELITE, conserver : parents et signatures ; grille `available_wls` effectivement
reçue ; compte et famille des candidats ; motif de rejet du contrat/dédoublonnage ; score nominal aux
étapes de halving ; entrée dans les `elite_max_full_evals` ; score plein ; entrée au consensus ;
graines/profondeur/statut ; retenue comme parent au tour suivant. Inclure le tour et le nombre de blocs.

**Sources :**

- `_generate_elite_candidate_strategies` et sa closure `_push_candidate` pour les plans/IDs/héritages.
- `_apply_elite_refinement_if_enabled` pour parents, halving, plafond plein et tours.
- `_select_consensus_candidates` pour le sous-ensemble réellement renoté.
- `generated_candidates.json` et `prefix_calls` des essais natifs existants pour une première analyse sans simulation.

Comparer les géométries des bons plans avec les candidats proposés, indépendamment de leur ID.
Une λ présente dans le rejeu local peut être absente de la grille native : enregistrer ce cas. Une
projection vers la λ autorisée la plus proche et une extension de la grille sont deux expériences différentes.
Ne pas injecter 613/688 nm de force dans tous les composants.

Les traces doivent copier leurs structures avant qu’un autre étage puisse leur ajouter des tableaux
NumPy : une mutation tardive a déjà cassé l’export. Vérifier copie, sérialisation et sauvegarde finale
même après un échec de trace ; ne jamais avaler l’exception. La trace doit déléguer chaque appel physique inchangé.

**Fin de R2 :** un tableau explique pour chaque géométrie de référence où elle disparaît et avec
quelle preuve. Choisir ensuite **une seule cause prioritaire** à traiter en R3.

### R3 — une modification native dictée par la trace

La première paire doit comparer une base forte à une variante qui ne change qu’un facteur.
La base forte conserve l’ordre historique, `elite_rate_balanced_moves=false`, budget Rate240 et
six raffinements. Elle n’est pas le défaut livré : ces paramètres sont des surcharges de campagne.
Comparer aussi les résultats aux plans fixes9900001,9900006,9900008 après notation homogène.

| Diagnostic R2 | Première expérience proposée | Paramètres conservés | Preuve nécessaire |
|---|---|---|---|
| Géométrie utile jamais proposée | Étendre les largeurs du voisinage conjoint de2/4/6 à1..7 | Budget conjoint480, Rate240, six tours, même sélection | Géométrie admissible réellement générée et score homogène final |
| Géométrie proposée mais λ utile absente | Ajouter un raffinement local autour des λ disponibles, avec filtrage sur la grille native | Même géométrie, mêmes plafonds, même priorité des familles | Liste de λ reçue/proposée, aucune λ illégale |
| Famille utile évincée du plein | Tester un quota expérimental de6 places, puis12 seulement si6 aide | Plafond total plein36, même screening/objectif | Candidats auparavant écartés réellement notés, budget total inchangé |
| Bonne famille notée mais jamais parent | Tester une sélection de parents à profondeur homogène | Même générateur, mêmes budgets, même poids de consensus | Scores comparables et parent retenu au tour suivant |
| Bonne famille trop tardive | Changer uniquement sa place dans l’ordonnancement ou le partage du budget | Même ensemble/plafond, même physique | Parcours chronologique montrant l’effet, pas seulement un compteur total |

Ces options sont **des propositions**, pas des paramètres déjà implémentés. Choisir une ligne après
le diagnostic, préparer la spécification et le test de son chemin inactif, puis faire l’A/B. Ne pas
ajouter simultanément des largeurs impaires, un quota et une nouvelle politique de parents.

Pour les largeurs impaires : reprendre le générateur pur existant, sans constantes propres à75 couches.
Les longueurs1..7 et déplacements initiaux±2 constituent le premier facteur ; un déplacement±3 serait
un autre essai. Respecter les bornes de chaque bloc, les masques Rate et les contrats de reconstruction.
Pour le préfixe, parcourir2..fin du premier bloc ; distinguer sa longueur et sa λ, comme le faisaient
les recherches locales. Répartir les propositions entre parents et fenêtres sans rendre le résultat
dépendant de l’ordre d’un set. Dédupliquer avant consommation du budget, avec la signature du projet.

Pour un quota : les6 ou12 places **font partie des36**, elles ne s’y ajoutent pas. Répartir le solde
entre les anciens candidats ; définir le repli si la nouvelle famille a moins de candidats admissibles.
Un quota doit être éteint par défaut et ne jamais rendre admissible un plan rejeté scientifiquement.
Le résultat de l’équilibrage initial impose cette prudence : diversifier un budget peut évincer le bon chemin.

Pour des parents homogènes : ne pas transformer un score de base en score de consensus par étiquette.
Évaluer réellement le sous-ensemble choisi avec les mêmes graines/profondeurs, ou conserver les
catégories séparées. Enregistrer le coût supplémentaire ; un nouveau consensus partout peut être coûteux.
Le poids `consensus_std_weight` actuel0,35 et la formule d’objectif restent inchangés.

**Séquence bornée :** au plus trois hypothèses R3, choisies l’une après l’autre, chacune avec une
paire contrôle/variante native sur101. Figer le gagnant de chaque paire avant les groupes frais.
Une variante sans gain de recherche à profondeur homogène ne reçoit pas une longue confirmation.
Une variante gagnante reçoit trois groupes frais appariés ; si l’effet est petit ou hétérogène,
réserver trois autres groupes avant inspection, puis conclure sans poursuivre indéfiniment.

**Critère de travail proposé, à figer dans le protocole :** gain moyen et médian positifs contre la
base forte, gain sur au moins deux des trois premiers groupes, aucun nouveau rejet physique ;
pour considérer le gain comme solide, viser les trois groupes favorables ou élargir à six avec
au moins cinq gains. Rapporter toujours la pire perte. Ce critère n’est pas un intervalle de confiance
et ne suffit pas à changer un défaut. Une petite amélioration qui ne se confirme pas reste expérimentale.

**Livrable :** trace de génération et sélection, paire native, plans finaux renotés, groupes indépendants,
diff et coût. Un rejeu local du meilleur plan ne constitue pas une preuve que le natif l’a trouvé.

### R4 — raffinement local alterné, puis petit faisceau si nécessaire

Cette phase teste une voie plus directe si les ajouts pendant ELITE se dispersent dans le screening.
Le raffinement local se place **après** une sélection homogène des meilleurs plans, et doit rester
désactivé dans le comportement livré tant que sa validation native n’est pas faite.

Premier prototype : partir de deux parents conservés,9900006 et9900008, et de la référence comme ancre.
Choisir un parent de départ natif dans une expérience distincte pour démontrer l’usage automatique.
Le départ depuis le plan local déjà optimisé mesure seulement le potentiel résiduel, pas la capacité de découverte.

1. Pour un parent, faire varier ensemble longueur/position d’une fenêtre optique et sa λ ; ne pas
   transformer tous les blocs Rate en fenêtres. Conserver les autres fenêtres et métadonnées.
2. Parcourir un voisinage grossier légal, puis un voisinage fin autour des meilleurs candidats de101.
   La grille fine n’est pas une permission d’inventer des λ absentes de `available_wls` dans le natif.
3. Retenir au plus quatre plans de signatures distinctes ; diversifier d’abord les masques, puis les λ.
   Utiliser un tri stable dont les critères sont écrits avant les scores.
4. Alterner fenêtre interne puis préfixe, au plus deux passes ; une passe sans gain arrête cette voie.
   Ne pas combiner arbitrairement plusieurs changements physiques dans un seul candidat.
5. Limiter à **1200 propositions nouvelles au total**, hors ancres, sur ce prototype. Conserver un
   compteur de propositions, contrats rejetés, doublons, scores non finis et consensus incomplets.

Chaque groupe garde les ancres et le plafond de douze candidats de consensus : trois ancres plus
neuf propositions au maximum. Les champs hérités et le transfert Workerfloat32 sont ceux des replayers.
Ne pas renoter des changements de λ dans un bloc entièrement Rate comme s’ils produisaient une nouvelle
stratégie physique ; enregistrer leur équivalence sans attribuer un gain de temps à cette seule déduplication.

Le meilleur plan de101 est figé avant trois nouveaux groupes frais. S’il bat seulement la référence
mais perd contre9900006/9900008, il ne représente pas un progrès sur le résultat disponible.
Si le faisceau ne donne aucun gain indépendant, conserver les résultats et abandonner cette extension.
Un nouveau faisceau plus large demanderait un nouveau protocole, pas une boucle sans fin.

**Passage au natif :** tester le même raffinement depuis les meilleurs parents automatiquement sortis
de STRAT. Comparer recherche native avec/sans ce passage final, mêmes conditions ; comptabiliser son
budget supplémentaire. La voie locale est prometteuse parce qu’elle a déjà amélioré les fenêtres,
mais son intégration de production reste un travail à faire.

### R5 — intégration de la voie retenue et validation complète

Ne porter dans le cœur que la voie qui a passé la mesure native et sa confirmation. Réutiliser
les modules et constructeurs existants ; garder les générateurs purs dans le voisinage Rate existant.
L’adaptateur expérimental qui patche temporairement des fonctions est une preuve de campagne,
pas l’architecture finale. Ne pas ajouter de dépendance ou de framework de recherche.

Points d’intégration à relire :

- `certus/core/certus_strat_robustness_rate.py` pour les mouvements et candidats Rate.
- `_generate_elite_candidate_strategies` et sa closure `_push_candidate` pour IDs, signature et héritage.
- `_apply_elite_refinement_if_enabled` pour tours et admission au plein.
- `_select_consensus_candidates` pour notation homogène et admission au consensus.
- `certus/core/certus_strat_leviers.py` pour une éventuelle option expérimentale correctement routée.
- `certus/ui/certus_strat_ui_state.py` pour la collecte seulement, si une option doit réellement être exposée.

Ne pas passer `max_candidates=0` au générateur historique pour prétendre l’avoir désactivé : son
implémentation le borne à au moins1. Le prototype utilisait un patch temporaire des mouvements
pour son deuxième appel ; remplacer cette astuce par un flux explicite, minimal et testé.
La route désactivée doit appeler le chemin historique sans modifier sorties, ordre, IDs ou curseur.

Les blocs, `rate_layers`, fente/facteur de bruit et témoins doivent être hérités exactement. Les
structures des parents ne doivent pas être mutées. Les patchs des tests/prototypes se restaurent
même après une exception. Garder le cœur indépendant dePyQt et les limites d’architecture actuelles :
`certus_strat_consensus.py`1500 lignes, fonction ELITE300 ; ne pas relever ces plafonds dans le registre.

Vérifications ciblées à préparer : chemin éteint absent/False/zéro selon l’option ; déterminisme
ordre/IDs ; héritage Rate/fente/témoins ; contrats aux frontières ; parents inchangés ; quota total
constant ; candidat actif utile ; export complet/incomplet. Au moins une régression active doit
échouer sur l’ancien code, pas seulement comparer deux copies de la nouvelle implémentation.

Comparer ensuite les plans et paramètres de l’implémentation intégrée à ceux du prototype sur un
corpus déterministe, puis mesurer réellement le natif intégré. Un générateur équivalent n’implique
pas automatiquement une sélection équivalente : vérifier aussi les parcours jusqu’au consensus.

La validation finale requiert toutes les commandes de§8.3, hors mesure. Pour tout changement de noyau,
ajouter `c1_diff.py` froid contre froid et oracle avant/après selon CLAUDE. Une recompilation Numba
peut changer les derniers bits : ne pas accepter un écart silencieux parce que le SEEL arrondi est identique.

**Décision de livraison :** pas de commit avant validation complète, revue du diff et bilan des
résultats. Aucun push/publication autorisé. L’activation d’un nouveau défaut scientifique reste une
décision utilisateur après plusieurs graines et composants ; l’autonomie des essais ne l’active pas.

### R6 — vérifier la généralisation de la recherche native

Commencer seulement avec une voie native prometteuse et correctement testée. Toutes les comparaisons
sont appariées : même composant, mode, graine de recherche, bruit, fente, témoins, profondeur et
sources hors facteur étudié. Rejouer les plans finalistes à profondeur homogène lorsque leurs scores
exportés ne l’étaient pas. A2 compare l’ancien `elite_rate_moves`, pas les nouveaux voisinages proposés.

| Ordre | Cas proposé | But | Nombre maximal de recherches natives |
|---:|---|---|---:|
| 1 | `r75x0.5 deep`, graines77,202,404 | Capacité de découverte hors101 | 3 paires, soit6 |
| 2 | `48c premium`, graine77, recherche de fente1 | Interaction avec un autre composant et la fente | 1 paire, soit2 |
| 3 | `r75x1.5 deep`, graine42 | Autre épaisseur, comparaison avec le contexte A2 | 1 paire, soit2 |
| 4 | `r75x2 deep`, graine77 | Cas plus éloigné et coût plus lourd | 1 paire, soit2 |

Cette liste est un programme proposé, pas une mesure déjà faite. Les paramètres exacts des huit
arguments se reprennent dans les cellules du contrôleur A2 ou l’aide du probe ; le seul argument
`slit_search` diffère pour48c. Ne pas reconstruire une commande depuis le nom du dossier seulement.

Pour chaque paire, figer les plans de sortie avant au moins trois groupes frais propres à ce cas.
Les graines de recherche202/404 sont du contexte déjà utilisé pour d’autres replays : elles servent
ici à diversifier la recherche, pas à être annoncées comme confirmations fraîches du résultat historique.
Réserver les nouvelles graines de validation dans le protocole de généralisation avant inspection.

Passage à la suite : gain indépendant sur au moins deux des trois recherches `r75x0.5`, bilan favorable
de la troisième ou régression explicitement comprise, sans nouveau défaut physique. Sinon analyser
et arrêter le déploiement à d’autres composants ; conserver l’option expérimentale. Ne pas forcer
L1–L5/613 ou L35–L37/688 sur tous les cas. Chaque cas négatif compte dans le bilan.

**Livrable :** tableau par cas/graine, résultats natifs et replays, gains contre leur propre contrôle,
dispersion, pire perte, coût et provenance. La portée de la conclusion ne dépasse pas ce corpus.

### R7 — modèle de vitesse entre dépôts : chantier distinct

Cette phase nécessite des données quantitatives encore absentes. Elle ne bloque pas R1–R6.
Demander ou exploiter des séries disponibles pour chaque matériau H/L : vitesse et unité, moyenne,
dispersion entre dépôts, corrélation des deux matériaux, méthode et moment de calibration, durée,
recalibrations/témoins et éventuelle évolution pendant le dépôt. Écarter toute donnée personnelle ou
secret d’un tiers avant indexation dans ce dépôt public.

Auditer d’abord `certus/physics/certus_strat_growth.py`, les branches Rate, l’estimateur de vitesse
et ses mises à jour optiques. Une erreur constante de vitesse par dépôt peut être absorbée par une
calibration optique initiale ; c’est une hypothèse à éprouver, pas une conclusion acquise. Distinguer
vitesse nominale, vitesse réelle et vitesse estimée utilisée pour arrêter une couche au Rate.

Si un nouveau modèle est justifié : perturbation tirée par dépôt/matériau, commune aux plans comparés
selon C2, cohérente avec temps, croissance optique et Rate. Ne pas simplement multiplier l’épaisseur
des seules couches Rate pour simuler toute la machine. Un paramètre de dispersion0 doit conserver
exactement les bits historiques ; amplitude mesurée, scénarios et sensibilité documentés avant essais.
Tout changement de physique nécessite les oracles et C1, une expérience dédiée et une nouvelle référence.

## 7. Périmètre autonome et critères d’arrêt

La décision actuelle autorise cette IA à préparer, vérifier et mesurer le programme ci-dessus après A2,
sans redemander l’accord pour une routine déjà couverte. Elle ne demande ni publication, ni changement
de défaut, ni suppression d’artefacts. Le modèle machine R7 attend les données manquantes.

Le programme est borné : A224runs ; R0un contrôle de trois plans ; R2au plus une nouvelle trace de base
si les traces conservées ne suffisent pas ; R3au plus trois paires et leurs confirmations conditionnelles ;
R4deux passes/1200propositions au total ; R6six paires si les premières conditions passent.
Les durées anciennes donnent un ordre de grandeur, pas un ETA garanti des nouveaux cas.

Arrêter une voie, sauvegarder et rapporter si :

- Un point fixe strict, le contrat de plan, les sources ou C1 ne sont plus vérifiés.
- Une erreur de contrôleur reste non réparable sans toucher un calcul vivant : le laisser finir et conserver son état.
- Les confirmations contredisent le gain de recherche, ou le budget borné est épuisé.
- Le coût supplémentaire rend la voie peu utile : chiffrer les durées comparables et le coût de notation.
- La suite exige une amplitude machine inconnue ou une activation/publication non demandée.

Un échec de test présent avant modification doit être signalé et résolu suivant CLAUDE ; ne pas le
masquer. Les échecs scientifiques de candidats non finis ne sont pas des erreurs du contrôleur :
ils sont conservés et exclus de la sélection. Un run global peut continuer normalement après eux.

## 8. Commandes et procédures utilisables

### 8.1 Sonde officielle : ordre des arguments et surcharges

Commande existante pour le cas de développement, **à lancer uniquement hors mesure et avec le protocole préparé** :

```powershell
python scripts/probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 101 0
```

Les huit valeurs désignent composant, mode, activation de recherche de fente (`fente`), minimum de
points tournants (`min_tp`), largeur de fente (`res_nm`), profil d’exploration élargie (`elargi`),
graine, choix de surcharges Rate (`par_swing`). Le dernier0 garde les réglages de production,
il ne signifie pas « Rate éteint ». Vérifier leur définition
dans `main()` avant une nouvelle expérience : cette ligne conserve les huit valeurs de la référence,
elle ne documente pas de nouveaux leviers. `CERTUS_PROBE_OVERRIDES` transporte les paramètres
de recherche reconnus ; `CERTUS_PROBE_TAG` distingue la sortie. Lire le routage effectif dans le journal
et dans l’artefact, pas seulement l’environnement du parent.

```powershell
$env:CERTUS_PROBE_OVERRIDES = 'elite_rate_balanced_moves=false,elite_rate_max_candidates=240,elite_rounds=6'
$env:CERTUS_PROBE_TAG = 'rate_suite_baseline_unique'
```

Cette préparation seule ne lance rien. Restaurer ces variables après usage pour ne pas contaminer
un autre run. Ne pas envoyer à cette sonde un nom d’option R3 non implémenté : l’absence de routage
ne serait pas un résultat négatif de la proposition.

Les prototypes natifs existants proposent `--joint-budget`, `--rate-budget`, `--elite-rounds`,
`--seed` et `--plan`. Leurs gardes temporelles anciennes sont expirées : utiliser de nouvelles copies
relues et validées, puis une commande d’aperçu avant lancement. Il n’existe pas encore une CLI de
production pour les quotas ou le faisceau proposés dans ce guide.

### 8.2 Ressources et lancement Windows

Privilégier les contrôleurs existants correctement adaptés : ils posent les limites avant de créer
le Worker, enregistrent les ressources et vérifient la provenance. Ne pas lancer un probe isolé sans
ce contrôle. `PYTHON_CPU_COUNT=24` et les variables de threads ne remplacent pas l’affinité Windows.

Pour préparer un contrôleur neuf, garder :

```powershell
$env:PYTHON_CPU_COUNT = '24'
$env:OMP_NUM_THREADS = '23'
$env:OPENBLAS_NUM_THREADS = '23'
$env:MKL_NUM_THREADS = '23'
$env:NUMEXPR_NUM_THREADS = '23'
$env:NUMBA_NUM_THREADS = '23'
```

Utiliser `Start-Process -WindowStyle Hidden -PassThru`, prioritéNormal, affinité16777215 (`0xffffff`), et journaux
stdout/stderr propres au dossier de tentative. Citer les arguments contenant des espaces comme le
font les contrôleurs existants. La fonction de limite du helper doit agir avant les imports lourds
et le lancement des enfants ; réduire l’affinité après le début d’une simulation ne prouve pas son héritage.
Vérifier chaque enfant scientifique via `Get-Process`, son journal de workers et ses appels réels.
Le maximum24 ne garantit pas24workers : le nombre de workers est aussi déterminé par le code.

Avant lancement : aucun enfant scientifique actif, empreintes inchangées, contrôleur unique, lock
cohérent, test/aperçu passés, dossier neuf et paramètres figés. Après lancement : vérifier une fois
le statut, l’enfant, les limites et les journaux ; éviter un sondage serré qui n’apporte rien.

### 8.3 Vérifications de code hors calcul scientifique

Pour la première itération, cibler les tests des sources réellement modifiées. Les fichiers existants
à relire incluent `test_strat_elite_rate_moves.py`, `test_strat_elite_round_robin.py`,
`test_elite_children_keep_what_their_parent_carries.py`,
`test_elite_children_are_judged_with_the_slit_bias.py`, `test_strat_strategy_id_ranges.py`,
`test_certus_strat_context.py`, `test_the_architecture_debt_only_shrinks.py`,
`test_strat_optics_after_rate.py` et `test_strat_rate_and_resolution.py`, sous `tests/unit/`.
Ne pas affirmer que tous couvrent une nouvelle option : lire leurs assertions et ajouter la régression nécessaire.

Validation complète requise avant commit :

```powershell
python -m ruff check .
python -m pytest tests/oracle/ -q --no-cov
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov
python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui
python scripts/coherence_md.py
python scripts/check_claude_md.py
python scripts/check_docs.py
git diff --check
```

Changement de noyau : ajouter `python scripts/c1_diff.py HEAD` et les contrôles froids selon CLAUDE.
Ne pas exécuter cette liste pendant A2 ou un rejeu. En l’absence d’un outil IDE/LSP, utiliser les
diagnostics statiques disponibles et écrire cette limite ; une commande non lancée reste non lancée.
Les commandes `/code-review`, `/simplify`, `/verify` du standard utilisateur ne sont pas des exécutables
PowerShell : utiliser leur capacité si disponible ; sinon réaliser la revue ou vérification correspondante
et ne pas prétendre avoir appelé une commande indisponible.

### 8.4 Reprise après extinction ou crash

1. Preflight puis états/processus ; vérifier le dernier artefact et ses sources, ne pas repartir du premier run.
2. Préserver les fichiers d’état/tmp/locks/logs de l’échec dans une nouvelle archive de reprise.
3. Un résultat terminé et conforme se réconcilie avec le checkpoint. Un calcul incomplet se reprend
   au dernier groupe sauvegardé ; son groupe interrompu peut devoir être recalculé.
4. Aucune double adoption, aucun changement de paramètres en cours de reprise. Pour une nouvelle
   hypothèse, créer un nouveau protocole/dossier ; les anciennes étapes restent attachées à leur source.
5. Relancer seulement après l’absence de l’ancien enfant et les validations de provenance.

Ainsi une extinction ne fait pas perdre les groupes déjà sauvegardés ; elle peut perdre le travail
du groupe courant. Les sauvegardes des contrôleurs et leur granularité déterminent cette limite.

## 9. Format minimal du bilan de chaque expérience

Le résumé machine doit distinguer **sélection native**, **renotation de pool** et **rejeu de plans fixes**.
Il peut suivre cette structure ; les nombres ci-dessous sont des champs à renseigner, pas des mesures :

```json
{
  "experiment": "R3_hypothesis_01",
  "status": "prepared",
  "hypothesis": "cause observée et preuve R2",
  "changed_factor": "un seul levier",
  "code_provenance": {"head": null, "dirty_paths": [], "sha256": {}},
  "protocol_sha256": null,
  "search_seed": 101,
  "native_generation": {"proposed": null, "full_evaluated": null, "consensus_complete": null},
  "actual_depth": {"full_runs": null, "consensus_runs": null, "consensus_seeds": []},
  "fixed_plan_comparisons": [],
  "fresh_groups": [],
  "gain_vs_control_percent": null,
  "gain_vs_reference_percent": null,
  "worst_loss_percent": null,
  "physical_failures_observed": null,
  "elapsed_seconds": null,
  "cache_context": "unknown",
  "decision": "not_evaluated",
  "limitations": []
}
```

Gain en% =100×(SEELcontrôle−SEELvariante)/SEELcontrôle, avec le **contrôle du même groupe**.
Ne pas comparer une variante fraîche à la référence101 d’un autre groupe. Garder les scores bruts
et les niveaux de bruit, pas seulement le SEEL. Une absence de plantage observé n’est pas une preuve
de risque nul en fabrication. Écrire la taille du corpus, les valeurs manquantes et les exclusions.

Le Markdown doit expliquer : facteur changé, résultat et son comparateur, preuve de profondeur,
contrats/provenance, nombre de confirmations favorables, pire cas, coût, décision et prochain essai.
Mettre à jour ETAT en place avec le résultat actuel ; le détail daté reste dans `reports/`.

## 10. Liste de reprise immédiatement applicable

- [x] Terminer le document et relier ETAT/bilan à ce guide.
- [x] Contrôler la transition du nocturne vers la continuation A2, sans double mesure.
- [x] Terminer A2 jusqu’à24/24 et vérifier tous les artefacts.
- [x] Préparer R1 dans l’arbre de développement, conserver les mesures dans leur code figé.
- [x] Analyser statiquement les traces natives existantes pour R2 pendant A2.
- [ ] Hors mesure, vérifier R1 et la validation déjà en attente d’A1/équilibrage ; signaler tout échec.
- [ ] Préparer de nouveaux lanceurs avec provenance et garde propres ; reproduire les trois points fixes R0.
- [ ] Figer le diagnostic R2, choisir une hypothèse R3 et ses graines fraîches avant les nouveaux résultats.
- [ ] Mesurer/confirmer R3 ; passer àR4 ou intégrer selon le diagnostic, dans les limites prévues.
- [ ] Vérifier la voie retenue native et intégrée ; généraliser conditionnellement selon R6.
- [ ] Produire le bilan complet ; conserver les défauts actuels et toutes les preuves.

### Texte de reprise autonome, utilisable dans cette IA ou une autre

> Travaille dans le projet CERTUS `certus0310`. Première commande `python scripts\preflight.py`,
> puis lis `docs/ETAT.md`§0, `CLAUDE.md`, `reports/STRAT_Rate_bilan_2026-10-14.md` et
> `docs/STRAT_Rate_suite_chantier.md`. L’utilisateur autorise depuis le15 octobre la correction RMSE
> puis la poursuite jusqu’à la fin du programme borné R0–R6 ; A2 est complète24/24.
> Cette décision remplace l’ancienne limite de8 h. Les contrôleurs nouveaux vérifient les quotas
> restants avant chaque mesure, y compris les confirmations. Les anciens lanceurs ne sont pas modifiés.
> Inspecte checkpoint, continuation et processus avant toute action ; ne lance pas un deuxième
> contrôleur. Une seule mesure,24processeurs/0xffffff/Normal/23threads ; aucun test pendant une mesure,
> aucun arrêt scientifique. Pendant A2, prépare R1 et analyse les traces R2 sans modifier les sources
> figées. Après libération de la machine, vérifie le code et les points fixes, puis change un seul
> facteur à la fois. Référence0,3967147882nm, meilleur local0,3345159946nm ; le gain local confirmé
> ne prouve pas encore la découverte automatique native. Les exports peuvent mélanger base/consensus :
> conserver les métadonnées, observer la profondeur réelle, figer avant confirmations fraîches.
> Préserve tous les rapports, sources, graines, rejets et échecs. Aucune activation de défaut, aucun
> push/publication, aucun commit avant validation complète. R7 attend des données machine quantitatives.
> Tiens ETAT et le guide à jour ; informe seulement pour un résultat utile, un échec ou une décision.
> Quand les phases autorisées sont terminées ou nécessitent une décision, rends un bilan honnête et
> mets le suivi en pause, sans multiplier les essais au-delà du programme.

## 11. État de préparation de ce guide

Le suivi existant `certus-essais-rate-jusqu-au-14-octobre-9-h` est **ACTIVE** le15 octobre,
« CERTUS — corriger RMSE puis finir R0–R6 », dans le même chat. L’autorisation nouvelle porte sur
le correctif puis la fin du programme borné, à24/23 ; l’ancienne limite de8 h est remplacée.
Les configurations précédentes sont conservées. Aucun nouveau suivi doublon n’a été créé.
**Correctif RMSE, R0/R2 validés ; R3_h01 terminé sans gain, R3_h02 engagé à12 h42.** Voir§12 pour la reprise actuelle.
Le blocage initial du14 octobre et sa contre-épreuve
sur la base propre restent décrits dans le rapport daté ci-dessous ; l’autorisation de le corriger est reçue.
[Preuves, bilan et procédure de reprise](../reports/STRAT_Rate_suite_2026-10-14/validation_after_A2/blocker_20261014/bilan_et_reprise.md).

Au14 octobre à17 h01 Paris : **A2 terminée24/24 à16 h35**, continuation et contrôleur original
terminés, aucun processus/contrôleur ni verrou résiduel. Worktree A2 figé et propre ;
[audit complet et bilan](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md)
conservés, options effectives/provenances/SHA256 vérifiées. Preuves de transition et santé dans
`reports/STRAT_A2_continuation_2026-10-14/`. Ce relevé daté ne remplace jamais les JSON et processus présents lors de la reprise.
Paire75c complète :0,2407378291 avec /0,2408512734 sans, gain brut0,0471 %, aucun progrès établi.
Paire48c/premium/77 :0,1922274813 nm avec,2602 déposables,8 min46 s ;0,1911013642 sans,
2472 déposables,8 min18 s. Régression brute0,5893 %, aucune supériorité établie.
Paire48c/premium/101 :0,1919806063 avec /0,1922429122 sans ; gain brut0,1364 %, aucune
supériorité établie, verdict/provenance/options effectives/empreintes vérifiés.202/avec sauvegardé à12 h04 :
0,1873016155 nm,2575 déposables,8 min47 s ;202/sans sauvegardé à12 h12 :0,1879353657 nm,
2482 déposables,8 min16 s, contrôles vérifiés. Gain brut0,3372 %, aucune supériorité établie.
Les profondeurs déclarées premium150/25/40/150 et deep300/50/100/300 restent distinctes ;
les exports A2 figés n'ont pas la provenance complète de consensus.
Paire `r75x0.5`/77 complète :0,4362542820 nm avec,3675 déposables,38 min39 s ;0,4943430491 sans,
3594 déposables,37 min21 s. Gain brut11,7507 % pour les mouvements Rate de production existants ;
artefacts/provenances/options/empreintes vérifiés, confirmation homogène indépendante encore à faire.
Ce n’est pas une mesure de l’intégration native du nouveau raffinement local. Pas de comparaison directe
à la référence101 ou au plan local : graine de recherche distincte et notation homogène non vérifiée.
[Contrôle de la paire](../reports/STRAT_A2_continuation_2026-10-14/progress_20261014_1330.json).
`r75x2`/202 avec sauvegardé à14 h16 :0,5411587816 nm,4964 déposables,48 min16 s,
Sans sauvegardé à15 h02 :0,5678354293 nm,4168 déposables,45 min29 s, contrôles vérifiés.
Paire202 complète : gain brut4,6980 %, aucune supériorité établie ni confirmation homogène indépendante.
Composant distinct de `r75x0.5`, aucune comparaison directe des SEEL.
[Contrôle de la paire](../reports/STRAT_A2_continuation_2026-10-14/progress_20261014_1500.json).
`r75x2`/77 avec sauvegardé à15 h51 :0,5440634380 nm,4744 déposables,49 min18 s ;
verdict/provenance/option effective/empreinte vérifiés. Sans sauvegardé à16 h35 :0,5713569313 nm,
3754 déposables,44 min12 s, mêmes contrôles vérifiés. Gain brut4,7770 %, sans confirmation homogène
indépendante. [Audit final](../reports/STRAT_A2_continuation_2026-10-14/final_audit_20261014_1700.json).
Les phases R3–R7 et leurs résultats futurs ne sont pas validés par cette documentation. La préparation
de R1 et le diagnostic statique R2 doivent être consignés séparément avec leur validation réelle.

Les préparations datées du14 octobre ci-dessous restent des archives : leurs attentes de validation et
anciennes CLI ne décrivent pas la reprise courante, consignée en§12.

**R1 préparée le14 octobre à9 h23 :** `scripts/probe_blocs_vs_plantage.py` exporte les deux scores
séparés et `robustness_consensus_meta`, sans reclasser ni modifier le score historique. Les métadonnées
et `witness_reset_layers` sont copiées pour éviter la mutation des résultats sources ; absence→null.
`tests/unit/test_probe_keeps_consensus_score_provenance.py` exerce la sortie de `mesurer()` avec un
Worker substitué, pour consensus complet/incomplet et métadonnées absentes. **3 passed avec R1 ;
les mêmes3 tests échouent sur le code avant R1 pour les champs absents.** Premier montage d’import
du snapshot échoué puis réparé, sans changement de source ; toutes les tentatives conservées dans
`reports/STRAT_Rate_suite_2026-10-14/validation_after_A2/`. Ruff et oracle1143 passed ; unité échouée :
5428 passed,7 skipped,2 failed en31 min04 s. Ré-export manquant du helper d’équilibrage corrigé
dans la façade principale ; écart strict de pondération uniforme5,55e-17 en expertise avec cache neuf.
Contrôle ciblé à froid dans `targeted_repair_attempt_01/` :65 passed,1 failed, ré-export corrigé validé.
Contre-épreuve `baseline_spectral_attempt_01/` :A2 propre au même HEAD,4 passed,1 failed,
même écart d’un ULP ; noyau et test identiques, pas de simple cache chaud. Cause compilée précise
encore à instruire, noyaux/tests et worktrees figés inchangés. Décision requise avant R0/R2.
Les suites UI/reste et contrôles documentaires restent à terminer ; aucune nouvelle mesure Rate lancée.
Snapshot avant/après et SHA256 dans
[`R1_score_export/prepared.json`](../reports/STRAT_Rate_suite_2026-10-14/R1_score_export/prepared.json).
Le nombre `n_samples` compte les scores de graines, pas le nombre de tirages physiques par graine ;
la profondeur de consensus réelle reste à observer en R2. Le worktree A2 n’a pas reçu ce changement.

**R2 statique terminée le14 octobre :** [analyse et limites](../reports/STRAT_Rate_suite_2026-10-14/R2_static_trace_v2/analysis.md),
JSON détaillé et script figé dans le même dossier. Les deux couples utiles688/613 sont absents des
familles supplémentaires tracées ; ni leur disponibilité dans la grille ni leurs étapes de sélection
ne peuvent être reconstituées à partir des traces actuelles. Première action R2 suivante : nouvelle
trace qui conserve grille/parents/étapes, avant de choisir entre génération et sélection en R3.
La version initiale du comptage reste conservée ; la version2 vérifie signatures et chronologie.

**Observateur R2 préparé à9 h43 :** `scratch/rate_native_pipeline_trace.py` contient les wrappers
passifs de grille/parents, génération, contrats rejetés, seuil nominal, appels physiques,
sélection/configuration/cache de consensus et résultats finaux. Snapshot/SHA256, Ruff et parsing dans
[`R2_pipeline_trace_preparation/prepared.json`](../reports/STRAT_Rate_suite_2026-10-14/R2_pipeline_trace_preparation/prepared.json).
**Raccordement préparé à10 h18, non exécuté et non validé runtime.**
`scratch/rate_native_pipeline_probe.py` reprend la recette native480/240/six tours avec `functools.wraps`,
une échéance/tag explicites et des gardes obligatoires : A2complète24/24, absence d’autre processus,
vérificationGO aux mêmes sources et contrôle R0 valide des trois plans/graines/profondeurs observées.
`scratch/verify_rate_native_pipeline_trace.py` prépare les contrôles de délégation et restauration,
sans simuler un dépôt. [Snapshots et commandes](../reports/STRAT_Rate_suite_2026-10-14/R2_native_trace_launch_preparation/commands.md).
Ruff/parsing passent ; aucun test ni aperçu de cette CLI exécuté pendant A2. R0 est préparé ci-dessous.
Les sorties privées de budget/dédoublonnage ne sont pas
exhaustivement observées ; cette limite doit rester visible. Aucun nouveau gain mesuré.
La [revue statique de préparation](../reports/STRAT_Rate_suite_2026-10-14/R2_native_trace_launch_preparation/static_review_20261014.md)
précise les jointures : ID provisoire réutilisable après refus de contrat, ordre de fin des tâches
distinct de l'ordre de sélection, seuil avant journalisation du tour et fallback d'une étape vide.
Ces règles d'analyse ne remplacent pas le vérificateur runtime ni la future mesure R2.

**R0 préparé le14 octobre :** nouvelle copie `scratch/rate_fixed_replay_R0_suite.py`, protocole de
contrôle et snapshot des trois plans dans [la préparation R0](../reports/STRAT_Rate_suite_2026-10-14/R0_replay_preparation/commands.md).
Contrôle seulement, garde explicite, A2complète/machine libre obligatoires, sauvegardes atomiques.
AST scientifique identique àv11 et Ruff vert ; aucune exécution/mesure de cette copie encore faite.
Le [protocole borné au15 octobre8 h](../reports/STRAT_Rate_suite_2026-10-14/autonomie_jusqu_20261015_0800/protocol_R0_until_20261015_0800.json)
et ses [commandes](../reports/STRAT_Rate_suite_2026-10-14/autonomie_jusqu_20261015_0800/commands.md)
restent des archives de préparation. La continuation autorisée le15 octobre exige de nouvelles copies,
une provenance mise à jour et des gardes de quotas, comme décrit en§12. Ne pas employer les anciennes CLI telles quelles.

## 12. Continuation autorisée le15 octobre : RMSE puis R0–R6

**Autonomie confirmée le15 octobre jusqu’à demain matin.** Le repère annoncé par l’IA est le
**vendredi16 octobre2026 à8 h Paris, soit06:00UTC** : aucun nouveau test ni mesure après ce repère.
La fin des quotas R0–R6 reste une condition d’arrêt plus précoce. L’IA tranche les choix techniques
courants et réparations sûres sans nouvelle question, à partir des preuves ; elle n’invente ni donnée
machine ni approbation hors périmètre. À8 h, conserver et laisser finir le calcul engagé, sauvegarder
et rendre le bilan, puis mettre le même suivi en pause. Les futurs lanceurs doivent vérifier cette
limite avant chaque lancement, dans de nouvelles copies ; scripts scientifiques vivants inchangés.
[Demande exacte, interprétation horaire et limites](../reports/STRAT_Rate_suite_2026-10-15/autonomie_jusqu_20261016_0800/authorization.json).

La décision actuelle et les ressources24/23 sont consignées dans [l’autorisation](../reports/STRAT_RMSE_uniform_weights_2026-10-15/authorization_and_baseline.json).
Le [rapport RMSE et plan de reprise concret](../reports/STRAT_RMSE_uniform_weights_2026-10-15/bilan_et_reprise.md)
porte le diagnostic, les tentatives rejetées, les comparaisons à froid et les limites ; ne pas confondre
ces contrôles numériques avec un gain de stratégie. Les assertions strictes restent en place.

Le [contrôleur de validation générale courant](../reports/STRAT_RMSE_uniform_weights_2026-10-15/full_validation_02/validation.json)
est terminéGO le15 octobre à9 h06 : groupe restant359 passed, documentation verte, C1froid8008 tableaux
identiques au bit. La première validation échouée reste conservée ; les suites inchangées sont reprises
avec leur provenance explicite. Le suivi existant est réactivé dans ce même chat,
avec le repère annoncé du16 octobre8 hParis ; il se met en pause à la première limite atteinte, à la fin des quotas ou si aucune réparation sûre ne permet de progresser.

Contexte de mesure distinct créé : [HEAD, sources, cache et préflight](../reports/STRAT_Rate_suite_2026-10-15/reference_context.json),
worktree géré `rate-rmse-r0`. Cinq fichiers de calcul/sonde copiés ; les24 autres écarts d’octets sont
uniquementCRLF/LF, sources normalisées/AST identiques. Les copies des lanceurs sont contrôlées par
l’autorisation et les quotas finis de§7. Les protocoles historiques et leurs
attentes ne sont jamais réécrits pour accepter une source différente. Les trois points fixes et la trace passive
sont vérifiés ; la seule base R2 est terminée et auditée. Le
[bilan de transition actuel](../reports/STRAT_Rate_suite_2026-10-15/bilan_R0_R2_transition_20261015.md)
détaille les preuves et opérations restantes ; les anciens scripts à garde expirée ne constituent pas des commandes actuelles.

Copies du15 octobre : **gardes/aperçusGO, R0 terminéGO, observateurGO, R2 terminé à10 h13 Paris** :
`scratch/rate_fixed_replay_R0_bounded.py`, `scratch/rate_native_pipeline_probe_bounded.py` et
`scratch/verify_rate_native_pipeline_trace_bounded.py`. La garde commune
`scratch/rate_suite_bounded_guard.py` impose validation généraleGO, empreintes validées, A2complète,
machine libre et un seul emplacement permanent pour chacun des contrôles R0/R2. Une réservation
reste conservée après échec ; aucune répétition silencieuse. Sources et SHA dans
[la préparation des lanceurs actuels](../reports/STRAT_Rate_suite_2026-10-15/launcher_preparation/preparation_current_03.json).
[R0 auditéGO](../reports/STRAT_Rate_suite_2026-10-15/R0_verified.json) : trois plans complets et douze appels
effectifs à300tirages101/41/42/43 ; les références sont reproduites dans le nouveau contexte numérique.
[ObservateurGO](../reports/STRAT_Rate_suite_2026-10-15/observer_verification/verification.json) aux empreintes exactes.
[R2 terminé](../reports/STRAT_Rate_suite_2026-10-15/R2_native_base/etat.json), processus32588 terminé,
tag `r2_rmse24_20261015_v1` ; recette480/240/six tours, préfixe0, équilibragefalse. R0/R2 ont chacun
consommé leur réservation unique. [AuditGO et diagnostic](../reports/STRAT_Rate_suite_2026-10-15/bilan_R2_diagnostic_R3_20261015.md) :
5353 stratégies,1076 lignes de consensus complet, meilleur natif historique0,3600608863nm retrouvé.
La grille légale contient613/688 ; aucune proposition conjointe ne reconstruit directement la fenêtre interne
de trois couches avec sa λ. Les348 occurrences de cette géométrie sont héritées. Cela motive le premier
facteurR3 : largeurs2/4/6 contre1..7, sans changer le flux de λ ni les autres budgets ou la sélection.

Le rejeu R0 observe une inversion de classement : la base101 préfère9900006, le consensus41/42/43
préfère9900008. Cela motive l’inspection des parents avant/après consensus ; la trace doit aussi dire si
la géométrie utile et sa longueur d’onde sont proposées. Ne pas conclure à une causalité avant cet audit.
L’affinité effective24 et les plafonds23 sont vérifiés. La paireR3 déclare aussiCPU24 au démarrage
de chaque interpréteur, de façon identique ; ne pas attribuer une différence de temps contreR2 au code.

**R3_h01 engagé à10 h35 Paris** : [protocole v3 figé](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/protocol_v3.json),
[générateur/observateurGO](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/verification_02/verification.json),
[gardes/quotaGO](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/guard_verification/verification.json).
Contrôle21508 **terminé et auditéGO à11 h20**,44min20s,5412 stratégies ; meilleur natif0,3600608863nm
inchangé. [Audit complet](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/audit_control.json).
Variante17704 terminée à12 h18, coordinateur33592 terminé, sortie0 ;
[état final h01](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/pair_controller_v4.json).
Le premier coordinateur19112 a échoué avant tout enfant, sans consommer de quota : persistance corrigée
dans une copie v2 et [fonction de sauvegarde réellement vérifiée](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/controller_persistence_verification/verification.json).
Le coordinateur36608 échoue après le contrôle parce que PowerShell5.1 renvoie un code de sortie absent
sans handle conservé ; contre-épreuve avec Python vide, avant/après, conservée. Une reprise41504 échoue
avant enfant faute deGet-FileHash ; SHA256.NET remplace cette dépendance et passe sous PowerShell5.1.
La copie `run_rate_R3_widths_resume_variant_v2.ps1` adopte le contrôle audité et lance seulement la variante.
Les anciens états, protocoles préparatoires et scripts restent conservés ; aucun calcul ni quota rejoué.
**Bilan h01 terminé : aucun gain,0,0000 %.** Même meilleur plan complet et score dans les deux voies.
Rejeu homogène de cinq plans uniques,20 appels300tirages101/41/42/43, points fixes reproduits ; aucun
groupe frais consommé. [Bilan complet](../reports/STRAT_Rate_suite_2026-10-15/R3_h01_widths/bilan_R3_h01_20261015.md).
La variante crée347 fois la géométrie interne de trois couches sans jamais688 : ce mécanisme est bien
exécuté, mais ne suffit pas à améliorer le résultat.

**Deuxième paireR3_h02 engagée à12 h42 Paris** : contrôle30284 terminé à13 h25 min38 s, sortie0 enregistrée ;
variante28532 terminée à14 h10 min37 s, sortie0 ; coordinateur24768 terminé à14 h10 min48 s,
[état courant](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/pair_controller.json).
[Protocole exact](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/protocol.json) : largeurs1..7
dans les deux voies, seul facteur =λ du bloc parent et voisins légaux±1/±2/±3 avant le flux historique.
Budgets480/240, six tours, sélection, bruits et physique inchangés. Ce contrôle conditionnel large ne
présente pas les largeurs seules comme gagnantes. Si la combinaison gagne, la troisième paire peut
retirer les largeurs impaires àλ fine identique pour tester l’interaction. Aucun quatrième essaiR3.
[Vérifications, garde, reprise et critères](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/reprise_et_protocole.md).
Aucun doublon ni test pendant la paire ; après sa fin, figer et renoter les finalistes avant une confirmation fraîche conditionnelle.

Audits h02GO :5375/5408 stratégies, les sources/scripts/copies et sorties sont vérifiés.
Renotation homogène38144 engagée à14 h38 : six plans uniques et24 appels300tirages101/41/42/43,22 contrôles de
garde/contrats/ASTGO. [Commande, revue et preuves](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/replay_command_and_review.json).
Aucun gain retenu avant cette renotation ; les12 propositions conjointes[34,37)/688 prouvent seulement leur accessibilité.

**H02 terminé sans gain après24 appels homogènes** : variante0,3600987135nm contre contrôle0,3600608863nm.
Aucun groupe frais consommé. [Bilan et diagnostic des portes](../reports/STRAT_Rate_suite_2026-10-15/R3_h02_wavelengths/bilan_R3_h02_20261015.md).
R4 est terminé/auditéGO :62groupes/518propositions/2198appels300tirages ; branche locale sans gain, natif raffiné0,3431123800nm (gain de recherche4,7071%). [Recherche et limites](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/bilan_R4_recherche_20261015.md).
Confirmation indépendanteGO : sept plans figés, trois groupes/84appels réels, gagnant97000497 fixé avant inspection ;3/3gains natifs, moyenne4,4772%, médiane4,2638%, minimum2,5777%, pire perte0. Le meilleur local9900008 reste devant sur2/3groupes ; secondaire de la seule lignée de contrôle non confirmé1/3. [Bilan de confirmation et incidents conservés](../reports/STRAT_Rate_suite_2026-10-15/R4_refinement/confirmation_01/bilan_confirmation_20261015.md).
Dernière paireR3_h03 terminée/auditée et confirmée3/3 : gain frais propre5,2130% moyen, minimum4,0078%,0/3contre le meilleur local ; trois pairesR3 épuisées. R5 code inactif écrit, validation générale terminéeGO à22h29Paris (5450unité/1324UI/359reste et C1froid8008identiques) ; contexte rate-r5-native séparé et nouveaux slotsR5_points/R5_native préparés/vérifiés, points28340 terminésOK(12appels300), mesureR5 terminée sortie0 à23h31Paris et auditée avec limites (305propositions/307plans du raffinement identiques,29appelsnatifs distincts) ; R6paire77 terminée et confirmée sur72appels300 :3/3gains propres,moyenne1,2541%/médiane1,0523%, effet modeste ; cas202 terminé/auditéGO et confirmé sur72appels300 :3/3,moyenne1,2888%/médiane1,4166%,pire perte0 ;0/3contre meilleur local ; cas404 confirmé3/3,moyenne1,7562%/médiane2,3623%,72appels frais300 ; trois cas favorables,216appels frais ; groupes176100xx/176200xx/176300xx consommés ; autres composants préparés/vérifiés en copiesR6_other_components ; paire48c terminée/auditéeGO, même plan complet et0% de gain frais sur trois groupes/12appels300 ;0nouvelle proposition,8appels post150 ; arrêt précoce de cette extension fixé avant mesure, x1.5/x2 non lancés, quatre pairesR6 consommées sur six ; programme clos, sauvegarde et pause du même suivi, lire R6_generalization/launch_review.md, lire R5_integration/measurement_launch_review.md et measurement_controller.json, aucun doublon : même politiqueλ fine, post-raffinement finaloff/on, parents de la seule sortie native du bras concerné. [Plan concret et critères](../reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/reprise_et_plan.md). R4 prototype clos, aucun reliquat réaffecté ; R5/R6 seulement après preuve native. Les groupes202–3535 et17410001..04/11..14/21..24 sont consommés. Limite16octobre06:00UTC, aucun test/mesure concurrent ni source engagée modifiée.
