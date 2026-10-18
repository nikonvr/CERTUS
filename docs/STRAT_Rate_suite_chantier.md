# STRAT — guide de méthode pour améliorer le Rate

Guide de travail préparé le 14 octobre 2026 à la demande de 👤, élagué le 2026-10-18. Il garde la **méthode** (contrat d'une expérience,
conditions de notation, commandes, reprise après crash, format du bilan) et les **repères** (plans fixes, résultats confirmés et limites,
carte des artefacts). Le récit du programme R0–R6 et les états de préparation en ont été retirés : `git show 9fc49269:docs/STRAT_Rate_suite_chantier.md`
donne la version d'avant (1 010 lignes). Les sections 2, 4, 6 (sauf R7), 7 et 10 à 12 n'existent plus ; la numérotation est conservée.

**Programme borné clos le 16 octobre 2026 par arrêt précoce R6 après 48c sans gain.** [Bilan final, résultats, limites et cas non exécutés](../reports/STRAT_Rate_suite_2026-10-15/final_20261016/bilan_final.md).
Aucun nouveau défaut activé ; toute nouvelle campagne nécessite une décision distincte. L'état courant est dans [ETAT.md, section 0](ETAT.md) ; la
[passation précise du 16 octobre](STRAT_Rate_reprise_20261016.md) décrit le diagnostic 48c et les écarts R5/h03 non résolus ; livraison et restauration des
preuves : [README](../reports/STRAT_Rate_publication_2026-10-16/README.md) ; les règles sont dans [CLAUDE.md](../CLAUDE.md) ; les mesures datées dans
[le bilan](../reports/STRAT_Rate_bilan_2026-10-14.md) et [l'expertise](../reports/STRAT_Rate_expertise_2026-10-13.md). Une piste proposée ici n'est ni
implémentée ni validée par sa seule présence dans ce document.

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


## 6. R7 — modèle de vitesse entre dépôts : chantier distinct (action A6 de [ETAT.md](ETAT.md))

Cette phase nécessite des données quantitatives encore absentes. Elle est distincte de l'optimisation (programme R0–R6, clos).
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

Les valeurs ci-dessous sont celles de la dernière autorisation (15 octobre) : reprendre celles que 👤 autorise à la nouvelle demande. Privilégier les contrôleurs existants correctement adaptés : ils posent les limites avant de créer
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

Validation complète requise avant commit : celle de [CLAUDE.md](../CLAUDE.md) §2, que `python scripts\validate_parallel.py` rejoue en parallèle (≈ 17 min sur 16 cœurs), puis `git diff --check`.

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
